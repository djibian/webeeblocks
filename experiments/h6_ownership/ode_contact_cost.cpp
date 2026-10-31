// Pinned Webots R2025a bundled-ODE ownership/memory experiment.
// Research-only: not a replacement for Webots/Qt QHash or a worker-safety proof.
// Four modes operate on EXACTLY the same n contact joints and physics fixture:
// shared: historical single group (cannot free a selected contact);
// individual: existing #766-style standalone with registered-key erasure;
// notify: standalone with tiny ODE pre/post-free hook (external destruction);
// singleton: one ODE group per contact (group-owned dJointDestroy no-op).
#include <ode/ode.h>
#include <malloc.h>
#include <unistd.h>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <unordered_set>
#include <vector>
#include <string>

extern "C" void h6SetContactJointDestroyHooks(void (*before)(dJointID),
                                               void (*after)(dJointID));

static std::unordered_set<dJointID> tracked;
static std::recursive_mutex contactMutex;
static int entered=0, exited=0, registeredBefore=0;
static void preDestroy(dJointID joint) {
  contactMutex.lock();
  ++entered;
  if (tracked.erase(joint)) ++registeredBefore;
}
static void postDestroy(dJointID) {
  ++exited;
  contactMutex.unlock();
}
static void insist(bool yes,const char *why) {
  if(!yes) {std::fprintf(stderr,"H6_BENCH_REJECT %s\n",why);std::exit(3);}
}
static long rssBytes() {
  FILE *f=std::fopen("/proc/self/statm","r");insist(f!=nullptr,"open statm");
  unsigned long total=0,resident=0;
  insist(std::fscanf(f,"%lu %lu",&total,&resident)==2,"parse statm");
  std::fclose(f);
  return static_cast<long>(resident*sysconf(_SC_PAGESIZE));
}
struct Memory {long active,arena,rss;};
static Memory memory() {
  const auto m=mallinfo2();
  return {static_cast<long>(m.uordblks),
          static_cast<long>(m.arena + m.hblkhd),rssBytes()};
}
static double us(std::chrono::steady_clock::time_point start) {
  return std::chrono::duration<double,std::micro>(
    std::chrono::steady_clock::now()-start).count();
}
static int nContact(dBodyID body) {
  int count=0;
  for(int i=0;i<dBodyGetNumJoints(body);++i)
    if(dJointGetType(dBodyGetJoint(body,i))==dJointTypeContact) ++count;
  return count;
}
static void emitMem(const char *phase, const Memory &v,int alive,int registered) {
  std::printf("\"%s\":{\"active\":%ld,\"reserved\":%ld,\"rss\":%ld,"
              "\"alive\":%d,\"tracked\":%d}",phase,
              v.active,v.arena,v.rss,alive,registered);
}
int main(int argc,char **argv) {
  insist(argc==4,"usage: ode_contact_cost {shared|individual|notify|singleton} n repeat");
  const std::string mode=argv[1];
  const bool shared=mode=="shared",single=mode=="singleton";
  const bool notify=mode=="notify",individual=mode=="individual";
  insist(shared||single||notify||individual,"mode");
  const int n=std::atoi(argv[2]),repeat=std::atoi(argv[3]);
  insist(n==1||n==8||n==64||n==256||n==1024,"n allowed");
  insist(repeat>=0 && repeat<100,"repeat range");
  insist(dInitODE2(0)!=0,"ODE init");
  dWorldID world=dWorldCreate();
  insist(world!=nullptr,"create world");
  dWorldSetGravity(world,0,0,-9.81);
  dWorldSetERP(world,.8);
  dWorldSetCFM(world,.00001);
  dBodyID body=dBodyCreate(world);
  dMass mass;
  dMassSetBoxTotal(&mass,0.12,.2,.2,.2);
  dBodySetMass(body,&mass);
  dBodySetPosition(body,0,0,.09);
  dWorldSetQuickStepNumIterations(world,20);
  std::vector<dJointID> joints;
  std::vector<dJointGroupID> groups;
  joints.reserve(n);
  groups.reserve(single?n:1);
  if(shared) groups.push_back(dJointGroupCreate(0));
  if(notify) h6SetContactJointDestroyHooks(preDestroy,postDestroy);
  else h6SetContactJointDestroyHooks(nullptr,nullptr);
  const Memory before=memory();
  const auto beginCreation=std::chrono::steady_clock::now();
  for(int i=0;i<n;++i) {
    dJointGroupID group=nullptr;
    if(single) {
      group=dJointGroupCreate(0);
      insist(group!=nullptr,"create singleton group");
      groups.push_back(group);
    } else if(shared) group=groups[0];
    dContact c{};
    c.surface.mode=dContactSoftERP|dContactSoftCFM;
    c.surface.soft_erp=.8;
    c.surface.soft_cfm=.00001;
    c.surface.mu=0;
    c.geom.depth=.01;
    c.geom.normal[2]=1;
    c.geom.pos[0]=(i%17)*.0001;
    c.geom.pos[1]=(i%13)*.0001;
    dJointID j=dJointCreateContact(world,group,&c);
    insist(j!=nullptr,"create contact");
    dJointAttach(j,body,nullptr);
    joints.push_back(j);
    if(individual||notify) insist(tracked.insert(j).second,"registry duplicate");
  }
  const double create_us=us(beginCreation);
  const Memory peak=memory();
  insist(nContact(body)==n,"not all contacts attached");
  const auto beginWorldStep=std::chrono::steady_clock::now();
  dWorldQuickStep(world,.032);
  const double step_us=us(beginWorldStep);
  insist(std::isfinite(dBodyGetLinearVel(body)[2]),"invalid physics");
  dBodyDisable(body); // test contact preservation while sleeping
  const auto beginSelective=std::chrono::steady_clock::now();
  int attempted=0;
  for(int i=0;i<n;++i) {
    if(i%2!=0) continue; // exact identical every-other-contact invalidation
    ++attempted;
    if(single) {
      dJointGroupEmpty(groups[i]); // retains reusable 16 KiB arena
    } else if(shared) {
      dJointDestroy(joints[i]);  // documented ODE grouped no-op
    } else if(individual) {
      insist(tracked.erase(joints[i])==1,"manual unregister before destroy");
      dJointDestroy(joints[i]);
    } else {
      // external call: no explicit registry erase. Actual ODE hook must notify
      // prior to effective free, under the same recursive lock held here.
      std::lock_guard<std::recursive_mutex> guard(contactMutex);
      dJointDestroy(joints[i]);
      insist(tracked.count(joints[i])==0,"hook did not unregister");
    }
    joints[i]=nullptr;
  }
  const double selective_us=us(beginSelective);
  const int survivors=n-attempted;
  const int physicallyAlive=nContact(body);
  insist(physicallyAlive==(shared?n:survivors),"unexpected selective invalidation");
  if(individual||notify)
    insist(static_cast<int>(tracked.size())==survivors,"registry stale or missing live contact");
  if(notify)
    insist(registeredBefore==attempted && entered==attempted && exited==attempted,
      "unexpected pre/post notification counts");
  const Memory afterSelective=memory();
  dBodyEnable(body); // first solver after wake must see all legitimate contacts
  const auto beginWake=std::chrono::steady_clock::now();
  dWorldQuickStep(world,.032);
  const double wake_us=us(beginWake);
  insist(std::isfinite(dBodyGetLinearVel(body)[2]),"wake physics");
  // Retire all contacts. Group empty keeps reusable arenas until group destroy.
  const auto beginRetirement=std::chrono::steady_clock::now();
  if(single||shared) {
    for(dJointGroupID group:groups) dJointGroupEmpty(group);
  } else {
    for(dJointID j:joints) {
      if(j==nullptr) continue;
      if(individual) {
        insist(tracked.erase(j)==1,"manual retire registry");
        dJointDestroy(j);
      } else {
        std::lock_guard<std::recursive_mutex> guard(contactMutex);
        dJointDestroy(j);
        insist(tracked.count(j)==0,"hook retire registry");
      }
    }
  }
  const double retirement_us=us(beginRetirement);
  insist(nContact(body)==0,"retirement did not detach all contacts");
  insist(tracked.empty(),"registered keys still present");
  const Memory afterEmpty=memory();
  const auto beginTeardown=std::chrono::steady_clock::now();
  for(dJointGroupID group:groups) dJointGroupDestroy(group);
  dBodyDestroy(body);
  dWorldDestroy(world);
  h6SetContactJointDestroyHooks(nullptr,nullptr);
  dCloseODE();
  const double teardown_us=us(beginTeardown);
  const Memory afterDestroy=memory();
  std::printf("{\"mode\":\"%s\",\"n\":%d,\"repeat\":%d,\"invalid\":%d,"
              "\"selective_possible\":%s,\"alive_after_selective\":%d,"
              "\"survivors_expected\":%d,"
              "\"hook_pre\":%d,\"hook_post\":%d,\"hook_registered\":%d,"
              "\"create_us\":%.6f,\"step_us\":%.6f,\"selective_us\":%.6f,"
              "\"wake_us\":%.6f,\"retire_us\":%.6f,\"teardown_us\":%.6f,",
              mode.c_str(),n,repeat,attempted,shared?"false":"true",
              physicallyAlive,survivors,entered,exited,registeredBefore,
              create_us,step_us,selective_us,wake_us,retirement_us,teardown_us);
  emitMem("before",before,0,0);std::putchar(',');
  emitMem("peak",peak,n,static_cast<int>(individual||notify?n:0));std::putchar(',');
  emitMem("after_selective",afterSelective,physicallyAlive,static_cast<int>(tracked.size()));std::putchar(',');
  emitMem("after_empty",afterEmpty,0,0);std::putchar(',');
  emitMem("after_destroy",afterDestroy,0,0);
  std::puts("}");
  return 0;
}

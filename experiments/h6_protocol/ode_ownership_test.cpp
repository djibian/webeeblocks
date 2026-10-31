// H6 native falsification of a pre-dereference ODE contact ownership gate.
// Actual pinned bundled libode; research-only, no guarantee about actual Webots workers.
#include <ode/ode.h>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <unordered_set>
#include <vector>
#include <string>
#include <cmath>

extern "C" void h6SetPolicy(int);
extern "C" void h6SetBeforeFree(void(*)(dJointID,int));
extern "C" dJointID h6CreateEngineContact(dWorldID,const dContact*,int);
extern "C" int h6EngineDestroyContact(dJointID);
extern "C" unsigned long h6CountReused(),h6CountDenied(),h6CountDuplicates(),h6CountEffective();
extern "C" size_t h6CountTracked();
static std::unordered_set<dJointID> two[2];
static int callbackCount=0, wrongBuffer=0, nestedAttempt=0, nestedDuringPrivileged=0;
static bool callbackReenter=false, callbackCallExternalWhileEngine=false;
static void require(bool yes,const char *reason){
  if(!yes){std::fprintf(stderr,"H6_PROTO_ASSERT_FAIL %s\n",reason);std::exit(5);}
}
static dContact contact(){
  dContact c{};
  c.surface.mode=dContactSoftERP|dContactSoftCFM;
  c.surface.mu=0;
  c.surface.soft_erp=.8;
  c.surface.soft_cfm=.00001;
  c.geom.depth=.01;
  c.geom.normal[2]=1;
  return c;
}
static void before(dJointID joint,int buffer){
  require(buffer==0 || buffer==1,"callback invalid buffer");
  ++callbackCount;
  if(two[buffer].erase(joint)!=1 || two[1-buffer].erase(joint)!=0)
    ++wrongBuffer;
  if(callbackReenter){++nestedAttempt;dJointDestroy(joint);}
  if(callbackCallExternalWhileEngine){
    ++nestedDuringPrivileged;
    // Explicit API authority must not leak to ordinary external dJointDestroy.
    dJointDestroy(joint);
  }
}
static dJointID fresh(dWorldID world,dBodyID body,int buf){
  dContact c=contact();
  dJointID j=h6CreateEngineContact(world,&c,buf);
  require(j!=nullptr,"create");
  require(two[buf].insert(j).second,"double register");
  dJointAttach(j,body,nullptr);
  return j;
}
static int joints(dBodyID b){
  int n=0;
  for(int i=0;i<dBodyGetNumJoints(b);++i)
    if(dJointGetType(dBodyGetJoint(b,i))==dJointTypeContact) ++n;
  return n;
}
static void actualStep(dWorldID world,dBodyID body){
  dBodyEnable(body);
  dWorldQuickStep(world,.032);
  require(std::isfinite(dBodyGetLinearVel(body)[2]),"nonfinite solver");
}
int main(int argc,char **argv){
  require(argc==2,"usage: h6_ownership_test p0|p1");
  const std::string mode=argv[1];require(mode=="p0"||mode=="p1","policy");
  const int policy=mode=="p1";
  require(dInitODE2(0)!=0,"ODE init");
  dWorldID world=dWorldCreate();
  dWorldSetGravity(world,0,0,-9.81);
  dBodyID body=dBodyCreate(world);
  dMass m;
  dMassSetBoxTotal(&m,.12,.2,.2,.2);
  dBodySetMass(body,&m);
  dBodySetPosition(body,0,0,.095);
  h6SetPolicy(policy);
  h6SetBeforeFree(before);
  // First assert two separate register buffers while owner body is asleep.
  const dJointID a=fresh(world,body,0),b=fresh(world,body,1);
  require(joints(body)==2 && h6CountTracked()==2,"two buffers create");
  dBodyDisable(body);
  dJointDestroy(a);  // always plugin/public entry, P0 no-op, P1 actual
  require(joints(body)==(policy?1:2),"P0/P1 observable public result");
  require(two[0].count(a)==(policy?0u:1u),"P0/P1 registry");
  actualStep(world,body); // surviving legitimate contact first wake solver
  // Engine-owned destruction overrides P0 without a global privileged TLS flag.
  require(h6EngineDestroyContact(b)==1,"destroy internal buffer1");
  require(two[1].empty(),"buffer1 notification");
  if(!policy)require(h6EngineDestroyContact(a)==1,"destroy internal P0");
  else require(h6EngineDestroyContact(a)==0,"do not redo external P1");
  require(joints(body)==0 && two[0].empty() && two[1].empty(),"registry and joints empty");
  // Repeated destruction while retired: must be rejected BEFORE pointer dereference.
  const auto priorDuplicate=h6CountDuplicates();
  dJointDestroy(a);
  require(h6EngineDestroyContact(b)==0,"retired engine call");
  require(h6CountDuplicates()>=priorDuplicate+2,"repeat rejected");
  // Reentrant notify attempts an ordinary destruction of same joint, including
  // while a dedicated engine entry-point is in progress.
  callbackReenter=true;callbackCallExternalWhileEngine=true;
  const dJointID c=fresh(world,body,0);
  require(h6EngineDestroyContact(c)==1,"reentrant privileged");
  callbackReenter=false;callbackCallExternalWhileEngine=false;
  require(joints(body)==0 && nestedAttempt>=1 && nestedDuringPrivileged>=1,
    "recursive callback must not double free or deadlock");
  // Plugin-created standalone (not tagged engine-owned): stock ODE destruction.
  dContact pluginC=contact();
  const dJointID plug=dJointCreateContact(world,nullptr,&pluginC);
  dJointAttach(plug,body,nullptr);
  require(joints(body)==1,"plugin standalone create");
  const unsigned long prev=h6CountEffective();
  dJointDestroy(plug);
  const bool pluginDestroyPreserved = joints(body)==0; // false is a *negative*.
  require(h6CountEffective()==prev,"plugin not classified as engine");
  // Group-owned plugin: historic dJointDestroy no-op, dJointGroupEmpty works.
  dJointGroupID pluginGroup=dJointGroupCreate(0);
  dJointID pj=dJointCreateContact(world,pluginGroup,&pluginC);
  dJointAttach(pj,body,nullptr);
  const int beforeGroup=joints(body);
  dJointDestroy(pj);
  require(joints(body)==beforeGroup,"plugin group dJointDestroy must be no-op");
  dJointGroupEmpty(pluginGroup);
  require(joints(body)==beforeGroup-1,"plugin group cleanup");
  dJointGroupDestroy(pluginGroup);
  // Two threads destroy the same engine joint from a hard start barrier.
  const dJointID race=fresh(world,body,1);
  const int beforeRace=callbackCount;
  std::atomic<int> ready{0};
  std::atomic<bool> go{false};
  auto external=[&](){
    ready.fetch_add(1,std::memory_order_release);
    while(!go.load(std::memory_order_acquire)) std::this_thread::yield();
    dJointDestroy(race);
  };
  std::thread t1(external),t2(external);
  while(ready.load(std::memory_order_acquire)!=2) std::this_thread::yield();
  go.store(true,std::memory_order_release);
  t1.join();t2.join();
  require(joints(body)==(policy?0:1),"concurrent P0/P1");
  require(callbackCount==beforeRace+(policy?1:0),"at most one notification");
  // Buffer retirement concurrent to public destroy; only one wins.
  const dJointID retire=fresh(world,body,0);
  std::atomic<int> ready2{0};std::atomic<bool> start2{false};
  auto retireThread=[&](){
    ready2.fetch_add(1,std::memory_order_release);
    while(!start2.load(std::memory_order_acquire)) std::this_thread::yield();
    h6EngineDestroyContact(retire);
  };
  auto pluginThread=[&](){
    ready2.fetch_add(1,std::memory_order_release);
    while(!start2.load(std::memory_order_acquire)) std::this_thread::yield();
    dJointDestroy(retire);
  };
  const int beforeRetire=callbackCount;
  std::thread t3(retireThread),t4(pluginThread);
  while(ready2.load(std::memory_order_acquire)!=2)std::this_thread::yield();
  start2.store(true,std::memory_order_release);
  t3.join();t4.join();
  require(callbackCount==beforeRetire+1,"retire exactly one effective delete");
  require(two[0].empty(),"retire erased buffer0");
  if(!policy)require(h6EngineDestroyContact(race)==1,"P0 race left engine alive");
  require(two[1].empty() && h6CountTracked()==0,"no live engine at teardown");
  require(joints(body)==0,"all contacts removed before teardown");
  require(wrongBuffer==0,"double-registry corruption");
  h6SetBeforeFree(nullptr);
  dBodyDestroy(body);
  dWorldDestroy(world);
  dCloseODE();
  std::printf("{\"policy\":\"%s\",\"verdict\":\"BOUNDED_PASS\","
       "\"plugin_standalone_destroyed\":%s,"
       "\"callback_count\":%d,\"wrong_buffer\":%d,"
       "\"reentrant_calls\":%d,\"denied\":%lu,\"duplicates\":%lu,"
       "\"effective_engine_free\":%lu,\"address_reuse\":%lu}\n",
       mode.c_str(),pluginDestroyPreserved?"true":"false",
       callbackCount,wrongBuffer,nestedAttempt,
       h6CountDenied(),h6CountDuplicates(),h6CountEffective(),h6CountReused());
  return 0;
}

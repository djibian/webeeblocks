// H6-E2: exact bundled Webots R2025a ODE group-owned joint lifetime.
// Native collision dCollide creates real contact geometry, no simulated measurements.
// Owner A is intentionally disabled while B is repeatedly reset.
#include <ode/ode.h>
#include <malloc.h>
#include <sys/resource.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include <cmath>
#include <cstdint>

static void check(bool ok, const char *msg) {
  if (!ok) { std::fprintf(stderr,"H6_E2_REFUSED %s\n",msg); std::exit(2); }
}
static long rss_kb() {
  FILE *f=std::fopen("/proc/self/status","r");
  check(f!=nullptr,"proc status unavailable");
  char line[256];long v=-1;
  while (std::fgets(line,sizeof(line),f)) {
    if (std::sscanf(line,"VmRSS: %ld kB",&v)==1) break;
  }
  std::fclose(f);check(v>=0,"VmRSS unavailable");return v;
}
static size_t heap_bytes() { return mallinfo2().uordblks; }
static void mass(dBodyID b) {
  dMass m;dMassSetSphereTotal(&m,0.05,0.035);dBodySetMass(b,&m);
}
static dJointID real_collision(dWorldID w,dJointGroupID g,dGeomID g1,dGeomID g2,dBodyID b1,dBodyID b2) {
  dContact c{};
  int n=dCollide(g1,g2,1,&c.geom,sizeof(dContactGeom));
  check(n==1&&c.geom.depth>0,"real native ODE sphere contact missing");
  c.surface.mode=dContactSoftERP|dContactSoftCFM;
  c.surface.mu=0.0;c.surface.soft_erp=0.85;c.surface.soft_cfm=0.00001;
  dJointID j=dJointCreateContact(w,g,&c);
  check(j!=nullptr,"contact joint allocation failed");
  dJointAttach(j,b1,b2);return j;
}
static bool touches(dJointID j,dBodyID b) {
  return dJointGetBody(j,0)==b || dJointGetBody(j,1)==b;
}
static int detach_only_contacts(dBodyID reset) {
  std::vector<dJointID> contacts;
  const int before=dBodyGetNumJoints(reset);
  for(int i=0;i<before;i++) {
    dJointID j=dBodyGetJoint(reset,i);
    if(dJointGetType(j)==dJointTypeContact) contacts.push_back(j);
  }
  for(dJointID j:contacts) {
    dJointAttach(j,nullptr,nullptr);
    dJointDestroy(j); // group-owned => no-op in pinned ODE
  }
  return static_cast<int>(contacts.size());
}
static void report(const char *arm, const char *stage,int step,
                   dJointGroupID g1,dJointGroupID g2,dBodyID a,dBodyID b,
                   dBodyID c,dJointID untouched,dJointID permanent,int generated,int detached) {
  check(touches(untouched,a)&&touches(untouched,c),"unrelated legitimate contact altered");
  check(touches(permanent,b)&&touches(permanent,c),"permanent joint altered");
  int allocated=dJointGroupGetCount(g1)+dJointGroupGetCount(g2);
  check(allocated>=1,"group lost unrelated contact");
  int target_attached=dBodyGetNumJoints(b)-1;
  check(target_attached>=0,"permanent joint lost from target");
  std::printf("{\"arm\":\"%s\",\"stage\":\"%s\",\"cycle\":%d,\"group_owned_allocated\":%d,\"target_attached_contacts\":%d,\"permanent_joints\":1,\"unrelated_attached\":1,\"created\":%d,\"detached\":%d,\"owner_enabled\":%d,\"rss_kb\":%ld,\"heap_bytes\":%zu}\n",
      arm,stage,step,allocated,target_attached,generated,detached,dBodyIsEnabled(a),rss_kb(),heap_bytes());
  std::fflush(stdout);
}
static void run(const char *arm, bool use_r,int cycles){
  dWorldID w=dWorldCreate();check(w!=nullptr,"world");
  dWorldSetGravity(w,0,0,0);
  dJointGroupID group1=dJointGroupCreate(0),group2=dJointGroupCreate(0);
  dBodyID a=dBodyCreate(w),b=dBodyCreate(w),c=dBodyCreate(w);
  mass(a);mass(b);mass(c);
  dBodySetPosition(a,0,0,0);
  dBodySetPosition(b,0.05,0,0);
  dBodySetPosition(c,-0.05,0,0);
  dGeomID ga=dCreateSphere(0,0.035),gb=dCreateSphere(0,0.035),gc=dCreateSphere(0,0.035);
  dGeomSetBody(ga,a);dGeomSetBody(gb,b);dGeomSetBody(gc,c);
  dJointID untouched=real_collision(w,group1,ga,gc,a,c);
  dJointID permanent=dJointCreateBall(w,nullptr);
  check(permanent!=nullptr,"permanent");
  dJointAttach(permanent,b,c);
  check(dJointGetType(permanent)==dJointTypeBall,"not a permanent ball joint");
  dBodyDisable(a);
  report(arm,"initial",0,group1,group2,a,b,c,untouched,permanent,0,0);
  int created=0,detached=0;
  const int checkpoints[]={1,64,512,2048,8192};
  for(int i=1;i<=cycles;++i){
    dJointGroupID grp=(i&1)?group1:group2; // actual Webots contact double buffers
    dBodySetPosition(b,0.05,0,0); // collision at same physical position
    dJointID j=real_collision(w,grp,ga,gb,a,b);
    check(touches(j,b),"new contact not attached to reset target");
    created++;
    // Keep the foreign group owner artificially disabled through RESET.
    dBodyDisable(a);
    // RESET B; owner A stays disabled and a second legitimate contact exists.
    dBodySetPosition(b,2,0,0);
    dBodySetLinearVel(b,0,0,0);dBodySetAngularVel(b,0,0,0);
    dBodySetForce(b,0,0,0);dBodySetTorque(b,0,0,0);
    if(use_r)detached+=detach_only_contacts(b);
    // Check simulation's normal enabled-owner cleanup: disabled A must remain.
    if(dBodyIsEnabled(a)){dJointGroupEmpty(group1);dJointGroupEmpty(group2);}
    check(dJointGetType(permanent)==dJointTypeBall&&touches(permanent,b),"permanent joint lost");
    if(use_r)check(dBodyGetNumJoints(b)==1,"R left contacts on B");
    for(int checkpoint:checkpoints) if(i==checkpoint)
      report(arm,"disabled_owner",i,group1,group2,a,b,c,untouched,permanent,created,detached);
  }
  check(!dBodyIsEnabled(a),"disabled owner spontaneously enabled");
  check(dJointGroupGetCount(group1)+dJointGroupGetCount(group2)==1+cycles,
        "group ownership not monotone as expected");
  if(use_r)check(detached==cycles,"R failed to detach all allocated contacts");
  // Ordinary enabled-owner cleanup is now allowed: first check before touching freed joints.
  dBodyEnable(a);
  dJointGroupEmpty(group1);dJointGroupEmpty(group2);
  check(dJointGroupGetCount(group1)+dJointGroupGetCount(group2)==0,
        "owner reactivation did not allow release");
  check(dBodyGetNumJoints(b)==1&&touches(permanent,c),
        "normal cleanup changed a noncontact joint");
  std::printf("{\"arm\":\"%s\",\"stage\":\"reactivation_empty\",\"cycle\":%d,\"group_owned_allocated\":0,\"target_attached_contacts\":0,\"rss_kb\":%ld,\"heap_bytes\":%zu}\n",
      arm,cycles,rss_kb(),heap_bytes());
  std::fflush(stdout);
  dJointID new_normal=real_collision(w,group1,ga,gc,a,c);
  check(touches(new_normal,a)&&touches(new_normal,c),"new contact cannot recover");
  check(dJointGroupGetCount(group1)==1,"new group creation not possible");
  dJointGroupDestroy(group1);dJointGroupDestroy(group2);
  dJointDestroy(permanent);
  dGeomDestroy(ga);dGeomDestroy(gb);dGeomDestroy(gc);
  dBodyDestroy(a);dBodyDestroy(b);dBodyDestroy(c);dWorldDestroy(w);
  malloc_trim(0);
  std::printf("{\"arm\":\"%s\",\"stage\":\"world_destroyed\",\"cycle\":%d,\"rss_kb\":%ld,\"heap_bytes\":%zu}\n",
      arm,cycles,rss_kb(),heap_bytes());
  std::fflush(stdout);
}
int main(){
  check(dInitODE2(0)!=0,"ODE init");
  constexpr int CYCLES=8192;
  run("R_detach",true,CYCLES);
  run("A_no_detach",false,CYCLES);
  dCloseODE();
  std::puts("H6_E2_NATIVE_PASS");
  return 0;
}

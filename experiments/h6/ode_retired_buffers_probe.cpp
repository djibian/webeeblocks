// H6-G: representative ODE R+retired-buffer cleanup, without per-pair groups.
#include <ode/ode.h>
#include <malloc.h>
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <vector>
static void need(bool ok,const char *why) {
  if(!ok){std::fprintf(stderr,"H6_G_REFUSED %s\n",why);std::exit(2);}
}
static long rss_kb() {
  FILE *f=std::fopen("/proc/self/status","r");need(f!=nullptr,"proc");
  char s[256];long n=-1;
  while(std::fgets(s,sizeof(s),f))if(std::sscanf(s,"VmRSS: %ld kB",&n)==1)break;
  std::fclose(f);need(n>=0,"rss");return n;
}
static bool attached(dJointID j,dBodyID b) {
  return dJointGetBody(j,0)==b||dJointGetBody(j,1)==b;
}
static dJointID collide(dWorldID w,dJointGroupID g,dGeomID x,dGeomID y,dBodyID a,dBodyID b){
  dContact c{};
  need(dCollide(x,y,1,&c.geom,sizeof(dContactGeom))==1 && c.geom.depth>0,"contact geometry");
  c.surface.mode=dContactSoftERP|dContactSoftCFM;c.surface.soft_erp=0.85;
  c.surface.soft_cfm=0.00001;c.surface.mu=0;
  dJointID j=dJointCreateContact(w,g,&c);
  need(j!=nullptr,"joint");dJointAttach(j,a,b);return j;
}
static void report(const char* stage,int n,dJointGroupID active,dJointGroupID retired,
                   dBodyID a,dBodyID b,dBodyID c,dJointID third,dJointID fixed) {
  need(!dBodyIsEnabled(a),"owner awoke");
  need(dJointGroupGetCount(active)==2 && dJointGroupGetCount(retired)==0,"retired group allocation");
  need(attached(third,a)&&attached(third,c),"third body contact lost");
  need(dBodyGetNumJoints(b)==1 && attached(fixed,b)&&attached(fixed,c),"joint permanent changed");
  std::printf("{\"stage\":\"%s\",\"cycle\":%d,\"group_joints_total\":2,\"detached_joints_current\":1,\"contacts_on_B\":0,\"contacts_on_AC\":1,\"permanent_joints\":1,\"owner_enabled\":0,\"heap_bytes\":%zu,\"rss_kb\":%ld}\n",
    stage,n,mallinfo2().uordblks,rss_kb());
  std::fflush(stdout);
}
int main(){
  need(dInitODE2(0)!=0,"init");
  dWorldID w=dWorldCreate();need(w!=nullptr,"world");dWorldSetGravity(w,0,0,0);
  dJointGroupID g[2]={dJointGroupCreate(0),dJointGroupCreate(0)};
  dBodyID a=dBodyCreate(w),b=dBodyCreate(w),c=dBodyCreate(w);
  for(auto x:{a,b,c}) {dMass m;dMassSetSphereTotal(&m,0.05,0.035);dBodySetMass(x,&m);}
  dBodySetPosition(a,0,0,0);dBodySetPosition(b,0.05,0,0);dBodySetPosition(c,-0.05,0,0);
  dGeomID ga=dCreateSphere(0,0.035),gb=dCreateSphere(0,0.035),gc=dCreateSphere(0,0.035);
  dGeomSetBody(ga,a);dGeomSetBody(gb,b);dGeomSetBody(gc,c);
  dJointID fixed=dJointCreateBall(w,nullptr);
  need(fixed!=nullptr,"ball");dJointAttach(fixed,b,c);
  dBodyDisable(a);
  for(int i=1;i<=8192;++i){
    const int active=i&1,retired=1-active;
    // A simulated physics step boundary: retire the previous contact buffer,
    // independent of the owning body's asleep/disabled state.
    dJointGroupEmpty(g[retired]);
    dBodySetPosition(b,0.05,0,0);
    dJointID third=collide(w,g[active],ga,gc,a,c);
    dJointID old=collide(w,g[active],ga,gb,a,b);
    need(dJointGroupGetCount(g[active])==2,"unexpected new contacts");
    dBodyDisable(a);
    // RESET B at safe physical boundary; R is attachment-selective.
    dBodySetPosition(b,2,0,0);
    dBodySetLinearVel(b,0,0,0);dBodySetAngularVel(b,0,0,0);
    dBodySetForce(b,0,0,0);dBodySetTorque(b,0,0,0);
    need(attached(old,b),"old joint does not link target");
    dJointAttach(old,nullptr,nullptr);
    dJointDestroy(old); // group-owned: intentionally stays until buffer retirement
    if(i==1||i==64||i==512||i==2048||i==8192)
      report("retired_cleanup",i,g[active],g[retired],a,b,c,third,fixed);
  }
  dBodyEnable(a);
  dJointGroupEmpty(g[0]);dJointGroupEmpty(g[1]);
  need(dJointGroupGetCount(g[0])+dJointGroupGetCount(g[1])==0,"reattached owner failed to clear");
  need(dBodyGetNumJoints(b)==1 && attached(fixed,b),"permanent after group cleanup");
  dJointID fresh=collide(w,g[0],ga,gc,a,c);
  need(attached(fresh,a)&&attached(fresh,c),"fresh contact after cleanup");
  dJointGroupDestroy(g[0]);dJointGroupDestroy(g[1]);
  dJointDestroy(fixed);
  dGeomDestroy(ga);dGeomDestroy(gb);dGeomDestroy(gc);
  dBodyDestroy(a);dBodyDestroy(b);dBodyDestroy(c);dWorldDestroy(w);
  malloc_trim(0);
  std::printf("{\"stage\":\"destroyed\",\"heap_bytes\":%zu,\"rss_kb\":%ld}\n",
     mallinfo2().uordblks,rss_kb());
  dCloseODE();
  std::puts("H6_G_NATIVE_PASS");
  return 0;
}

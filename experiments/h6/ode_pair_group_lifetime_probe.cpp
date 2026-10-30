// H6-E3 ODE R2025a: alternative double-buffer contact groups indexed by body pair.
// Reset of B empties AB groups only; unrelated AC contacts survive, no detached orphans.
#include <ode/ode.h>
#include <malloc.h>
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <cstring>
static void must(bool b,const char *why){
 if(!b){std::fprintf(stderr,"H6_E3_REFUSED %s\n",why);std::exit(2);}
}
static long rss(){
 FILE *f=std::fopen("/proc/self/status","r");must(f!=nullptr,"proc");
 char b[160];long k=-1;
 while(std::fgets(b,sizeof(b),f))if(std::sscanf(b,"VmRSS: %ld kB",&k)==1)break;
 std::fclose(f);must(k>=0,"rss");return k;
}
static bool attached(dJointID j,dBodyID b){
 return dJointGetBody(j,0)==b||dJointGetBody(j,1)==b;
}
static dJointID make_contact(dWorldID w,dJointGroupID g,dGeomID g1,dGeomID g2,dBodyID b1,dBodyID b2){
 dContact c{};
 must(dCollide(g1,g2,1,&c.geom,sizeof(dContactGeom))==1&&c.geom.depth>0,"collision");
 c.surface.mode=dContactSoftERP|dContactSoftCFM;
 c.surface.mu=0;c.surface.soft_erp=0.85;c.surface.soft_cfm=0.00001;
 dJointID j=dJointCreateContact(w,g,&c);
 must(j!=nullptr,"joint");dJointAttach(j,b1,b2);return j;
}
static void snap(const char *phase,int cycle,dJointGroupID ab1,dJointGroupID ab2,dJointGroupID ac1,dJointGroupID ac2,
                 dBodyID b,dJointID other,dJointID permanent,dBodyID a,dBodyID c){
 const int own=dJointGroupGetCount(ab1)+dJointGroupGetCount(ab2);
 const int unrelated=dJointGroupGetCount(ac1)+dJointGroupGetCount(ac2);
 must(own==0,"reset pair groups not empty");
 must(unrelated==1&&attached(other,a)&&attached(other,c),"third-body contact destroyed");
 must(dBodyGetNumJoints(b)==1&&attached(permanent,b)&&attached(permanent,c),"permanent joint altered");
 must(!dBodyIsEnabled(a),"owner activated");
 std::printf("{\"phase\":\"%s\",\"cycle\":%d,\"reset_pair_group_joints\":%d,\"unrelated_pair_group_joints\":%d,\"target_attached_contact_joints\":0,\"permanent_joint_kept\":1,\"owner_disabled\":1,\"heap_bytes\":%zu,\"rss_kb\":%ld}\n",
     phase,cycle,own,unrelated,mallinfo2().uordblks,rss());
 std::fflush(stdout);
}
int main(){
 must(dInitODE2(0)!=0,"init");
 dWorldID w=dWorldCreate();must(w!=nullptr,"world");
 dWorldSetGravity(w,0,0,0);
 dJointGroupID ab[2]={dJointGroupCreate(0),dJointGroupCreate(0)};
 dJointGroupID ac[2]={dJointGroupCreate(0),dJointGroupCreate(0)};
 dBodyID a=dBodyCreate(w),b=dBodyCreate(w),c=dBodyCreate(w);
 for(dBodyID x:{a,b,c}){dMass m;dMassSetSphereTotal(&m,0.05,0.035);dBodySetMass(x,&m);}
 dBodySetPosition(a,0,0,0);dBodySetPosition(b,0.05,0,0);dBodySetPosition(c,-0.05,0,0);
 dGeomID ga=dCreateSphere(0,0.035),gb=dCreateSphere(0,0.035),gc=dCreateSphere(0,0.035);
 dGeomSetBody(ga,a);dGeomSetBody(gb,b);dGeomSetBody(gc,c);
 dJointID other=make_contact(w,ac[0],ga,gc,a,c);
 dJointID permanent=dJointCreateBall(w,nullptr);must(permanent!=nullptr,"permanent");
 dJointAttach(permanent,b,c);dBodyDisable(a);
 snap("initial",0,ab[0],ab[1],ac[0],ac[1],b,other,permanent,a,c);
 for(int i=1;i<=8192;++i){
   dBodySetPosition(b,0.05,0,0);
   dJointID old=make_contact(w,ab[i%2],ga,gb,a,b);
   must(attached(old,b),"contact missing");
   dBodyDisable(a);
   dBodySetPosition(b,2,0,0);
   dBodySetLinearVel(b,0,0,0);dBodySetAngularVel(b,0,0,0);
   dBodySetForce(b,0,0,0);dBodySetTorque(b,0,0,0);
   // Reset B invalidates all AB contacts. Unlike current Webots groups,
   // separate AC contact groups are unaffected. Both buffers are cleared.
   dJointGroupEmpty(ab[0]);dJointGroupEmpty(ab[1]);
   if(i==1||i==64||i==512||i==2048||i==8192)
     snap("pair_reset",i,ab[0],ab[1],ac[0],ac[1],b,other,permanent,a,c);
 }
 // Reset of A would invalidate AC too; test pair-specific eviction & restitution.
 dBodyEnable(a);
 dJointGroupEmpty(ac[0]);dJointGroupEmpty(ac[1]);
 must(dJointGroupGetCount(ac[0])+dJointGroupGetCount(ac[1])==0,"A reset pair cleanup");
 must(dBodyGetNumJoints(b)==1&&attached(permanent,b),"noncontact joint invalidated");
 dBodySetPosition(c,-0.05,0,0);
 dJointID later=make_contact(w,ac[1],ga,gc,a,c);
 must(attached(later,a)&&attached(later,c),"new AC contact missing");
 dJointGroupDestroy(ab[0]);dJointGroupDestroy(ab[1]);
 dJointGroupDestroy(ac[0]);dJointGroupDestroy(ac[1]);
 dJointDestroy(permanent);
 dGeomDestroy(ga);dGeomDestroy(gb);dGeomDestroy(gc);
 dBodyDestroy(a);dBodyDestroy(b);dBodyDestroy(c);dWorldDestroy(w);
 malloc_trim(0);
 std::printf("{\"phase\":\"destroyed\",\"heap_bytes\":%zu,\"rss_kb\":%ld}\n",mallinfo2().uordblks,rss());
 dCloseODE();
 std::puts("H6_E3_NATIVE_PASS");
 return 0;
}

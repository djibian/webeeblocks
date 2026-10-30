// Independent native ODE no-RESET falsification of unconditional disabled-owner G.
// Pinned Webots R2025a bundled ODE; no Webots scheduler claim.
#include <ode/ode.h>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <vector>
struct Obs {double speed; int old_remains; int fresh_remains;};
void check(bool x,const char* msg){if(!x){std::fprintf(stderr,"H6_NORESET_REFUSED %s\n",msg); std::exit(2);}}
static dJointID joint(dWorldID w,dJointGroupID g,dGeomID x,dGeomID y,dBodyID a,dBodyID b){
 dContact c{};check(dCollide(x,y,1,&c.geom,sizeof(dContactGeom))==1 && c.geom.depth>0,"contact geometry");
 c.surface.mode=dContactSoftERP|dContactSoftCFM;
 c.surface.soft_erp=.85;c.surface.soft_cfm=.00001;c.surface.mu=0;
 dJointID j=dJointCreateContact(w,g,&c);check(j!=nullptr,"joint");
 dJointAttach(j,a,b);return j;
}
Obs trial(bool G, bool fresh){
 dWorldID w=dWorldCreate();check(w!=nullptr,"world");
 dWorldSetGravity(w,0,0,0);
 dJointGroupID retired=dJointGroupCreate(0),current=dJointGroupCreate(0);
 dBodyID owner=dBodyCreate(w),other=dBodyCreate(w);
 for(dBodyID b:{owner,other}){dMass m;dMassSetSphereTotal(&m,.05,.035);dBodySetMass(b,&m);}
 dBodySetPosition(owner,0,0,0);dBodySetPosition(other,.05,0,0);
 dGeomID a=dCreateSphere(0,.035),b=dCreateSphere(0,.035);
 dGeomSetBody(a,owner);dGeomSetBody(b,other);
 // Realistic standard pose/contact geometry; absolutely NO RESET, teleport,
 // velocity reset or invalidation of the existing contact.
 joint(w,retired,a,b,owner,other);
 if(fresh) joint(w,current,a,b,owner,other);
 dBodyDisable(owner);check(!dBodyIsEnabled(owner),"owner must be disabled");
 if(G) dJointGroupEmpty(retired);
 int old_count=dJointGroupGetCount(retired),fresh_count=dJointGroupGetCount(current);
 check(old_count==(G?0:1) && fresh_count==(fresh?1:0),"G scope changed");
 dWorldStep(w,.01);
 const dReal *v=dBodyGetLinearVel(other);
 double speed=std::sqrt(v[0]*v[0]+v[1]*v[1]+v[2]*v[2]);
 check(std::isfinite(speed),"nonfinite no-reset physics");
 Obs result{speed,old_count,fresh_count};
 std::printf("{\"RESET\":0,\"G\":%d,\"fresh\":%d,\"owner_disabled\":1,"
             "\"old_group_contacts\":%d,\"fresh_group_contacts\":%d,\"other_speed_m_s\":%.17g}\n",
             static_cast<int>(G),static_cast<int>(fresh),old_count,fresh_count,speed);
 dJointGroupDestroy(current);dJointGroupDestroy(retired);
 dGeomDestroy(a);dGeomDestroy(b);
 dBodyDestroy(owner);dBodyDestroy(other);dWorldDestroy(w);
 return result;
}
int main(){
 check(dInitODE2(0)!=0,"init");
 for(int fresh=0;fresh<2;fresh++){
   Obs baseline=trial(false,fresh!=0),g=trial(true,fresh!=0);
   check(baseline.old_remains==1 && g.old_remains==0,"G failed to remove owner-disabled retired contact");
   check(baseline.fresh_remains==fresh && g.fresh_remains==fresh,"fresh contact lost");
   if(!fresh)
     check(baseline.speed>0.5 && g.speed==0.0,"no-RESET physical contrast absent"); // explicit nontrivial effect; prior arbitrary >1 rejected a real 0.84997875 m/s
 }
 dCloseODE();
 std::puts("H6_G_NO_RESET_NATIVE_PASS");
}

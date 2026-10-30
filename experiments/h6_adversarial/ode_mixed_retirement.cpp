// Independent adversarial fixture for exact H6 R+G semantics, pinned Webots ODE.
// Simulates a retired per-owner group that also contains an unrelated LIVE contact.
// Does not assert this owner-disabled state is reachable in every Webots scheduler path.
#include <ode/ode.h>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <vector>
static void need(bool ok,const char *reason){
 if(!ok){std::fprintf(stderr,"H6_ADVERSARIAL_REFUSED %s\n",reason);std::exit(2);}
}
static bool linked(dJointID j,dBodyID b){return dJointGetBody(j,0)==b || dJointGetBody(j,1)==b;}
static void mass(dBodyID b){dMass m;dMassSetSphereTotal(&m,0.05,0.035);dBodySetMass(b,&m);}
static dJointID contact(dWorldID w,dJointGroupID g,dGeomID x,dGeomID y,dBodyID a,dBodyID b){
 dContact c{};
 need(dCollide(x,y,1,&c.geom,sizeof(dContactGeom))==1 && c.geom.depth>0,"geometry did not overlap");
 c.surface.mode=dContactSoftERP|dContactSoftCFM;
 c.surface.soft_erp=0.85;c.surface.soft_cfm=0.00001;c.surface.mu=0;
 dJointID j=dJointCreateContact(w,g,&c);
 need(j!=nullptr,"create contact failed");dJointAttach(j,a,b);return j;
}
struct Observed {double c_speed;int a_c_attached,stale_b,group_count,permanent;};
static Observed scenario(bool reset_b,bool g){
 dWorldID w=dWorldCreate();need(w!=nullptr,"world");
 dWorldSetGravity(w,0,0,0);
 dJointGroupID retired=dJointGroupCreate(0);need(retired!=nullptr,"group");
 dBodyID a=dBodyCreate(w),b=dBodyCreate(w),c=dBodyCreate(w),d=dBodyCreate(w);
 for(dBodyID x:{a,b,c,d})mass(x);
 dBodySetPosition(a,0,0,0);dBodySetPosition(b,.05,0,0);dBodySetPosition(c,-.05,0,0);dBodySetPosition(d,2,0,0);
 dGeomID ga=dCreateSphere(0,.035),gb=dCreateSphere(0,.035),gc=dCreateSphere(0,.035);
 dGeomSetBody(ga,a);dGeomSetBody(gb,b);dGeomSetBody(gc,c);
 dJointID permanent=dJointCreateBall(w,nullptr);need(permanent!=nullptr,"ball");
 dJointAttach(permanent,b,d);
 dJointID legit=contact(w,retired,ga,gc,a,c);
 if(reset_b) {
   dJointID stale=contact(w,retired,ga,gb,a,b);
   // The actual R source walks B's joint attachments, filtering by contact type.
   std::vector<dJointID> to_detach;
   for(int i=dBodyGetNumJoints(b)-1;i>=0;--i){
     dJointID j=dBodyGetJoint(b,i);
     if(dJointGetType(j)==dJointTypeContact)to_detach.push_back(j);
   }
   need(to_detach.size()==1 && to_detach[0]==stale,"R didn't select exact stale contact");
   for(dJointID j:to_detach){dJointAttach(j,nullptr,nullptr);dJointDestroy(j);}
   need(linked(legit,a)&&linked(legit,c),"R destroyed legitimate A-C contact");
 }
 need(linked(permanent,b)&&linked(permanent,d),"R destroyed permanent ball joint");
 need(dJointGroupGetCount(retired)==(reset_b?2:1),"original group count");
 dBodyDisable(a); // disabled OWNER, not reset target B nor legitimate partner C
 need(!dBodyIsEnabled(a),"owner not disabled");
 // This is the precise newly broadened G predicate at post-swap retirement:
 // (dBodyIsEnabled(owner) || H6_NATIVE_G), applied to a retired group.
 if(dBodyIsEnabled(a)||g)dJointGroupEmpty(retired);
 int legit_live=dBodyGetNumJoints(c)==1;
 int stale_on_b=dBodyGetNumJoints(b)-1;
 int retained=dJointGroupGetCount(retired);
 need(stale_on_b==0 && linked(permanent,b)&&linked(permanent,d),"permanent/RESET invalid");
 dWorldStep(w,0.01);
 const dReal *v=dBodyGetLinearVel(c);
 double speed=std::sqrt(v[0]*v[0]+v[1]*v[1]+v[2]*v[2]);
 need(std::isfinite(speed),"nonfinite");
 const Observed o{speed,legit_live,stale_on_b,retained,1};
 std::printf("{\"reset_B\":%d,\"G\":%d,\"foreign_owner_disabled\":1,"
             "\"legitimate_AC_attached\":%d,\"stale_B_attached\":%d,"
             "\"group_owned_joints\":%d,\"permanent_ball_joint\":%d,"
             "\"third_body_speed\":%.17g}\n",
             int(reset_b),int(g),o.a_c_attached,o.stale_b,o.group_count,o.permanent,o.c_speed);
 dJointGroupDestroy(retired);dJointDestroy(permanent);
 dGeomDestroy(ga);dGeomDestroy(gb);dGeomDestroy(gc);
 for(dBodyID x:{a,b,c,d})dBodyDestroy(x);
 dWorldDestroy(w);return o;
}
int main(){
 need(dInitODE2(0)!=0,"init");
 for(bool reset:{false,true}){
   auto a=scenario(reset,false), g=scenario(reset,true);
   need(a.a_c_attached==1 && g.a_c_attached==0,"G did not delete unrelated legitimate contact");
   need(a.c_speed>0.5 && g.c_speed==0.0,"no physical contrast");
   need(a.stale_b==0 && g.stale_b==0,"R left stale contact");
   need(a.permanent==1 && g.permanent==1,"permanent joint lost");
   need(a.group_count==(reset?2:1)&&g.group_count==0,"G group count");
 }
 dCloseODE();
 std::puts("H6_ADVERSARIAL_NATIVE_ODE_PASS");
}

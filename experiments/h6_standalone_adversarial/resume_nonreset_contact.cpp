// H6 adversarial Webots R2025a path: pausePhysics() -> resumePhysics()
// -> resetSingleSolidPhysics() -> PR765 R: detachResetBodyContacts().
// Real Webots GUI WbDragSolidEvent calls pause/resume even with no displacement.
// This native ODE probe reproduces the contact deletion and the FIRST solver.
// Limits: Webots GUI event dispatch and full scheduler are not executed here.
#include <ode/ode.h>
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <cstring>
static void require(bool x,const char*msg){if(!x){std::fprintf(stderr,"H6_RESUME_REFUSED %s\n",msg);std::exit(2);}}
struct Result{double z,vz;int oldContacts,preContacts;};
static Result run(bool r){
 dWorldID w=dWorldCreate();require(w!=nullptr,"world");
 dWorldSetGravity(w,0,0,-9.81);
 dWorldSetERP(w,0.8);
 dWorldSetCFM(w,0.00001);
 dWorldSetAutoDisableFlag(w,0);
 dBodyID b=dBodyCreate(w);require(b!=nullptr,"body");
 dMass m;dMassSetBoxTotal(&m,0.1,0.2,0.2,0.2);
 dBodySetMass(b,&m);
 dBodySetPosition(b,0,0,.09);
 dGeomID box=dCreateBox(nullptr,0.2,0.2,0.2);
 dGeomID floor=dCreatePlane(nullptr,0,0,1,0);
 require(box&&floor,"geometry");
 dGeomSetBody(box,b);
 dContact c{};
 require(dCollide(box,floor,1,&c.geom,sizeof(dContactGeom))==1,"real intersecting ground contact");
 require(c.geom.depth>0.005,"penetrating ground");
 c.surface.mode=dContactSoftERP|dContactSoftCFM;
 c.surface.mu=0;
 c.surface.soft_erp=0.8;
 c.surface.soft_cfm=0.00001;
 dJointID j=dJointCreateContact(w,nullptr,&c);
 require(j!=nullptr,"contact joint");
 dJointAttach(j,b,nullptr);
 require(dBodyGetNumJoints(b)==1,"initial contact was not attached");
 // WbSolid::pausePhysics(), no movement.
 dBodyDisable(b);
 require(dBodyIsEnabled(b)==0,"pause failed");
 // WbSolid::resumePhysics() always calls resetSingleSolidPhysics() even without
 // Supervisor RESET; the latter zeroes velocities and PR765 R destroys contact.
 dBodySetLinearVel(b,0,0,0);dBodySetAngularVel(b,0,0,0);
 dBodySetForce(b,0,0,0);dBodySetTorque(b,0,0,0);
 if(r){ // exact PR765 contact type filter / standalone destructor
  require(dJointGetType(j)==dJointTypeContact,"non-contact");
  dJointDestroy(j);
  j=nullptr;
 }
 int attached=dBodyGetNumJoints(b);
 dBodyEnable(b);
 require(dBodyIsEnabled(b)!=0,"resume failed");
 require(dBodyGetLinearVel(b)[2]==0.0,"pre velocity unequal");
 dWorldStep(w,0.032);
 const dReal *p=dBodyGetPosition(b);
 const dReal *v=dBodyGetLinearVel(b);
 Result result{p[2],v[2],1,attached};
 require(std::isfinite(result.vz)&&std::isfinite(result.z),"nonfinite");
 std::printf("{\"resume_without_RESET\":true,\"standalone_R\":%d,"
  "\"pre_attached_contacts\":%d,\"initial_z\":0.09,"
  "\"pre_vertical_velocity\":0,\"post_z\":%.17g,\"post_vz\":%.17g}\n",
  int(r),attached,result.z,result.vz);
 if(j)dJointDestroy(j);
 dGeomDestroy(box);dGeomDestroy(floor);dBodyDestroy(b);dWorldDestroy(w);
 return result;
}
int main(){
 require(dInitODE2(0)!=0,"init ODE");
 const Result a=run(false),r=run(true);
 require(a.preContacts==1&&r.preContacts==0,"wrong R contact selection");
 require(std::fabs(a.vz-r.vz)>0.1,"no first-solver physical difference");
 require(std::fabs(a.z-r.z)>0.002,"no position difference");
 dCloseODE();
 std::printf("H6_RESUME_WITHOUT_RESET_PHYSICAL_CONTRAST_PROVEN\n");
 return 0;
}

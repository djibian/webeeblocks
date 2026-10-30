// H6 adversarial: active vs retired contact buffer with foreign group owner.
// Uses only pinned Webots R2025a ODE; this does NOT emulate Webots' full scheduler.
#include <ode/ode.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <vector>

static void require(bool ok, const char* why) {
  if (!ok) { std::fprintf(stderr,"H6_RG_ODE_REFUSED %s\n",why); std::exit(2); }
}
static bool attached(dJointID joint,dBodyID body) {
  return dJointGetBody(joint,0)==body || dJointGetBody(joint,1)==body;
}
static dJointID createContact(dWorldID world,dJointGroupID group,
                              dGeomID x,dGeomID y,dBodyID b1,dBodyID b2) {
  dContact contact{};
  require(dCollide(x,y,1,&contact.geom,sizeof(dContactGeom))==1, "missing geometry contact");
  require(contact.geom.depth>0, "nonpositive penetration");
  contact.surface.mode=dContactSoftERP|dContactSoftCFM;
  contact.surface.soft_erp=0.85;
  contact.surface.soft_cfm=0.00001;
  contact.surface.mu=0;
  dJointID j=dJointCreateContact(world,group,&contact);
  require(j!=nullptr,"joint create");
  dJointAttach(j,b1,b2);
  return j;
}
static void sample(bool staleCurrent, bool useR, bool useG) {
  dWorldID w=dWorldCreate();
  require(w!=nullptr,"world");
  dWorldSetGravity(w,0,0,0);
  dJointGroupID current=dJointGroupCreate(0);
  dJointGroupID retired=dJointGroupCreate(0);
  dBodyID owner=dBodyCreate(w),target=dBodyCreate(w),third=dBodyCreate(w);
  for(dBodyID b:{owner,target,third}) {
    dMass m;dMassSetSphereTotal(&m,0.05,0.035);
    dBodySetMass(b,&m);
  }
  dBodySetPosition(owner,0,0,0);
  dBodySetPosition(target,0.05,0,0);
  dBodySetPosition(third,-0.05,0,0);
  dGeomID go=dCreateSphere(0,0.035),gt=dCreateSphere(0,0.035),gc=dCreateSphere(0,0.035);
  dGeomSetBody(go,owner);
  dGeomSetBody(gt,target);
  dGeomSetBody(gc,third);
  // Dynamic-dynamic contact belongs to owner group's buffer, NOT target body.
  dJointGroupID staleGroup=staleCurrent ? current : retired;
  dJointID old=createContact(w,staleGroup,go,gt,owner,target);
  // Independent, still-current third-party contact must not be detached by R.
  dJointID legitimate=createContact(w,current,go,gc,owner,third);
  require(attached(old,target) && attached(legitimate,owner) &&
          attached(legitimate,third), "initial joint attachment");
  dBodyDisable(owner);
  require(!dBodyIsEnabled(owner),"foreign owner must be disabled");

  // Physically teleport target without the old joint's geometry.
  dBodySetPosition(target,2,0,0);
  dBodySetLinearVel(target,0,0,0);
  dBodySetAngularVel(target,0,0,0);
  dBodySetForce(target,0,0,0);
  dBodySetTorque(target,0,0,0);

  int gRemoved=0;
  if(useG) {
    // Simulates the retired-only cleanup, not the active solver buffer.
    gRemoved=dJointGroupGetCount(retired);
    dJointGroupEmpty(retired);
  }
  int rRemoved=0;
  if(useR) {
    // Select by *actual target attachment*, not contact group ownership.
    std::vector<dJointID> joints;
    int n=dBodyGetNumJoints(target);
    for(int i=0;i<n;i++){
      dJointID j=dBodyGetJoint(target,i);
      if(dJointGetType(j)==dJointTypeContact)joints.push_back(j);
    }
    for(dJointID j:joints){
      dJointAttach(j,nullptr,nullptr);
      dJointDestroy(j); // ODE group retains allocation until retirement
    }
    rRemoved=static_cast<int>(joints.size());
  }
  const int targetAttached=dBodyGetNumJoints(target);
  const int retainedGroupJoints=dJointGroupGetCount(current)+dJointGroupGetCount(retired);
  const int thirdValid=attached(legitimate,owner) && attached(legitimate,third);
  require(thirdValid,"legitimate third-party contact removed");
  require((useG && !staleCurrent ? gRemoved==1 : gRemoved==0),
          "G acted beyond retired buffer");
  require((useR && !(useG && !staleCurrent) ? rRemoved==1 : rRemoved==0),
          "unexpected R selection");
  require(targetAttached==((!useR && (staleCurrent || !useG)) ? 1 : 0),
          "old attached joint presence mismatch");
  dWorldStep(w,0.01);
  const dReal *v=dBodyGetLinearVel(target);
  const dReal *av=dBodyGetAngularVel(target);
  const double speed=std::sqrt(v[0]*v[0]+v[1]*v[1]+v[2]*v[2]);
  const double spin=std::sqrt(av[0]*av[0]+av[1]*av[1]+av[2]*av[2]);
  require(std::isfinite(speed)&&std::isfinite(spin),"nonfinite physics");
  std::printf("{\"buffer\":\"%s\",\"R\":%d,\"G\":%d,"
              "\"foreign_owner_disabled\":1,\"g_removed\":%d,"
              "\"r_detached\":%d,\"target_attached_pre_solve\":%d,"
              "\"legitimate_third_contact\":%d,\"remaining_group_allocations\":%d,"
              "\"target_speed\":%.17g,\"target_spin\":%.17g}\n",
              staleCurrent?"current":"retired",static_cast<int>(useR),static_cast<int>(useG),
              gRemoved,rRemoved,targetAttached,thirdValid,retainedGroupJoints,speed,spin);
  dJointGroupDestroy(current);
  dJointGroupDestroy(retired);
  dGeomDestroy(go); dGeomDestroy(gt); dGeomDestroy(gc);
  dBodyDestroy(owner);dBodyDestroy(target);dBodyDestroy(third);
  dWorldDestroy(w);
}
int main(){
  require(dInitODE2(0)!=0,"init ode");
  for (int current=0;current<=1;current++)
    for (int r=0;r<=1;r++)
      for (int g=0;g<=1;g++)
        sample(current!=0,r!=0,g!=0);
  dCloseODE();
  std::puts("H6_RG_ODE_ADVERSARIAL_COMPLETE");
  return 0;
}

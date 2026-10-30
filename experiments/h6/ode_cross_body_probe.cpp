// H6 E1: native R2025a ODE, contacts owned by one body but attached to another.
// In a group, dJointDestroy() alone is ineffective: ODE releases group joints
// on dJointGroupEmpty/Destroy. Detach selectively without emptying the group.
#include <ode/ode.h>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
static void must(bool p,const char *m){if(!p){fprintf(stderr,"H6_E1_REFUSED %s\n",m);exit(2);}}
static dBodyID body(dWorldID w,double x){
  dBodyID b=dBodyCreate(w);dMass m;dMassSetSphereTotal(&m,0.05,0.035);
  dBodySetMass(b,&m);dBodySetPosition(b,x,0,0);return b;
}
static dJointID contact(dWorldID w,dJointGroupID g,dBodyID a,dBodyID b,double x){
  dContact c={};c.surface.mode=dContactSoftERP|dContactSoftCFM;
  c.surface.mu=0;c.surface.soft_erp=0.85;c.surface.soft_cfm=0.00001;
  c.geom.pos[0]=x;c.geom.normal[1]=1;c.geom.depth=0.04;
  dJointID j=dJointCreateContact(w,g,&c);must(j!=0,"contact creation");dJointAttach(j,a,b);return j;
}
static bool linked(dJointID j,dBodyID b){return dJointGetBody(j,0)==b||dJointGetBody(j,1)==b;}
static void detach_contacts(dBodyID b){
  std::vector<dJointID> j;int n=dBodyGetNumJoints(b);
  for(int i=0;i<n;++i){dJointID x=dBodyGetJoint(b,i);if(dJointGetType(x)==dJointTypeContact)j.push_back(x);}
  for(auto x:j){dJointAttach(x,0,0);dJointDestroy(x);}
}
static double attempt(const char *scenario,const char *arm,bool owner_disabled,bool reset_owner){
  dWorldID w=dWorldCreate();must(w!=0,"world creation");
  dWorldSetGravity(w,0,0,0);dWorldSetERP(w,0.2);dWorldSetCFM(w,0.00001);
  dJointGroupID group=dJointGroupCreate(0);
  dBodyID a=body(w,0),b=body(w,0.07),c=body(w,-0.07);
  dJointID old=contact(w,group,a,b,0.065);
  dJointID other=contact(w,group,a,c,-0.065);
  must(dJointGroupGetCount(group)==2,"initial group count");
  dBodyID reset=reset_owner?a:b;
  if(owner_disabled)dBodyDisable(a);
  dBodySetPosition(reset,2,0,0);
  dBodySetLinearVel(reset,0,0,0);dBodySetAngularVel(reset,0,0,0);
  dBodySetForce(reset,0,0,0);dBodySetTorque(reset,0,0,0);
  if(reset_owner)dBodyEnable(a);
  must(linked(old,reset),"joint attached to reset");
  if(!strcmp(arm,"P")){
    volatile int n=dJointGroupGetCount(group);(void)n;
  }else if(!strcmp(arm,"F")){
    if(reset_owner)dJointGroupEmpty(group); // old F only owns the target's group
  }else if(!strcmp(arm,"R")){
    detach_contacts(reset); // actual joint attachment regardless of owner
  }else must(!strcmp(arm,"A"),"unknown arm");
  int n=dJointGroupGetCount(group);
  // Never dereference a joint after its group has been emptied.
  bool stale = n && linked(old,reset);
  bool kept = n && linked(other,a)&&linked(other,c);
  if(!reset_owner)must(kept,"unrelated contact altered");
  if(!strcmp(arm,"R")){
    must(!stale && dBodyGetNumJoints(reset)==0,"stale reset joint retained");
    if(!reset_owner)must(n==2,"other owner's group destroyed");
  }
  dWorldStep(w,0.032);
  const dReal *om=dBodyGetAngularVel(reset);
  double rot=sqrt(om[0]*om[0]+om[1]*om[1]+om[2]*om[2]);
  must(std::isfinite(rot),"nonfinite angular velocity");
  int new_contact=0;
  if(!reset_owner&&!strcmp(arm,"R")){
    dJointID newj=contact(w,group,a,c,-0.065);
    new_contact=linked(newj,a)&&linked(newj,c)&&dJointGroupGetCount(group)==3;
    must(new_contact,"legitimate new contact cannot be created");
  }
  printf("{\"scenario\":\"%s\",\"arm\":\"%s\",\"omega_rad_s\":%.17g,\"old_attached\":%d,\"unrelated_contact_preserved\":%d,\"group_count\":%d,\"new_contact_created\":%d}\n",
        scenario,arm,rot,int(stale),int(kept),n,new_contact);
  dJointGroupDestroy(group);dWorldDestroy(w);return rot;
}
int main(){
  must(dInitODE2(0)!=0,"ODE init");
  const char* cases[]={"foreign_owner_disabled","foreign_owner_enabled","reset_owner"};
  for(const char* s:cases){
    bool owns=!strcmp(s,"reset_owner");
    bool disabled=strcmp(s,"foreign_owner_enabled")!=0;
    double a=attempt(s,"A",disabled,owns),p=attempt(s,"P",disabled,owns);
    double f=attempt(s,"F",disabled,owns),r=attempt(s,"R",disabled,owns);
    must(fabs(a-p)<1e-12,"placebo changed ODE behavior");
    must(r<1e-12,"R did not prevent physical rotation");
    if(!owns){
      must(a>1e-7,"old foreign-owned joint produced no measurable rotation");
      must(fabs(a-f)<1e-12,"F unexpectedly reached foreign group");
    }else must(f<1e-12,"F failed on owned group");
  }
  dCloseODE();puts("H6_E1_NATIVE_PASS");return 0;
}

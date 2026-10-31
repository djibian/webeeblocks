// Adversarial physics plugin exercising public ODE dJointDestroy against a
// Webots-generated contact. This is not a proposed production plugin.
#include <plugins/physics.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static dBodyID a;
static int tick;
static int destroyed;
static int enabled;
void webots_physics_init(void){
 a=dWebotsGetBodyFromDEF("TARGET");
 if(!a)abort();
 enabled=getenv("H6_EXTERNAL_DESTROY")&&strcmp(getenv("H6_EXTERNAL_DESTROY"),"1")==0;
 fprintf(stderr,"H6_EXT_INIT body=%p enabled=%d\n",(void*)a,enabled);
}
void webots_physics_step(void){
 ++tick;
 if(!enabled||destroyed||tick<3)return;
 int contacts=0;
 for(int i=0;i<dBodyGetNumJoints(a);++i){
   dJointID j=dBodyGetJoint(a,i);
   if(dJointGetType(j)!=dJointTypeContact)continue;
   ++contacts;
   fprintf(stderr,"H6_EXT_DESTROY_BEFORE tick=%d body=%p contact=%p b0=%p b1=%p\n",
    tick,(void*)a,(void*)j,(void*)dJointGetBody(j,0),(void*)dJointGetBody(j,1));
   fflush(stderr);
   dJointDestroy(j);
   destroyed=1;
   fprintf(stderr,"H6_EXT_DESTROY_AFTER tick=%d contact=%p\n",tick,(void*)j);
   fflush(stderr);
   break;
 }
 if(!destroyed)fprintf(stderr,"H6_EXT_NO_CONTACT tick=%d observed=%d\n",tick,contacts);
}
void webots_physics_step_end(void){
 if(tick>=3)fprintf(stderr,"H6_EXT_STEP_END tick=%d destroyed=%d\n",tick,destroyed);
}
void webots_physics_cleanup(void){
 fprintf(stderr,"H6_EXT_CLEANUP tick=%d destroyed=%d\n",tick,destroyed);
}

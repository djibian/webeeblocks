// Independent physics plugin: observes A, B, C, then disables A AFTER solver.
// It does not create, destroy, or detach ANY contact joints.
#include <plugins/physics.h>
#include <stdio.h>
#include <stdlib.h>
static dBodyID a,b,c;
static int tick;
void webots_physics_init(void){
  a=dWebotsGetBodyFromDEF("A");
  b=dWebotsGetBodyFromDEF("B");
  c=dWebotsGetBodyFromDEF("C");
  if(!a||!b||!c)abort();
  fprintf(stderr,"H6_D1_PLUGIN_INIT a=%p b=%p c=%p\n",(void*)a,(void*)b,(void*)c);
}
void webots_physics_step(void){ ++tick; }
void webots_physics_step_end(void){
  if(tick>=2&&a){
    dBodyDisable(a);
    int ac=0,ab=0,tot=0;
    for(int i=0;i<dBodyGetNumJoints(a);++i){
      dJointID j=dBodyGetJoint(a,i);
      if(dJointGetType(j)!=dJointTypeContact)continue;
      ++tot;
      if(dJointGetBody(j,0)==b||dJointGetBody(j,1)==b)++ab;
      if(dJointGetBody(j,0)==c||dJointGetBody(j,1)==c)++ac;
    }
    fprintf(stderr,"H6_D1_PLUGIN_SLEEP tick=%d a=%p enabled=%d ab=%d ac=%d total=%d\n",
      tick,(void*)a,dBodyIsEnabled(a),ab,ac,tot);
  }
}
void webots_physics_cleanup(void){fprintf(stderr,"H6_D1_PLUGIN_CLEANUP tick=%d\n",tick);}

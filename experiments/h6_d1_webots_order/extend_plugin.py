#!/usr/bin/env python3
"""Test-only physical contribution probe in the already used observer plugin.
Set contact feedback before the next solver and observe it after. No plugin joint
creation/deletion, collision callback intervention, or owner mutation.
"""
from pathlib import Path
p=Path("experiments/h6_d1_adversarial/plugins/physics/h6_d1_owner_sleep/h6_d1_owner_sleep.c")
s=p.read_text()
assert s.count("static int tick;")==1
s=s.replace("static int tick;",'''static int tick;
static dJointFeedback h6_ac_feedback[32];
static int h6_ac_count, h6_wake_test;
''')
s=s.replace("#include <stdlib.h>","#include <stdlib.h>\n#include <math.h>\n#include <string.h>")
old="void webots_physics_step(void){ ++tick; }"
new='''void webots_physics_step(void){
  ++tick;
  if(tick==4 && getenv("H6_D1_WAKE_FIRST_SOLVER") &&
     strcmp(getenv("H6_D1_WAKE_FIRST_SOLVER"),"1")==0) {
    const int initially_enabled=dBodyIsEnabled(a);
    for(int i=0;i<dBodyGetNumJoints(a);++i){
      dJointID j=dBodyGetJoint(a,i);
      if(dJointGetType(j)!=dJointTypeContact)continue;
      if(dJointGetBody(j,0)!=c && dJointGetBody(j,1)!=c)continue;
      if(h6_ac_count>=32)abort();
      memset(&h6_ac_feedback[h6_ac_count],0,sizeof(dJointFeedback));
      dJointSetFeedback(j,&h6_ac_feedback[h6_ac_count]);
      ++h6_ac_count;
    }
    if(!initially_enabled && h6_ac_count){
      dBodyEnable(a);
      h6_wake_test=1;
    }
    // Test-only controlled closing velocity. No mutation of joint owners, maps,
    // attachments or spatial positions; physical response becomes observable.
    if(h6_ac_count && getenv("H6_D1_EXCITE_AC") &&
       strcmp(getenv("H6_D1_EXCITE_AC"),"1")==0){
      const dReal *ap=dBodyGetPosition(a),*cp=dBodyGetPosition(c);
      const double dx=cp[0]-ap[0],dy=cp[1]-ap[1],dz=cp[2]-ap[2];
      const double len=sqrt(dx*dx+dy*dy+dz*dz);
      if(len<1e-7)abort();
      dBodySetLinearVel(c,0,0,0);
      dBodySetLinearVel(a,6*dx/len,6*dy/len,6*dz/len);
      fprintf(stderr,"H6_D1_EXCITE tick=4 speed=6 distance=%.17g ac=%d\\n",
        len,h6_ac_count);
    }
    fprintf(stderr,"H6_D1_FIRST_SOLVER_BEFORE tick=%d enabled_before=%d ac=%d forcedWake=%d\\n",
            tick,initially_enabled,h6_ac_count,h6_wake_test);
  }
}'''
assert s.count(old)==1
s=s.replace(old,new)
old="void webots_physics_step_end(void){\n  if(tick>=2&&a){"
new='''void webots_physics_step_end(void){
  if(tick==4 && getenv("H6_D1_WAKE_FIRST_SOLVER")){
    double f=0.0;
    for(int i=0;i<h6_ac_count;i++){
      for(int axis=0;axis<3;axis++)f+=fabs(h6_ac_feedback[i].f1[axis]);
    }
    fprintf(stderr,"H6_D1_FIRST_SOLVER_AFTER tick=%d ac=%d forcedWake=%d forceL1=%.17g enabled=%d\\n",
      tick,h6_ac_count,h6_wake_test,f,dBodyIsEnabled(a));
  }
  if(tick>=2&&a){'''
assert s.count(old)==1
s=s.replace(old,new)
p.write_text(s)
print("H6_D1_PLUGIN_WAKES_A_ONLY_AT_FIRST_POST_REMOVE_SOLVER_TEST_ARM")

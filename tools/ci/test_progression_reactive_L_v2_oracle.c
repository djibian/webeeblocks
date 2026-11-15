/* Isolated C11 Activity 5 v2 oracle positive and adversarial witnesses.
 * Synthetic poses DO NOT authorize a real Webots pupil-flight PASS.
 */
#include "reactive_core_v2.h"
#include <assert.h>
#include <stdio.h>
typedef struct{wb_rl2_mission m;wb_rl2_sample s;} journey;
static void begin_at(journey *j,char v,double origin_z){
  wb_rl2_reset(&j->m,101,v,origin_z);
  j->s=(wb_rl2_sample){.time=.1,.x=0,.y=0,.z=origin_z,.yaw=0};
  assert(wb_rl2_sample_mission(&j->m,&j->s)==WB_RL2_WAIT);
}
static void begin(journey *j,char v){begin_at(j,v,.015);}
static void step(journey *j,double x,double y,double z,
                 double yaw,int completed,int contact){
  /* Match the actual classroom basicTimeStep=32 ms, not an 80-ms proxy. */
  const double dt=.032;const wb_rl2_sample old=j->s;
  j->s.time+=dt;j->s.x=x;j->s.y=y;j->s.z=z;j->s.yaw=yaw;
  j->s.vx=(x-old.x)/dt;j->s.vy=(y-old.y)/dt;
  j->s.vz=(z-old.z)/dt;j->s.completed=completed;j->s.contact=contact;
  /* Synthetic default is not a native contact attestation. */
  j->s.floor_contact=(z<=WB_RL2_LAND_ABSOLUTE_Z&&contact==0)?1:0;
}
static void move(journey *j,double x,double y,double z,double yaw){
  const double d=atan2(sin(yaw-j->s.yaw),cos(yaw-j->s.yaw));
  int n=(int)ceil(fmax(fmax(fabs(x-j->s.x),fabs(y-j->s.y))/.035,
                        fmax(fabs(z-j->s.z)/.035,fabs(d)/.075)));
  if(n<1)n=1;
  const wb_rl2_sample old=j->s;
  for(int k=1;k<=n;++k){
    const double a=(double)k/n;
    step(j,old.x+a*(x-old.x),old.y+a*(y-old.y),
         old.z+a*(z-old.z),old.yaw+a*d,0,0);
    assert(wb_rl2_sample_mission(&j->m,&j->s)==WB_RL2_WAIT);
  }
}
static void prefix_at(journey *j,char v,double origin_z){
  begin_at(j,v,origin_z);move(j,0,0,.5,0);move(j,.8,0,.5,0);
  move(j,.8,0,.5,WB_RL2_PI/2);
  assert(j->m.stage==1);
  move(j,.8,1,.5,WB_RL2_PI/2);
  assert(j->m.stage==2);
}
static void prefix(journey *j,char v){prefix_at(j,v,.015);}
static void full_route_at(journey *j,char v,double origin_z,double landing_z){
  prefix_at(j,v,origin_z);
  if(v=='A'){
    move(j,.8,1,.5,0);move(j,1.58,1,.5,0);
  }else{
    move(j,.8,1,.5,WB_RL2_PI);
    if(v=='B')move(j,-.62,1,.5,WB_RL2_PI);
    else{
      move(j,-.45,1,.5,WB_RL2_PI);
      move(j,-.45,1,.5,WB_RL2_PI/2);
      assert(j->m.stage==3);
      move(j,-.45,1.6,.5,WB_RL2_PI/2);
    }
  }
  assert(j->m.stage==wb_rl2_total(v));
  move(j,wb_rl2_pad_x(v),wb_rl2_pad_y(v),landing_z,wb_rl2_pad_yaw(v));
}
static void full_route(journey *j,char v){full_route_at(j,v,.015,.015);}
static void false_hover_landing(char v){
  /* Start was accepted at 10 cm, but an immobile 16.5-cm hover is NOT
   * grounded, even with correct gates, pad, yaw, LAND and 32-ms dwell. */
  journey j;full_route_at(&j,v,.100,.165);
  step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,1,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  for(int i=0;i<12;++i){
    step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
    assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  }
  step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
  j.s.time=j.m.completion_at+WB_RL2_LAND_TIMEOUT;
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_FAILED);
}
/* Full corridor and checkpoint sequence followed by a low sustained hover.
 * The historical 0.070-m absolute ceiling falsely granted ACHIEVED after
 * eight 32-ms native intervals at both z=0.030 and 0.060. The later failure
 * must be due to the deadline, not an unobserved huge dt or blocked route. */
static void false_low_hover_landing(char v,double hover_z){
  assert(hover_z==.030||hover_z==.060);
  journey j;full_route_at(&j,v,.015,hover_z);
  assert(j.m.stage==wb_rl2_total(v));
  assert(hover_z<=j.m.origin_z+WB_RL2_LAND_Z);
  assert(hover_z>WB_RL2_LAND_ABSOLUTE_Z);
  step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,1,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  for(int i=1;i<=46;++i){
    step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
    assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  }
  step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
  j.s.time=j.m.completion_at+WB_RL2_LAND_TIMEOUT;
  assert(j.s.time-j.m.previous_time<.048);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_FAILED);
}
/* Low stationary hover without native Floor contact is never achieved. */
static void floating_at_floor_height(char v){
  journey j;full_route(&j,v);
  step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,1,0);
  j.s.floor_contact=0;
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  for(int i=0;i<12;++i){
    step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
    j.s.floor_contact=0;
    assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  }
  assert(!j.m.stable_since_valid);
}
/* Losing one Floor sample restarts the uninterrupted 250-ms landing dwell. */
static void interrupted_floor_dwell(char v){
  journey j;full_route(&j,v);
  step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,1,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  for(int i=0;i<5;++i){
    step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
    assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  }
  step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
  j.s.floor_contact=0;
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  assert(!j.m.stable_since_valid);
  for(int i=0;i<8;++i){
    step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
    assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  }
  step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_ACHIEVED);
}
static void invalid_floor_observation(char v){
  journey j;begin(&j,v);
  step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
  j.s.floor_contact=-1;
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_FAILED);
}
static void positive(char v){
  journey j;full_route(&j,v);
  step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,1,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  for(int i=0;i<7;++i){
    step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
    assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  }
  step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_ACHIEVED);
  step(&j,j.s.x+1,j.s.y,j.s.z,j.s.yaw,0,1);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_ACHIEVED);
}
/* A late-spawned observer must never treat an airborne craft at z=0.4 m
 * as a new ground origin. This was a previously untested false-positive. */
static void raised_origin(char v){
  journey j;
  wb_rl2_reset(&j.m,101,v,.400);
  j.s=(wb_rl2_sample){.time=.1,.x=0,.y=0,.z=.400,.yaw=0};
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_FAILED);
}
/* Repeated sparse samples cannot establish 0.25 s uninterrupted landing.
 * A fresh continuous 80-ms cadence may still establish it afterward. */
static void sparse_landing(char v){
  journey j;full_route(&j,v);
  step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,1,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  for(int i=0;i<3;++i){
    step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
    j.s.time+=.11; /* 190-ms physical gap: inside MAX_DT but NOT continuous. */
    assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  }
  for(int i=0;i<7;++i){
    step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
    assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  }
  step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_ACHIEVED);
}
/* Losing even ONE native 32-ms sampling interval must reset dwell,
 * irrespective of the duration of a subsequent uninterrupted observation. */
static void missed_native_frame(char v){
  journey j;full_route(&j,v);
  step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,1,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  for(int i=0;i<5;++i){
    step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
    j.s.time+=.032; /* Observations 64ms apart, one actual frame missing. */
    assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  }
  for(int i=0;i<7;++i){
    step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
    assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  }
  step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_ACHIEVED);
}
/* An open-loop policy copied from variant A must not pass B or C.
 * These are C11 swept physical-collider checks, NOT motorized Webots or
 * proof that every possible open-loop policy fails. */
static void blind_a_turn_on_other_variant(char v){
  assert(v=='B'||v=='C');
  journey j;prefix(&j,v);
  move(&j,.8,1,.5,0); /* Replays the A turn instead of sensing the side. */
  int hit=0;
  for(int i=1;i<=30;++i){
    /* Reach x=.97 in small admissible steps; the next 3-cm segment
     * intersects the actual wall at x~.99 before corridor-only rejection
     * can make this an ambiguous negative. 0.03/0.032 < 2 m/s. */
    const double x=i<=17 ? .8+.01*i : 1.0;
    const int collider=wb_rl2_hits_wall(v,j.s.x,j.s.y,x,1.0);
    step(&j,x,1.,.5,0,0,0);
    const wb_rl2_verdict verdict=wb_rl2_sample_mission(&j.m,&j.s);
    if(verdict==WB_RL2_FAILED){
      assert(collider); /* Physical swept wall, not only an oracle boundary. */
      hit=1;break;
    }
    assert(verdict==WB_RL2_WAIT);
  }
  assert(hit&&j.m.verdict==WB_RL2_FAILED);
}
static void skip_waypoint(char v){
  journey j;begin(&j,v);move(&j,0,0,.5,0);
  step(&j,0,0,.5,0,1,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_FAILED);
  wb_rl2_reset(&j.m,102,v,.015);
  assert(j.m.stage==0&&!j.m.airborne&&!j.m.sampled&&!j.m.completion_seen);
}
static void bypass_wall(char v){
  journey j;begin(&j,v);move(&j,0,0,.5,0);move(&j,.8,0,.5,0);
  step(&j,.85,0,.5,0,0,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  step(&j,.91,0,.5,0,0,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_FAILED);
}
static void contact(char v){
  journey j;begin(&j,v);step(&j,0,0,.015,0,0,1);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_FAILED);
}
static void false_landing(char v){
  journey j;full_route(&j,v);
  step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,1,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  step(&j,j.s.x+.03,j.s.y,j.s.z,j.s.yaw,0,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  step(&j,j.s.x-.03,j.s.y,j.s.z,j.s.yaw,0,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  /* First stable sample starts after the preceding movement: allow eight
   * complete 32-ms intervals thereafter, not seven. */
  for(int i=0;i<8;++i){
    step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
    assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  }
  step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_ACHIEVED);
}
static void late_pose(char v){
  journey j;full_route(&j,v);
  step(&j,j.s.x,j.s.y,.015,j.s.yaw,1,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  const double deadline=j.m.completion_at+WB_RL2_LAND_TIMEOUT;
  while(j.s.time+.08<deadline){
    step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
    j.s.vx=.3;
    assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  }
  step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
  j.s.time=deadline;
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_FAILED);
}
static void replay(char v){
  journey j;begin(&j,v);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_FAILED);
}
static void side_bypass(char v){
  journey j;begin(&j,v);move(&j,0,0,.5,0);
  step(&j,0,.28,.5,0,0,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_FAILED);
}
static void invalid_sample(char v){
  journey j;begin(&j,v);
  step(&j,0,0,.015,0,0,0);j.s.vy=NAN;
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_FAILED);
}
static void wrong_direction(char v){
  journey j;begin(&j,v);move(&j,0,0,.5,0);move(&j,.8,0,.5,0);
  assert(j.m.stage==0);
  step(&j,.8,0,.5,0,1,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_FAILED);
}
static void teleport(char v){
  journey j;begin(&j,v);step(&j,.7,0,.5,0,0,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_FAILED);
}
static void wrong_pad(char v){
  journey j;full_route(&j,v);
  move(&j,j.s.x+.12,j.s.y,j.s.z,j.s.yaw);
  step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,1,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  for(int i=0;i<17;++i){
    step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
    assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  }
  step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
  j.s.time=j.m.completion_at+WB_RL2_LAND_TIMEOUT;
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_FAILED);
}
static void never_completed(char v){
  journey j;full_route(&j,v);
  for(int i=0;i<8;++i){
    step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
    assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  }
  assert(!j.m.completion_seen);
}
int main(void){
  for(const char *v="ABC";*v;++v){
    positive(*v);raised_origin(*v);false_hover_landing(*v);
    false_low_hover_landing(*v,.030);false_low_hover_landing(*v,.060);
    floating_at_floor_height(*v);interrupted_floor_dwell(*v);
    invalid_floor_observation(*v);
    sparse_landing(*v);
    missed_native_frame(*v);skip_waypoint(*v);bypass_wall(*v);contact(*v);
    false_landing(*v);late_pose(*v);replay(*v);side_bypass(*v);
    invalid_sample(*v);wrong_direction(*v);teleport(*v);
    wrong_pad(*v);never_completed(*v);
  }
  for(const char *v="BC";*v;++v)blind_a_turn_on_other_variant(*v);
  wb_rl2_mission bad={0};wb_rl2_sample s={0};
  assert(wb_rl2_sample_mission(&bad,&s)==WB_RL2_FAILED);
  wb_rl2_reset(&bad,0,'Z',NAN);
  assert(wb_rl2_sample_mission(&bad,&s)==WB_RL2_FAILED);
  puts("PASS A5 V2 C oracle: floor-contact positive/adversarial cases");
  return 0;
}

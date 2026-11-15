/* Isolated C11 Activity 5 v2 oracle positive and adversarial witnesses.
 * Synthetic poses DO NOT authorize a real Webots pupil-flight PASS.
 */
#include "reactive_core_v2.h"
#include <assert.h>
#include <stdio.h>
typedef struct{wb_rl2_mission m;wb_rl2_sample s;} journey;
static void begin(journey *j,char v){
  wb_rl2_reset(&j->m,101,v,.015);
  j->s=(wb_rl2_sample){.time=.1,.x=0,.y=0,.z=.015,.yaw=0};
  assert(wb_rl2_sample_mission(&j->m,&j->s)==WB_RL2_WAIT);
}
static void step(journey *j,double x,double y,double z,
                 double yaw,int completed,int contact){
  const double dt=.08;const wb_rl2_sample old=j->s;
  j->s.time+=dt;j->s.x=x;j->s.y=y;j->s.z=z;j->s.yaw=yaw;
  j->s.vx=(x-old.x)/dt;j->s.vy=(y-old.y)/dt;
  j->s.vz=(z-old.z)/dt;j->s.completed=completed;j->s.contact=contact;
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
static void prefix(journey *j,char v){
  begin(j,v);move(j,0,0,.5,0);move(j,.8,0,.5,0);
  move(j,.8,0,.5,WB_RL2_PI/2);
  assert(j->m.stage==1);
  move(j,.8,1,.5,WB_RL2_PI/2);
  assert(j->m.stage==2);
}
static void full_route(journey *j,char v){
  prefix(j,v);
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
  move(j,wb_rl2_pad_x(v),wb_rl2_pad_y(v),.015,wb_rl2_pad_yaw(v));
}
static void positive(char v){
  journey j;full_route(&j,v);
  step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,1,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  for(int i=0;i<3;++i){
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
  for(int i=0;i<3;++i){
    step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
    assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_WAIT);
  }
  step(&j,j.s.x,j.s.y,j.s.z,j.s.yaw,0,0);
  assert(wb_rl2_sample_mission(&j.m,&j.s)==WB_RL2_ACHIEVED);
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
  for(int i=0;i<4;++i){
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
    positive(*v);raised_origin(*v);sparse_landing(*v);
    skip_waypoint(*v);bypass_wall(*v);contact(*v);
    false_landing(*v);late_pose(*v);replay(*v);side_bypass(*v);
    invalid_sample(*v);wrong_direction(*v);teleport(*v);
    wrong_pad(*v);never_completed(*v);
  }
  wb_rl2_mission bad={0};wb_rl2_sample s={0};
  assert(wb_rl2_sample_mission(&bad,&s)==WB_RL2_FAILED);
  wb_rl2_reset(&bad,0,'Z',NAN);
  assert(wb_rl2_sample_mission(&bad,&s)==WB_RL2_FAILED);
  puts("PASS A5 V2 C oracle: 47 positive/adversarial cases");
  return 0;
}

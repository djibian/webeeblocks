#ifndef WEBEEBLOCKS_REACTIVE_L_V2_CORE_H
#define WEBEEBLOCKS_REACTIVE_L_V2_CORE_H
/* A5 v2 Draft: simulated-pose mission oracle. No AST, Webots I/O or motors.
 * Requires a separate, independent native attestation of scene identity,
 * real pose, contact state, attempt freshness and program completion.
 * This core alone is NOT a qualified pupil/Blockly flight.
 */
#include <math.h>
#include <string.h>
#define WB_RL2_ORACLE "progression-reactive-L-v2"
#define WB_RL2_PI 3.14159265358979323846
#define WB_RL2_BODY 0.09
#define WB_RL2_CHECKPOINT 0.13
#define WB_RL2_CORRIDOR 0.25
#define WB_RL2_YAW_TOL 0.23
#define WB_RL2_PAD_TOL 0.07 /* 0.16 pad half-side - 0.09 craft half-span */
#define WB_RL2_LAND_Z 0.07
#define WB_RL2_LAND_SPEED 0.12
#define WB_RL2_LAND_DWELL 0.25
/* Native classroom start is on the physical floor, not an arbitrary z offset.
 * Keep a small tolerance for the Crazyflie's initial physical elevation. */
#define WB_RL2_START_MIN_Z -0.04
#define WB_RL2_START_MAX_Z 0.10
/* Webots' normal classroom physics/observer sample is 32 ms. Allow 16 ms
 * jitter, but not a missed 32-ms sample (64-ms gap): no unobserved interval
 * may be credited as continuous landing dwell. This is NOT MAX_DT, which
 * separately constrains movement/inter-sample jumps. */
#define WB_RL2_LAND_MAX_SAMPLE_GAP 0.048
#define WB_RL2_LAND_TIMEOUT 1.50
#define WB_RL2_MAX_DT 0.20
#define WB_RL2_MAX_SPEED 2.0
#define WB_RL2_MAX_YAW_RATE 7.0
typedef enum {WB_RL2_WAIT=0,WB_RL2_ACHIEVED=1,WB_RL2_FAILED=2} wb_rl2_verdict;
typedef struct {
  double time,x,y,z,vx,vy,vz,yaw;
  int contact,completed;
} wb_rl2_sample;
typedef struct {double x,y,z,sx,sy,sz;} wb_rl2_box;
typedef struct {
  unsigned long long attempt;
  char variant;
  double origin_z,previous_time,previous_x,previous_y,previous_yaw;
  double previous_speed,completion_at,stable_since;
  int sampled,airborne,stage,completion_seen,stable_since_valid;
  wb_rl2_verdict verdict;
} wb_rl2_mission;
static inline int wb_rl2_variant(char v){return v=='A'||v=='B'||v=='C';}
static inline int wb_rl2_total(char v){return v=='C'?4:3;}
static inline double wb_rl2_pad_x(char v){
  return v=='A'?1.58:(v=='B'?-0.62:-0.45);
}
static inline double wb_rl2_pad_y(char v){return v=='C'?1.60:1.0;}
static inline double wb_rl2_pad_yaw(char v){
  return v=='A'?0.0:(v=='B'?WB_RL2_PI:WB_RL2_PI/2.0);
}
static inline double wb_rl2_err(double a,double b){
  return fabs(atan2(sin(a-b),cos(a-b)));
}
static inline void wb_rl2_reset(wb_rl2_mission *m,
                                unsigned long long attempt,char variant,
                                double origin_z){
  if(!m)return;
  memset(m,0,sizeof(*m));
  m->attempt=attempt;m->variant=variant;m->origin_z=origin_z;
  m->verdict=WB_RL2_WAIT;
}
static inline int wb_rl2_finite(const wb_rl2_sample *s){
  return s&&isfinite(s->time)&&isfinite(s->x)&&isfinite(s->y)&&
    isfinite(s->z)&&isfinite(s->vx)&&isfinite(s->vy)&&
    isfinite(s->vz)&&isfinite(s->yaw)&&
    (s->contact==0||s->contact==1)&&
    (s->completed==0||s->completed==1);
}
/* Exact box dimensions of the staged v2 worlds. The native adapter must
 * independently attest all instantiated Solids, not trust this table alone.
 */
static inline int wb_rl2_boxes(char v,wb_rl2_box out[7]){
  if(!out||!wb_rl2_variant(v))return 0;
  out[0]=(wb_rl2_box){1.02,0,.55,.08,.64,1.10};
  out[1]=(wb_rl2_box){.80,-.32,.55,.48,.08,1.10};
  out[2]=(wb_rl2_box){.80,1.25,.55,.64,.08,1.10};
  out[3]=(wb_rl2_box){v=='A'?.48:1.12,1.0,.55,.08,.50,1.10};
  if(v=='C'){
    out[4]=(wb_rl2_box){-.68,1.0,.55,.08,.64,1.10};
    out[5]=(wb_rl2_box){-.45,.68,.55,.48,.08,1.10};
    out[6]=(wb_rl2_box){-.45,1.95,.55,.72,.08,1.10};
    return 7;
  }
  out[4]=(wb_rl2_box){v=='A'?1.95:-1.02,1.0,.55,.08,.72,1.10};
  return 5;
}
/* Swept body radius against physical 1.10m walls. Sampled flight stays
 * below 0.95m above takeoff, so passing over a wall is not an escape. */
static inline int wb_rl2_segment_hits_box(double ax,double ay,double bx,
                                           double by,const wb_rl2_box *b){
  double lo=0.0,hi=1.0;
  const double origin[2]={ax,ay},delta[2]={bx-ax,by-ay};
  const double center[2]={b->x,b->y},size[2]={b->sx,b->sy};
  for(int i=0;i<2;++i){
    const double min=center[i]-(size[i]/2.0+WB_RL2_BODY);
    const double max=center[i]+(size[i]/2.0+WB_RL2_BODY);
    if(fabs(delta[i])<1e-12){
      if(origin[i]<min||origin[i]>max)return 0;
    }else{
      const double a=(min-origin[i])/delta[i];
      const double c=(max-origin[i])/delta[i];
      lo=fmax(lo,fmin(a,c));hi=fmin(hi,fmax(a,c));
      if(hi<lo)return 0;
    }
  }
  return 1;
}
static inline int wb_rl2_hits_wall(char v,double ax,double ay,
                                   double bx,double by){
  wb_rl2_box walls[7];
  const int n=wb_rl2_boxes(v,walls);
  if(!n)return 1;
  for(int i=0;i<n;++i)
    if(wb_rl2_segment_hits_box(ax,ay,bx,by,&walls[i]))return 1;
  return 0;
}
/* Sequence-aware corridors rule out nonphysical lateral detours that still
 * happen to pass a sparse set of checkpoints. No AST/Blockly-shape test. */
static inline int wb_rl2_on_leg(char v,int stage,double x,double y){
  const double eps=.18;
  if(stage==0)return fabs(y)<=WB_RL2_CORRIDOR&&x>=-eps&&x<=.8+eps;
  if(stage==1)return fabs(x-.8)<=WB_RL2_CORRIDOR&&y>=-eps&&y<=1.0+eps;
  if(stage==2){
    const double end=v=='A'?1.58:(v=='B'?-.62:-.45);
    return fabs(y-1.0)<=WB_RL2_CORRIDOR&&
      x>=fmin(.8,end)-eps&&x<=fmax(.8,end)+eps;
  }
  if(stage==3&&v=='C')
    return fabs(x+.45)<=WB_RL2_CORRIDOR&&y>=1.0-eps&&y<=1.60+eps;
  return fabs(x-wb_rl2_pad_x(v))<=WB_RL2_CORRIDOR&&
         fabs(y-wb_rl2_pad_y(v))<=WB_RL2_CORRIDOR;
}
static inline int wb_rl2_at_checkpoint(char v,int stage,
                                       const wb_rl2_sample *s){
  double x,y,yaw;
  if(stage==0){x=.8;y=0.;yaw=WB_RL2_PI/2.;}
  else if(stage==1){x=.8;y=1.;yaw=WB_RL2_PI/2.;}
  else if(stage==2&&v=='C'){
    x=-.45;y=1.;yaw=WB_RL2_PI/2.;
  }else{
    x=wb_rl2_pad_x(v);y=wb_rl2_pad_y(v);yaw=wb_rl2_pad_yaw(v);
  }
  return fabs(s->x-x)<=WB_RL2_CHECKPOINT&&
    fabs(s->y-y)<=WB_RL2_CHECKPOINT&&
    wb_rl2_err(s->yaw,yaw)<=WB_RL2_YAW_TOL;
}
static inline wb_rl2_verdict wb_rl2_sample_mission(
    wb_rl2_mission *m,const wb_rl2_sample *s){
  if(!m||!m->attempt||!wb_rl2_variant(m->variant)||
     !isfinite(m->origin_z)||
     m->origin_z<WB_RL2_START_MIN_Z||
     m->origin_z>WB_RL2_START_MAX_Z)return WB_RL2_FAILED;
  if(m->verdict!=WB_RL2_WAIT)return m->verdict;
  if(!wb_rl2_finite(s)||s->contact||
     s->z<m->origin_z-.04||s->z>m->origin_z+.95||
     hypot(s->vx,s->vy)>WB_RL2_MAX_SPEED||
     fabs(s->vz)>WB_RL2_MAX_SPEED){
    m->verdict=WB_RL2_FAILED;return m->verdict;
  }
  /* Capture the interval before previous_time is updated below. A skipped
   * observation cannot silently contribute to stable landing dwell. */
  const double observation_gap=m->sampled?s->time-m->previous_time:0.0;
  if(!m->sampled){
    /* The first observation must originate at this attempt's starting pad,
     * including its absolute ground level, not a redefined flight altitude. */
    if(fabs(s->x)>.15||fabs(s->y)>.15||
       s->z<WB_RL2_START_MIN_Z||s->z>WB_RL2_START_MAX_Z||
       s->z>m->origin_z+.12||s->completed){
      m->verdict=WB_RL2_FAILED;return m->verdict;
    }
    m->sampled=1;
  }else{
    const double dt=s->time-m->previous_time;
    const double distance=hypot(s->x-m->previous_x,s->y-m->previous_y);
    const double speed=hypot(s->vx,s->vy);
    if(!(dt>0.0&&dt<=WB_RL2_MAX_DT)||
       distance>.03+WB_RL2_MAX_SPEED*dt||
       distance>.04+2.0*(fmax(m->previous_speed,speed)+.10)*dt||
       wb_rl2_err(s->yaw,m->previous_yaw)>.10+WB_RL2_MAX_YAW_RATE*dt||
       wb_rl2_hits_wall(m->variant,m->previous_x,m->previous_y,s->x,s->y)){
      m->verdict=WB_RL2_FAILED;return m->verdict;
    }
  }
  m->previous_time=s->time;m->previous_x=s->x;m->previous_y=s->y;
  m->previous_yaw=s->yaw;m->previous_speed=hypot(s->vx,s->vy);
  if(wb_rl2_hits_wall(m->variant,s->x,s->y,s->x,s->y)||
     !wb_rl2_on_leg(m->variant,m->stage,s->x,s->y)){
    m->verdict=WB_RL2_FAILED;return m->verdict;
  }
  if(s->z>=m->origin_z+.20)m->airborne=1;
  if(!m->completion_seen&&!s->completed&&m->airborne&&
     m->stage<wb_rl2_total(m->variant)&&
     wb_rl2_at_checkpoint(m->variant,m->stage,s))++m->stage;
  if(s->completed&&!m->completion_seen){
    m->completion_seen=1;m->completion_at=s->time;
    if(!m->airborne||m->stage!=wb_rl2_total(m->variant)){
      m->verdict=WB_RL2_FAILED;return m->verdict;
    }
  }
  if(m->completion_seen){
    if(s->time-m->completion_at>=WB_RL2_LAND_TIMEOUT){
      m->verdict=WB_RL2_FAILED;return m->verdict;
    }
    const int stable=s->z<=m->origin_z+WB_RL2_LAND_Z&&
      hypot(s->vx,s->vy)<=WB_RL2_LAND_SPEED&&
      fabs(s->vz)<=WB_RL2_LAND_SPEED&&
      fabs(s->x-wb_rl2_pad_x(m->variant))<=WB_RL2_PAD_TOL&&
      fabs(s->y-wb_rl2_pad_y(m->variant))<=WB_RL2_PAD_TOL&&
      wb_rl2_err(s->yaw,wb_rl2_pad_yaw(m->variant))<=WB_RL2_YAW_TOL;
    if(stable){
      if(!m->stable_since_valid||
         observation_gap>WB_RL2_LAND_MAX_SAMPLE_GAP){
        m->stable_since=s->time;m->stable_since_valid=1;
      }
      if(s->time-m->stable_since>=WB_RL2_LAND_DWELL)
        m->verdict=WB_RL2_ACHIEVED;
    }else m->stable_since_valid=0;
  }
  return m->verdict;
}
#endif

#ifndef WB_MINI_GP_CORE_H
#define WB_MINI_GP_CORE_H
/* Activity 7 isolated behavioral C oracle: not yet wired to Webots.
 * Only a native observer attesting scene/contacts/pose may supply samples.
 * No pupil AST inspection, no physical Crazyflie authorization. */
#include <math.h>
#include <string.h>
#define WB_MINI_PI 3.14159265358979323846
#define WB_MINI_H_ENVELOPE (0.035 + 0.090)
#define WB_MINI_H_CENTER_TOL 0.025
#define WB_MINI_H_Y_TOL 0.175
#define WB_MINI_H_Z_MAX 0.530
#define WB_MINI_AIRBORNE 0.200
/* The very first observed sample must attest the blue start marker; late
 * attachment near H cannot count as a fresh mission attempt. Webots native
 * scene/identity validation is still required at the observer boundary. */
/* Native school floor z=0: the Crazyflie body center rests around 0.015m.
 * This reference is independently bounded, not pupil- or reset-supplied.
 * A high airborne origin must not turn a hover into a false landing. */
#define WB_MINI_GROUND_CENTER_Z 0.015
#define WB_MINI_GROUND_TOL 0.040
#define WB_MINI_START_X -1.400
#define WB_MINI_START_XY_TOL 0.080
#define WB_MINI_START_Z_TOL 0.060
#define WB_MINI_START_SPEED 0.120
#define WB_MINI_TURN_TOL 0.150
#define WB_MINI_YAW_TOL 0.20
#define WB_MINI_LAND_TOL 0.065
/* At completion the craft may still settle, but cannot be an entire leg
 * away from the landing pad. This is only an admission envelope; success
 * still needs WB_MINI_LAND_TOL and a continuous physical dwell. */
#define WB_MINI_COMPLETION_CAPTURE_TOL 0.160
/* Native floor is z=0; measured Crazyflie body center at rest is about
 * 0.015 m. The old 0.070 m bound accepted a stationary 0.060 m hover.
 * Fail closed on a tighter absolute envelope; this is NOT by itself a
 * Webots floor-contact certificate. Validate genuine native landings. */
/* Keep the historical relative descent allowance and independently prove
 * proximity to the actual z=0 classroom floor. A near-ground hover must
 * not inherit relative freedom as permission to finish above the floor. */
#define WB_MINI_LAND_Z 0.070
#define WB_MINI_LAND_ABSOLUTE_Z 0.020
#define WB_MINI_LAND_SPEED 0.120
#define WB_MINI_SETTLE 1.5
/* Completion is a one-shot notification; stability must be observed after it. */
#define WB_MINI_LAND_DWELL 0.25
/* The classroom R2025a world samples at 32ms. Missing one full native
 * observation cannot count toward a continuous 250ms landing proof.
 * Pausing Webots freezes simulation time and never creates a false gap. */
#define WB_MINI_MAX_LANDING_SAMPLE_GAP 0.040
typedef enum { WB_MINI_WAIT=0, WB_MINI_ACHIEVED=1, WB_MINI_FAILED=2 } wb_mini_verdict;
/* A7: only independent, terminal observations can justify a pupil reason.
 * NONE = evidence is unavailable or insufficient; do not speculate. */
typedef enum {
  WB_MINI_REASON_NONE=0,
  WB_MINI_REASON_CONTACT,
  WB_MINI_REASON_INVALID_START,
  WB_MINI_REASON_H_CLEARANCE,
  WB_MINI_REASON_ROUTE,
  WB_MINI_REASON_WRONG_HEADING,
  WB_MINI_REASON_BOUNDARY,
  WB_MINI_REASON_EARLY,
  WB_MINI_REASON_LANDING,
  WB_MINI_REASON_WRONG_PAD
} wb_mini_reason;
static inline const char *wb_mini_reason_token(wb_mini_reason r) {
  switch(r) {
    case WB_MINI_REASON_CONTACT: return "obstacle-contact";
    case WB_MINI_REASON_INVALID_START: return "invalid-start";
    case WB_MINI_REASON_H_CLEARANCE: return "unsafe-h-crossing";
    case WB_MINI_REASON_ROUTE: return "route-incomplete";
    case WB_MINI_REASON_WRONG_HEADING: return "wrong-heading";
    case WB_MINI_REASON_BOUNDARY: return "course-boundary";
    case WB_MINI_REASON_EARLY: return "early-finish";
    case WB_MINI_REASON_LANDING: return "landing-timeout";
    case WB_MINI_REASON_WRONG_PAD: return "wrong-pad";
    default: return NULL;
  }
}
typedef struct {
  double time,x,y,z,vx,vy,vz,yaw;
  int contact,completed;
  /* Independent native floor contact, not an altitude approximation. */
  int floor_contact;
} wb_mini_sample;
typedef struct {
  unsigned long long attempt;
  char variant; /* native-attested L/R, never Blockly-supplied */
  double origin_z,last_time,completion_at,stable_since;
  /* Previous real sample permits checking the entire swept H strip. */
  double previous_x,previous_y,previous_z;
  int airborne,armed,center_seen,crossed,turned,completion_seen;
  int stable_since_valid,previous_valid;
  wb_mini_verdict verdict;
  wb_mini_reason reason; /* Latched at first irreversible native failure. */
} wb_mini_mission;
static inline double wb_mini_h_x(char v) {return v=='L' ? -0.750 : -0.450;}
static inline double wb_mini_turn_x(char v) {return v=='L' ? 0.200 : 0.500;}
static inline double wb_mini_pad_y(char v) {return v=='L' ? 0.950 : -0.950;}
static inline double wb_mini_heading(char v) {return v=='L' ? WB_MINI_PI/2 : -WB_MINI_PI/2;}
static inline double wb_mini_yaw_error(double a,double b) {
  return fabs(atan2(sin(a-b),cos(a-b)));
}
static inline void wb_mini_reset(wb_mini_mission *m,unsigned long long attempt,
                                  char variant,double origin_z) {
  if (!m) return;
  memset(m,0,sizeof(*m));
  m->attempt=attempt;m->variant=variant;m->origin_z=origin_z;
  m->last_time=-1.0;
}
static inline int wb_mini_valid(const wb_mini_sample *s) {
  return s&&isfinite(s->time)&&isfinite(s->x)&&isfinite(s->y)&&
    isfinite(s->z)&&isfinite(s->vx)&&isfinite(s->vy)&&
    isfinite(s->vz)&&isfinite(s->yaw)&&
    (s->contact==0||s->contact==1)&&
    (s->floor_contact==0||s->floor_contact==1)&&
    (s->completed==0||s->completed==1);
}
static inline wb_mini_verdict wb_mini_sample_mission(wb_mini_mission *m,
                                                     const wb_mini_sample *s) {
  if(!m||!m->attempt||(m->variant!='L'&&m->variant!='R')||
     !isfinite(m->origin_z))return WB_MINI_FAILED;
  if(m->verdict!=WB_MINI_WAIT)return m->verdict;
  if(!wb_mini_valid(s)||s->time<=m->last_time||s->time<0) {
    /* Invalid evidence fails closed, but cannot yield a claimed cause. */
    m->verdict=WB_MINI_FAILED;return m->verdict;
  }
  if(s->contact) {
    m->reason=WB_MINI_REASON_CONTACT;
    m->verdict=WB_MINI_FAILED;return m->verdict;
  }
  /* A fresh attempt must be observed on the blue marker, on the ground,
   * approximately stationary and initially facing the first H. This is an
   * observation precondition, not an inspection of the pupil's algorithm. */
  if(!m->previous_valid &&
     (fabs(m->origin_z-WB_MINI_GROUND_CENTER_Z)>WB_MINI_GROUND_TOL||
      fabs(s->z-WB_MINI_GROUND_CENTER_Z)>WB_MINI_GROUND_TOL||
      fabs(s->x-WB_MINI_START_X)>WB_MINI_START_XY_TOL||
      fabs(s->y)>WB_MINI_START_XY_TOL||
      fabs(s->z-m->origin_z)>WB_MINI_START_Z_TOL||
      hypot(s->vx,s->vy)>WB_MINI_START_SPEED||
      fabs(s->vz)>WB_MINI_START_SPEED||
      wb_mini_yaw_error(s->yaw,0)>WB_MINI_YAW_TOL||
      s->completed)) {
    /* At valid launch pose, immediate COMPLETE is premature, not an
     * incorrectly placed start. Both are observations, not AST rules. */
    const int invalid_start=
      fabs(m->origin_z-WB_MINI_GROUND_CENTER_Z)>WB_MINI_GROUND_TOL||
      fabs(s->z-WB_MINI_GROUND_CENTER_Z)>WB_MINI_GROUND_TOL||
      fabs(s->x-WB_MINI_START_X)>WB_MINI_START_XY_TOL||
      fabs(s->y)>WB_MINI_START_XY_TOL||
      fabs(s->z-m->origin_z)>WB_MINI_START_Z_TOL||
      hypot(s->vx,s->vy)>WB_MINI_START_SPEED||
      fabs(s->vz)>WB_MINI_START_SPEED||
      wb_mini_yaw_error(s->yaw,0)>WB_MINI_YAW_TOL;
    m->reason=invalid_start?WB_MINI_REASON_INVALID_START:WB_MINI_REASON_EARLY;
    m->verdict=WB_MINI_FAILED;return m->verdict;
  }
  /* A sparse sequence of identical poses is not continuous evidence.
   * A gap after COMPLETE restarts dwell from the next real sample. */
  if(m->completion_seen &&
     s->time-m->last_time>WB_MINI_MAX_LANDING_SAMPLE_GAP)
    m->stable_since_valid=0;
  m->last_time=s->time;
  if(s->z>=m->origin_z+WB_MINI_AIRBORNE)m->airborne=1;
  const double h=wb_mini_h_x(m->variant);
  /* A sequence of individually legal sample points is insufficient:
   * the entire LINE SEGMENT through the H's collision envelope must be
   * centered and low. This excludes a skipped/sideways H crossing between
   * samples without inspecting the pupil's Blockly or imposing a route AST.
   * Linear interpolation is conservative at the native observer's steps. */
  if(!m->crossed) {
    double a=0.0,b=1.0;
    int intersects=fabs(s->x-h)<=WB_MINI_H_ENVELOPE;
    if(m->previous_valid) {
      const double dx=s->x-m->previous_x;
      if(fabs(dx)>1e-12) {
        const double t0=(h-WB_MINI_H_ENVELOPE-m->previous_x)/dx;
        const double t1=(h+WB_MINI_H_ENVELOPE-m->previous_x)/dx;
        a=fmax(0.0,fmin(t0,t1));
        b=fmin(1.0,fmax(t0,t1));
        intersects=(a<=b);
      }
    }
    if(intersects) {
      const double ya=m->previous_valid ?
        m->previous_y+a*(s->y-m->previous_y) : s->y;
      const double yb=m->previous_valid ?
        m->previous_y+b*(s->y-m->previous_y) : s->y;
      const double za=m->previous_valid ?
        m->previous_z+a*(s->z-m->previous_z) : s->z;
      const double zb=m->previous_valid ?
        m->previous_z+b*(s->z-m->previous_z) : s->z;
      if(fabs(ya)>WB_MINI_H_Y_TOL||fabs(yb)>WB_MINI_H_Y_TOL||
         za>WB_MINI_H_Z_MAX||zb>WB_MINI_H_Z_MAX) {
        m->reason=WB_MINI_REASON_H_CLEARANCE;
        m->verdict=WB_MINI_FAILED;return m->verdict;
      }
    }
  }
  m->previous_x=s->x;m->previous_y=s->y;m->previous_z=s->z;
  m->previous_valid=1;
  /* Reaching the centre is not a token valid forever: an upstream
   * retreat cancels the unfinished pass, permitting a fresh legal try. */
  if(!m->crossed&&m->center_seen&&
     s->x<=h-WB_MINI_H_ENVELOPE-0.01)m->center_seen=0;
  if(!m->crossed && !s->completed && !m->completion_seen) {
    if(s->x<=h-WB_MINI_H_ENVELOPE-0.01 && m->airborne)m->armed=1;
    if(m->armed&&fabs(s->x-h)<=WB_MINI_H_CENTER_TOL&&
       fabs(s->y)<=WB_MINI_H_Y_TOL&&s->z<=WB_MINI_H_Z_MAX&&
       wb_mini_yaw_error(s->yaw,0)<=WB_MINI_YAW_TOL)m->center_seen=1;
    if(s->x>=h+WB_MINI_H_ENVELOPE+0.01) {
      if(!m->armed||!m->center_seen) {
        m->reason=WB_MINI_REASON_ROUTE;
        m->verdict=WB_MINI_FAILED;return m->verdict;
      }
      m->crossed=1;
    }
  }
  const double turn_x=wb_mini_turn_x(m->variant);
  /* Require a physically observed 90-degree yaw at the visible corner. */
  if(m->crossed&&!m->turned&&!s->completed&&!m->completion_seen&&
     fabs(s->x-turn_x)<=WB_MINI_TURN_TOL&&
     fabs(s->y)<=WB_MINI_TURN_TOL&&
     wb_mini_yaw_error(s->yaw,wb_mini_heading(m->variant))<=WB_MINI_YAW_TOL)
    m->turned=1;
  /* The second leg must preserve the observed 90-degree local heading.
   * A momentary yaw at the corner followed by a lateral slide is not a turn.
   * Near-corner adjustments remain free until the second leg begins. */
  if(m->turned && fabs(s->y)>WB_MINI_TURN_TOL &&
     wb_mini_yaw_error(s->yaw,wb_mini_heading(m->variant))>WB_MINI_YAW_TOL) {
    m->reason=WB_MINI_REASON_WRONG_HEADING;
    m->verdict=WB_MINI_FAILED;return m->verdict;
  }
  if(m->crossed && (m->variant=='L'?s->y>1.26:s->y< -1.26)) {
    m->reason=WB_MINI_REASON_BOUNDARY;
    m->verdict=WB_MINI_FAILED;return m->verdict;
  }
  /* Like the native Activity 1/3 controllers, completion is an event, NOT
   * a level required on subsequent physics steps. No post-completion
   * progress is allowed: an unfinished route fails on first completion. */
  if(s->completed && !m->completion_seen) {
    m->completion_seen=1;
    m->completion_at=s->time;
    /* Program completion is a one-shot end-of-flight event. Do not allow
     * a whole remaining leg to be flown in the 1.5 s settling window.
     * Reasonable residual drift toward the pad is still admitted. */
    if(!m->airborne||!m->crossed||!m->turned||
       fabs(s->x-turn_x)>WB_MINI_COMPLETION_CAPTURE_TOL||
       fabs(s->y-wb_mini_pad_y(m->variant))>WB_MINI_COMPLETION_CAPTURE_TOL) {
      m->reason=WB_MINI_REASON_EARLY;
      m->verdict=WB_MINI_FAILED;return m->verdict;
    }
  }
  if(m->completion_seen) {
    /* At the deadline (including equality), failure is terminal.
     * A completed dwell cannot promote a late sample to success. */
    if(s->time-m->completion_at>=WB_MINI_SETTLE) {
      /* Call the pad wrong only when genuine floor contact and current
       * position independently show that the whole craft is off target. */
      const int grounded=s->floor_contact==1 &&
        s->z<=WB_MINI_LAND_ABSOLUTE_Z;
      const int outside=fabs(s->x-turn_x)>WB_MINI_LAND_TOL ||
        fabs(s->y-wb_mini_pad_y(m->variant))>WB_MINI_LAND_TOL;
      m->reason=grounded&&outside ?
        WB_MINI_REASON_WRONG_PAD:WB_MINI_REASON_LANDING;
      m->verdict=WB_MINI_FAILED;return m->verdict;
    }
    const int stable =
      fabs(s->x-turn_x)<=WB_MINI_LAND_TOL &&
      fabs(s->y-wb_mini_pad_y(m->variant))<=WB_MINI_LAND_TOL &&
      s->z-m->origin_z<=WB_MINI_LAND_Z &&
      s->z<=WB_MINI_LAND_ABSOLUTE_Z &&
      s->floor_contact==1 &&
      hypot(s->vx,s->vy)<=WB_MINI_LAND_SPEED &&
      fabs(s->vz)<=WB_MINI_LAND_SPEED;
    if(stable) {
      if(!m->stable_since_valid) {
        m->stable_since=s->time;
        m->stable_since_valid=1;
      }
      if(s->time-m->stable_since>=WB_MINI_LAND_DWELL)
        m->verdict=WB_MINI_ACHIEVED;
    } else {
      m->stable_since_valid=0;
    }
  }
  return m->verdict;
}
#endif

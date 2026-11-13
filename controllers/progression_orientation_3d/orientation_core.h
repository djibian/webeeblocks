#ifndef WEBEEBLOCKS_ORIENTATION_3D_CORE_H
#define WEBEEBLOCKS_ORIENTATION_3D_CORE_H
/* Pure simulated-pose evaluator for Activity 3; no Webots, AST or flight I/O.
 * Dimensions are in metres, yaw in radians. One immutable terminal outcome
 * per native attempt. Physical Crazyflie qualification is out of scope.
 */
#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define WB_ORIENT_ORACLE "progression-orientation-3d-v1"
#define WB_ORIENT_CHILDREN 24
#define WB_ORIENT_PI 3.14159265358979323846
#define WB_ORIENT_WAYPOINTS 3
#define WB_ORIENT_XY_TOL 0.105
#define WB_ORIENT_Z_TOL 0.085
#define WB_ORIENT_YAW_TOL 0.20
#define WB_ORIENT_LAND_X 0.90
#define WB_ORIENT_LAND_Y -0.90
#define WB_ORIENT_LAND_TOL 0.11
#define WB_ORIENT_LAND_HEIGHT 0.07
#define WB_ORIENT_MAX_SPEED 0.12
#define WB_ORIENT_AIRBORNE 0.20
#define WB_ORIENT_SETTLE 1.5

typedef enum {
  WB_ORIENT_WAIT = 0,
  WB_ORIENT_ACHIEVED = 1,
  WB_ORIENT_NOT_ACHIEVED = 2
} wb_orient_verdict;

typedef struct {
  double time, x, y, z, vx, vy, vz, yaw;
  int completed;
} wb_orient_sample;

typedef struct {
  unsigned long long attempt;
  double origin_z, completion_at;
  int airborne, stage, completion_seen;
  wb_orient_verdict result;
} wb_orient_mission;

static inline void wb_orient_reset(wb_orient_mission *mission,
                                    unsigned long long attempt, double origin_z) {
  memset(mission, 0, sizeof(*mission));
  mission->attempt = attempt;
  mission->origin_z = origin_z;
}

static inline int wb_orient_finite(const wb_orient_sample *s) {
  return s && isfinite(s->time) && isfinite(s->x) && isfinite(s->y) &&
    isfinite(s->z) && isfinite(s->vx) && isfinite(s->vy) &&
    isfinite(s->vz) && isfinite(s->yaw);
}

/* Webots C orientation matrices are row-major; first column is local +X. */
static inline int wb_orient_yaw(const double orientation[9], double *out) {
  if (!orientation || !out) return 0;
  for (int i = 0; i < 9; ++i)
    if (!isfinite(orientation[i])) return 0;
  const double x = orientation[0], y = orientation[3];
  if (hypot(x, y) < 0.5) return 0;
  *out = atan2(y, x);
  return isfinite(*out);
}

static inline double wb_orient_angular_error(double actual, double target) {
  return fabs(atan2(sin(actual - target), cos(actual - target)));
}

static inline wb_orient_verdict wb_orient_sample_mission(
    wb_orient_mission *m, const wb_orient_sample *s) {
  if (!m || m->attempt == 0 || !isfinite(m->origin_z))
    return WB_ORIENT_NOT_ACHIEVED;
  if (m->result != WB_ORIENT_WAIT)
    return m->result;
  if (!wb_orient_finite(s)) {
    m->result = WB_ORIENT_NOT_ACHIEVED;
    return m->result;
  }
  const double x[] = {0.45, 0.45, 0.90};
  const double y[] = {0.00,-0.45,-0.45};
  const double z[] = {0.63, 0.79, 0.63};
  const double yaw[] = {-WB_ORIENT_PI / 2, 0.0, -WB_ORIENT_PI / 2};
  if (s->z >= m->origin_z + WB_ORIENT_AIRBORNE)
    m->airborne = 1;
  /* Verify each checkpoint at the actual body orientation before completion.
   * A simultaneous fly-through without turning does not earn progression.
   */
  if (!m->completion_seen && !s->completed && m->airborne &&
      m->stage < WB_ORIENT_WAYPOINTS) {
    const int i = m->stage;
    if (fabs(s->x - x[i]) <= WB_ORIENT_XY_TOL &&
        fabs(s->y - y[i]) <= WB_ORIENT_XY_TOL &&
        fabs(s->z - z[i]) <= WB_ORIENT_Z_TOL &&
        wb_orient_angular_error(s->yaw, yaw[i]) <= WB_ORIENT_YAW_TOL)
      ++m->stage;
  }
  if (s->completed && !m->completion_seen) {
    m->completion_seen = 1;
    m->completion_at = s->time;
  }
  if (!m->completion_seen)
    return WB_ORIENT_WAIT;
  if (!m->airborne || m->stage != WB_ORIENT_WAYPOINTS) {
    m->result = WB_ORIENT_NOT_ACHIEVED;
    return m->result;
  }
  const int landed = (s->z - m->origin_z) <= WB_ORIENT_LAND_HEIGHT;
  const int stationary =
    hypot(s->vx, s->vy) <= WB_ORIENT_MAX_SPEED && fabs(s->vz) <= WB_ORIENT_MAX_SPEED;
  const int on_pad =
    fabs(s->x - WB_ORIENT_LAND_X) <= WB_ORIENT_LAND_TOL &&
    fabs(s->y - WB_ORIENT_LAND_Y) <= WB_ORIENT_LAND_TOL;
  if (landed && stationary && on_pad) {
    m->result = WB_ORIENT_ACHIEVED;
  } else if (s->time - m->completion_at >= WB_ORIENT_SETTLE) {
    m->result = WB_ORIENT_NOT_ACHIEVED;
  }
  return m->result;
}

#endif

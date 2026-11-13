#ifndef WEBEEBLOCKS_PROGRESSION_ALTITUDE_CORE_H
#define WEBEEBLOCKS_PROGRESSION_ALTITUDE_CORE_H

/* Pure, bounded, physics-observation mission logic for Activity 2 only.
 * No Blockly, AST, Webots process, radio or physical qualification dependency.
 * Coordinates and margins are part of the isolated scene's accepted contract.
 */
#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define WB_ALT_ORACLE "progression-altitude-3d-v1"
#define WB_ALT_TARGET_X 1.35
#define WB_ALT_TARGET_Y 0.0
/* Physical landing contract: the visual target is a 0.34 m square.
 * A 0.09 m conservative half-span must fit INSIDE its 0.17 m half-side.
 * Checking only the drone's center permits a false success off the pad.
 */
#define WB_ALT_TARGET_X_TOL 0.08
#define WB_ALT_TARGET_Y_TOL 0.08
#define WB_ALT_BARRIER_X 0.62
#define WB_ALT_BARRIER_HALF_X 0.06
#define WB_ALT_BARRIER_HALF_Y 0.42
#define WB_ALT_BARRIER_TOP 0.62
#define WB_ALT_CRAFT_CLEARANCE 0.09
#define WB_ALT_SETTLE_SEC 1.5
#define WB_ALT_MAX_SPEED 0.12
#define WB_ALT_MAX_LANDING_Z 0.07

typedef enum {
  WB_ALT_WAIT = 0,
  WB_ALT_ACHIEVED = 1,
  WB_ALT_NOT_ACHIEVED = 2
} wb_alt_verdict;

typedef struct {
  unsigned long long attempt;
  double origin_z;
  double completion_at;
  int airborne;
  int before_barrier;
  int inside_barrier;
  int crossed_barrier;
  int collision_seen;
  int completion_seen;
  wb_alt_verdict result;
} wb_alt_mission;

typedef struct {
  double time;
  double x, y, z, vx, vy, vz;
  /* 0: contact array valid and no obstacle contact;
   * 1: native obstacle contact observed; -1: contact observation unavailable.
   * Floor contacts are not obstacle contacts. */
  int obstacle_contact;
  int completed;
} wb_alt_sample;

static inline void wb_alt_reset(wb_alt_mission *m,
                                unsigned long long attempt, double origin_z) {
  memset(m, 0, sizeof(*m));
  m->attempt = attempt;
  m->origin_z = origin_z;
}

static inline int wb_alt_finite(const wb_alt_sample *s) {
  return isfinite(s->time) && isfinite(s->x) && isfinite(s->y) &&
         isfinite(s->z) && isfinite(s->vx) && isfinite(s->vy) && isfinite(s->vz);
}

/* Geometry-only contact classification. Return failure for malformed native
 * coordinates; the only allowed ignored contact is a contact outside all
 * registered obstacle AABBs (normally the ground plane).
 */
static inline int wb_alt_obstacle_point(const double p[3]) {
  if (!p || !isfinite(p[0]) || !isfinite(p[1]) || !isfinite(p[2]))
    return -1;
  const double epsilon = 0.004;
  if (fabs(p[0] - 0.62) <= 0.06 + epsilon &&
      fabs(p[1]) <= 0.42 + epsilon &&
      p[2] >= -epsilon && p[2] <= 0.62 + epsilon)
    return 1;
  if (fabs(p[0] - 0.68) <= 0.825 + epsilon &&
      fabs(fabs(p[1]) - 0.51) <= 0.04 + epsilon &&
      p[2] >= -epsilon && p[2] <= 0.85 + epsilon)
    return 1;
  return 0;
}

/* All state changes are monotonic until a new native attempt is observed.
 * Crossing must be observed before the independent landing verdict.
 */
static inline wb_alt_verdict wb_alt_sample_mission(wb_alt_mission *m,
                                                  const wb_alt_sample *s) {
  if (!m || m->attempt == 0)
    return WB_ALT_NOT_ACHIEVED;
  if (m->result != WB_ALT_WAIT)
    return m->result;
  if (!s || !wb_alt_finite(s) || s->obstacle_contact < 0 ||
      s->obstacle_contact > 1) {
    m->result = WB_ALT_NOT_ACHIEVED;
    return m->result;
  }
  if (s->obstacle_contact) {
    m->collision_seen = 1;
    m->result = WB_ALT_NOT_ACHIEVED;
    return m->result;
  }
  if (s->z >= m->origin_z + 0.20)
    m->airborne = 1;

  const double x = s->x, y = s->y, z = s->z - m->origin_z;
  /* The opening is guarded by a 9 cm craft clearance in all dimensions.
   * A side detour in the middle corridor cannot be accepted as a crossing.
   */
  const int in_barrier_span =
    x >= WB_ALT_BARRIER_X - WB_ALT_BARRIER_HALF_X - WB_ALT_CRAFT_CLEARANCE &&
    x <= WB_ALT_BARRIER_X + WB_ALT_BARRIER_HALF_X + WB_ALT_CRAFT_CLEARANCE;
  if (in_barrier_span &&
      fabs(y) <= WB_ALT_BARRIER_HALF_Y + WB_ALT_CRAFT_CLEARANCE &&
      z < WB_ALT_BARRIER_TOP + WB_ALT_CRAFT_CLEARANCE) {
    m->result = WB_ALT_NOT_ACHIEVED;
    return m->result;
  }

  if (x <= WB_ALT_BARRIER_X - WB_ALT_BARRIER_HALF_X - WB_ALT_CRAFT_CLEARANCE)
    m->before_barrier = 1;
  if (m->before_barrier && in_barrier_span &&
      x >= WB_ALT_BARRIER_X - WB_ALT_BARRIER_HALF_X &&
      fabs(y) <= 0.30 &&
      z >= WB_ALT_BARRIER_TOP + WB_ALT_CRAFT_CLEARANCE) {
    m->inside_barrier = 1;
  }
  if (m->inside_barrier &&
      x > WB_ALT_BARRIER_X + WB_ALT_BARRIER_HALF_X + WB_ALT_CRAFT_CLEARANCE &&
      fabs(y) <= 0.30)
    m->crossed_barrier = 1;

  if (s->completed && !m->completion_seen) {
    m->completion_seen = 1;
    m->completion_at = s->time;
  }
  if (!m->completion_seen)
    return WB_ALT_WAIT;

  const int on_pad =
    fabs(x - WB_ALT_TARGET_X) <= WB_ALT_TARGET_X_TOL &&
    fabs(y - WB_ALT_TARGET_Y) <= WB_ALT_TARGET_Y_TOL;
  const int landed = z <= WB_ALT_MAX_LANDING_Z;
  const int stationary =
    hypot(s->vx, s->vy) <= WB_ALT_MAX_SPEED && fabs(s->vz) <= WB_ALT_MAX_SPEED;

  if (m->airborne && m->crossed_barrier && on_pad && landed && stationary) {
    m->result = WB_ALT_ACHIEVED;
    return m->result;
  }
  if (s->time - m->completion_at >= WB_ALT_SETTLE_SEC)
    m->result = WB_ALT_NOT_ACHIEVED;
  return m->result;
}

#endif

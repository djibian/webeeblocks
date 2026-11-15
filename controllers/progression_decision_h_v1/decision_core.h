#ifndef WEBEEBLOCKS_PROGRESSION_DECISION_H_CORE_H
#define WEBEEBLOCKS_PROGRESSION_DECISION_H_CORE_H

/* Activity 4: isolated, native C mission-state logic. No AST inspection,
 * Blockly, flight actuator or real-Crazyflie dependency. A future independent
 * R2025a Webots observer must attest actual scene identity, collision boxes,
 * craft/sensor provenance and attempt/completion before calling this core.
 * These pure sample tests do NOT constitute a Webots pupil mission PASS.
 */
#include <math.h>
#include <stdint.h>
#include <string.h>

#define WB_DH_ORACLE "progression-decision-h-v1"
#define WB_DH_NEAR_X 0.750
#define WB_DH_FAR_X 1.350
#define WB_DH_H_BOTTOM 0.620
#define WB_DH_CURB_TOP 0.700
#define WB_DH_CRAFT_MARGIN 0.090
#define WB_DH_H_HALF_X 0.035
#define WB_DH_CURB_HALF_X 0.050
#define WB_DH_MAX_LANE_Y 0.280
#define WB_DH_LAND_X 1.750
#define WB_DH_LAND_Y 0.000
/* 34-cm-square landing pad, with 9-cm whole-craft half-span. */
#define WB_DH_LAND_TOL 0.080
#define WB_DH_LAND_Z 0.070
#define WB_DH_LAND_MAX_SPEED 0.120
#define WB_DH_SETTLE_SEC 1.500
/* An instant at the target is not an immobile landing. Preserve enough
 * consecutive physical samples to exclude an in-motion crossing. */
#define WB_DH_LAND_DWELL_SEC 0.250
#define WB_DH_MAX_Z 1.100

typedef enum {
  WB_DH_WAIT = 0,
  WB_DH_ACHIEVED = 1,
  WB_DH_NOT_ACHIEVED = 2
} wb_dh_verdict;

typedef enum {
  WB_DH_SCENE_A = 1, /* H near, threshold far. */
  WB_DH_SCENE_B = 2  /* Threshold near, H far. */
} wb_dh_scene;

typedef struct {
  double time, x, y, z, vx, vy, vz;
  /* 0: independently established absence of obstacle contact;
   * 1: actual physical obstacle contact; -1: unavailable (fail closed). */
  int obstacle_contact;
  /* Independently attested program-completion marker, not the pupil's AST. */
  int completed;
} wb_dh_sample;

typedef struct {
  unsigned long long attempt;
  wb_dh_scene scene;
  double origin_z, completion_at, last_time, landed_since;
  unsigned stage; /* 0 before first, 1 inside first, 2 cleared first,
                   * 3 inside second, 4 cleared both. */
  int airborne, before_first, before_second, completion_seen;
  wb_dh_verdict verdict;
} wb_dh_mission;

static inline void wb_dh_reset(wb_dh_mission *m, unsigned long long attempt,
                               wb_dh_scene scene, double origin_z) {
  if (!m) return;
  memset(m, 0, sizeof(*m));
  m->attempt = attempt;
  m->scene = scene;
  m->origin_z = origin_z;
  m->last_time = -1.0;
  m->landed_since = -1.0;
}

static inline int wb_dh_valid_sample(const wb_dh_sample *s) {
  return s && isfinite(s->time) && isfinite(s->x) && isfinite(s->y) &&
    isfinite(s->z) && isfinite(s->vx) && isfinite(s->vy) &&
    isfinite(s->vz) && (s->obstacle_contact == 0 ||
                       s->obstacle_contact == 1) &&
    (s->completed == 0 || s->completed == 1);
}

static inline int wb_dh_is_h(wb_dh_scene scene, unsigned stage) {
  /* station 0 is at x=.75; station 1 at x=1.35. */
  return scene == WB_DH_SCENE_A ? (stage == 0) : (stage == 1);
}

static inline int wb_dh_clearance(double x, double z, double centre,
                                  int is_h) {
  const double half_x = is_h ? WB_DH_H_HALF_X : WB_DH_CURB_HALF_X;
  if (fabs(x - centre) > half_x + WB_DH_CRAFT_MARGIN)
    return 1; /* Still physically outside the collision envelope. */
  if (is_h)
    return z <= WB_DH_H_BOTTOM - WB_DH_CRAFT_MARGIN;
  return z >= WB_DH_CURB_TOP + WB_DH_CRAFT_MARGIN;
}

/* An authoritative observer must call this on every native world step.
 * A right answer is purely behavioral: directed actual passage BELOW H,
 * ABOVE the low barrier, inside corridor, and an entire-craft pad landing.
 */
static inline wb_dh_verdict wb_dh_sample_mission(wb_dh_mission *m,
                                                  const wb_dh_sample *s) {
  if (!m || !m->attempt ||
      (m->scene != WB_DH_SCENE_A && m->scene != WB_DH_SCENE_B) ||
      !isfinite(m->origin_z))
    return WB_DH_NOT_ACHIEVED;
  if (m->verdict != WB_DH_WAIT)
    return m->verdict;
  if (!wb_dh_valid_sample(s) || s->obstacle_contact ||
      s->time <= m->last_time || s->time < 0.0) {
    m->verdict = WB_DH_NOT_ACHIEVED;
    return m->verdict;
  }
  m->last_time = s->time;
  if (s->z >= m->origin_z + 0.20) m->airborne = 1;

  /* Real corridor walls are physical, but an elevated detour can still
   * bypass them. Fail-closed source-independent flight-zone admission. */
  if ((s->x >= -0.20 && s->x <= 1.60 &&
       (fabs(s->y) > WB_DH_MAX_LANE_Y || s->z > WB_DH_MAX_Z)) ||
      !wb_dh_clearance(s->x, s->z, WB_DH_NEAR_X,
                       wb_dh_is_h(m->scene, 0)) ||
      !wb_dh_clearance(s->x, s->z, WB_DH_FAR_X,
                       wb_dh_is_h(m->scene, 1))) {
    m->verdict = WB_DH_NOT_ACHIEVED;
    return m->verdict;
  }

  if (!m->completion_seen && !s->completed && m->airborne) {
    if (m->stage == 0) {
      if (s->x <= WB_DH_NEAR_X - WB_DH_CURB_HALF_X - WB_DH_CRAFT_MARGIN)
        m->before_first = 1;
      if (m->before_first && fabs(s->x - WB_DH_NEAR_X) <= 0.025 &&
          fabs(s->y) <= 0.25) m->stage = 1;
      else if (s->x > WB_DH_NEAR_X + WB_DH_CURB_HALF_X + WB_DH_CRAFT_MARGIN)
        m->verdict = WB_DH_NOT_ACHIEVED;
    } else if (m->stage == 1) {
      if (s->x >= WB_DH_NEAR_X + WB_DH_CURB_HALF_X + WB_DH_CRAFT_MARGIN &&
          fabs(s->y) <= 0.25) m->stage = 2;
    } else if (m->stage == 2) {
      if (s->x <= WB_DH_FAR_X - WB_DH_CURB_HALF_X - WB_DH_CRAFT_MARGIN)
        m->before_second = 1;
      if (m->before_second && fabs(s->x - WB_DH_FAR_X) <= 0.025 &&
          fabs(s->y) <= 0.25) m->stage = 3;
      else if (s->x > WB_DH_FAR_X + WB_DH_CURB_HALF_X + WB_DH_CRAFT_MARGIN)
        m->verdict = WB_DH_NOT_ACHIEVED;
    } else if (m->stage == 3) {
      if (s->x >= WB_DH_FAR_X + WB_DH_CURB_HALF_X + WB_DH_CRAFT_MARGIN &&
          fabs(s->y) <= 0.25) m->stage = 4;
    }
  }
  if (m->verdict != WB_DH_WAIT)
    return m->verdict;

  if (s->completed && !m->completion_seen) {
    m->completion_seen = 1;
    m->completion_at = s->time;
    if (!m->airborne || m->stage != 4) {
      m->verdict = WB_DH_NOT_ACHIEVED;
      return m->verdict;
    }
  }
  if (!m->completion_seen)
    return WB_DH_WAIT;
  /* Never award a newly stable landing at/after the terminal deadline.
   * Equality belongs to failure, even when 0.250 s dwell also completes. */
  if (s->time - m->completion_at >= WB_DH_SETTLE_SEC) {
    m->verdict = WB_DH_NOT_ACHIEVED;
    return m->verdict;
  }

  const int landed = s->z - m->origin_z <= WB_DH_LAND_Z;
  const int still = hypot(s->vx, s->vy) <= WB_DH_LAND_MAX_SPEED &&
                    fabs(s->vz) <= WB_DH_LAND_MAX_SPEED;
  const int whole_craft_on_pad =
    fabs(s->x - WB_DH_LAND_X) <= WB_DH_LAND_TOL &&
    fabs(s->y - WB_DH_LAND_Y) <= WB_DH_LAND_TOL;
  if (landed && still && whole_craft_on_pad) {
    if (m->landed_since < 0.0)
      m->landed_since = s->time;
    if (s->time - m->landed_since >= WB_DH_LAND_DWELL_SEC)
      m->verdict = WB_DH_ACHIEVED;
  } else {
    /* Any excursion, vertical drift or renewed motion restarts the dwell. */
    m->landed_since = -1.0;
  }
  return m->verdict;
}

#endif

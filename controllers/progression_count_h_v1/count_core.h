#ifndef WEBEEBLOCKS_PROGRESSION_COUNT_H_CORE_H
#define WEBEEBLOCKS_PROGRESSION_COUNT_H_CORE_H

/* Activity 6: bounded behavioral 1/2/3-H counting mission core.
 * The trusted native Webots observer MUST independently attest scene, physical
 * gate identities/colliders, clock, Crazyflie pose, contacts and completion.
 * No pupil AST or variable inspection. Not a Webots / Blockly flight PASS.
 * The simulation mission never authorizes physical Crazyflie flight.
 */
#include <math.h>
#include <stdint.h>
#include <string.h>

#define WB_COUNT_ORACLE "progression-count-h-v1"
#define WB_COUNT_MAX_GATES 3
#define WB_COUNT_HALF_X 0.035
#define WB_COUNT_CRAFT_MARGIN 0.090
#define WB_COUNT_GATE_ENVELOPE (WB_COUNT_HALF_X + WB_COUNT_CRAFT_MARGIN)
#define WB_COUNT_MAX_GATE_Y 0.175
#define WB_COUNT_MAX_GATE_Z 0.530
#define WB_COUNT_CENTER_TOL 0.025
#define WB_COUNT_PAD_X 1.480
#define WB_COUNT_PAD_TOL 0.060
#define WB_COUNT_LAND_Z 0.070
#define WB_COUNT_LAND_MAX_SPEED 0.120
#define WB_COUNT_SETTLE_SEC 1.500
/* A passing landing requires consecutive measured stability, not one frame. */
#define WB_COUNT_LAND_DWELL_SEC 0.250

typedef enum {
  WB_COUNT_WAIT = 0,
  WB_COUNT_ACHIEVED = 1,
  WB_COUNT_NOT_ACHIEVED = 2
} wb_count_verdict;

typedef struct {
  double time, x, y, z, vx, vy, vz;
  /* 0 = independent native contact-free observation; 1 = real contact;
   * unavailable values, including -1, MUST fail closed. */
  int obstacle_contact;
  /* Authenticated mission completion, NEVER derived from the pupil AST. */
  int completed;
} wb_count_sample;

typedef struct {
  unsigned long long attempt;
  unsigned variant; /* Exactly the native-attested scene with 1, 2 or 3 H. */
  unsigned crossed;
  unsigned armed;
  unsigned observed_center;
  int airborne, completion_seen, has_last, stable_since_valid;
  double origin_z, last_time, last_x, completion_at, stable_since;
  wb_count_verdict verdict;
} wb_count_mission;

static inline double wb_count_gate_x(unsigned index) {
  return -0.850 + 0.850 * (double)index;
}

static inline double wb_count_target_y(unsigned variant) {
  return variant == 1 ? 0.0 : (variant == 2 ? 0.550 : -0.550);
}

static inline void wb_count_reset(wb_count_mission *m,
                                  unsigned long long attempt,
                                  unsigned scene_variant,
                                  double origin_z) {
  if (!m) return;
  memset(m, 0, sizeof(*m));
  m->attempt = attempt;
  m->variant = scene_variant;
  m->origin_z = origin_z;
  m->last_time = -1.0;
}

static inline int wb_count_valid_sample(const wb_count_sample *s) {
  return s && isfinite(s->time) && isfinite(s->x) && isfinite(s->y) &&
    isfinite(s->z) && isfinite(s->vx) && isfinite(s->vy) &&
    isfinite(s->vz) && (s->obstacle_contact == 0 ||
                       s->obstacle_contact == 1) &&
    (s->completed == 0 || s->completed == 1);
}

/* Call ONCE PER NATIVE PHYSICS OBSERVATION, not from Blockly or JavaScript.
 * Physical overlap is rejected for every present H even if the learner never
 * tries to cross it. Passages are certified by directed samples on the true
 * scene geometry, with no analysis of the solution's coding strategy.
 */
static inline wb_count_verdict wb_count_sample_mission(
    wb_count_mission *m, const wb_count_sample *s) {
  if (!m || !m->attempt || m->variant < 1 || m->variant > 3 ||
      !isfinite(m->origin_z)) return WB_COUNT_NOT_ACHIEVED;
  if (m->verdict != WB_COUNT_WAIT) return m->verdict;
  if (!wb_count_valid_sample(s) || s->obstacle_contact ||
      s->time <= m->last_time || s->time < 0.0) {
    m->verdict = WB_COUNT_NOT_ACHIEVED;
    return m->verdict;
  }

  /* Prevent a virtual backtrack across a previously confirmed H. A limited
   * wobble after its far face is harmless but cannot count a second crossing. */
  if (m->has_last && m->crossed > 0 &&
      s->x <= wb_count_gate_x(m->crossed - 1) -
                  WB_COUNT_GATE_ENVELOPE - 0.020) {
    m->verdict = WB_COUNT_NOT_ACHIEVED;
    return m->verdict;
  }
  m->last_time = s->time;
  m->last_x = s->x;
  m->has_last = 1;
  if (s->z >= m->origin_z + 0.200) m->airborne = 1;

  for (unsigned i = 0; i < m->variant; ++i) {
    const double x = wb_count_gate_x(i);
    if (fabs(s->x - x) <= WB_COUNT_GATE_ENVELOPE &&
        (fabs(s->y) > WB_COUNT_MAX_GATE_Y ||
         s->z > WB_COUNT_MAX_GATE_Z)) {
      m->verdict = WB_COUNT_NOT_ACHIEVED;
      return m->verdict;
    }
  }

  /* The index is advanced only by observed, ordered, directed passages.
   * A jump over a gate without a measured centre never counts as crossing. */
  if (!m->completion_seen && !s->completed && m->airborne &&
      m->crossed < m->variant) {
    const double gate = wb_count_gate_x(m->crossed);
    if (s->x <= gate - WB_COUNT_GATE_ENVELOPE - 0.010)
      m->armed = 1;
    if (m->armed && fabs(s->x - gate) <= WB_COUNT_CENTER_TOL &&
        fabs(s->y) <= WB_COUNT_MAX_GATE_Y &&
        s->z <= WB_COUNT_MAX_GATE_Z)
      m->observed_center = 1;
    if (s->x >= gate + WB_COUNT_GATE_ENVELOPE + 0.010) {
      if (!m->armed || !m->observed_center) {
        m->verdict = WB_COUNT_NOT_ACHIEVED;
        return m->verdict;
      }
      ++m->crossed;
      m->armed = 0;
      m->observed_center = 0;
    }
  }

  if (s->completed && !m->completion_seen) {
    m->completion_seen = 1;
    m->completion_at = s->time;
    if (!m->airborne || m->crossed != m->variant) {
      m->verdict = WB_COUNT_NOT_ACHIEVED;
      return m->verdict;
    }
  }
  if (!m->completion_seen) return WB_COUNT_WAIT;
  /* Expiration is terminal even when a 0.250-s dwell also completes
   * on this native tick. Never award a success after the 1.500-s limit. */
  if (s->time - m->completion_at >= WB_COUNT_SETTLE_SEC) {
    m->verdict = WB_COUNT_NOT_ACHIEVED;
    return m->verdict;
  }

  const int landed = s->z - m->origin_z <= WB_COUNT_LAND_Z;
  const int still = hypot(s->vx, s->vy) <= WB_COUNT_LAND_MAX_SPEED &&
                    fabs(s->vz) <= WB_COUNT_LAND_MAX_SPEED;
  const int whole_craft_on_pad =
    fabs(s->x - WB_COUNT_PAD_X) <= WB_COUNT_PAD_TOL &&
    fabs(s->y - wb_count_target_y(m->variant)) <= WB_COUNT_PAD_TOL;
  if (landed && still && whole_craft_on_pad) {
    if (!m->stable_since_valid) {
      m->stable_since = s->time;
      m->stable_since_valid = 1;
    }
    if (s->time - m->stable_since >= WB_COUNT_LAND_DWELL_SEC)
      m->verdict = WB_COUNT_ACHIEVED;
  } else {
    /* Any new motion or loss of full-craft pad containment restarts dwell. */
    m->stable_since_valid = 0;
  }
  return m->verdict;
}

#endif /* WEBEEBLOCKS_PROGRESSION_COUNT_H_CORE_H */

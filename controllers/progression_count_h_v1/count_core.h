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
#include <stdio.h>
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
/* Static school Floor is z=0; grounded centre is about z=0.015 m.
 * Reject a motionless hover even if the observer admitted an elevated origin. */
/* R2025a measurements on the same classroom Crazyflie/floor for A4
 * report native grounded centre around z=0.0145-0.0150 m. Admit an
 * additional 5 mm, but not a motionless 3/6-cm hover. The A6 motorized
 * native observer must independently requalify its own landing height. */
#define WB_COUNT_LAND_ABSOLUTE_Z 0.020
#define WB_COUNT_LAND_MAX_SPEED 0.120
#define WB_COUNT_SETTLE_SEC 1.500
/* A passing landing requires consecutive measured stability, not one frame. */
#define WB_COUNT_LAND_DWELL_SEC 0.250
/* This scene runs Webots at 32 ms. Two consecutive samples may be at most
 * 48 ms apart: a missed native frame cannot count toward stable landing. */
#define WB_COUNT_LAND_MAX_SAMPLE_GAP_SEC 0.048

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
  /* -1 invalid, 0 absent, 1 physical Floor contact observed by Supervisor. */
  int floor_contact;
} wb_count_sample;

typedef struct {
  unsigned long long attempt;
  unsigned variant; /* Exactly the native-attested scene with 1, 2 or 3 H. */
  unsigned crossed;
  unsigned armed;
  unsigned observed_center;
  int airborne, completion_seen, has_last, stable_since_valid;
  double origin_z, last_time, last_x, last_y, last_z, completion_at, stable_since;
  wb_count_verdict verdict;
} wb_count_mission;

/* A distinct, opt-in CI-only binary may use the independently attested
 * B holdout positions. The ordinary C oracle's geometry and semantics are
 * byte-for-byte unchanged when the test-only macro is absent. Never enable
 * this mode in a product, pupil or physical-Crazyflie build. */
#ifdef WEBEEBLOCKS_A6_B_PRIVATE_MOTOR_TEST_ONLY
extern double wb_count_b_private_gate_x[WB_COUNT_MAX_GATES];
#endif
static inline double wb_count_gate_x(unsigned index) {
#ifdef WEBEEBLOCKS_A6_B_PRIVATE_MOTOR_TEST_ONLY
  return index < WB_COUNT_MAX_GATES ? wb_count_b_private_gate_x[index] : NAN;
#else
  return -0.850 + 0.850 * (double)index;
#endif
}

static inline double wb_count_target_y(unsigned variant) {
  return variant == 1 ? 0.0 : (variant == 2 ? 0.550 : -0.550);
}

/* Match only the broker's exact reset-scoped mission completion marker:
 * neither pad coordinates nor a client/UI success event constitute COMPLETE. */
static inline int wb_count_exact_completion(const char *data,
                                             unsigned long long attempt) {
  char marker[192];
  if (!data || !attempt) return 0;
  const int n = snprintf(marker, sizeof(marker),
      "WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=%llu oracle=%s",
      attempt, WB_COUNT_ORACLE);
  return n > 0 && (size_t)n < sizeof(marker) && strcmp(data, marker) == 0;
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
    (s->completed == 0 || s->completed == 1) &&
    (s->floor_contact == 0 || s->floor_contact == 1);
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
  /* Check the swept segment against EVERY physical H, not just the
   * centre of an observed sample. This is conservative linear interpolation
   * between native physics frames, not an assumption about the pupil AST. */
  for (unsigned i = 0; i < m->variant; ++i) {
    const double gate = wb_count_gate_x(i);
    double enter = 0.0, leave = 1.0;
    int intersects = fabs(s->x - gate) <= WB_COUNT_GATE_ENVELOPE;
    if (m->has_last) {
      const double dx = s->x - m->last_x;
      if (fabs(dx) > 1e-12) {
        const double t0 = (gate - WB_COUNT_GATE_ENVELOPE - m->last_x) / dx;
        const double t1 = (gate + WB_COUNT_GATE_ENVELOPE - m->last_x) / dx;
        enter = fmax(0.0, fmin(t0, t1));
        leave = fmin(1.0, fmax(t0, t1));
        intersects = enter <= leave;
      }
    }
    if (intersects) {
      const double ya = m->has_last ? m->last_y + enter * (s->y - m->last_y) : s->y;
      const double yb = m->has_last ? m->last_y + leave * (s->y - m->last_y) : s->y;
      const double za = m->has_last ? m->last_z + enter * (s->z - m->last_z) : s->z;
      const double zb = m->has_last ? m->last_z + leave * (s->z - m->last_z) : s->z;
      if (fabs(ya) > WB_COUNT_MAX_GATE_Y || fabs(yb) > WB_COUNT_MAX_GATE_Y ||
          za > WB_COUNT_MAX_GATE_Z || zb > WB_COUNT_MAX_GATE_Z) {
        m->verdict = WB_COUNT_NOT_ACHIEVED;
        return m->verdict;
      }
    }
  }
  /* A missing native step destroys evidence of continuously observed
   * stillness. The next valid stationary tick must start a NEW dwell. */
  if (m->completion_seen && m->stable_since_valid && m->has_last &&
      s->time - m->last_time > WB_COUNT_LAND_MAX_SAMPLE_GAP_SEC)
    m->stable_since_valid = 0;
  m->last_time = s->time;
  m->last_x = s->x;
  m->last_y = s->y;
  m->last_z = s->z;
  m->has_last = 1;
  if (s->z >= m->origin_z + 0.200) m->airborne = 1;

  /* The index is advanced only by observed, ordered, directed passages.
   * A jump over a gate without a measured centre never counts as crossing. */
  if (!m->completion_seen && !s->completed && m->airborne &&
      m->crossed < m->variant) {
    const double gate = wb_count_gate_x(m->crossed);
    /* A centred measurement is not a durable pass token after retreating
     * upstream. Permit a new correctly observed pass after correction. */
    if (m->observed_center &&
        s->x <= gate - WB_COUNT_GATE_ENVELOPE - 0.010)
      m->observed_center = 0;
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

  /* Height is only proximity, not evidence of a physical landing. */
  const int landed = s->z - m->origin_z <= WB_COUNT_LAND_Z &&
                     s->z <= WB_COUNT_LAND_ABSOLUTE_Z &&
                     s->floor_contact == 1;
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

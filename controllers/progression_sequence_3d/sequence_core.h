#ifndef WEBEEBLOCKS_SEQUENCE_3D_CORE_H
#define WEBEEBLOCKS_SEQUENCE_3D_CORE_H

/* Activity 1. Pure C scene-local oracle: no Webots API, AST or flight control.
 * Exact attempt isolation, fail-closed observations and terminal outcome.
 * All dimensions are meters, velocities meters per second.
 */
#include <math.h>
#include <string.h>

#define WB_SEQ_ORACLE "progression-sequence-3d-v1"
#define WB_SEQ_CHILDREN 18
#define WB_SEQ_X 0.35
#define WB_SEQ_Y 0.28
/* Full craft on 0.28 x 0.34 pad with conservative 0.09 half-span:
 * maximum center offsets = 0.14-0.09 and 0.17-0.09.
 */
#define WB_SEQ_X_TOL 0.05
#define WB_SEQ_Y_TOL 0.08
#define WB_SEQ_AIRBORNE 0.20
#define WB_SEQ_LAND_HEIGHT 0.07
#define WB_SEQ_MAX_SPEED 0.12
#define WB_SEQ_SETTLE 1.5

typedef enum {
  WB_SEQ_WAIT = 0,
  WB_SEQ_ACHIEVED = 1,
  WB_SEQ_NOT_ACHIEVED = 2
} wb_seq_verdict;

typedef struct {
  double time, x, y, z, vx, vy, vz;
  int completed;
} wb_seq_sample;

typedef struct {
  unsigned long long attempt;
  double origin_z;
  double completion_at;
  int airborne;
  int completion_seen;
  wb_seq_verdict result;
} wb_seq_mission;

static inline void wb_seq_reset(wb_seq_mission *m,
                                unsigned long long attempt, double origin_z) {
  if (!m) return;
  memset(m, 0, sizeof(*m));
  m->attempt = attempt;
  m->origin_z = origin_z;
}

static inline int wb_seq_sample_valid(const wb_seq_sample *s) {
  return s && isfinite(s->time) && isfinite(s->x) && isfinite(s->y) &&
    isfinite(s->z) && isfinite(s->vx) && isfinite(s->vy) && isfinite(s->vz);
}

static inline wb_seq_verdict wb_seq_sample_mission(wb_seq_mission *m,
                                                   const wb_seq_sample *s) {
  if (!m || !m->attempt || !isfinite(m->origin_z)) return WB_SEQ_NOT_ACHIEVED;
  if (m->result != WB_SEQ_WAIT) return m->result;
  if (!wb_seq_sample_valid(s)) {
    /* Before completion a missed observation does not grant success.
     * Once completion was seen, an unknown physical state is terminal negative.
     */
    if ((s && s->completed) || m->completion_seen)
      m->result = WB_SEQ_NOT_ACHIEVED;
    return m->result;
  }
  if (s->z >= m->origin_z + WB_SEQ_AIRBORNE)
    m->airborne = 1;
  if (s->completed && !m->completion_seen) {
    m->completion_seen = 1;
    m->completion_at = s->time;
  }
  if (!m->completion_seen) return WB_SEQ_WAIT;
  const int landed = s->z <= m->origin_z + WB_SEQ_LAND_HEIGHT;
  const int stationary = hypot(s->vx, s->vy) <= WB_SEQ_MAX_SPEED &&
                         fabs(s->vz) <= WB_SEQ_MAX_SPEED;
  const int on_pad = fabs(s->x - WB_SEQ_X) <= WB_SEQ_X_TOL &&
                     fabs(s->y - WB_SEQ_Y) <= WB_SEQ_Y_TOL;
  if (m->airborne && landed && stationary && on_pad)
    m->result = WB_SEQ_ACHIEVED;
  else if (s->time - m->completion_at >= WB_SEQ_SETTLE)
    m->result = WB_SEQ_NOT_ACHIEVED;
  return m->result;
}

#endif

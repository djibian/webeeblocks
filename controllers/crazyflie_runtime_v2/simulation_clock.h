#ifndef WEBEEBLOCKS_SIMULATION_CLOCK_H
#define WEBEEBLOCKS_SIMULATION_CLOCK_H
#include <math.h>

/* Program observation only. The mission evaluator owns its separate clock.
 * Call with Webots getTime(), never wall time. Each admitted takeoff starts a
 * new observation lifetime; reset, stop, failure and completed land revoke it. */
typedef struct { double start, last; int active; } simulation_clock_t;
static inline void simulation_clock_revoke(simulation_clock_t *clock) { clock->active = 0; }
static inline void simulation_clock_begin(simulation_clock_t *clock, double now) {
  clock->active = isfinite(now) && now >= 0.0;
  clock->start = clock->last = now;
}
static inline int simulation_clock_read(simulation_clock_t *clock, double now, double *seconds) {
  if (!clock->active || !isfinite(now) || now < clock->last || !isfinite(now - clock->start)) {
    simulation_clock_revoke(clock);
    return 0;
  }
  clock->last = now;
  *seconds = now - clock->start;
  return 1;
}
#endif

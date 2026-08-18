#ifndef WEBEEBLOCKS_EXECUTOR_H
#define WEBEEBLOCKS_EXECUTOR_H

#include <math.h>
#include <stddef.h>

#define WEBEEBLOCKS_STOP_SPEED_XY_MAX 0.12
#define WEBEEBLOCKS_STOP_YAW_RATE_MAX 0.10
#define WEBEEBLOCKS_STOP_VZ_MAX 0.15
#define WEBEEBLOCKS_STOP_ALTITUDE_ERROR_MAX 0.05
#define WEBEEBLOCKS_STOP_WINDOW_S 0.5

typedef enum {
  WEBEEBLOCKS_COMMAND_TAKEOFF,
  WEBEEBLOCKS_COMMAND_FORWARD,
  WEBEEBLOCKS_COMMAND_TURN,
  WEBEEBLOCKS_COMMAND_LAND
} webeeblocks_command_type_t;

typedef struct {
  webeeblocks_command_type_t type;
  double value;
} webeeblocks_command_t;

typedef struct {
  const webeeblocks_command_t *commands;
  size_t count;
  size_t index;
  double stop_stable_since;
} webeeblocks_runner_t;

static inline void webeeblocks_runner_init(webeeblocks_runner_t *runner,
                                            const webeeblocks_command_t *commands,
                                            size_t count) {
  runner->commands = commands;
  runner->count = count;
  runner->index = 0;
  runner->stop_stable_since = -1.0;
}

static inline const webeeblocks_command_t *webeeblocks_runner_current(const webeeblocks_runner_t *runner) {
  if (!runner || runner->index >= runner->count)
    return NULL;
  return &runner->commands[runner->index];
}

static inline int webeeblocks_runner_finished(const webeeblocks_runner_t *runner) {
  return !runner || runner->index >= runner->count;
}

static inline int webeeblocks_runner_completion_stop(webeeblocks_runner_t *runner,
                                                       int geometric_ready,
                                                       double speed_xy,
                                                       double yaw_rate,
                                                       double vz,
                                                       double altitude_error,
                                                       double now) {
  if (!runner)
    return 0;

  const int stop_ready = geometric_ready &&
                         speed_xy < WEBEEBLOCKS_STOP_SPEED_XY_MAX &&
                         fabs(yaw_rate) < WEBEEBLOCKS_STOP_YAW_RATE_MAX &&
                         fabs(vz) < WEBEEBLOCKS_STOP_VZ_MAX &&
                         fabs(altitude_error) < WEBEEBLOCKS_STOP_ALTITUDE_ERROR_MAX;

  if (!stop_ready) {
    runner->stop_stable_since = -1.0;
    return 0;
  }

  if (runner->stop_stable_since < 0.0) {
    runner->stop_stable_since = now;
    return 0;
  }

  return now - runner->stop_stable_since >= WEBEEBLOCKS_STOP_WINDOW_S;
}

static inline int webeeblocks_runner_advance(webeeblocks_runner_t *runner) {
  if (!runner || runner->index >= runner->count)
    return 0;
  ++runner->index;
  runner->stop_stable_since = -1.0;
  return runner->index < runner->count;
}

static inline const char *webeeblocks_command_name(webeeblocks_command_type_t type) {
  switch (type) {
    case WEBEEBLOCKS_COMMAND_TAKEOFF: return "TAKEOFF";
    case WEBEEBLOCKS_COMMAND_FORWARD: return "FORWARD";
    case WEBEEBLOCKS_COMMAND_TURN: return "TURN";
    case WEBEEBLOCKS_COMMAND_LAND: return "LAND";
  }
  return "UNKNOWN";
}

#endif

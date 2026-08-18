#ifndef WEBEEBLOCKS_EXECUTOR_H
#define WEBEEBLOCKS_EXECUTOR_H

#include <stddef.h>

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
} webeeblocks_runner_t;

static inline void webeeblocks_runner_init(webeeblocks_runner_t *runner,
                                            const webeeblocks_command_t *commands,
                                            size_t count) {
  runner->commands = commands;
  runner->count = count;
  runner->index = 0;
}

static inline const webeeblocks_command_t *webeeblocks_runner_current(const webeeblocks_runner_t *runner) {
  if (!runner || runner->index >= runner->count)
    return NULL;
  return &runner->commands[runner->index];
}

static inline int webeeblocks_runner_finished(const webeeblocks_runner_t *runner) {
  return !runner || runner->index >= runner->count;
}

static inline int webeeblocks_runner_completion_stop(int stabilized) {
  return stabilized;
}

static inline int webeeblocks_runner_advance(webeeblocks_runner_t *runner) {
  if (!runner || runner->index >= runner->count)
    return 0;
  ++runner->index;
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

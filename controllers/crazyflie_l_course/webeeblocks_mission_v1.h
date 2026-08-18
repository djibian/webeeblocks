#ifndef WEBEEBLOCKS_MISSION_V1_H
#define WEBEEBLOCKS_MISSION_V1_H

#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "webeeblocks_executor.h"

#define WEBEEBLOCKS_MISSION_V1_HEADER "WEBEEBLOCKS_MISSION_V1"
#define WEBEEBLOCKS_MISSION_V1_MAX_COMMANDS 5
#define WEBEEBLOCKS_MISSION_V1_MAX_MESSAGE 1024
#define WEBEEBLOCKS_MISSION_V1_VALUE_TOLERANCE 1e-6

typedef enum {
  WEBEEBLOCKS_MISSION_V1_OK = 0,
  WEBEEBLOCKS_MISSION_V1_ERR_VERSION,
  WEBEEBLOCKS_MISSION_V1_ERR_COMMAND,
  WEBEEBLOCKS_MISSION_V1_ERR_PARAMETER,
  WEBEEBLOCKS_MISSION_V1_ERR_SEQUENCE,
  WEBEEBLOCKS_MISSION_V1_ERR_TOO_LONG
} webeeblocks_mission_v1_status_t;

static const char *webeeblocks_mission_v1_status_name(webeeblocks_mission_v1_status_t status) {
  switch (status) {
    case WEBEEBLOCKS_MISSION_V1_OK: return "OK";
    case WEBEEBLOCKS_MISSION_V1_ERR_VERSION: return "VERSION";
    case WEBEEBLOCKS_MISSION_V1_ERR_COMMAND: return "COMMAND";
    case WEBEEBLOCKS_MISSION_V1_ERR_PARAMETER: return "PARAMETER";
    case WEBEEBLOCKS_MISSION_V1_ERR_SEQUENCE: return "SEQUENCE";
    case WEBEEBLOCKS_MISSION_V1_ERR_TOO_LONG: return "TOO_LONG";
  }
  return "UNKNOWN";
}

static int webeeblocks_mission_v1_parse_number(const char *text, double *value) {
  char *end = NULL;
  errno = 0;
  const double parsed = strtod(text, &end);
  if (errno || end == text || *end != '\0' || !isfinite(parsed))
    return 0;
  *value = parsed;
  return 1;
}

static int webeeblocks_mission_v1_matches(double actual, double expected) {
  return fabs(actual - expected) <= WEBEEBLOCKS_MISSION_V1_VALUE_TOLERANCE;
}

static webeeblocks_mission_v1_status_t webeeblocks_mission_v1_parse(
    const char *message,
    webeeblocks_command_t *commands,
    size_t *count) {
  if (!message || !commands || !count)
    return WEBEEBLOCKS_MISSION_V1_ERR_SEQUENCE;
  if (strlen(message) >= WEBEEBLOCKS_MISSION_V1_MAX_MESSAGE)
    return WEBEEBLOCKS_MISSION_V1_ERR_TOO_LONG;

  char buffer[WEBEEBLOCKS_MISSION_V1_MAX_MESSAGE];
  strcpy(buffer, message);
  char *save = NULL;
  char *line = strtok_r(buffer, "\n", &save);
  if (!line || strcmp(line, WEBEEBLOCKS_MISSION_V1_HEADER) != 0)
    return WEBEEBLOCKS_MISSION_V1_ERR_VERSION;

  size_t n = 0;
  while ((line = strtok_r(NULL, "\n", &save))) {
    if (*line == '\0')
      continue;
    if (n >= WEBEEBLOCKS_MISSION_V1_MAX_COMMANDS)
      return WEBEEBLOCKS_MISSION_V1_ERR_TOO_LONG;

    char command[32], value_text[64], extra[2];
    if (sscanf(line, "%31s %63s %1s", command, value_text, extra) != 2)
      return WEBEEBLOCKS_MISSION_V1_ERR_COMMAND;

    double value = 0.0;
    if (!webeeblocks_mission_v1_parse_number(value_text, &value))
      return WEBEEBLOCKS_MISSION_V1_ERR_PARAMETER;

    if (strcmp(command, "TAKEOFF") == 0) {
      if (!webeeblocks_mission_v1_matches(value, 1.0))
        return WEBEEBLOCKS_MISSION_V1_ERR_PARAMETER;
      commands[n++] = (webeeblocks_command_t){WEBEEBLOCKS_COMMAND_TAKEOFF, value};
    } else if (strcmp(command, "FORWARD") == 0) {
      // Transport v1 deliberately accepts only the already-proven one-metre L.
      // General student distances come after this runtime seam is closed.
      if (!webeeblocks_mission_v1_matches(value, 1.0))
        return WEBEEBLOCKS_MISSION_V1_ERR_PARAMETER;
      commands[n++] = (webeeblocks_command_t){WEBEEBLOCKS_COMMAND_FORWARD, value};
    } else if (strcmp(command, "TURN") == 0) {
      if (!webeeblocks_mission_v1_matches(value, M_PI / 2.0))
        return WEBEEBLOCKS_MISSION_V1_ERR_PARAMETER;
      commands[n++] = (webeeblocks_command_t){WEBEEBLOCKS_COMMAND_TURN, value};
    } else if (strcmp(command, "LAND") == 0) {
      if (!webeeblocks_mission_v1_matches(value, 0.0))
        return WEBEEBLOCKS_MISSION_V1_ERR_PARAMETER;
      commands[n++] = (webeeblocks_command_t){WEBEEBLOCKS_COMMAND_LAND, value};
    } else {
      return WEBEEBLOCKS_MISSION_V1_ERR_COMMAND;
    }
  }

  // Runtime v1 deliberately proves exactly the L-shaped pedagogical sequence
  // already characterized in #31-#34. Parameter generalization is a later lot.
  if (n != 5 ||
      commands[0].type != WEBEEBLOCKS_COMMAND_TAKEOFF ||
      commands[1].type != WEBEEBLOCKS_COMMAND_FORWARD ||
      commands[2].type != WEBEEBLOCKS_COMMAND_TURN ||
      commands[3].type != WEBEEBLOCKS_COMMAND_FORWARD ||
      commands[4].type != WEBEEBLOCKS_COMMAND_LAND)
    return WEBEEBLOCKS_MISSION_V1_ERR_SEQUENCE;

  *count = n;
  return WEBEEBLOCKS_MISSION_V1_OK;
}

#endif

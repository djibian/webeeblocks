#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <webots/robot.h>
#include <webots/supervisor.h>

#define ATTEMPT_PREFIX "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 "
#define OUTCOME_PREFIX "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1"
#define ORACLE "sequence-landing-zone-v1"
#define TARGET_X_MIN 0.18
#define TARGET_X_MAX 0.32
#define TARGET_Y_ABS_MAX 0.10
#define LANDED_Z_MAX 0.12

static int parse_attempt(const char *value, unsigned long long *attempt) {
  if (!value || !attempt)
    return 0;
  const size_t prefix_length = strlen(ATTEMPT_PREFIX);
  if (strncmp(value, ATTEMPT_PREFIX, prefix_length) != 0)
    return 0;

  errno = 0;
  char *end = NULL;
  const unsigned long long parsed = strtoull(value + prefix_length, &end, 10);
  if (errno != 0 || parsed < 1 || !end || *end != '\0')
    return 0;
  *attempt = parsed;
  return 1;
}

static const char *mission_status(WbNodeRef crazyflie) {
  const double *position = wb_supervisor_node_get_position(crazyflie);
  if (!position)
    return "not-achieved";
  const int in_target = position[0] >= TARGET_X_MIN && position[0] <= TARGET_X_MAX &&
                        fabs(position[1]) <= TARGET_Y_ABS_MAX;
  const int landed = position[2] <= LANDED_Z_MAX;
  return in_target && landed ? "achieved" : "not-achieved";
}

int main(void) {
  wb_robot_init();
  const int step = (int)wb_robot_get_basic_time_step();
  WbNodeRef crazyflie = wb_supervisor_node_get_from_def("WEBEEBLOCKS_CRAZYFLIE");
  if (!crazyflie) {
    fprintf(stderr, "WEBEEBLOCKS_SEQUENCE_EVALUATOR_ERROR missing WEBEEBLOCKS_CRAZYFLIE DEF\n");
    wb_robot_cleanup();
    return 2;
  }
  WbFieldRef custom_data = wb_supervisor_node_get_field(crazyflie, "customData");
  if (!custom_data) {
    fprintf(stderr, "WEBEEBLOCKS_SEQUENCE_EVALUATOR_ERROR missing Crazyflie customData field\n");
    wb_robot_cleanup();
    return 2;
  }

  unsigned long long current_attempt = 0;
  char published[192] = {0};
  printf("WEBEEBLOCKS_SEQUENCE_EVALUATOR_READY oracle=%s\n", ORACLE);
  fflush(stdout);

  while (wb_robot_step(step) != -1) {
    const char *data = wb_supervisor_field_get_sf_string(custom_data);
    unsigned long long observed_attempt = 0;
    if (parse_attempt(data, &observed_attempt) && observed_attempt != current_attempt) {
      current_attempt = observed_attempt;
      published[0] = '\0';
      printf("WEBEEBLOCKS_SEQUENCE_EVALUATOR_ATTEMPT attempt=%llu\n", current_attempt);
      fflush(stdout);
    }
    if (current_attempt < 1)
      continue;

    const char *status = mission_status(crazyflie);
    char outcome[192];
    const int written = snprintf(outcome, sizeof(outcome),
                                 "%s attempt=%llu oracle=%s status=%s",
                                 OUTCOME_PREFIX, current_attempt, ORACLE, status);
    if (written < 0 || (size_t)written >= sizeof(outcome)) {
      fprintf(stderr, "WEBEEBLOCKS_SEQUENCE_EVALUATOR_ERROR outcome overflow\n");
      wb_robot_cleanup();
      return 2;
    }
    if (strcmp(outcome, published) == 0)
      continue;

    wb_supervisor_field_set_sf_string(custom_data, outcome);
    strcpy(published, outcome);
    const double *position = wb_supervisor_node_get_position(crazyflie);
    printf("WEBEEBLOCKS_SEQUENCE_EVALUATOR_OUTCOME attempt=%llu status=%s x=%.4f y=%.4f z=%.4f\n",
           current_attempt, status,
           position ? position[0] : NAN,
           position ? position[1] : NAN,
           position ? position[2] : NAN);
    fflush(stdout);
  }

  wb_robot_cleanup();
  return 0;
}

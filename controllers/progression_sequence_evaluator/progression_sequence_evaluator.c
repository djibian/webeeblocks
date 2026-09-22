#include <math.h>
#include <stdio.h>
#include <string.h>
#include <webots/robot.h>
#include <webots/supervisor.h>

#define ATTEMPT_PREFIX "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 "
#define ORACLE "progression-sequence-v1"
#define AIRBORNE_DELTA 0.20
#define LANDED_DELTA 0.07
#define MAX_LANDING_SPEED 0.12
#define TARGET_X 0.25
#define TARGET_X_TOLERANCE 0.09
#define TARGET_Y_TOLERANCE 0.12

static int parse_attempt(const char *data, unsigned long long *attempt) {
  if (!data || !attempt)
    return 0;
  char trailing[2] = {0};
  return sscanf(data, "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu %1s", attempt, trailing) == 1;
}

static void publish_outcome(WbFieldRef custom_data, unsigned long long attempt, const char *status) {
  char result[192];
  snprintf(result, sizeof(result),
           "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=%s",
           attempt, ORACLE, status);
  wb_supervisor_field_set_sf_string(custom_data, result);
  printf("WEBEEBLOCKS_SEQUENCE_RESULT attempt=%llu status=%s\n", attempt, status);
  fflush(stdout);
}

int main(void) {
  wb_robot_init();
  const int step = (int)wb_robot_get_basic_time_step();
  WbNodeRef crazyflie = wb_supervisor_node_get_from_def("CRAZYFLIE");
  if (!crazyflie) {
    fprintf(stderr, "WEBEEBLOCKS_SEQUENCE_EVALUATOR_ERROR missing DEF CRAZYFLIE\n");
    wb_robot_cleanup();
    return 2;
  }
  WbFieldRef custom_data = wb_supervisor_node_get_field(crazyflie, "customData");
  if (!custom_data) {
    fprintf(stderr, "WEBEEBLOCKS_SEQUENCE_EVALUATOR_ERROR missing Crazyflie customData\n");
    wb_robot_cleanup();
    return 2;
  }

  const double *initial = wb_supervisor_node_get_position(crazyflie);
  if (!initial) {
    fprintf(stderr, "WEBEEBLOCKS_SEQUENCE_EVALUATOR_ERROR missing Crazyflie position\n");
    wb_robot_cleanup();
    return 2;
  }
  const double origin_z = initial[2];
  unsigned long long active_attempt = 0;
  int has_attempt = 0;
  int airborne_seen = 0;
  int reported = 0;

  printf("WEBEEBLOCKS_SEQUENCE_EVALUATOR_READY target_x=%.3f target_y=0.000\n", TARGET_X);
  fflush(stdout);

  while (wb_robot_step(step) != -1) {
    const char *data = wb_supervisor_field_get_sf_string(custom_data);
    unsigned long long observed_attempt = 0;
    if (parse_attempt(data, &observed_attempt)) {
      if (!has_attempt || observed_attempt != active_attempt) {
        active_attempt = observed_attempt;
        has_attempt = 1;
        airborne_seen = 0;
        reported = 0;
        printf("WEBEEBLOCKS_SEQUENCE_ATTEMPT attempt=%llu\n", active_attempt);
        fflush(stdout);
      }
    }
    if (!has_attempt || reported)
      continue;

    const double *position = wb_supervisor_node_get_position(crazyflie);
    const double *velocity = wb_supervisor_node_get_velocity(crazyflie);
    if (!position || !velocity)
      continue;
    const double horizontal_speed = hypot(velocity[0], velocity[1]);
    const double vertical_speed = fabs(velocity[2]);

    if (position[2] >= origin_z + AIRBORNE_DELTA)
      airborne_seen = 1;
    if (!airborne_seen)
      continue;

    if (position[2] > origin_z + LANDED_DELTA ||
        horizontal_speed > MAX_LANDING_SPEED || vertical_speed > MAX_LANDING_SPEED)
      continue;

    const int in_target = fabs(position[0] - TARGET_X) <= TARGET_X_TOLERANCE &&
                          fabs(position[1]) <= TARGET_Y_TOLERANCE;
    publish_outcome(custom_data, active_attempt, in_target ? "achieved" : "not-achieved");
    reported = 1;
  }

  wb_robot_cleanup();
  return 0;
}

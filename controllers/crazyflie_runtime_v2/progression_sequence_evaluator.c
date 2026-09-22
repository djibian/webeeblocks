#include <math.h>
#include <stdio.h>
#include <string.h>
#include <webots/robot.h>
#include <webots/supervisor.h>

#define SEQUENCE_ORACLE "progression-sequence-v1"
#define SEQUENCE_AIRBORNE_DELTA 0.20
#define SEQUENCE_LANDED_DELTA 0.07
#define SEQUENCE_MAX_LANDING_SPEED 0.12
#define SEQUENCE_SETTLE_TIMEOUT 1.5
#define SEQUENCE_TARGET_X 0.25
#define SEQUENCE_TARGET_X_TOLERANCE 0.09
#define SEQUENCE_TARGET_Y_TOLERANCE 0.12

static int sequence_parse_attempt(const char *data, unsigned long long *attempt) {
  if (!data || !attempt)
    return 0;
  char trailing[2] = {0};
  return sscanf(data, "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu %1s", attempt, trailing) == 1;
}

static int sequence_parse_completion(const char *data, unsigned long long *attempt) {
  if (!data || !attempt)
    return 0;
  char oracle[64] = {0};
  char trailing[2] = {0};
  if (sscanf(data,
             "WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=%llu oracle=%63s %1s",
             attempt, oracle, trailing) != 2)
    return 0;
  return strcmp(oracle, SEQUENCE_ORACLE) == 0;
}

static WbNodeRef sequence_find_named_node(WbNodeRef node, const char *target_name) {
  if (!node)
    return NULL;
  WbFieldRef name = wb_supervisor_node_get_field(node, "name");
  if (name) {
    const char *value = wb_supervisor_field_get_sf_string(name);
    if (value && strcmp(value, target_name) == 0)
      return node;
  }
  WbFieldRef children = wb_supervisor_node_get_field(node, "children");
  if (!children)
    return NULL;
  const int count = wb_supervisor_field_get_count(children);
  for (int index = 0; index < count; ++index) {
    WbNodeRef child = wb_supervisor_field_get_mf_node(children, index);
    WbNodeRef match = sequence_find_named_node(child, target_name);
    if (match)
      return match;
  }
  return NULL;
}

static void sequence_publish_outcome(WbFieldRef custom_data, unsigned long long attempt, const char *status) {
  char result[192];
  snprintf(result, sizeof(result),
           "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=%s",
           attempt, SEQUENCE_ORACLE, status);
  wb_supervisor_field_set_sf_string(custom_data, result);
  printf("WEBEEBLOCKS_SEQUENCE_RESULT attempt=%llu status=%s\n", attempt, status);
  fflush(stdout);
}

int webeeblocks_progression_sequence_evaluator_main(void) {
  wb_robot_init();
  const int step = (int)wb_robot_get_basic_time_step();
  WbNodeRef crazyflie = sequence_find_named_node(wb_supervisor_node_get_root(), "Crazyflie WebeeBlocks");
  if (!crazyflie) {
    fprintf(stderr, "WEBEEBLOCKS_SEQUENCE_EVALUATOR_ERROR missing Crazyflie WebeeBlocks node\n");
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
  int completion_seen = 0;
  double completion_time = 0.0;
  int reported = 0;

  printf("WEBEEBLOCKS_SEQUENCE_EVALUATOR_READY target_x=%.3f target_y=0.000\n", SEQUENCE_TARGET_X);
  fflush(stdout);

  while (wb_robot_step(step) != -1) {
    const char *data = wb_supervisor_field_get_sf_string(custom_data);
    unsigned long long observed_attempt = 0;
    if (sequence_parse_attempt(data, &observed_attempt)) {
      if (!has_attempt || observed_attempt != active_attempt) {
        active_attempt = observed_attempt;
        has_attempt = 1;
        airborne_seen = 0;
        completion_seen = 0;
        completion_time = 0.0;
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

    if (position[2] >= origin_z + SEQUENCE_AIRBORNE_DELTA)
      airborne_seen = 1;

    if (!completion_seen) {
      unsigned long long completed_attempt = 0;
      if (!sequence_parse_completion(data, &completed_attempt) || completed_attempt != active_attempt)
        continue;
      completion_seen = 1;
      completion_time = wb_robot_get_time();
      printf("WEBEEBLOCKS_SEQUENCE_COMPLETION attempt=%llu settle_timeout=%.3f\n",
             active_attempt, SEQUENCE_SETTLE_TIMEOUT);
      fflush(stdout);
    }

    const double horizontal_speed = hypot(velocity[0], velocity[1]);
    const double vertical_speed = fabs(velocity[2]);
    const int landed = position[2] <= origin_z + SEQUENCE_LANDED_DELTA;
    const int stationary = horizontal_speed <= SEQUENCE_MAX_LANDING_SPEED &&
                           vertical_speed <= SEQUENCE_MAX_LANDING_SPEED;
    const int in_target = fabs(position[0] - SEQUENCE_TARGET_X) <= SEQUENCE_TARGET_X_TOLERANCE &&
                          fabs(position[1]) <= SEQUENCE_TARGET_Y_TOLERANCE;
    const int achieved = airborne_seen && landed && stationary && in_target;
    if (achieved) {
      sequence_publish_outcome(custom_data, active_attempt, "achieved");
      reported = 1;
      continue;
    }

    if (wb_robot_get_time() - completion_time >= SEQUENCE_SETTLE_TIMEOUT) {
      sequence_publish_outcome(custom_data, active_attempt, "not-achieved");
      reported = 1;
    }
  }

  wb_robot_cleanup();
  return 0;
}

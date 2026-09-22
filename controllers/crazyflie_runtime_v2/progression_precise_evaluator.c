#include <math.h>
#include <stdio.h>
#include <string.h>
#include <webots/contact_point.h>
#include <webots/robot.h>
#include <webots/supervisor.h>

#define PRECISE_ORACLE "progression-precise-movement-v1"
#define PRECISE_AIRBORNE_DELTA 0.20
#define PRECISE_LANDED_DELTA 0.07
#define PRECISE_MAX_LANDING_SPEED 0.12
#define PRECISE_SETTLE_TIMEOUT 1.5
#define PRECISE_TARGET_X 0.30
#define PRECISE_TARGET_Y 0.20
#define PRECISE_TARGET_X_TOLERANCE 0.10
#define PRECISE_TARGET_Y_TOLERANCE 0.10
#define FIRST_OBSTACLE_X 0.45
#define FIRST_OBSTACLE_X_HALF 0.03
#define FIRST_OBSTACLE_Y_HALF 0.06
#define FIRST_OBSTACLE_Z_MIN 0.0
#define FIRST_OBSTACLE_Z_MAX 1.10
#define CONTACT_TOLERANCE 0.004

static int precise_parse_attempt(const char *data, unsigned long long *attempt) {
  if (!data || !attempt)
    return 0;
  char trailing[2] = {0};
  return sscanf(data, "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu %1s", attempt, trailing) == 1;
}

static int precise_parse_completion(const char *data, unsigned long long *attempt) {
  if (!data || !attempt)
    return 0;
  char oracle[64] = {0};
  char trailing[2] = {0};
  if (sscanf(data,
             "WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=%llu oracle=%63s %1s",
             attempt, oracle, trailing) != 2)
    return 0;
  return strcmp(oracle, PRECISE_ORACLE) == 0;
}

static WbNodeRef precise_find_named_node(WbNodeRef node, const char *target_name) {
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
    WbNodeRef match = precise_find_named_node(wb_supervisor_field_get_mf_node(children, index), target_name);
    if (match)
      return match;
  }
  return NULL;
}

static int precise_contact_is_first_obstacle(const double point[3]) {
  return fabs(point[0] - FIRST_OBSTACLE_X) <= FIRST_OBSTACLE_X_HALF + CONTACT_TOLERANCE &&
         fabs(point[1]) <= FIRST_OBSTACLE_Y_HALF + CONTACT_TOLERANCE &&
         point[2] >= FIRST_OBSTACLE_Z_MIN - CONTACT_TOLERANCE &&
         point[2] <= FIRST_OBSTACLE_Z_MAX + CONTACT_TOLERANCE;
}

static void precise_publish_outcome(WbFieldRef custom_data, unsigned long long attempt, const char *status) {
  char result[192];
  snprintf(result, sizeof(result),
           "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=%s",
           attempt, PRECISE_ORACLE, status);
  wb_supervisor_field_set_sf_string(custom_data, result);
  printf("WEBEEBLOCKS_PRECISE_RESULT attempt=%llu status=%s\n", attempt, status);
  fflush(stdout);
}

int webeeblocks_progression_precise_evaluator_main(void) {
  wb_robot_init();
  const int step = (int)wb_robot_get_basic_time_step();
  WbNodeRef crazyflie = precise_find_named_node(wb_supervisor_node_get_root(), "Crazyflie WebeeBlocks");
  if (!crazyflie) {
    fprintf(stderr, "WEBEEBLOCKS_PRECISE_EVALUATOR_ERROR missing Crazyflie WebeeBlocks node\n");
    wb_robot_cleanup();
    return 2;
  }
  WbFieldRef custom_data = wb_supervisor_node_get_field(crazyflie, "customData");
  if (!custom_data) {
    fprintf(stderr, "WEBEEBLOCKS_PRECISE_EVALUATOR_ERROR missing Crazyflie customData\n");
    wb_robot_cleanup();
    return 2;
  }
  const double *initial = wb_supervisor_node_get_position(crazyflie);
  if (!initial) {
    fprintf(stderr, "WEBEEBLOCKS_PRECISE_EVALUATOR_ERROR missing Crazyflie position\n");
    wb_robot_cleanup();
    return 2;
  }
  const double origin_z = initial[2];
  wb_supervisor_node_enable_contact_points_tracking(crazyflie, step, true);

  unsigned long long active_attempt = 0;
  int has_attempt = 0;
  int airborne_seen = 0;
  int collision_seen = 0;
  int completion_seen = 0;
  double completion_time = 0.0;
  int reported = 0;

  printf("WEBEEBLOCKS_PRECISE_EVALUATOR_READY target_x=%.3f target_y=%.3f\n",
         PRECISE_TARGET_X, PRECISE_TARGET_Y);
  fflush(stdout);

  while (wb_robot_step(step) != -1) {
    const char *data = wb_supervisor_field_get_sf_string(custom_data);
    unsigned long long observed_attempt = 0;
    if (precise_parse_attempt(data, &observed_attempt) && (!has_attempt || observed_attempt != active_attempt)) {
      active_attempt = observed_attempt;
      has_attempt = 1;
      airborne_seen = 0;
      collision_seen = 0;
      completion_seen = 0;
      completion_time = 0.0;
      reported = 0;
      printf("WEBEEBLOCKS_PRECISE_ATTEMPT attempt=%llu\n", active_attempt);
      fflush(stdout);
    }
    if (!has_attempt || reported)
      continue;

    const double *position = wb_supervisor_node_get_position(crazyflie);
    const double *velocity = wb_supervisor_node_get_velocity(crazyflie);
    if (!position || !velocity)
      continue;
    if (position[2] >= origin_z + PRECISE_AIRBORNE_DELTA)
      airborne_seen = 1;

    int contact_count = 0;
    WbContactPoint *contacts = wb_supervisor_node_get_contact_points(crazyflie, true, &contact_count);
    for (int index = 0; index < contact_count; ++index) {
      if (precise_contact_is_first_obstacle(contacts[index].point)) {
        if (!collision_seen) {
          printf("WEBEEBLOCKS_PRECISE_COLLISION attempt=%llu x=%.6f y=%.6f z=%.6f\n",
                 active_attempt, contacts[index].point[0], contacts[index].point[1], contacts[index].point[2]);
          fflush(stdout);
        }
        collision_seen = 1;
        break;
      }
    }

    if (!completion_seen) {
      unsigned long long completed_attempt = 0;
      if (!precise_parse_completion(data, &completed_attempt) || completed_attempt != active_attempt)
        continue;
      completion_seen = 1;
      completion_time = wb_robot_get_time();
    }

    const double horizontal_speed = hypot(velocity[0], velocity[1]);
    const double vertical_speed = fabs(velocity[2]);
    const int landed = position[2] <= origin_z + PRECISE_LANDED_DELTA;
    const int stationary = horizontal_speed <= PRECISE_MAX_LANDING_SPEED &&
                           vertical_speed <= PRECISE_MAX_LANDING_SPEED;
    const int in_target = fabs(position[0] - PRECISE_TARGET_X) <= PRECISE_TARGET_X_TOLERANCE &&
                          fabs(position[1] - PRECISE_TARGET_Y) <= PRECISE_TARGET_Y_TOLERANCE;
    const int achieved = airborne_seen && !collision_seen && landed && stationary && in_target;
    if (achieved) {
      precise_publish_outcome(custom_data, active_attempt, "achieved");
      reported = 1;
      continue;
    }
    if (wb_robot_get_time() - completion_time >= PRECISE_SETTLE_TIMEOUT) {
      printf("WEBEEBLOCKS_PRECISE_TIMEOUT attempt=%llu x=%.6f y=%.6f z=%.6f collision=%d airborne=%d landed=%d stationary=%d in_target=%d\n",
             active_attempt, position[0], position[1], position[2], collision_seen,
             airborne_seen, landed, stationary, in_target);
      fflush(stdout);
      precise_publish_outcome(custom_data, active_attempt, "not-achieved");
      reported = 1;
    }
  }

  wb_robot_cleanup();
  return 0;
}

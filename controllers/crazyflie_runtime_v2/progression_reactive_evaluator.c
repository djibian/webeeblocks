#include <math.h>
#include <stdio.h>
#include <string.h>
#include <webots/contact_point.h>
#include <webots/robot.h>
#include <webots/supervisor.h>

#define REACTIVE_ORACLE "progression-reactive-v1"
#define REACTIVE_ROWS 3
#define REACTIVE_AIRBORNE_DELTA 0.20
#define REACTIVE_LANDED_DELTA 0.07
#define REACTIVE_MAX_LANDING_SPEED 0.12
#define REACTIVE_SETTLE_TIMEOUT 1.5
#define REACTIVE_CHECKPOINT_TOLERANCE 0.10
#define REACTIVE_START_X 0.90
#define REACTIVE_START_Y 1.60
#define REACTIVE_STEP_X 0.30
#define REACTIVE_STEP_Y 0.30
#define REACTIVE_BARRIER_OFFSET_X 0.15
#define REACTIVE_BARRIER_Z 0.55
#define REACTIVE_BARRIER_HALF_EXTENT 0.07
#define REACTIVE_BARRIER_Z_MIN 0.0
#define REACTIVE_BARRIER_Z_MAX 1.10
#define CONTACT_TOLERANCE 0.004

static int reactive_parse_attempt(const char *data, unsigned long long *attempt) {
  if (!data || !attempt)
    return 0;
  char trailing[2] = {0};
  return sscanf(data, "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu %1s", attempt, trailing) == 1;
}

static int reactive_parse_completion(const char *data, unsigned long long *attempt) {
  if (!data || !attempt)
    return 0;
  char oracle[64] = {0};
  char trailing[2] = {0};
  if (sscanf(data, "WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=%llu oracle=%63s %1s",
             attempt, oracle, trailing) != 2)
    return 0;
  return strcmp(oracle, REACTIVE_ORACLE) == 0;
}

static int reactive_parse_failure_probe(const char *data, unsigned long long *attempt) {
  if (!data || !attempt)
    return 0;
  char oracle[64] = {0};
  char trailing[2] = {0};
  if (sscanf(data, "WEBEEBLOCKS_ACTIVITY_FAILURE_PROBE_V1 attempt=%llu oracle=%63s %1s",
             attempt, oracle, trailing) != 2)
    return 0;
  return strcmp(oracle, REACTIVE_ORACLE) == 0;
}

static WbNodeRef reactive_find_named_node(WbNodeRef node, const char *target_name) {
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
    WbNodeRef match = reactive_find_named_node(wb_supervisor_field_get_mf_node(children, index), target_name);
    if (match)
      return match;
  }
  return NULL;
}

static int reactive_near(const double *position, double x, double y, double tolerance) {
  return fabs(position[0] - x) <= tolerance && fabs(position[1] - y) <= tolerance;
}

static int reactive_contact_is_barrier(const double point[3], const double barrier[3]) {
  return fabs(point[0] - barrier[0]) <= REACTIVE_BARRIER_HALF_EXTENT + CONTACT_TOLERANCE &&
         fabs(point[1] - barrier[1]) <= REACTIVE_BARRIER_HALF_EXTENT + CONTACT_TOLERANCE &&
         point[2] >= REACTIVE_BARRIER_Z_MIN - CONTACT_TOLERANCE &&
         point[2] <= REACTIVE_BARRIER_Z_MAX + CONTACT_TOLERANCE;
}

static void reactive_publish_outcome(WbFieldRef custom_data, unsigned long long attempt, const char *status) {
  char result[192];
  snprintf(result, sizeof(result),
           "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=%s",
           attempt, REACTIVE_ORACLE, status);
  wb_supervisor_field_set_sf_string(custom_data, result);
  printf("WEBEEBLOCKS_REACTIVE_RESULT attempt=%llu status=%s\n", attempt, status);
  fflush(stdout);
}

static void reactive_configure_attempt(unsigned long long attempt,
                                       WbFieldRef barrier_fields[REACTIVE_ROWS],
                                       double barrier_positions[REACTIVE_ROWS][3],
                                       double checkpoints[REACTIVE_ROWS][2],
                                       int blocked[REACTIVE_ROWS],
                                       double *arrival_y) {
  const int odd = (attempt % 2ULL) == 1ULL;
  blocked[0] = odd ? 1 : 0;
  blocked[1] = odd ? 0 : 1;
  blocked[2] = odd ? 1 : 0;
  double y = REACTIVE_START_Y;
  for (int row = 0; row < REACTIVE_ROWS; ++row) {
    const double decision_x = REACTIVE_START_X + REACTIVE_STEP_X * row;
    barrier_positions[row][0] = decision_x + REACTIVE_BARRIER_OFFSET_X;
    barrier_positions[row][1] = y + (blocked[row] ? 0.0 : REACTIVE_STEP_Y);
    barrier_positions[row][2] = REACTIVE_BARRIER_Z;
    wb_supervisor_field_set_sf_vec3f(barrier_fields[row], barrier_positions[row]);
    if (blocked[row])
      y += REACTIVE_STEP_Y;
    checkpoints[row][0] = decision_x + REACTIVE_STEP_X;
    checkpoints[row][1] = y;
  }
  *arrival_y = y;
}

int webeeblocks_progression_reactive_evaluator_main(void) {
  wb_robot_init();
  const int step = (int)wb_robot_get_basic_time_step();
  WbNodeRef root = wb_supervisor_node_get_root();
  WbNodeRef crazyflie = reactive_find_named_node(root, "Crazyflie WebeeBlocks");
  WbNodeRef barriers[REACTIVE_ROWS] = {
    wb_supervisor_node_get_from_def("ACTIVITY5_BARRIER_1"),
    wb_supervisor_node_get_from_def("ACTIVITY5_BARRIER_2"),
    wb_supervisor_node_get_from_def("ACTIVITY5_BARRIER_3")
  };
  if (!crazyflie || !barriers[0] || !barriers[1] || !barriers[2]) {
    fprintf(stderr, "WEBEEBLOCKS_REACTIVE_EVALUATOR_ERROR missing Crazyflie or Activity 5 barrier node\n");
    wb_robot_cleanup();
    return 2;
  }
  WbFieldRef custom_data = wb_supervisor_node_get_field(crazyflie, "customData");
  WbFieldRef barrier_fields[REACTIVE_ROWS];
  for (int row = 0; row < REACTIVE_ROWS; ++row)
    barrier_fields[row] = wb_supervisor_node_get_field(barriers[row], "translation");
  if (!custom_data || !barrier_fields[0] || !barrier_fields[1] || !barrier_fields[2]) {
    fprintf(stderr, "WEBEEBLOCKS_REACTIVE_EVALUATOR_ERROR missing mission fields\n");
    wb_robot_cleanup();
    return 2;
  }
  const double *initial = wb_supervisor_node_get_position(crazyflie);
  if (!initial) {
    fprintf(stderr, "WEBEEBLOCKS_REACTIVE_EVALUATOR_ERROR missing Crazyflie position\n");
    wb_robot_cleanup();
    return 2;
  }
  const double origin_z = initial[2];
  wb_supervisor_node_enable_contact_points_tracking(crazyflie, step, true);

  unsigned long long active_attempt = 0;
  int has_attempt = 0;
  int blocked[REACTIVE_ROWS] = {0};
  double barrier_positions[REACTIVE_ROWS][3] = {{0}};
  double checkpoints[REACTIVE_ROWS][2] = {{0}};
  double arrival_y = REACTIVE_START_Y;
  int airborne_seen = 0;
  int checkpoint_index = 0;
  int collision_seen = 0;
  int completion_seen = 0;
  double completion_time = 0.0;
  int reported = 0;

  printf("WEBEEBLOCKS_REACTIVE_EVALUATOR_READY rows=%d start_x=%.3f start_y=%.3f\n",
         REACTIVE_ROWS, REACTIVE_START_X, REACTIVE_START_Y);
  fflush(stdout);

  while (wb_robot_step(step) != -1) {
    const char *data = wb_supervisor_field_get_sf_string(custom_data);
    unsigned long long observed_attempt = 0;
    if (reactive_parse_attempt(data, &observed_attempt) && (!has_attempt || observed_attempt != active_attempt)) {
      active_attempt = observed_attempt;
      has_attempt = 1;
      reactive_configure_attempt(active_attempt, barrier_fields, barrier_positions, checkpoints, blocked, &arrival_y);
      airborne_seen = 0;
      checkpoint_index = 0;
      collision_seen = 0;
      completion_seen = 0;
      completion_time = 0.0;
      reported = 0;
      printf("WEBEEBLOCKS_REACTIVE_CONFIG attempt=%llu pattern=%c%c%c arrival_y=%.3f\n",
             active_attempt, blocked[0] ? 'B' : 'O', blocked[1] ? 'B' : 'O', blocked[2] ? 'B' : 'O', arrival_y);
      fflush(stdout);
    }
    if (!has_attempt || reported)
      continue;

    const double *position = wb_supervisor_node_get_position(crazyflie);
    const double *velocity = wb_supervisor_node_get_velocity(crazyflie);
    if (!position || !velocity)
      continue;
    if (position[2] >= origin_z + REACTIVE_AIRBORNE_DELTA)
      airborne_seen = 1;

    int contact_count = 0;
    WbContactPoint *contacts = wb_supervisor_node_get_contact_points(crazyflie, true, &contact_count);
    for (int index = 0; index < contact_count && !collision_seen; ++index) {
      for (int row = 0; row < REACTIVE_ROWS; ++row) {
        if (reactive_contact_is_barrier(contacts[index].point, barrier_positions[row])) {
          collision_seen = 1;
          printf("WEBEEBLOCKS_REACTIVE_COLLISION attempt=%llu row=%d x=%.6f y=%.6f z=%.6f\n",
                 active_attempt, row + 1, contacts[index].point[0], contacts[index].point[1], contacts[index].point[2]);
          fflush(stdout);
          break;
        }
      }
    }

    if (airborne_seen && checkpoint_index < REACTIVE_ROWS &&
        reactive_near(position, checkpoints[checkpoint_index][0], checkpoints[checkpoint_index][1],
                      REACTIVE_CHECKPOINT_TOLERANCE)) {
      ++checkpoint_index;
      printf("WEBEEBLOCKS_REACTIVE_ROW attempt=%llu completed=%d\n", active_attempt, checkpoint_index);
      fflush(stdout);
    }

    if (!completion_seen) {
      unsigned long long failure_attempt = 0;
      if (reactive_parse_failure_probe(data, &failure_attempt) && failure_attempt == active_attempt) {
        reactive_publish_outcome(custom_data, active_attempt, "not-achieved");
        reported = 1;
        continue;
      }
      unsigned long long completed_attempt = 0;
      if (!reactive_parse_completion(data, &completed_attempt) || completed_attempt != active_attempt)
        continue;
      completion_seen = 1;
      completion_time = wb_robot_get_time();
    }

    if (collision_seen) {
      reactive_publish_outcome(custom_data, active_attempt, "not-achieved");
      reported = 1;
      continue;
    }

    const double horizontal_speed = hypot(velocity[0], velocity[1]);
    const double vertical_speed = fabs(velocity[2]);
    const int landed = position[2] <= origin_z + REACTIVE_LANDED_DELTA;
    const int stationary = horizontal_speed <= REACTIVE_MAX_LANDING_SPEED &&
                           vertical_speed <= REACTIVE_MAX_LANDING_SPEED;
    const int in_arrival = reactive_near(position, REACTIVE_START_X + REACTIVE_STEP_X * REACTIVE_ROWS,
                                         arrival_y, REACTIVE_CHECKPOINT_TOLERANCE);
    const int achieved = airborne_seen && checkpoint_index == REACTIVE_ROWS && landed && stationary && in_arrival;
    if (achieved) {
      reactive_publish_outcome(custom_data, active_attempt, "achieved");
      reported = 1;
      continue;
    }

    if (wb_robot_get_time() - completion_time >= REACTIVE_SETTLE_TIMEOUT) {
      printf("WEBEEBLOCKS_REACTIVE_TIMEOUT attempt=%llu checkpoints=%d x=%.6f y=%.6f z=%.6f landed=%d stationary=%d in_arrival=%d\n",
             active_attempt, checkpoint_index, position[0], position[1], position[2], landed, stationary, in_arrival);
      fflush(stdout);
      reactive_publish_outcome(custom_data, active_attempt, "not-achieved");
      reported = 1;
    }
  }

  wb_robot_cleanup();
  return 0;
}

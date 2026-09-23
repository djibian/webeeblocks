#include <math.h>
#include <stdio.h>
#include <string.h>
#include <webots/contact_point.h>
#include <webots/robot.h>
#include <webots/supervisor.h>

#define DECISION_ORACLE "progression-simple-decision-v1"
#define DECISION_AIRBORNE_DELTA 0.20
#define DECISION_LANDED_DELTA 0.07
#define DECISION_MAX_LANDING_SPEED 0.12
#define DECISION_SETTLE_TIMEOUT 1.5
#define DECISION_ROUTE_TOLERANCE 0.09
#define DECISION_ARRIVAL_X 1.40
#define DECISION_ARRIVAL_Y 1.20
#define DECISION_ARRIVAL_TOLERANCE 0.11
#define DECISION_FORWARD_ROUTE_X 1.30
#define DECISION_FORWARD_ROUTE_Y 0.80
#define DECISION_LEFT_ROUTE_X 1.00
#define DECISION_LEFT_ROUTE_Y 1.10
#define DECISION_BARRIER_Z 0.55
#define DECISION_BARRIER_HALF_EXTENT 0.07
#define DECISION_BARRIER_Z_MIN 0.0
#define DECISION_BARRIER_Z_MAX 1.10
#define CONTACT_TOLERANCE 0.004

static const double DECISION_FORWARD_BLOCKED[3] = {1.20, 0.80, DECISION_BARRIER_Z};
static const double DECISION_LEFT_BLOCKED[3] = {1.00, 1.00, DECISION_BARRIER_Z};

static int decision_parse_attempt(const char *data, unsigned long long *attempt) {
  if (!data || !attempt)
    return 0;
  char trailing[2] = {0};
  return sscanf(data, "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu %1s", attempt, trailing) == 1;
}

static int decision_parse_completion(const char *data, unsigned long long *attempt) {
  if (!data || !attempt)
    return 0;
  char oracle[64] = {0};
  char trailing[2] = {0};
  if (sscanf(data,
             "WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=%llu oracle=%63s %1s",
             attempt, oracle, trailing) != 2)
    return 0;
  return strcmp(oracle, DECISION_ORACLE) == 0;
}

static int decision_parse_failure_probe(const char *data, unsigned long long *attempt) {
  if (!data || !attempt)
    return 0;
  char oracle[64] = {0};
  char trailing[2] = {0};
  if (sscanf(data,
             "WEBEEBLOCKS_ACTIVITY_FAILURE_PROBE_V1 attempt=%llu oracle=%63s %1s",
             attempt, oracle, trailing) != 2)
    return 0;
  return strcmp(oracle, DECISION_ORACLE) == 0;
}

static WbNodeRef decision_find_named_node(WbNodeRef node, const char *target_name) {
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
    WbNodeRef match = decision_find_named_node(wb_supervisor_field_get_mf_node(children, index), target_name);
    if (match)
      return match;
  }
  return NULL;
}

static int decision_near(const double *position, double x, double y, double tolerance) {
  return fabs(position[0] - x) <= tolerance && fabs(position[1] - y) <= tolerance;
}

static int decision_contact_is_barrier(const double point[3], const double barrier[3]) {
  return fabs(point[0] - barrier[0]) <= DECISION_BARRIER_HALF_EXTENT + CONTACT_TOLERANCE &&
         fabs(point[1] - barrier[1]) <= DECISION_BARRIER_HALF_EXTENT + CONTACT_TOLERANCE &&
         point[2] >= DECISION_BARRIER_Z_MIN - CONTACT_TOLERANCE &&
         point[2] <= DECISION_BARRIER_Z_MAX + CONTACT_TOLERANCE;
}

static void decision_publish_outcome(WbFieldRef custom_data, unsigned long long attempt, const char *status) {
  char result[192];
  snprintf(result, sizeof(result),
           "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=%s",
           attempt, DECISION_ORACLE, status);
  wb_supervisor_field_set_sf_string(custom_data, result);
  printf("WEBEEBLOCKS_DECISION_RESULT attempt=%llu status=%s\n", attempt, status);
  fflush(stdout);
}

int webeeblocks_progression_simple_decision_evaluator_main(void) {
  wb_robot_init();
  const int step = (int)wb_robot_get_basic_time_step();
  WbNodeRef root = wb_supervisor_node_get_root();
  WbNodeRef crazyflie = decision_find_named_node(root, "Crazyflie WebeeBlocks");
  WbNodeRef barrier = wb_supervisor_node_get_from_def("ACTIVITY4_BARRIER");
  if (!crazyflie || !barrier) {
    fprintf(stderr, "WEBEEBLOCKS_DECISION_EVALUATOR_ERROR missing Crazyflie or ACTIVITY4_BARRIER node\n");
    wb_robot_cleanup();
    return 2;
  }
  WbFieldRef custom_data = wb_supervisor_node_get_field(crazyflie, "customData");
  WbFieldRef barrier_translation = wb_supervisor_node_get_field(barrier, "translation");
  if (!custom_data || !barrier_translation) {
    fprintf(stderr, "WEBEEBLOCKS_DECISION_EVALUATOR_ERROR missing mission fields\n");
    wb_robot_cleanup();
    return 2;
  }
  const double *initial = wb_supervisor_node_get_position(crazyflie);
  if (!initial) {
    fprintf(stderr, "WEBEEBLOCKS_DECISION_EVALUATOR_ERROR missing Crazyflie position\n");
    wb_robot_cleanup();
    return 2;
  }
  const double origin_z = initial[2];
  wb_supervisor_node_enable_contact_points_tracking(crazyflie, step, true);

  unsigned long long active_attempt = 0;
  int has_attempt = 0;
  int forward_blocked = 0;
  int airborne_seen = 0;
  int valid_route_seen = 0;
  int wrong_route_seen = 0;
  int collision_seen = 0;
  int completion_seen = 0;
  double completion_time = 0.0;
  int reported = 0;
  double barrier_position[3] = {0.0, 0.0, DECISION_BARRIER_Z};

  printf("WEBEEBLOCKS_DECISION_EVALUATOR_READY arrival_x=%.3f arrival_y=%.3f\n",
         DECISION_ARRIVAL_X, DECISION_ARRIVAL_Y);
  fflush(stdout);

  while (wb_robot_step(step) != -1) {
    const char *data = wb_supervisor_field_get_sf_string(custom_data);
    unsigned long long observed_attempt = 0;
    if (decision_parse_attempt(data, &observed_attempt) && (!has_attempt || observed_attempt != active_attempt)) {
      active_attempt = observed_attempt;
      has_attempt = 1;
      forward_blocked = (active_attempt % 2ULL) == 1ULL;
      const double *selected = forward_blocked ? DECISION_FORWARD_BLOCKED : DECISION_LEFT_BLOCKED;
      barrier_position[0] = selected[0];
      barrier_position[1] = selected[1];
      barrier_position[2] = selected[2];
      wb_supervisor_field_set_sf_vec3f(barrier_translation, barrier_position);
      airborne_seen = 0;
      valid_route_seen = 0;
      wrong_route_seen = 0;
      collision_seen = 0;
      completion_seen = 0;
      completion_time = 0.0;
      reported = 0;
      printf("WEBEEBLOCKS_DECISION_CONFIG attempt=%llu state=%s barrier_x=%.3f barrier_y=%.3f\n",
             active_attempt, forward_blocked ? "forward-blocked" : "forward-open",
             barrier_position[0], barrier_position[1]);
      fflush(stdout);
    }
    if (!has_attempt || reported)
      continue;

    const double *position = wb_supervisor_node_get_position(crazyflie);
    const double *velocity = wb_supervisor_node_get_velocity(crazyflie);
    if (!position || !velocity)
      continue;
    if (position[2] >= origin_z + DECISION_AIRBORNE_DELTA)
      airborne_seen = 1;

    int contact_count = 0;
    WbContactPoint *contacts = wb_supervisor_node_get_contact_points(crazyflie, true, &contact_count);
    for (int index = 0; index < contact_count; ++index) {
      if (decision_contact_is_barrier(contacts[index].point, barrier_position)) {
        if (!collision_seen) {
          printf("WEBEEBLOCKS_DECISION_COLLISION attempt=%llu x=%.6f y=%.6f z=%.6f\n",
                 active_attempt, contacts[index].point[0], contacts[index].point[1], contacts[index].point[2]);
          fflush(stdout);
        }
        collision_seen = 1;
        break;
      }
    }

    if (airborne_seen && !valid_route_seen && !wrong_route_seen) {
      const int on_forward_route = decision_near(position, DECISION_FORWARD_ROUTE_X, DECISION_FORWARD_ROUTE_Y,
                                                  DECISION_ROUTE_TOLERANCE);
      const int on_left_route = decision_near(position, DECISION_LEFT_ROUTE_X, DECISION_LEFT_ROUTE_Y,
                                               DECISION_ROUTE_TOLERANCE);
      if (forward_blocked && on_left_route) {
        valid_route_seen = 1;
        printf("WEBEEBLOCKS_DECISION_ROUTE attempt=%llu route=left valid=1\n", active_attempt);
        fflush(stdout);
      } else if (!forward_blocked && on_forward_route) {
        valid_route_seen = 1;
        printf("WEBEEBLOCKS_DECISION_ROUTE attempt=%llu route=forward valid=1\n", active_attempt);
        fflush(stdout);
      } else if ((forward_blocked && on_forward_route) || (!forward_blocked && on_left_route)) {
        wrong_route_seen = 1;
        printf("WEBEEBLOCKS_DECISION_ROUTE attempt=%llu route=%s valid=0\n",
               active_attempt, forward_blocked ? "forward" : "left");
        fflush(stdout);
      }
    }

    if (!completion_seen) {
      unsigned long long failure_attempt = 0;
      if (decision_parse_failure_probe(data, &failure_attempt) && failure_attempt == active_attempt &&
          (collision_seen || wrong_route_seen)) {
        decision_publish_outcome(custom_data, active_attempt, "not-achieved");
        reported = 1;
        continue;
      }

      unsigned long long completed_attempt = 0;
      if (!decision_parse_completion(data, &completed_attempt) || completed_attempt != active_attempt)
        continue;
      completion_seen = 1;
      completion_time = wb_robot_get_time();
    }

    if (collision_seen || wrong_route_seen) {
      decision_publish_outcome(custom_data, active_attempt, "not-achieved");
      reported = 1;
      continue;
    }

    const double horizontal_speed = hypot(velocity[0], velocity[1]);
    const double vertical_speed = fabs(velocity[2]);
    const int landed = position[2] <= origin_z + DECISION_LANDED_DELTA;
    const int stationary = horizontal_speed <= DECISION_MAX_LANDING_SPEED &&
                           vertical_speed <= DECISION_MAX_LANDING_SPEED;
    const int in_arrival = decision_near(position, DECISION_ARRIVAL_X, DECISION_ARRIVAL_Y,
                                         DECISION_ARRIVAL_TOLERANCE);
    const int achieved = airborne_seen && valid_route_seen && landed && stationary && in_arrival;
    if (achieved) {
      decision_publish_outcome(custom_data, active_attempt, "achieved");
      reported = 1;
      continue;
    }

    if (wb_robot_get_time() - completion_time >= DECISION_SETTLE_TIMEOUT) {
      printf("WEBEEBLOCKS_DECISION_TIMEOUT attempt=%llu route=%d x=%.6f y=%.6f z=%.6f landed=%d stationary=%d in_arrival=%d\n",
             active_attempt, valid_route_seen, position[0], position[1], position[2], landed, stationary, in_arrival);
      fflush(stdout);
      decision_publish_outcome(custom_data, active_attempt, "not-achieved");
      reported = 1;
    }
  }

  wb_robot_cleanup();
  return 0;
}

#include <math.h>
#include <stdio.h>
#include <string.h>
#include <webots/contact_point.h>
#include <webots/robot.h>
#include <webots/supervisor.h>

#define COMBINED_ORACLE "progression-combined-decisions-v1"
#define COMBINED_PATTERN_COUNT 3
#define COMBINED_AIRBORNE_DELTA 0.20
#define COMBINED_LANDED_DELTA 0.07
#define COMBINED_MAX_LANDING_SPEED 0.12
#define COMBINED_SETTLE_TIMEOUT 1.5
#define COMBINED_ROUTE_TOLERANCE 0.10
#define COMBINED_ARRIVAL_TOLERANCE 0.11
#define COMBINED_DECISION_X 1.40
#define COMBINED_DECISION_Y 0.60
#define COMBINED_FORWARD_ROUTE_X 1.70
#define COMBINED_FORWARD_ROUTE_Y 0.60
#define COMBINED_LEFT_ROUTE_X 1.40
#define COMBINED_LEFT_ROUTE_Y 0.90
#define COMBINED_RIGHT_ROUTE_X 1.40
#define COMBINED_RIGHT_ROUTE_Y 0.30
#define COMBINED_ARRIVAL_X 1.80
#define COMBINED_ARRIVAL_Y 0.90
#define COMBINED_BARRIER_Z 0.55
#define COMBINED_OPEN_BARRIER_Z -1.00
#define COMBINED_BARRIER_HALF_EXTENT 0.07
#define COMBINED_BARRIER_HALF_HEIGHT 0.55
#define CONTACT_TOLERANCE 0.004

enum CombinedRoute {
  COMBINED_ROUTE_FORWARD = 0,
  COMBINED_ROUTE_LEFT = 1,
  COMBINED_ROUTE_RIGHT = 2
};

typedef struct {
  int front_blocked;
  int left_blocked;
  int right_blocked;
  enum CombinedRoute valid_route;
  const char *name;
} CombinedPattern;

/*
 * Each retained configuration has one physically open immediate corridor.  The
 * matrix therefore exercises all three student-visible directions without
 * making success depend on a hidden solution shape: any program that reaches
 * the valid route checkpoint and the common arrival zone is accepted.
 */
static const CombinedPattern COMBINED_PATTERNS[COMBINED_PATTERN_COUNT] = {
  {0, 1, 1, COMBINED_ROUTE_FORWARD, "OBB-forward"},
  {1, 0, 1, COMBINED_ROUTE_LEFT,    "BOB-left"},
  {1, 1, 0, COMBINED_ROUTE_RIGHT,   "BBO-right"}
};

static const char *combined_route_name(enum CombinedRoute route) {
  switch (route) {
    case COMBINED_ROUTE_FORWARD:
      return "forward";
    case COMBINED_ROUTE_LEFT:
      return "left";
    case COMBINED_ROUTE_RIGHT:
      return "right";
  }
  return "unknown";
}

static int combined_parse_attempt(const char *data, unsigned long long *attempt) {
  if (!data || !attempt)
    return 0;
  char trailing[2] = {0};
  return sscanf(data, "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu %1s", attempt, trailing) == 1;
}

static int combined_parse_completion(const char *data, unsigned long long *attempt) {
  if (!data || !attempt)
    return 0;
  char oracle[64] = {0};
  char trailing[2] = {0};
  if (sscanf(data,
             "WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=%llu oracle=%63s %1s",
             attempt, oracle, trailing) != 2)
    return 0;
  return strcmp(oracle, COMBINED_ORACLE) == 0;
}

static int combined_parse_failure_probe(const char *data, unsigned long long *attempt) {
  if (!data || !attempt)
    return 0;
  char oracle[64] = {0};
  char trailing[2] = {0};
  if (sscanf(data,
             "WEBEEBLOCKS_ACTIVITY_FAILURE_PROBE_V1 attempt=%llu oracle=%63s %1s",
             attempt, oracle, trailing) != 2)
    return 0;
  return strcmp(oracle, COMBINED_ORACLE) == 0;
}

static WbNodeRef combined_find_named_node(WbNodeRef node, const char *target_name) {
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
    WbNodeRef match = combined_find_named_node(wb_supervisor_field_get_mf_node(children, index), target_name);
    if (match)
      return match;
  }
  return NULL;
}

static int combined_near(const double *position, double x, double y, double tolerance) {
  return fabs(position[0] - x) <= tolerance && fabs(position[1] - y) <= tolerance;
}

static int combined_contact_is_barrier(const double point[3], const double barrier[3]) {
  return fabs(point[0] - barrier[0]) <= COMBINED_BARRIER_HALF_EXTENT + CONTACT_TOLERANCE &&
         fabs(point[1] - barrier[1]) <= COMBINED_BARRIER_HALF_EXTENT + CONTACT_TOLERANCE &&
         fabs(point[2] - barrier[2]) <= COMBINED_BARRIER_HALF_HEIGHT + CONTACT_TOLERANCE;
}

static void combined_publish_outcome(WbFieldRef custom_data, unsigned long long attempt, const char *status) {
  char result[192];
  snprintf(result, sizeof(result),
           "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=%s",
           attempt, COMBINED_ORACLE, status);
  wb_supervisor_field_set_sf_string(custom_data, result);
  printf("WEBEEBLOCKS_COMBINED_RESULT attempt=%llu status=%s\n", attempt, status);
  fflush(stdout);
}

int webeeblocks_progression_combined_decisions_evaluator_main(void) {
  wb_robot_init();
  const int step = (int)wb_robot_get_basic_time_step();
  WbNodeRef root = wb_supervisor_node_get_root();
  WbNodeRef crazyflie = combined_find_named_node(root, "Crazyflie WebeeBlocks");
  WbNodeRef barrier_nodes[3] = {
    wb_supervisor_node_get_from_def("ACTIVITY6_FRONT_BARRIER"),
    wb_supervisor_node_get_from_def("ACTIVITY6_LEFT_BARRIER"),
    wb_supervisor_node_get_from_def("ACTIVITY6_RIGHT_BARRIER")
  };
  if (!crazyflie || !barrier_nodes[0] || !barrier_nodes[1] || !barrier_nodes[2]) {
    fprintf(stderr, "WEBEEBLOCKS_COMBINED_EVALUATOR_ERROR missing Crazyflie or Activity 6 barrier node\n");
    wb_robot_cleanup();
    return 2;
  }
  WbFieldRef custom_data = wb_supervisor_node_get_field(crazyflie, "customData");
  WbFieldRef barrier_fields[3];
  for (int index = 0; index < 3; ++index)
    barrier_fields[index] = wb_supervisor_node_get_field(barrier_nodes[index], "translation");
  if (!custom_data || !barrier_fields[0] || !barrier_fields[1] || !barrier_fields[2]) {
    fprintf(stderr, "WEBEEBLOCKS_COMBINED_EVALUATOR_ERROR missing mission fields\n");
    wb_robot_cleanup();
    return 2;
  }
  const double *initial = wb_supervisor_node_get_position(crazyflie);
  if (!initial) {
    fprintf(stderr, "WEBEEBLOCKS_COMBINED_EVALUATOR_ERROR missing Crazyflie position\n");
    wb_robot_cleanup();
    return 2;
  }
  const double origin_z = initial[2];
  wb_supervisor_node_enable_contact_points_tracking(crazyflie, step, true);

  const double base_positions[3][3] = {
    {1.65, 0.60, COMBINED_BARRIER_Z},
    {1.40, 0.85, COMBINED_BARRIER_Z},
    {1.40, 0.35, COMBINED_BARRIER_Z}
  };
  double barrier_positions[3][3] = {{0}};
  unsigned long long active_attempt = 0;
  int has_attempt = 0;
  int pattern_index = 0;
  int airborne_seen = 0;
  int decision_seen = 0;
  int valid_route_seen = 0;
  int wrong_route_seen = 0;
  int collision_seen = 0;
  int completion_seen = 0;
  double completion_time = 0.0;
  int reported = 0;

  printf("WEBEEBLOCKS_COMBINED_EVALUATOR_READY patterns=%d decision_x=%.3f decision_y=%.3f\n",
         COMBINED_PATTERN_COUNT, COMBINED_DECISION_X, COMBINED_DECISION_Y);
  fflush(stdout);

  while (wb_robot_step(step) != -1) {
    const char *data = wb_supervisor_field_get_sf_string(custom_data);
    unsigned long long observed_attempt = 0;
    if (combined_parse_attempt(data, &observed_attempt) && (!has_attempt || observed_attempt != active_attempt)) {
      active_attempt = observed_attempt;
      has_attempt = 1;
      const unsigned long long normalized = active_attempt > 0 ? active_attempt - 1ULL : 0ULL;
      pattern_index = (int)(normalized % COMBINED_PATTERN_COUNT);
      const CombinedPattern *pattern = &COMBINED_PATTERNS[pattern_index];
      const int blocked[3] = {pattern->front_blocked, pattern->left_blocked, pattern->right_blocked};
      for (int index = 0; index < 3; ++index) {
        barrier_positions[index][0] = base_positions[index][0];
        barrier_positions[index][1] = base_positions[index][1];
        barrier_positions[index][2] = blocked[index] ? COMBINED_BARRIER_Z : COMBINED_OPEN_BARRIER_Z;
        wb_supervisor_field_set_sf_vec3f(barrier_fields[index], barrier_positions[index]);
      }
      airborne_seen = 0;
      decision_seen = 0;
      valid_route_seen = 0;
      wrong_route_seen = 0;
      collision_seen = 0;
      completion_seen = 0;
      completion_time = 0.0;
      reported = 0;
      printf("WEBEEBLOCKS_COMBINED_CONFIG attempt=%llu pattern=%s front=%d left=%d right=%d valid=%s\n",
             active_attempt, pattern->name,
             pattern->front_blocked, pattern->left_blocked, pattern->right_blocked,
             combined_route_name(pattern->valid_route));
      fflush(stdout);
    }
    if (!has_attempt || reported)
      continue;

    const double *position = wb_supervisor_node_get_position(crazyflie);
    const double *velocity = wb_supervisor_node_get_velocity(crazyflie);
    if (!position || !velocity)
      continue;
    if (position[2] >= origin_z + COMBINED_AIRBORNE_DELTA)
      airborne_seen = 1;
    if (airborne_seen && !decision_seen &&
        combined_near(position, COMBINED_DECISION_X, COMBINED_DECISION_Y, COMBINED_ROUTE_TOLERANCE)) {
      decision_seen = 1;
      printf("WEBEEBLOCKS_COMBINED_DECISION attempt=%llu\n", active_attempt);
      fflush(stdout);
    }

    int contact_count = 0;
    WbContactPoint *contacts = wb_supervisor_node_get_contact_points(crazyflie, true, &contact_count);
    for (int index = 0; index < contact_count && !collision_seen; ++index) {
      for (int barrier = 0; barrier < 3; ++barrier) {
        if (combined_contact_is_barrier(contacts[index].point, barrier_positions[barrier])) {
          collision_seen = 1;
          printf("WEBEEBLOCKS_COMBINED_COLLISION attempt=%llu barrier=%d x=%.6f y=%.6f z=%.6f\n",
                 active_attempt, barrier + 1,
                 contacts[index].point[0], contacts[index].point[1], contacts[index].point[2]);
          fflush(stdout);
          break;
        }
      }
    }

    if (decision_seen && !valid_route_seen && !wrong_route_seen) {
      const int on_forward = combined_near(position, COMBINED_FORWARD_ROUTE_X, COMBINED_FORWARD_ROUTE_Y,
                                           COMBINED_ROUTE_TOLERANCE);
      const int on_left = combined_near(position, COMBINED_LEFT_ROUTE_X, COMBINED_LEFT_ROUTE_Y,
                                        COMBINED_ROUTE_TOLERANCE);
      const int on_right = combined_near(position, COMBINED_RIGHT_ROUTE_X, COMBINED_RIGHT_ROUTE_Y,
                                         COMBINED_ROUTE_TOLERANCE);
      if (on_forward || on_left || on_right) {
        enum CombinedRoute selected = COMBINED_ROUTE_FORWARD;
        if (on_left)
          selected = COMBINED_ROUTE_LEFT;
        else if (on_right)
          selected = COMBINED_ROUTE_RIGHT;
        const CombinedPattern *pattern = &COMBINED_PATTERNS[pattern_index];
        if (selected == pattern->valid_route) {
          valid_route_seen = 1;
          printf("WEBEEBLOCKS_COMBINED_ROUTE attempt=%llu route=%s valid=1\n",
                 active_attempt, combined_route_name(selected));
        } else {
          wrong_route_seen = 1;
          printf("WEBEEBLOCKS_COMBINED_ROUTE attempt=%llu route=%s valid=0\n",
                 active_attempt, combined_route_name(selected));
        }
        fflush(stdout);
      }
    }

    if (!completion_seen) {
      unsigned long long failure_attempt = 0;
      if (combined_parse_failure_probe(data, &failure_attempt) && failure_attempt == active_attempt &&
          (collision_seen || wrong_route_seen)) {
        combined_publish_outcome(custom_data, active_attempt, "not-achieved");
        reported = 1;
        continue;
      }
      unsigned long long completed_attempt = 0;
      if (!combined_parse_completion(data, &completed_attempt) || completed_attempt != active_attempt)
        continue;
      completion_seen = 1;
      completion_time = wb_robot_get_time();
    }

    if (collision_seen || wrong_route_seen) {
      combined_publish_outcome(custom_data, active_attempt, "not-achieved");
      reported = 1;
      continue;
    }

    const double horizontal_speed = hypot(velocity[0], velocity[1]);
    const double vertical_speed = fabs(velocity[2]);
    const int landed = position[2] <= origin_z + COMBINED_LANDED_DELTA;
    const int stationary = horizontal_speed <= COMBINED_MAX_LANDING_SPEED &&
                           vertical_speed <= COMBINED_MAX_LANDING_SPEED;
    const int in_arrival = combined_near(position, COMBINED_ARRIVAL_X, COMBINED_ARRIVAL_Y,
                                         COMBINED_ARRIVAL_TOLERANCE);
    const int achieved = airborne_seen && decision_seen && valid_route_seen && landed && stationary && in_arrival;
    if (achieved) {
      combined_publish_outcome(custom_data, active_attempt, "achieved");
      reported = 1;
      continue;
    }

    if (wb_robot_get_time() - completion_time >= COMBINED_SETTLE_TIMEOUT) {
      printf("WEBEEBLOCKS_COMBINED_TIMEOUT attempt=%llu decision=%d route=%d x=%.6f y=%.6f z=%.6f landed=%d stationary=%d arrival=%d\n",
             active_attempt, decision_seen, valid_route_seen,
             position[0], position[1], position[2], landed, stationary, in_arrival);
      fflush(stdout);
      combined_publish_outcome(custom_data, active_attempt, "not-achieved");
      reported = 1;
    }
  }

  wb_robot_cleanup();
  return 0;
}

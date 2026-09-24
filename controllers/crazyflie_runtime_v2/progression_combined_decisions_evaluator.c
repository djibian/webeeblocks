#include <math.h>
#include <stdbool.h>
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
#define COMBINED_DECISION_Y -0.60
#define COMBINED_FORWARD_ROUTE_X 1.70
#define COMBINED_FORWARD_ROUTE_Y -0.60
#define COMBINED_LEFT_ROUTE_X 1.40
#define COMBINED_LEFT_ROUTE_Y -0.30
#define COMBINED_RIGHT_ROUTE_X 1.40
#define COMBINED_RIGHT_ROUTE_Y -0.90
#define COMBINED_ARRIVAL_X 1.80
#define COMBINED_ARRIVAL_Y -0.30
#define COMBINED_BARRIER_Z 0.55
#define COMBINED_OPEN_BARRIER_Z -1.00
#define COMBINED_BARRIER_HALF_EXTENT 0.07
#define COMBINED_BARRIER_HALF_HEIGHT 0.55

#define MEMORY_ORACLE "progression-memory-v1"
#define MEMORY_PATTERN_COUNT 2
#define MEMORY_STATION_X 0.0
#define MEMORY_STATION_Y -1.50
#define MEMORY_DECISION_1_X 0.65
#define MEMORY_DECISION_2_X 1.20
#define MEMORY_CENTER_Y -1.50
#define MEMORY_LEFT_Y -1.25
#define MEMORY_RIGHT_Y -1.75
#define MEMORY_ARRIVAL_X 1.65
#define MEMORY_ARRIVAL_Y -1.50
#define MEMORY_ROUTE_TOLERANCE 0.11
#define MEMORY_STATION_TOLERANCE 0.13
#define MEMORY_ARRIVAL_TOLERANCE 0.12
#define MEMORY_PANEL_Z 0.55
#define MEMORY_PANEL_HIDDEN_Z -1.00
#define MEMORY_PANEL_HIDE_X 0.12
#define MEMORY_LANDED_DELTA 0.07
#define MEMORY_MAX_LANDING_SPEED 0.12
#define MEMORY_SETTLE_TIMEOUT 1.5
#define CONTACT_TOLERANCE 0.004

enum CombinedRoute {
  COMBINED_ROUTE_FORWARD = 0,
  COMBINED_ROUTE_LEFT = 1,
  COMBINED_ROUTE_RIGHT = 2
};

enum MemoryRoute {
  MEMORY_ROUTE_LEFT = 0,
  MEMORY_ROUTE_RIGHT = 1
};

typedef struct {
  int front_blocked;
  int left_blocked;
  int right_blocked;
  enum CombinedRoute valid_route;
  const char *name;
} CombinedPattern;

typedef struct {
  double panel_x;
  int small_parcel;
  enum MemoryRoute first_route;
  enum MemoryRoute second_route;
  const char *name;
} MemoryPattern;

static const CombinedPattern COMBINED_PATTERNS[COMBINED_PATTERN_COUNT] = {
  {0, 1, 1, COMBINED_ROUTE_FORWARD, "OBB-forward"},
  {1, 0, 1, COMBINED_ROUTE_LEFT,    "BOB-left"},
  {1, 1, 0, COMBINED_ROUTE_RIGHT,   "BBO-right"}
};

static const MemoryPattern MEMORY_PATTERNS[MEMORY_PATTERN_COUNT] = {
  {1.25, 1, MEMORY_ROUTE_LEFT,  MEMORY_ROUTE_RIGHT, "small-far"},
  {0.35, 0, MEMORY_ROUTE_RIGHT, MEMORY_ROUTE_LEFT,  "large-near"}
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

static const char *memory_route_name(enum MemoryRoute route) {
  return route == MEMORY_ROUTE_LEFT ? "left" : "right";
}

static int parse_attempt(const char *data, unsigned long long *attempt) {
  if (!data || !attempt)
    return 0;
  char trailing[2] = {0};
  return sscanf(data, "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu %1s", attempt, trailing) == 1;
}

static int parse_oracle_message(const char *data,
                                const char *kind,
                                const char *expected_oracle,
                                unsigned long long *attempt) {
  if (!data || !kind || !expected_oracle || !attempt)
    return 0;
  char oracle[64] = {0};
  char trailing[2] = {0};
  char pattern[128] = {0};
  snprintf(pattern, sizeof(pattern),
           "WEBEEBLOCKS_ACTIVITY_%s_V1 attempt=%%llu oracle=%%63s %%1s", kind);
  if (sscanf(data, pattern, attempt, oracle, trailing) != 2)
    return 0;
  return strcmp(oracle, expected_oracle) == 0;
}

static WbNodeRef find_named_node(WbNodeRef node, const char *target_name) {
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
    WbNodeRef match = find_named_node(wb_supervisor_field_get_mf_node(children, index), target_name);
    if (match)
      return match;
  }
  return NULL;
}

static int near_xy(const double *position, double x, double y, double tolerance) {
  return fabs(position[0] - x) <= tolerance && fabs(position[1] - y) <= tolerance;
}

static int combined_contact_is_barrier(const double point[3], const double barrier[3]) {
  return fabs(point[0] - barrier[0]) <= COMBINED_BARRIER_HALF_EXTENT + CONTACT_TOLERANCE &&
         fabs(point[1] - barrier[1]) <= COMBINED_BARRIER_HALF_EXTENT + CONTACT_TOLERANCE &&
         fabs(point[2] - barrier[2]) <= COMBINED_BARRIER_HALF_HEIGHT + CONTACT_TOLERANCE;
}

static void publish_outcome(WbFieldRef custom_data,
                            unsigned long long attempt,
                            const char *oracle,
                            const char *status,
                            const char *log_prefix) {
  char result[192];
  snprintf(result, sizeof(result),
           "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=%s",
           attempt, oracle, status);
  wb_supervisor_field_set_sf_string(custom_data, result);
  printf("%s attempt=%llu status=%s\n", log_prefix, attempt, status);
  fflush(stdout);
}

static int import_memory_world(WbNodeRef root, WbNodeRef *panel_out, WbFieldRef *panel_translation_out) {
  WbFieldRef children = wb_supervisor_node_get_field(root, "children");
  if (!children)
    return 0;
  const char *nodes[] = {
    "DEF ACTIVITY7_MEASUREMENT_PAD Pose { translation 0 -1.50 0.002 children [ Shape { appearance PBRAppearance { baseColor 0.22 0.48 0.88 transparency 0.18 roughness 0.9 } geometry Box { size 0.24 0.24 0.004 } } ] }",
    "DEF ACTIVITY7_FIRST_SMALL_ROUTE Pose { translation 0.65 -1.25 0.002 children [ Shape { appearance PBRAppearance { baseColor 0.10 0.66 0.92 transparency 0.14 roughness 0.9 } geometry Box { size 0.20 0.20 0.004 } } ] }",
    "DEF ACTIVITY7_FIRST_LARGE_ROUTE Pose { translation 0.65 -1.75 0.002 children [ Shape { appearance PBRAppearance { baseColor 0.92 0.52 0.08 transparency 0.14 roughness 0.9 } geometry Box { size 0.20 0.20 0.004 } } ] }",
    "DEF ACTIVITY7_SECOND_LARGE_ROUTE Pose { translation 1.20 -1.25 0.002 children [ Shape { appearance PBRAppearance { baseColor 0.92 0.52 0.08 transparency 0.14 roughness 0.9 } geometry Box { size 0.20 0.20 0.004 } } ] }",
    "DEF ACTIVITY7_SECOND_SMALL_ROUTE Pose { translation 1.20 -1.75 0.002 children [ Shape { appearance PBRAppearance { baseColor 0.10 0.66 0.92 transparency 0.14 roughness 0.9 } geometry Box { size 0.20 0.20 0.004 } } ] }",
    "DEF ACTIVITY7_ARRIVAL_PAD Pose { translation 1.65 -1.50 0.002 children [ Shape { appearance PBRAppearance { baseColor 0.10 0.72 0.28 transparency 0.10 roughness 0.9 } geometry Box { size 0.26 0.26 0.004 } } ] }",
    "DEF ACTIVITY7_REFERENCE_PANEL Solid { translation 0 -1.50 -1.00 name \"Activity 7 parcel gauge reference panel\" children [ Shape { appearance PBRAppearance { baseColor 0.72 0.18 0.78 roughness 0.5 } geometry Box { size 0.10 0.50 1.10 } } ] boundingObject Box { size 0.10 0.50 1.10 } }"
  };
  const int count = (int)(sizeof(nodes) / sizeof(nodes[0]));
  for (int index = 0; index < count; ++index)
    wb_supervisor_field_import_mf_node_from_string(children, -1, nodes[index]);

  WbNodeRef panel = wb_supervisor_node_get_from_def("ACTIVITY7_REFERENCE_PANEL");
  if (!panel)
    return 0;
  WbFieldRef translation = wb_supervisor_node_get_field(panel, "translation");
  if (!translation)
    return 0;
  *panel_out = panel;
  *panel_translation_out = translation;
  return 1;
}

int webeeblocks_progression_combined_decisions_evaluator_main(void) {
  wb_robot_init();
  const int step = (int)wb_robot_get_basic_time_step();
  WbNodeRef root = wb_supervisor_node_get_root();
  WbNodeRef crazyflie = find_named_node(root, "Crazyflie WebeeBlocks");
  WbNodeRef barrier_nodes[3] = {
    wb_supervisor_node_get_from_def("ACTIVITY6_FRONT_BARRIER"),
    wb_supervisor_node_get_from_def("ACTIVITY6_LEFT_BARRIER"),
    wb_supervisor_node_get_from_def("ACTIVITY6_RIGHT_BARRIER")
  };
  WbNodeRef memory_panel = NULL;
  WbFieldRef memory_panel_translation = NULL;
  if (!crazyflie || !barrier_nodes[0] || !barrier_nodes[1] || !barrier_nodes[2] ||
      !import_memory_world(root, &memory_panel, &memory_panel_translation)) {
    fprintf(stderr, "WEBEEBLOCKS_COMBINED_EVALUATOR_ERROR missing Crazyflie, Activity 6 barrier, or Activity 7 mission node\n");
    wb_robot_cleanup();
    return 2;
  }
  WbFieldRef custom_data = wb_supervisor_node_get_field(crazyflie, "customData");
  WbFieldRef barrier_fields[3];
  for (int index = 0; index < 3; ++index)
    barrier_fields[index] = wb_supervisor_node_get_field(barrier_nodes[index], "translation");
  if (!custom_data || !barrier_fields[0] || !barrier_fields[1] || !barrier_fields[2] ||
      !memory_panel_translation) {
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
    {1.65, -0.60, COMBINED_BARRIER_Z},
    {1.40, -0.35, COMBINED_BARRIER_Z},
    {1.40, -0.85, COMBINED_BARRIER_Z}
  };
  double barrier_positions[3][3] = {{0}};
  double memory_panel_position[3] = {0.0, MEMORY_STATION_Y, MEMORY_PANEL_HIDDEN_Z};

  unsigned long long active_attempt = 0;
  int has_attempt = 0;
  int combined_pattern_index = 0;
  int combined_airborne_seen = 0;
  int combined_decision_seen = 0;
  int combined_valid_route_seen = 0;
  int combined_wrong_route_seen = 0;
  int combined_collision_seen = 0;
  int combined_completion_seen = 0;
  double combined_completion_time = 0.0;
  int combined_reported = 0;

  int memory_pattern_index = 0;
  int memory_airborne_seen = 0;
  int memory_station_seen = 0;
  int memory_panel_hidden = 0;
  int memory_first_decision_seen = 0;
  int memory_first_valid_route_seen = 0;
  int memory_second_decision_seen = 0;
  int memory_second_valid_route_seen = 0;
  int memory_wrong_route_seen = 0;
  int memory_completion_seen = 0;
  double memory_completion_time = 0.0;
  int memory_reported = 0;

  printf("WEBEEBLOCKS_COMBINED_EVALUATOR_READY patterns=%d decision_x=%.3f decision_y=%.3f\n",
         COMBINED_PATTERN_COUNT, COMBINED_DECISION_X, COMBINED_DECISION_Y);
  printf("WEBEEBLOCKS_MEMORY_EVALUATOR_READY patterns=%d station_y=%.3f decision1_x=%.3f decision2_x=%.3f\n",
         MEMORY_PATTERN_COUNT, MEMORY_STATION_Y, MEMORY_DECISION_1_X, MEMORY_DECISION_2_X);
  fflush(stdout);

  while (wb_robot_step(step) != -1) {
    const char *data = wb_supervisor_field_get_sf_string(custom_data);
    unsigned long long observed_attempt = 0;
    if (parse_attempt(data, &observed_attempt) && (!has_attempt || observed_attempt != active_attempt)) {
      active_attempt = observed_attempt;
      has_attempt = 1;
      const unsigned long long normalized = active_attempt > 0 ? active_attempt - 1ULL : 0ULL;

      combined_pattern_index = (int)(normalized % COMBINED_PATTERN_COUNT);
      const CombinedPattern *combined_pattern = &COMBINED_PATTERNS[combined_pattern_index];
      const int blocked[3] = {
        combined_pattern->front_blocked,
        combined_pattern->left_blocked,
        combined_pattern->right_blocked
      };
      for (int index = 0; index < 3; ++index) {
        barrier_positions[index][0] = base_positions[index][0];
        barrier_positions[index][1] = base_positions[index][1];
        barrier_positions[index][2] = blocked[index] ? COMBINED_BARRIER_Z : COMBINED_OPEN_BARRIER_Z;
        wb_supervisor_field_set_sf_vec3f(barrier_fields[index], barrier_positions[index]);
      }
      combined_airborne_seen = 0;
      combined_decision_seen = 0;
      combined_valid_route_seen = 0;
      combined_wrong_route_seen = 0;
      combined_collision_seen = 0;
      combined_completion_seen = 0;
      combined_completion_time = 0.0;
      combined_reported = 0;
      printf("WEBEEBLOCKS_COMBINED_CONFIG attempt=%llu pattern=%s front=%d left=%d right=%d valid=%s\n",
             active_attempt, combined_pattern->name,
             combined_pattern->front_blocked, combined_pattern->left_blocked, combined_pattern->right_blocked,
             combined_route_name(combined_pattern->valid_route));

      memory_pattern_index = (int)(normalized % MEMORY_PATTERN_COUNT);
      const MemoryPattern *memory_pattern = &MEMORY_PATTERNS[memory_pattern_index];
      memory_panel_position[0] = memory_pattern->panel_x;
      memory_panel_position[1] = MEMORY_STATION_Y;
      memory_panel_position[2] = MEMORY_PANEL_Z;
      wb_supervisor_field_set_sf_vec3f(memory_panel_translation, memory_panel_position);
      memory_airborne_seen = 0;
      memory_station_seen = 0;
      memory_panel_hidden = 0;
      memory_first_decision_seen = 0;
      memory_first_valid_route_seen = 0;
      memory_second_decision_seen = 0;
      memory_second_valid_route_seen = 0;
      memory_wrong_route_seen = 0;
      memory_completion_seen = 0;
      memory_completion_time = 0.0;
      memory_reported = 0;
      printf("WEBEEBLOCKS_MEMORY_CONFIG attempt=%llu pattern=%s panel_x=%.3f parcel=%s first=%s second=%s\n",
             active_attempt, memory_pattern->name, memory_pattern->panel_x,
             memory_pattern->small_parcel ? "small" : "large",
             memory_route_name(memory_pattern->first_route),
             memory_route_name(memory_pattern->second_route));
      fflush(stdout);
    }
    if (!has_attempt)
      continue;

    const double *position = wb_supervisor_node_get_position(crazyflie);
    const double *velocity = wb_supervisor_node_get_velocity(crazyflie);
    if (!position || !velocity)
      continue;

    if (!combined_reported) {
      if (position[2] >= origin_z + COMBINED_AIRBORNE_DELTA)
        combined_airborne_seen = 1;
      if (combined_airborne_seen && !combined_decision_seen &&
          near_xy(position, COMBINED_DECISION_X, COMBINED_DECISION_Y, COMBINED_ROUTE_TOLERANCE)) {
        combined_decision_seen = 1;
        printf("WEBEEBLOCKS_COMBINED_DECISION attempt=%llu\n", active_attempt);
        fflush(stdout);
      }

      int contact_count = 0;
      WbContactPoint *contacts = wb_supervisor_node_get_contact_points(crazyflie, true, &contact_count);
      for (int index = 0; index < contact_count && !combined_collision_seen; ++index) {
        for (int barrier = 0; barrier < 3; ++barrier) {
          if (combined_contact_is_barrier(contacts[index].point, barrier_positions[barrier])) {
            combined_collision_seen = 1;
            printf("WEBEEBLOCKS_COMBINED_COLLISION attempt=%llu barrier=%d x=%.6f y=%.6f z=%.6f\n",
                   active_attempt, barrier + 1,
                   contacts[index].point[0], contacts[index].point[1], contacts[index].point[2]);
            fflush(stdout);
            break;
          }
        }
      }

      if (combined_decision_seen && !combined_valid_route_seen && !combined_wrong_route_seen) {
        const int on_forward = near_xy(position, COMBINED_FORWARD_ROUTE_X, COMBINED_FORWARD_ROUTE_Y,
                                       COMBINED_ROUTE_TOLERANCE);
        const int on_left = near_xy(position, COMBINED_LEFT_ROUTE_X, COMBINED_LEFT_ROUTE_Y,
                                    COMBINED_ROUTE_TOLERANCE);
        const int on_right = near_xy(position, COMBINED_RIGHT_ROUTE_X, COMBINED_RIGHT_ROUTE_Y,
                                     COMBINED_ROUTE_TOLERANCE);
        if (on_forward || on_left || on_right) {
          enum CombinedRoute selected = COMBINED_ROUTE_FORWARD;
          if (on_left)
            selected = COMBINED_ROUTE_LEFT;
          else if (on_right)
            selected = COMBINED_ROUTE_RIGHT;
          const CombinedPattern *pattern = &COMBINED_PATTERNS[combined_pattern_index];
          if (selected == pattern->valid_route) {
            combined_valid_route_seen = 1;
            printf("WEBEEBLOCKS_COMBINED_ROUTE attempt=%llu route=%s valid=1\n",
                   active_attempt, combined_route_name(selected));
          } else {
            combined_wrong_route_seen = 1;
            printf("WEBEEBLOCKS_COMBINED_ROUTE attempt=%llu route=%s valid=0\n",
                   active_attempt, combined_route_name(selected));
          }
          fflush(stdout);
        }
      }

      unsigned long long combined_failure_attempt = 0;
      if (parse_oracle_message(data, "FAILURE_PROBE", COMBINED_ORACLE, &combined_failure_attempt) &&
          combined_failure_attempt == active_attempt &&
          (combined_collision_seen || combined_wrong_route_seen)) {
        publish_outcome(custom_data, active_attempt, COMBINED_ORACLE, "not-achieved",
                        "WEBEEBLOCKS_COMBINED_RESULT");
        combined_reported = 1;
        continue;
      } else if (!combined_completion_seen) {
        unsigned long long completed_attempt = 0;
        if (parse_oracle_message(data, "COMPLETION", COMBINED_ORACLE, &completed_attempt) &&
            completed_attempt == active_attempt) {
          combined_completion_seen = 1;
          combined_completion_time = wb_robot_get_time();
        }
      }

      if (!combined_reported && combined_completion_seen) {
        if (combined_collision_seen || combined_wrong_route_seen) {
          publish_outcome(custom_data, active_attempt, COMBINED_ORACLE, "not-achieved",
                          "WEBEEBLOCKS_COMBINED_RESULT");
          combined_reported = 1;
          continue;
        } else {
          const double horizontal_speed = hypot(velocity[0], velocity[1]);
          const double vertical_speed = fabs(velocity[2]);
          const int landed = position[2] <= origin_z + COMBINED_LANDED_DELTA;
          const int stationary = horizontal_speed <= COMBINED_MAX_LANDING_SPEED &&
                                 vertical_speed <= COMBINED_MAX_LANDING_SPEED;
          const int in_arrival = near_xy(position, COMBINED_ARRIVAL_X, COMBINED_ARRIVAL_Y,
                                         COMBINED_ARRIVAL_TOLERANCE);
          const int achieved = combined_airborne_seen && combined_decision_seen &&
                               combined_valid_route_seen && landed && stationary && in_arrival;
          if (achieved) {
            publish_outcome(custom_data, active_attempt, COMBINED_ORACLE, "achieved",
                            "WEBEEBLOCKS_COMBINED_RESULT");
            combined_reported = 1;
            continue;
          } else if (wb_robot_get_time() - combined_completion_time >= COMBINED_SETTLE_TIMEOUT) {
            printf("WEBEEBLOCKS_COMBINED_TIMEOUT attempt=%llu decision=%d route=%d x=%.6f y=%.6f z=%.6f landed=%d stationary=%d arrival=%d\n",
                   active_attempt, combined_decision_seen, combined_valid_route_seen,
                   position[0], position[1], position[2], landed, stationary, in_arrival);
            fflush(stdout);
            publish_outcome(custom_data, active_attempt, COMBINED_ORACLE, "not-achieved",
                            "WEBEEBLOCKS_COMBINED_RESULT");
            combined_reported = 1;
            continue;
          }
        }
      }
    }

    if (!memory_reported) {
      if (position[2] >= origin_z + COMBINED_AIRBORNE_DELTA)
        memory_airborne_seen = 1;
      if (memory_airborne_seen && !memory_station_seen &&
          near_xy(position, MEMORY_STATION_X, MEMORY_STATION_Y, MEMORY_STATION_TOLERANCE)) {
        memory_station_seen = 1;
        printf("WEBEEBLOCKS_MEMORY_STATION attempt=%llu\n", active_attempt);
        fflush(stdout);
      }
      if (memory_station_seen && !memory_panel_hidden &&
          position[0] >= MEMORY_PANEL_HIDE_X &&
          fabs(position[1] - MEMORY_STATION_Y) <= MEMORY_STATION_TOLERANCE) {
        memory_panel_position[2] = MEMORY_PANEL_HIDDEN_Z;
        wb_supervisor_field_set_sf_vec3f(memory_panel_translation, memory_panel_position);
        memory_panel_hidden = 1;
        printf("WEBEEBLOCKS_MEMORY_REFERENCE_UNAVAILABLE attempt=%llu\n", active_attempt);
        fflush(stdout);
      }
      if (memory_panel_hidden && !memory_first_decision_seen &&
          near_xy(position, MEMORY_DECISION_1_X, MEMORY_CENTER_Y, MEMORY_ROUTE_TOLERANCE)) {
        memory_first_decision_seen = 1;
        printf("WEBEEBLOCKS_MEMORY_DECISION attempt=%llu index=1\n", active_attempt);
        fflush(stdout);
      }
      if (memory_first_decision_seen && !memory_first_valid_route_seen && !memory_wrong_route_seen) {
        const int on_left = near_xy(position, MEMORY_DECISION_1_X, MEMORY_LEFT_Y, MEMORY_ROUTE_TOLERANCE);
        const int on_right = near_xy(position, MEMORY_DECISION_1_X, MEMORY_RIGHT_Y, MEMORY_ROUTE_TOLERANCE);
        if (on_left || on_right) {
          const enum MemoryRoute selected = on_left ? MEMORY_ROUTE_LEFT : MEMORY_ROUTE_RIGHT;
          const MemoryPattern *pattern = &MEMORY_PATTERNS[memory_pattern_index];
          if (selected == pattern->first_route) {
            memory_first_valid_route_seen = 1;
            printf("WEBEEBLOCKS_MEMORY_ROUTE attempt=%llu index=1 route=%s valid=1\n",
                   active_attempt, memory_route_name(selected));
          } else {
            memory_wrong_route_seen = 1;
            printf("WEBEEBLOCKS_MEMORY_ROUTE attempt=%llu index=1 route=%s valid=0\n",
                   active_attempt, memory_route_name(selected));
          }
          fflush(stdout);
        }
      }
      if (memory_first_valid_route_seen && !memory_second_decision_seen &&
          near_xy(position, MEMORY_DECISION_2_X, MEMORY_CENTER_Y, MEMORY_ROUTE_TOLERANCE)) {
        memory_second_decision_seen = 1;
        printf("WEBEEBLOCKS_MEMORY_DECISION attempt=%llu index=2\n", active_attempt);
        fflush(stdout);
      }
      if (memory_second_decision_seen && !memory_second_valid_route_seen && !memory_wrong_route_seen) {
        const int on_left = near_xy(position, MEMORY_DECISION_2_X, MEMORY_LEFT_Y, MEMORY_ROUTE_TOLERANCE);
        const int on_right = near_xy(position, MEMORY_DECISION_2_X, MEMORY_RIGHT_Y, MEMORY_ROUTE_TOLERANCE);
        if (on_left || on_right) {
          const enum MemoryRoute selected = on_left ? MEMORY_ROUTE_LEFT : MEMORY_ROUTE_RIGHT;
          const MemoryPattern *pattern = &MEMORY_PATTERNS[memory_pattern_index];
          if (selected == pattern->second_route) {
            memory_second_valid_route_seen = 1;
            printf("WEBEEBLOCKS_MEMORY_ROUTE attempt=%llu index=2 route=%s valid=1\n",
                   active_attempt, memory_route_name(selected));
          } else {
            memory_wrong_route_seen = 1;
            printf("WEBEEBLOCKS_MEMORY_ROUTE attempt=%llu index=2 route=%s valid=0\n",
                   active_attempt, memory_route_name(selected));
          }
          fflush(stdout);
        }
      }

      unsigned long long memory_failure_attempt = 0;
      if (parse_oracle_message(data, "FAILURE_PROBE", MEMORY_ORACLE, &memory_failure_attempt) &&
          memory_failure_attempt == active_attempt && memory_wrong_route_seen) {
        publish_outcome(custom_data, active_attempt, MEMORY_ORACLE, "not-achieved",
                        "WEBEEBLOCKS_MEMORY_RESULT");
        memory_reported = 1;
      } else if (!memory_completion_seen) {
        unsigned long long completed_attempt = 0;
        if (parse_oracle_message(data, "COMPLETION", MEMORY_ORACLE, &completed_attempt) &&
            completed_attempt == active_attempt) {
          memory_completion_seen = 1;
          memory_completion_time = wb_robot_get_time();
        }
      }

      if (!memory_reported && memory_completion_seen) {
        if (memory_wrong_route_seen) {
          publish_outcome(custom_data, active_attempt, MEMORY_ORACLE, "not-achieved",
                          "WEBEEBLOCKS_MEMORY_RESULT");
          memory_reported = 1;
        } else {
          const double horizontal_speed = hypot(velocity[0], velocity[1]);
          const double vertical_speed = fabs(velocity[2]);
          const int landed = position[2] <= origin_z + MEMORY_LANDED_DELTA;
          const int stationary = horizontal_speed <= MEMORY_MAX_LANDING_SPEED &&
                                 vertical_speed <= MEMORY_MAX_LANDING_SPEED;
          const int in_arrival = near_xy(position, MEMORY_ARRIVAL_X, MEMORY_ARRIVAL_Y,
                                         MEMORY_ARRIVAL_TOLERANCE);
          const int achieved = memory_airborne_seen && memory_station_seen && memory_panel_hidden &&
                               memory_first_decision_seen && memory_first_valid_route_seen &&
                               memory_second_decision_seen && memory_second_valid_route_seen &&
                               landed && stationary && in_arrival;
          if (achieved) {
            publish_outcome(custom_data, active_attempt, MEMORY_ORACLE, "achieved",
                            "WEBEEBLOCKS_MEMORY_RESULT");
            memory_reported = 1;
          } else if (wb_robot_get_time() - memory_completion_time >= MEMORY_SETTLE_TIMEOUT) {
            printf("WEBEEBLOCKS_MEMORY_TIMEOUT attempt=%llu station=%d hidden=%d first=%d first_route=%d second=%d second_route=%d x=%.6f y=%.6f z=%.6f landed=%d stationary=%d arrival=%d\n",
                   active_attempt, memory_station_seen, memory_panel_hidden,
                   memory_first_decision_seen, memory_first_valid_route_seen,
                   memory_second_decision_seen, memory_second_valid_route_seen,
                   position[0], position[1], position[2], landed, stationary, in_arrival);
            fflush(stdout);
            publish_outcome(custom_data, active_attempt, MEMORY_ORACLE, "not-achieved",
                            "WEBEEBLOCKS_MEMORY_RESULT");
            memory_reported = 1;
          }
        }
      }
    }
  }

  wb_robot_cleanup();
  return 0;
}

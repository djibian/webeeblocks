#include <math.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <webots/contact_point.h>
#include <webots/robot.h>
#include <webots/supervisor.h>

#define AUTONOMOUS_ORACLE "progression-autonomous-strategy-v1"
#define AUTONOMOUS_PATTERN_COUNT 4
#define AUTONOMOUS_AIRBORNE_DELTA 0.20
#define AUTONOMOUS_LANDED_DELTA 0.07
#define AUTONOMOUS_MAX_LANDING_SPEED 0.12
#define AUTONOMOUS_SETTLE_TIMEOUT 1.5
#define AUTONOMOUS_STATION_X 0.0
#define AUTONOMOUS_STATION_Y -1.50
#define AUTONOMOUS_STATION_TOLERANCE 0.13
#define AUTONOMOUS_REFERENCE_HIDE_X 0.12
#define AUTONOMOUS_CENTER_Y -2.50
#define AUTONOMOUS_LEFT_Y -2.15
#define AUTONOMOUS_RIGHT_Y -2.85
#define AUTONOMOUS_ROW1_X 0.50
#define AUTONOMOUS_ROW2_X 0.80
#define AUTONOMOUS_JUNCTION_X 0.80
#define AUTONOMOUS_ROUTE_X 1.10
#define AUTONOMOUS_FINAL_X 1.40
#define AUTONOMOUS_ROUTE_TOLERANCE 0.11
#define AUTONOMOUS_FINAL_TOLERANCE 0.12
#define AUTONOMOUS_BARRIER_Z 0.55
#define AUTONOMOUS_HIDDEN_Z -1.00
#define AUTONOMOUS_COLLISION_HEIGHT_DELTA 0.08

enum AutonomousRoute {
  AUTONOMOUS_ROUTE_FORWARD = 0,
  AUTONOMOUS_ROUTE_LEFT = 1,
  AUTONOMOUS_ROUTE_RIGHT = 2
};

typedef struct {
  int small_parcel;
  int row1_blocked;
  int row2_blocked;
  enum AutonomousRoute junction_route;
  const char *name;
} AutonomousPattern;

static const AutonomousPattern AUTONOMOUS_PATTERNS[AUTONOMOUS_PATTERN_COUNT] = {
  {1, 1, 0, AUTONOMOUS_ROUTE_FORWARD, "small-BE-forward"},
  {0, 0, 1, AUTONOMOUS_ROUTE_LEFT,    "large-EB-left"},
  {1, 1, 1, AUTONOMOUS_ROUTE_RIGHT,   "small-BB-right"},
  {0, 0, 0, AUTONOMOUS_ROUTE_FORWARD, "large-EE-forward"}
};

static const char *route_name(enum AutonomousRoute route) {
  switch (route) {
    case AUTONOMOUS_ROUTE_FORWARD:
      return "forward";
    case AUTONOMOUS_ROUTE_LEFT:
      return "left";
    case AUTONOMOUS_ROUTE_RIGHT:
      return "right";
  }
  return "unknown";
}

static int parse_attempt(const char *data, unsigned long long *attempt) {
  if (!data || !attempt)
    return 0;
  char trailing[2] = {0};
  return sscanf(data, "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu %1s", attempt, trailing) == 1;
}

static int parse_oracle_message(const char *data,
                                const char *kind,
                                unsigned long long *attempt) {
  if (!data || !kind || !attempt)
    return 0;
  char oracle[64] = {0};
  char trailing[2] = {0};
  char pattern[128] = {0};
  snprintf(pattern, sizeof(pattern),
           "WEBEEBLOCKS_ACTIVITY_%s_V1 attempt=%%llu oracle=%%63s %%1s", kind);
  if (sscanf(data, pattern, attempt, oracle, trailing) != 2)
    return 0;
  return strcmp(oracle, AUTONOMOUS_ORACLE) == 0;
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

static void publish_outcome(WbFieldRef custom_data,
                            unsigned long long attempt,
                            const char *status) {
  char result[192];
  snprintf(result, sizeof(result),
           "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=%s",
           attempt, AUTONOMOUS_ORACLE, status);
  wb_supervisor_field_set_sf_string(custom_data, result);
  printf("WEBEEBLOCKS_AUTONOMOUS_RESULT attempt=%llu status=%s\n", attempt, status);
  fflush(stdout);
}

static int import_autonomous_world(WbNodeRef root,
                                   WbFieldRef barrier_fields[7]) {
  WbFieldRef children = wb_supervisor_node_get_field(root, "children");
  if (!children)
    return 0;
  const char *nodes[] = {
    "DEF ACTIVITY8_FLOOR_EXTENSION Solid { translation 0.80 -2.50 -0.025 name \"Activity 8 autonomous warehouse floor\" children [ Shape { appearance PBRAppearance { baseColor 0.65 0.68 0.72 roughness 0.8 } geometry Box { size 2.00 1.20 0.05 } } ] boundingObject Box { size 2.00 1.20 0.05 } }",
    "DEF ACTIVITY8_ROW1_FORWARD_PAD Pose { translation 0.50 -2.50 0.002 children [ Shape { appearance PBRAppearance { baseColor 0.90 0.72 0.12 transparency 0.22 roughness 0.9 } geometry Box { size 0.18 0.18 0.004 } } ] }",
    "DEF ACTIVITY8_ROW1_DETOUR_PAD Pose { translation 0.50 -2.15 0.002 children [ Shape { appearance PBRAppearance { baseColor 0.90 0.72 0.12 transparency 0.22 roughness 0.9 } geometry Box { size 0.18 0.18 0.004 } } ] }",
    "DEF ACTIVITY8_ROW2_FORWARD_PAD Pose { translation 0.80 -2.50 0.002 children [ Shape { appearance PBRAppearance { baseColor 0.90 0.72 0.12 transparency 0.22 roughness 0.9 } geometry Box { size 0.18 0.18 0.004 } } ] }",
    "DEF ACTIVITY8_ROW2_DETOUR_PAD Pose { translation 0.80 -2.15 0.002 children [ Shape { appearance PBRAppearance { baseColor 0.90 0.72 0.12 transparency 0.22 roughness 0.9 } geometry Box { size 0.18 0.18 0.004 } } ] }",
    "DEF ACTIVITY8_JUNCTION_PAD Pose { translation 0.80 -2.50 0.003 children [ Shape { appearance PBRAppearance { baseColor 0.22 0.48 0.88 transparency 0.20 roughness 0.9 } geometry Box { size 0.20 0.20 0.004 } } ] }",
    "DEF ACTIVITY8_FORWARD_ROUTE_PAD Pose { translation 1.10 -2.50 0.002 children [ Shape { appearance PBRAppearance { baseColor 0.10 0.66 0.92 transparency 0.16 roughness 0.9 } geometry Box { size 0.18 0.18 0.004 } } ] }",
    "DEF ACTIVITY8_LEFT_ROUTE_PAD Pose { translation 1.10 -2.15 0.002 children [ Shape { appearance PBRAppearance { baseColor 0.10 0.66 0.92 transparency 0.16 roughness 0.9 } geometry Box { size 0.18 0.18 0.004 } } ] }",
    "DEF ACTIVITY8_RIGHT_ROUTE_PAD Pose { translation 1.10 -2.85 0.002 children [ Shape { appearance PBRAppearance { baseColor 0.10 0.66 0.92 transparency 0.16 roughness 0.9 } geometry Box { size 0.18 0.18 0.004 } } ] }",
    "DEF ACTIVITY8_SMALL_DELIVERY_PAD Pose { translation 1.40 -2.15 0.002 children [ Shape { appearance PBRAppearance { baseColor 0.10 0.72 0.28 transparency 0.10 roughness 0.9 } geometry Box { size 0.26 0.26 0.004 } } ] }",
    "DEF ACTIVITY8_LARGE_DELIVERY_PAD Pose { translation 1.40 -2.85 0.002 children [ Shape { appearance PBRAppearance { baseColor 0.92 0.52 0.08 transparency 0.10 roughness 0.9 } geometry Box { size 0.26 0.26 0.004 } } ] }",
    "DEF ACTIVITY8_ROW1_CENTER_BARRIER Solid { translation 0.45 -2.50 -1.00 name \"Activity 8 row 1 forward blocker\" children [ Shape { appearance PBRAppearance { baseColor 0.88 0.24 0.08 roughness 0.55 } geometry Box { size 0.14 0.14 1.10 } } ] boundingObject Box { size 0.14 0.14 1.10 } }",
    "DEF ACTIVITY8_ROW1_LEFT_BARRIER Solid { translation 0.35 -2.15 -1.00 name \"Activity 8 row 1 detour blocker\" children [ Shape { appearance PBRAppearance { baseColor 0.88 0.24 0.08 roughness 0.55 } geometry Box { size 0.14 0.14 1.10 } } ] boundingObject Box { size 0.14 0.14 1.10 } }",
    "DEF ACTIVITY8_ROW2_CENTER_BARRIER Solid { translation 0.75 -2.50 -1.00 name \"Activity 8 row 2 forward blocker\" children [ Shape { appearance PBRAppearance { baseColor 0.88 0.24 0.08 roughness 0.55 } geometry Box { size 0.14 0.14 1.10 } } ] boundingObject Box { size 0.14 0.14 1.10 } }",
    "DEF ACTIVITY8_ROW2_LEFT_BARRIER Solid { translation 0.65 -2.15 -1.00 name \"Activity 8 row 2 detour blocker\" children [ Shape { appearance PBRAppearance { baseColor 0.88 0.24 0.08 roughness 0.55 } geometry Box { size 0.14 0.14 1.10 } } ] boundingObject Box { size 0.14 0.14 1.10 } }",
    "DEF ACTIVITY8_JUNCTION_FRONT_BARRIER Solid { translation 1.05 -2.50 -1.00 name \"Activity 8 junction front blocker\" children [ Shape { appearance PBRAppearance { baseColor 0.84 0.16 0.10 roughness 0.55 } geometry Box { size 0.14 0.14 1.10 } } ] boundingObject Box { size 0.14 0.14 1.10 } }",
    "DEF ACTIVITY8_JUNCTION_LEFT_BARRIER Solid { translation 0.80 -2.15 -1.00 name \"Activity 8 junction left blocker\" children [ Shape { appearance PBRAppearance { baseColor 0.84 0.16 0.10 roughness 0.55 } geometry Box { size 0.14 0.14 1.10 } } ] boundingObject Box { size 0.14 0.14 1.10 } }",
    "DEF ACTIVITY8_JUNCTION_RIGHT_BARRIER Solid { translation 0.80 -2.85 -1.00 name \"Activity 8 junction right blocker\" children [ Shape { appearance PBRAppearance { baseColor 0.84 0.16 0.10 roughness 0.55 } geometry Box { size 0.14 0.14 1.10 } } ] boundingObject Box { size 0.14 0.14 1.10 } }"
  };
  const int count = (int)(sizeof(nodes) / sizeof(nodes[0]));
  for (int index = 0; index < count; ++index)
    wb_supervisor_field_import_mf_node_from_string(children, -1, nodes[index]);

  const char *barrier_defs[7] = {
    "ACTIVITY8_ROW1_CENTER_BARRIER",
    "ACTIVITY8_ROW1_LEFT_BARRIER",
    "ACTIVITY8_ROW2_CENTER_BARRIER",
    "ACTIVITY8_ROW2_LEFT_BARRIER",
    "ACTIVITY8_JUNCTION_FRONT_BARRIER",
    "ACTIVITY8_JUNCTION_LEFT_BARRIER",
    "ACTIVITY8_JUNCTION_RIGHT_BARRIER"
  };
  for (int index = 0; index < 7; ++index) {
    WbNodeRef node = wb_supervisor_node_get_from_def(barrier_defs[index]);
    if (!node)
      return 0;
    barrier_fields[index] = wb_supervisor_node_get_field(node, "translation");
    if (!barrier_fields[index])
      return 0;
  }
  return 1;
}

static void set_barrier(WbFieldRef field, double x, double y, int blocked) {
  double translation[3] = {x, y, blocked ? AUTONOMOUS_BARRIER_Z : AUTONOMOUS_HIDDEN_Z};
  wb_supervisor_field_set_sf_vec3f(field, translation);
}

static enum AutonomousRoute observed_route(const double *position) {
  if (near_xy(position, AUTONOMOUS_ROUTE_X, AUTONOMOUS_LEFT_Y, AUTONOMOUS_ROUTE_TOLERANCE))
    return AUTONOMOUS_ROUTE_LEFT;
  if (near_xy(position, AUTONOMOUS_ROUTE_X, AUTONOMOUS_RIGHT_Y, AUTONOMOUS_ROUTE_TOLERANCE))
    return AUTONOMOUS_ROUTE_RIGHT;
  return AUTONOMOUS_ROUTE_FORWARD;
}

int webeeblocks_progression_autonomous_evaluator_main(void) {
  wb_robot_init();
  const int step = (int)wb_robot_get_basic_time_step();
  WbNodeRef root = wb_supervisor_node_get_root();
  WbNodeRef crazyflie = find_named_node(root, "Crazyflie WebeeBlocks");
  WbFieldRef barrier_fields[7] = {0};
  if (!crazyflie || !import_autonomous_world(root, barrier_fields)) {
    fprintf(stderr, "WEBEEBLOCKS_AUTONOMOUS_EVALUATOR_ERROR missing Crazyflie or Activity 8 mission node\n");
    wb_robot_cleanup();
    return 2;
  }
  WbFieldRef custom_data = wb_supervisor_node_get_field(crazyflie, "customData");
  const double *initial = wb_supervisor_node_get_position(crazyflie);
  if (!custom_data || !initial) {
    fprintf(stderr, "WEBEEBLOCKS_AUTONOMOUS_EVALUATOR_ERROR missing mission fields\n");
    wb_robot_cleanup();
    return 2;
  }
  const double origin_z = initial[2];
  wb_supervisor_node_enable_contact_points_tracking(crazyflie, step, true);

  unsigned long long active_attempt = 0;
  int has_attempt = 0;
  int pattern_index = 0;
  int airborne_seen = 0;
  int station_seen = 0;
  int reference_unavailable = 0;
  int row_progress = 0;
  int wrong_route_seen = 0;
  int junction_decision_seen = 0;
  int junction_valid_route_seen = 0;
  int collision_seen = 0;
  int completion_seen = 0;
  double completion_time = 0.0;
  int reported = 0;

  printf("WEBEEBLOCKS_AUTONOMOUS_EVALUATOR_READY patterns=%d corridor_y=%.3f\n",
         AUTONOMOUS_PATTERN_COUNT, AUTONOMOUS_CENTER_Y);
  fflush(stdout);

  while (wb_robot_step(step) != -1) {
    const char *data = wb_supervisor_field_get_sf_string(custom_data);
    unsigned long long observed_attempt = 0;
    if (parse_attempt(data, &observed_attempt) && (!has_attempt || observed_attempt != active_attempt)) {
      active_attempt = observed_attempt;
      has_attempt = 1;
      const unsigned long long normalized = active_attempt > 0 ? active_attempt - 1ULL : 0ULL;
      pattern_index = (int)(normalized % AUTONOMOUS_PATTERN_COUNT);
      const AutonomousPattern *pattern = &AUTONOMOUS_PATTERNS[pattern_index];

      set_barrier(barrier_fields[0], 0.45, AUTONOMOUS_CENTER_Y, pattern->row1_blocked);
      set_barrier(barrier_fields[1], 0.35, AUTONOMOUS_LEFT_Y, !pattern->row1_blocked);
      set_barrier(barrier_fields[2], 0.75, AUTONOMOUS_CENTER_Y, pattern->row2_blocked);
      set_barrier(barrier_fields[3], 0.65, AUTONOMOUS_LEFT_Y, !pattern->row2_blocked);
      set_barrier(barrier_fields[4], 1.05, AUTONOMOUS_CENTER_Y,
                  pattern->junction_route != AUTONOMOUS_ROUTE_FORWARD);
      set_barrier(barrier_fields[5], AUTONOMOUS_JUNCTION_X, AUTONOMOUS_LEFT_Y,
                  pattern->junction_route != AUTONOMOUS_ROUTE_LEFT);
      set_barrier(barrier_fields[6], AUTONOMOUS_JUNCTION_X, AUTONOMOUS_RIGHT_Y,
                  pattern->junction_route != AUTONOMOUS_ROUTE_RIGHT);

      airborne_seen = 0;
      station_seen = 0;
      reference_unavailable = 0;
      row_progress = 0;
      wrong_route_seen = 0;
      junction_decision_seen = 0;
      junction_valid_route_seen = 0;
      collision_seen = 0;
      completion_seen = 0;
      completion_time = 0.0;
      reported = 0;

      printf("WEBEEBLOCKS_AUTONOMOUS_CONFIG attempt=%llu pattern=%s parcel=%s row1=%s row2=%s junction=%s\n",
             active_attempt, pattern->name, pattern->small_parcel ? "small" : "large",
             pattern->row1_blocked ? "blocked" : "open",
             pattern->row2_blocked ? "blocked" : "open",
             route_name(pattern->junction_route));
      fflush(stdout);
    }
    if (!has_attempt || reported)
      continue;

    const double *position = wb_supervisor_node_get_position(crazyflie);
    const double *velocity = wb_supervisor_node_get_velocity(crazyflie);
    if (!position || !velocity)
      continue;

    if (position[2] >= origin_z + AUTONOMOUS_AIRBORNE_DELTA)
      airborne_seen = 1;
    if (airborne_seen && !station_seen &&
        near_xy(position, AUTONOMOUS_STATION_X, AUTONOMOUS_STATION_Y,
                AUTONOMOUS_STATION_TOLERANCE)) {
      station_seen = 1;
      printf("WEBEEBLOCKS_AUTONOMOUS_STATION attempt=%llu\n", active_attempt);
      fflush(stdout);
    }
    if (station_seen && !reference_unavailable && position[0] >= AUTONOMOUS_REFERENCE_HIDE_X) {
      reference_unavailable = 1;
      printf("WEBEEBLOCKS_AUTONOMOUS_REFERENCE_UNAVAILABLE attempt=%llu\n", active_attempt);
      fflush(stdout);
    }

    int contact_count = 0;
    WbContactPoint *contacts = wb_supervisor_node_get_contact_points(crazyflie, true, &contact_count);
    for (int index = 0; index < contact_count && !collision_seen; ++index) {
      if (contacts[index].point[2] > origin_z + AUTONOMOUS_COLLISION_HEIGHT_DELTA) {
        collision_seen = 1;
        printf("WEBEEBLOCKS_AUTONOMOUS_COLLISION attempt=%llu x=%.6f y=%.6f z=%.6f\n",
               active_attempt, contacts[index].point[0], contacts[index].point[1], contacts[index].point[2]);
        fflush(stdout);
      }
    }

    const AutonomousPattern *pattern = &AUTONOMOUS_PATTERNS[pattern_index];
    if (reference_unavailable && row_progress == 0 && !wrong_route_seen) {
      const int forward = near_xy(position, AUTONOMOUS_ROW1_X, AUTONOMOUS_CENTER_Y,
                                  AUTONOMOUS_ROUTE_TOLERANCE);
      const int detour = near_xy(position, AUTONOMOUS_ROW1_X, AUTONOMOUS_LEFT_Y,
                                 AUTONOMOUS_ROUTE_TOLERANCE);
      if (forward || detour) {
        const int valid = pattern->row1_blocked ? detour : forward;
        if (valid) {
          row_progress = 1;
          printf("WEBEEBLOCKS_AUTONOMOUS_ROW attempt=%llu index=1 route=%s valid=1\n",
                 active_attempt, detour ? "left" : "forward");
        } else {
          wrong_route_seen = 1;
          printf("WEBEEBLOCKS_AUTONOMOUS_ROW attempt=%llu index=1 route=%s valid=0\n",
                 active_attempt, detour ? "left" : "forward");
        }
        fflush(stdout);
      }
    }

    if (row_progress == 1 && !wrong_route_seen) {
      const int forward = near_xy(position, AUTONOMOUS_ROW2_X, AUTONOMOUS_CENTER_Y,
                                  AUTONOMOUS_ROUTE_TOLERANCE);
      const int detour = near_xy(position, AUTONOMOUS_ROW2_X, AUTONOMOUS_LEFT_Y,
                                 AUTONOMOUS_ROUTE_TOLERANCE);
      if (forward || detour) {
        const int valid = pattern->row2_blocked ? detour : forward;
        if (valid) {
          row_progress = 2;
          printf("WEBEEBLOCKS_AUTONOMOUS_ROW attempt=%llu index=2 route=%s valid=1\n",
                 active_attempt, detour ? "left" : "forward");
        } else {
          wrong_route_seen = 1;
          printf("WEBEEBLOCKS_AUTONOMOUS_ROW attempt=%llu index=2 route=%s valid=0\n",
                 active_attempt, detour ? "left" : "forward");
        }
        fflush(stdout);
      }
    }

    if (row_progress == 2 && !junction_decision_seen &&
        near_xy(position, AUTONOMOUS_JUNCTION_X, AUTONOMOUS_CENTER_Y,
                AUTONOMOUS_ROUTE_TOLERANCE)) {
      junction_decision_seen = 1;
      printf("WEBEEBLOCKS_AUTONOMOUS_JUNCTION attempt=%llu\n", active_attempt);
      fflush(stdout);
    }

    if (junction_decision_seen && !junction_valid_route_seen && !wrong_route_seen) {
      const int on_forward = near_xy(position, AUTONOMOUS_ROUTE_X, AUTONOMOUS_CENTER_Y,
                                     AUTONOMOUS_ROUTE_TOLERANCE);
      const int on_left = near_xy(position, AUTONOMOUS_ROUTE_X, AUTONOMOUS_LEFT_Y,
                                  AUTONOMOUS_ROUTE_TOLERANCE);
      const int on_right = near_xy(position, AUTONOMOUS_ROUTE_X, AUTONOMOUS_RIGHT_Y,
                                   AUTONOMOUS_ROUTE_TOLERANCE);
      if (on_forward || on_left || on_right) {
        enum AutonomousRoute selected = observed_route(position);
        if (selected == pattern->junction_route) {
          junction_valid_route_seen = 1;
          printf("WEBEEBLOCKS_AUTONOMOUS_ROUTE attempt=%llu route=%s valid=1\n",
                 active_attempt, route_name(selected));
        } else {
          wrong_route_seen = 1;
          printf("WEBEEBLOCKS_AUTONOMOUS_ROUTE attempt=%llu route=%s valid=0\n",
                 active_attempt, route_name(selected));
        }
        fflush(stdout);
      }
    }

    unsigned long long failure_attempt = 0;
    if (parse_oracle_message(data, "FAILURE_PROBE", &failure_attempt) &&
        failure_attempt == active_attempt && (collision_seen || wrong_route_seen)) {
      publish_outcome(custom_data, active_attempt, "not-achieved");
      reported = 1;
      continue;
    }

    if (!completion_seen) {
      unsigned long long completed_attempt = 0;
      if (parse_oracle_message(data, "COMPLETION", &completed_attempt) &&
          completed_attempt == active_attempt) {
        completion_seen = 1;
        completion_time = wb_robot_get_time();
      }
    }

    if (!reported && completion_seen) {
      if (collision_seen || wrong_route_seen) {
        publish_outcome(custom_data, active_attempt, "not-achieved");
        reported = 1;
        continue;
      }
      const double horizontal_speed = hypot(velocity[0], velocity[1]);
      const double vertical_speed = fabs(velocity[2]);
      const int landed = position[2] <= origin_z + AUTONOMOUS_LANDED_DELTA;
      const int stationary = horizontal_speed <= AUTONOMOUS_MAX_LANDING_SPEED &&
                             vertical_speed <= AUTONOMOUS_MAX_LANDING_SPEED;
      const double final_y = pattern->small_parcel ? AUTONOMOUS_LEFT_Y : AUTONOMOUS_RIGHT_Y;
      const int in_final_bay = near_xy(position, AUTONOMOUS_FINAL_X, final_y,
                                       AUTONOMOUS_FINAL_TOLERANCE);
      const int achieved = airborne_seen && station_seen && reference_unavailable &&
                           row_progress == 2 && junction_decision_seen &&
                           junction_valid_route_seen && landed && stationary && in_final_bay;
      if (achieved) {
        publish_outcome(custom_data, active_attempt, "achieved");
        reported = 1;
      } else if (wb_robot_get_time() - completion_time >= AUTONOMOUS_SETTLE_TIMEOUT) {
        printf("WEBEEBLOCKS_AUTONOMOUS_TIMEOUT attempt=%llu station=%d unavailable=%d rows=%d junction=%d route=%d collision=%d wrong=%d x=%.6f y=%.6f z=%.6f landed=%d stationary=%d final=%d\n",
               active_attempt, station_seen, reference_unavailable, row_progress,
               junction_decision_seen, junction_valid_route_seen, collision_seen, wrong_route_seen,
               position[0], position[1], position[2], landed, stationary, in_final_bay);
        fflush(stdout);
        publish_outcome(custom_data, active_attempt, "not-achieved");
        reported = 1;
      }
    }
  }

  wb_robot_cleanup();
  return 0;
}

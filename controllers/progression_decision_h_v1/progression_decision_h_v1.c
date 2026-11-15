/* Activity 4: independent Webots R2025a classroom mission observer.
 * NEVER linked into shared flight runtime or any real Crazyflie binary.
 * This process cannot fly the vehicle. It can only attest, observe and report.
 * Real range-sensor pupil behavior and physical flight remain unqualified.
 */
#include "decision_core.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <webots/contact_point.h>
#include <webots/robot.h>
#include <webots/supervisor.h>

#define WB_DH_CRAFT "Crazyflie WebeeBlocks"
#define WB_DH_OBSERVER "Progression decision H native evaluator"
#define WB_DH_CONTROLLER "progression_decision_h_v1"
#define WB_DH_CHILDREN 29 /* 23 Pose markers + six physical Solid obstacles. */
#define WB_DH_COLLIDERS 6
static const char *const kDhColliderNames[WB_DH_COLLIDERS] = {
  "H_LEFT", "H_RIGHT", "H_BAR", "THRESHOLD", "CORRIDOR_LEFT", "CORRIDOR_RIGHT"
};

typedef struct {
  const char *def;
  double p[3];
  double box[3];
} expected_box;

static int near(double a, double b) {
  return isfinite(a) && fabs(a - b) <= 0.000001;
}

static int box_matches(const expected_box *expected) {
  WbNodeRef node = wb_supervisor_node_get_from_def(expected->def);
  const char *type = node ? wb_supervisor_node_get_type_name(node) : NULL;
  if (!type || strcmp(type, "Solid"))
    return 0;
  const double *p = wb_supervisor_node_get_position(node);
  const double *orientation = wb_supervisor_node_get_orientation(node);
  WbFieldRef bounding = wb_supervisor_node_get_field(node, "boundingObject");
  WbNodeRef geometry = bounding ? wb_supervisor_field_get_sf_node(bounding) : NULL;
  const char *shape = geometry ? wb_supervisor_node_get_type_name(geometry) : NULL;
  if (!shape || strcmp(shape, "Box"))
    return 0;
  WbFieldRef size_field = wb_supervisor_node_get_field(geometry, "size");
  const double *size = size_field ? wb_supervisor_field_get_sf_vec3f(size_field) : NULL;
  if (!p || !size || !orientation) return 0;
  for (int i = 0; i < 3; ++i)
    if (!near(p[i], expected->p[i]) || !near(size[i], expected->box[i]) ||
        size[i] <= 0.0) return 0;
  for (int i = 0; i < 9; ++i)
    if (!near(orientation[i], i % 4 == 0 ? 1.0 : 0.0)) return 0;
  return 1;
}

static int field_string_is(WbNodeRef node, const char *field, const char *value) {
  WbFieldRef f = node ? wb_supervisor_node_get_field(node, field) : NULL;
  const char *actual = f ? wb_supervisor_field_get_sf_string(f) : NULL;
  return actual && strcmp(actual, value) == 0;
}

static int valid_observer(WbNodeRef scene) {
  WbFieldRef children = wb_supervisor_node_get_field(scene, "children");
  if (!children || wb_supervisor_field_get_count(children) != WB_DH_CHILDREN)
    return 0;
  for (int i = 0; i < WB_DH_CHILDREN; ++i) {
    WbNodeRef child = wb_supervisor_field_get_mf_node(children, i);
    if (!child) return 0;
    const char *type = wb_supervisor_node_get_type_name(child);
    if (!type || (i < 23 ? strcmp(type, "Pose") : strcmp(type, "Solid")))
      return 0;
    if (i >= 23) continue;
    WbFieldRef nested = wb_supervisor_node_get_field(child, "children");
    const int count = nested ? wb_supervisor_field_get_count(nested) : -1;
    if (count != (i == 0 ? 2 : 1)) return 0;
    WbNodeRef marker = wb_supervisor_field_get_mf_node(nested, 0);
    const char *marker_type = marker ? wb_supervisor_node_get_type_name(marker) : NULL;
    if (!marker_type || strcmp(marker_type, "Shape"))
      return 0;
    if (i == 0) {
      WbNodeRef observer = wb_supervisor_field_get_mf_node(nested, 1);
      const char *observer_type = observer ? wb_supervisor_node_get_type_name(observer) : NULL;
      if (!observer_type || strcmp(observer_type, "Robot") ||
          !field_string_is(observer, "name", WB_DH_OBSERVER) ||
          !field_string_is(observer, "controller", WB_DH_CONTROLLER))
        return 0;
      WbFieldRef supervisor = wb_supervisor_node_get_field(observer, "supervisor");
      WbFieldRef sync = wb_supervisor_node_get_field(observer, "synchronization");
      if (!supervisor || !sync ||
          !wb_supervisor_field_get_sf_bool(supervisor) ||
          !wb_supervisor_field_get_sf_bool(sync))
        return 0;
    }
  }
  return 1;
}

static int verify_scene(wb_dh_scene *variant) {
  WbNodeRef a = wb_supervisor_node_get_from_def("WEBEEBLOCKS_DECISION_A_SCENE");
  WbNodeRef b = wb_supervisor_node_get_from_def("WEBEEBLOCKS_DECISION_B_SCENE");
  if ((!a && !b) || (a && b) || !variant ||
      wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_SCENE") ||
      wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_EVALUATORS") ||
      wb_supervisor_node_get_from_def("WEBEEBLOCKS_SEQUENCE_SCENE") ||
      wb_supervisor_node_get_from_def("WEBEEBLOCKS_ALTITUDE_SCENE") ||
      wb_supervisor_node_get_from_def("WEBEEBLOCKS_ORIENTATION_SCENE"))
    return 0;
  WbNodeRef world = wb_supervisor_node_get_from_def("WEBEEBLOCKS_CLASSROOM_START_WORLD");
  const char *world_type = world ? wb_supervisor_node_get_type_name(world) : NULL;
  const char *self_name = wb_robot_get_name();
  if (!world_type || strcmp(world_type, "WorldInfo") ||
      !self_name || strcmp(self_name, WB_DH_OBSERVER))
    return 0;
  const wb_dh_scene v = a ? WB_DH_SCENE_A : WB_DH_SCENE_B;
  WbNodeRef group = a ? a : b;
  const char *group_type = wb_supervisor_node_get_type_name(group);
  if (!group_type || strcmp(group_type, "Group") ||
      !valid_observer(group)) return 0;
  const double h_x = v == WB_DH_SCENE_A ? WB_DH_NEAR_X : WB_DH_FAR_X;
  const double curb_x = v == WB_DH_SCENE_A ? WB_DH_FAR_X : WB_DH_NEAR_X;
  const char *prefix = v == WB_DH_SCENE_A ? "ACTIVITY4_A_" : "ACTIVITY4_B_";
  const char *suffix[] = {
    "H_LEFT", "H_RIGHT", "H_BAR", "THRESHOLD", "CORRIDOR_LEFT", "CORRIDOR_RIGHT"
  };
  const double positions[6][3] = {
    {h_x, .300, .500}, {h_x, -.300, .500}, {h_x, 0, .740},
    {curb_x, 0, .350}, {.700, .420, .520}, {.700, -.420, .520}
  };
  const double sizes[6][3] = {
    {.070, .065, 1.00}, {.070, .065, 1.00}, {.070, .570, .240},
    {.100, .740, .700}, {1.80, .080, 1.04}, {1.80, .080, 1.04}
  };
  for (int i = 0; i < 6; ++i) {
    char def[70];
    int size = snprintf(def, sizeof(def), "%s%s", prefix, suffix[i]);
    if (size <= 0 || (size_t)size >= sizeof(def)) return 0;
    expected_box e = {0};
    e.def = def;
    for (int k = 0; k < 3; ++k) {
      e.p[k] = positions[i][k];
      e.box[k] = sizes[i][k];
    }
    if (!box_matches(&e)) return 0;
  }
  *variant = v;
  return 1;
}

static WbNodeRef unique_craft(void) {
  WbNodeRef root = wb_supervisor_node_get_root();
  WbFieldRef children = root ? wb_supervisor_node_get_field(root, "children") : NULL;
  WbNodeRef found = NULL;
  for (int i = 0; children && i < wb_supervisor_field_get_count(children); ++i) {
    WbNodeRef node = wb_supervisor_field_get_mf_node(children, i);
    if (!field_string_is(node, "name", WB_DH_CRAFT)) continue;
    /* The Crazyflie is a PROTO: get_type_name() may expose the PROTO
     * instead of Robot. The unique exact name and native sensor/contact
     * APIs, not a guessed node type string, attest the craft here. */
    if (found || !node) return NULL;
    found = node;
  }
  return found;
}

static int parse_attempt(const char *text, unsigned long long *out) {
  unsigned long long number = 0;
  char extra = '\0';
  if (!text || !out || sscanf(text, "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu%c",
                              &number, &extra) != 1 || number == 0)
    return 0;
  char canonical[100];
  int n = snprintf(canonical, sizeof(canonical),
                   "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu", number);
  if (n <= 0 || (size_t)n >= sizeof(canonical) || strcmp(text, canonical))
    return 0;
  *out = number;
  return 1;
}

static int parse_completion(const char *text, unsigned long long attempt) {
  char canonical[190];
  int n = snprintf(canonical, sizeof(canonical),
      "WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=%llu oracle=%s",
      attempt, WB_DH_ORACLE);
  return text && n > 0 && (size_t)n < sizeof(canonical) &&
         strcmp(text, canonical) == 0;
}

/* An unavailable contact point stream is not permission to pass.
 * The only harmless contact in this attested static world is the z=0 floor;
 * every non-floor contact (including unrecognized geometry) is an obstacle.
 */
static int obstacle_contact(WbNodeRef craft,
                            const WbNodeRef colliders[WB_DH_COLLIDERS]) {
  /* The six attested Solid obstacles extend down to the floor. The
   * Crazyflie's point.z alone does NOT identify the other contacted body:
   * a collision with a post below z=0.025 was previously hidden as floor.
   * Query the actual obstacle-side native contact lists first. */
  for (int j = 0; j < WB_DH_COLLIDERS; ++j) {
    int n = -1;
    const WbContactPoint *hits =
      wb_supervisor_node_get_contact_points(colliders[j], false, &n);
    if (n < 0 || (n > 0 && !hits)) {
      printf("WEBEEBLOCKS_DECISION_H_COLLIDER_CONTACT_UNAVAILABLE type=%s count=%d\n",
             kDhColliderNames[j], n);
      fflush(stdout);
      return -1;
    }
    for (int i = 0; i < n; ++i) {
      const double *p = hits[i].point;
      if (!isfinite(p[0]) || !isfinite(p[1]) || !isfinite(p[2]))
        return -1;
      printf("WEBEEBLOCKS_DECISION_H_COLLIDER_CONTACT type=%s z=%.9f node_id=%d\n",
             kDhColliderNames[j], p[2], hits[i].node_id);
      fflush(stdout);
      return 1;
    }
  }
  /* Preserve the existing fail-closed response to any unknown high
   * craft contact. Only actual floor-height contacts with NO attested
   * collider contact can remain benign during takeoff/landing. */
  int count = -1;
  const WbContactPoint *points = wb_supervisor_node_get_contact_points(craft, true, &count);
  if (count < 0 || (count > 0 && !points)) {
    printf("WEBEEBLOCKS_DECISION_H_CONTACT_UNAVAILABLE count=%d pointer=%d\n",
           count, points != NULL);
    fflush(stdout);
    return -1;
  }
  for (int i = 0; i < count; ++i) {
    const double *p = points[i].point;
    if (!isfinite(p[0]) || !isfinite(p[1]) || !isfinite(p[2])) {
      printf("WEBEEBLOCKS_DECISION_H_CONTACT_NONFINITE index=%d\n", i);
      fflush(stdout);
      return -1;
    }
    if (fabs(p[2]) > 0.025) {
      printf("WEBEEBLOCKS_DECISION_H_CONTACT_NONFLOOR x=%.9f y=%.9f z=%.9f\n",
             p[0], p[1], p[2]);
      fflush(stdout);
      return 1;
    }
  }
  return 0;
}

static void publish(WbFieldRef channel, const wb_dh_mission *m) {
  const char *status = m->verdict == WB_DH_ACHIEVED ? "achieved" : "not-achieved";
  char data[200];
  int n = snprintf(data, sizeof(data),
      "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=%s",
      m->attempt, WB_DH_ORACLE, status);
  if (n <= 0 || (size_t)n >= sizeof(data)) return;
  wb_supervisor_field_set_sf_string(channel, data);
  printf("WEBEEBLOCKS_DECISION_H_RESULT scene=%c attempt=%llu status=%s stage=%u\n",
         m->scene == WB_DH_SCENE_A ? 'A' : 'B', m->attempt,
         status, m->stage);
  fflush(stdout);
}

int main(void) {
  wb_robot_init();
  wb_dh_scene scene = 0;
  const int step = (int)wb_robot_get_basic_time_step();
  /* The continuous 250-ms landing oracle requires consecutive real 32-ms
   * observations (max gap 48 ms). Reject incompatible native cadence before
   * READY, instead of admitting a physically unwinnable mission. */
  if (step != 32 || !verify_scene(&scene)) {
    fprintf(stderr, "WEBEEBLOCKS_DECISION_H_FATAL invalid scene/observer/colliders\n");
    wb_robot_cleanup();
    return 2;
  }
  WbNodeRef craft = unique_craft();
  WbFieldRef channel = craft ? wb_supervisor_node_get_field(craft, "customData") : NULL;
  const double *initial = craft ? wb_supervisor_node_get_position(craft) : NULL;
  if (!channel || !initial || !isfinite(initial[2])) {
    fprintf(stderr, "WEBEEBLOCKS_DECISION_H_FATAL no unambiguous Crazyflie\n");
    wb_robot_cleanup();
    return 2;
  }
  const double origin_z = initial[2];
  WbNodeRef colliders[WB_DH_COLLIDERS] = {0};
  const char *prefix = scene == WB_DH_SCENE_A ? "ACTIVITY4_A_" : "ACTIVITY4_B_";
  for (int j = 0; j < WB_DH_COLLIDERS; ++j) {
    char def[96];
    const int n = snprintf(def, sizeof(def), "%s%s", prefix, kDhColliderNames[j]);
    WbNodeRef obstacle = (n > 0 && (size_t)n < sizeof(def))
      ? wb_supervisor_node_get_from_def(def) : NULL;
    if (!obstacle || wb_supervisor_node_get_id(obstacle) <= 0) {
      fprintf(stderr, "WEBEEBLOCKS_DECISION_H_FATAL missing collider node identity\n");
      wb_robot_cleanup();
      return 2;
    }
    colliders[j] = obstacle;
    wb_supervisor_node_enable_contact_points_tracking(obstacle, step, false);
  }
  wb_supervisor_node_enable_contact_points_tracking(craft, step, true);
  wb_dh_mission mission = {0};
  unsigned long long last_attempt = 0;
  printf("WEBEEBLOCKS_DECISION_H_READY scene=decision-h-%c-v1 oracle=%s\n",
         scene == WB_DH_SCENE_A ? 'a' : 'b', WB_DH_ORACLE);
  fflush(stdout);
  while (wb_robot_step(step) != -1) {
    const char *data = wb_supervisor_field_get_sf_string(channel);
    unsigned long long attempt = 0;
    if (parse_attempt(data, &attempt) && attempt > last_attempt) {
      wb_dh_reset(&mission, attempt, scene, origin_z);
      last_attempt = attempt;
      printf("WEBEEBLOCKS_DECISION_H_ATTEMPT attempt=%llu\n", attempt);
      fflush(stdout);
    }
    if (!last_attempt || mission.verdict != WB_DH_WAIT) continue;
    wb_dh_sample sample = {0};
    sample.time = wb_robot_get_time();
    sample.obstacle_contact = obstacle_contact(craft, colliders);
    sample.completed = parse_completion(data, mission.attempt);
    const double *position = wb_supervisor_node_get_position(craft);
    const double *velocity = wb_supervisor_node_get_velocity(craft);
    if (!position || !velocity) {
      sample.x = NAN;
    } else {
      sample.x = position[0]; sample.y = position[1]; sample.z = position[2];
      sample.vx = velocity[0]; sample.vy = velocity[1]; sample.vz = velocity[2];
    }
    if (mission.last_time < 0.0) {
      printf("WEBEEBLOCKS_DECISION_H_FIRST_SAMPLE attempt=%llu time=%.9f "
             "xyz=%.9f,%.9f,%.9f velocity=%.9f,%.9f,%.9f "
             "contact=%d completed=%d origin_z=%.9f\n",
             mission.attempt, sample.time, sample.x, sample.y, sample.z,
             sample.vx, sample.vy, sample.vz, sample.obstacle_contact,
             sample.completed, origin_z);
      fflush(stdout);
    }
    if (wb_dh_sample_mission(&mission, &sample) != WB_DH_WAIT) {
      printf("WEBEEBLOCKS_DECISION_H_VERDICT_SAMPLE attempt=%llu "
             "time=%.9f xyz=%.9f,%.9f,%.9f "
             "velocity=%.9f,%.9f,%.9f contact=%d completed=%d "
             "stage=%u airborne=%d verdict=%d\n",
             mission.attempt, sample.time, sample.x, sample.y, sample.z,
             sample.vx, sample.vy, sample.vz, sample.obstacle_contact,
             sample.completed, mission.stage, mission.airborne,
             (int)mission.verdict);
      fflush(stdout);
      publish(channel, &mission);
    }
  }
  wb_robot_cleanup();
  return 0;
}

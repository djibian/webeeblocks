/* Activity 2 native scene-only evaluator.
 * No Python interpreter, Blockly inspection, flight command or physical
 * qualification binary mutation. The dedicated Robot exists only in the
 * versioned altitude scene and observes the actual Webots supervisor state.
 */
#include "altitude_core.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <webots/contact_point.h>
#include <webots/robot.h>
#include <webots/supervisor.h>

#define WB_ALT_ID "WEBEEBLOCKS_ALTITUDE_SCENE"
#define WB_ALT_CRAFT_NAME "Crazyflie WebeeBlocks"

static int close_to(double observed, double expected) {
  return isfinite(observed) && fabs(observed - expected) <= 0.000001;
}

static int assert_box(const char *def, const double pos[3],
                      const double size[3]) {
  WbNodeRef node = wb_supervisor_node_get_from_def(def);
  if (!node || strcmp(wb_supervisor_node_get_type_name(node), "Solid") != 0)
    return 0;
  const double *p = wb_supervisor_node_get_position(node);
  if (!p)
    return 0;
  for (int i = 0; i != 3; ++i)
    if (!close_to(p[i], pos[i]))
      return 0;
  WbFieldRef collision = wb_supervisor_node_get_field(node, "boundingObject");
  WbNodeRef geometry = collision ? wb_supervisor_field_get_sf_node(collision) : NULL;
  if (!geometry || strcmp(wb_supervisor_node_get_type_name(geometry), "Box") != 0)
    return 0;
  WbFieldRef dimensions = wb_supervisor_node_get_field(geometry, "size");
  const double *v = dimensions ? wb_supervisor_field_get_sf_vec3f(dimensions) : NULL;
  if (!v)
    return 0;
  for (int i = 0; i != 3; ++i)
    if (!close_to(v[i], size[i]))
      return 0;
  return 1;
}

static int verify_scene(void) {
  WbNodeRef scene = wb_supervisor_node_get_from_def(WB_ALT_ID);
  if (!scene || strcmp(wb_supervisor_node_get_type_name(scene), "Group") != 0)
    return 0;
  WbFieldRef children = wb_supervisor_node_get_field(scene, "children");
  /* Exact cardinality: 18 visual Poses, 4 native solid obstacles.
   * The evaluator Robot is nested in the first Pose to preserve the 22-count.
   */
  if (!children || wb_supervisor_field_get_count(children) != 22)
    return 0;
  for (int i = 0; i != 22; ++i)
    if (!wb_supervisor_field_get_mf_node(children, i))
      return 0;
  if (wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_SCENE") ||
      wb_supervisor_node_get_from_def("WEBEEBLOCKS_SEQUENCE_SCENE"))
    return 0;

  const double canopy_pos[3] = {0.0, 0.0, 0.70};
  const double canopy_size[3] = {0.34, 0.86, 0.08};
  const double barrier_pos[3] = {0.62, 0.0, 0.31};
  const double barrier_size[3] = {0.12, 0.84, 0.62};
  const double left_pos[3] = {0.68, 0.51, 0.425};
  const double right_pos[3] = {0.68, -0.51, 0.425};
  const double wall_size[3] = {1.65, 0.08, 0.85};
  return assert_box("ACTIVITY2_START_CANOPY", canopy_pos, canopy_size) &&
         assert_box("ACTIVITY2_LOW_BARRIER", barrier_pos, barrier_size) &&
         assert_box("ACTIVITY2_LEFT_WALL", left_pos, wall_size) &&
         assert_box("ACTIVITY2_RIGHT_WALL", right_pos, wall_size);
}

static WbNodeRef find_unique_vehicle(void) {
  WbNodeRef root = wb_supervisor_node_get_root();
  WbFieldRef children = root ? wb_supervisor_node_get_field(root, "children") : NULL;
  if (!children)
    return NULL;
  WbNodeRef found = NULL;
  for (int i = 0; i < wb_supervisor_field_get_count(children); ++i) {
    WbNodeRef node = wb_supervisor_field_get_mf_node(children, i);
    WbFieldRef name = node ? wb_supervisor_node_get_field(node, "name") : NULL;
    const char *value = name ? wb_supervisor_field_get_sf_string(name) : NULL;
    if (value && strcmp(value, WB_ALT_CRAFT_NAME) == 0) {
      if (found)
        return NULL;  /* Ambiguity is not authority. */
      found = node;
    }
  }
  return found;
}

static int parse_attempt(const char *data, unsigned long long *out) {
  if (!data || !out)
    return 0;
  unsigned long long parsed = 0;
  char trailing = '\0';
  if (sscanf(data, "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu%c",
             &parsed, &trailing) != 1 || parsed == 0)
    return 0;
  char canonical[96];
  snprintf(canonical, sizeof(canonical),
           "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu", parsed);
  if (strcmp(data, canonical) != 0)
    return 0;
  *out = parsed;
  return 1;
}

static int parse_completion(const char *data, unsigned long long attempt) {
  char canonical[192];
  snprintf(canonical, sizeof(canonical),
           "WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=%llu oracle=%s",
           attempt, WB_ALT_ORACLE);
  return data && strcmp(data, canonical) == 0;
}

static int native_contact_observation(WbNodeRef craft) {
  int count = -1;
  const WbContactPoint *points =
    wb_supervisor_node_get_contact_points(craft, true, &count);
  if (count < 0 || (count > 0 && !points))
    return -1;
  for (int i = 0; i < count; ++i) {
    const int hit = wb_alt_obstacle_point(points[i].point);
    if (hit != 0)
      return hit;
  }
  return 0;
}

static void publish(WbFieldRef channel, unsigned long long attempt,
                    wb_alt_verdict result, const wb_alt_mission *mission) {
  const char *status = result == WB_ALT_ACHIEVED ? "achieved" : "not-achieved";
  char marker[192];
  snprintf(marker, sizeof(marker),
           "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=%s",
           attempt, WB_ALT_ORACLE, status);
  wb_supervisor_field_set_sf_string(channel, marker);
  printf("WEBEEBLOCKS_ALTITUDE_RESULT attempt=%llu status=%s "
         "airborne=%d crossed=%d contact=%d completion=%d\n",
         attempt, status, mission->airborne, mission->crossed_barrier,
         mission->collision_seen, mission->completion_seen);
  fflush(stdout);
}

int main(void) {
  wb_robot_init();
  const int step = (int)wb_robot_get_basic_time_step();
  if (step <= 0 || !verify_scene()) {
    fprintf(stderr, "WEBEEBLOCKS_ALTITUDE_FATAL invalid scene identity or geometry\n");
    wb_robot_cleanup();
    return 2;
  }
  WbNodeRef craft = find_unique_vehicle();
  WbFieldRef channel = craft ? wb_supervisor_node_get_field(craft, "customData") : NULL;
  const double *initial = craft ? wb_supervisor_node_get_position(craft) : NULL;
  if (!channel || !initial || !isfinite(initial[2])) {
    fprintf(stderr, "WEBEEBLOCKS_ALTITUDE_FATAL missing unambiguous vehicle\n");
    wb_robot_cleanup();
    return 2;
  }
  const double origin_z = initial[2];
  wb_supervisor_node_enable_contact_points_tracking(craft, step, true);

  wb_alt_mission mission = {0};
  int active = 0;
  printf("WEBEEBLOCKS_ALTITUDE_READY scene=altitude-v1 oracle=%s\n", WB_ALT_ORACLE);
  fflush(stdout);
  while (wb_robot_step(step) != -1) {
    const char *data = wb_supervisor_field_get_sf_string(channel);
    unsigned long long observed = 0;
    if (parse_attempt(data, &observed) &&
        (!active || mission.attempt != observed)) {
      wb_alt_reset(&mission, observed, origin_z);
      active = 1;
      printf("WEBEEBLOCKS_ALTITUDE_ATTEMPT attempt=%llu\n", observed);
      fflush(stdout);
    }
    if (!active || mission.result != WB_ALT_WAIT)
      continue;

    const double *position = wb_supervisor_node_get_position(craft);
    const double *velocity = wb_supervisor_node_get_velocity(craft);
    wb_alt_sample sample = {0};
    sample.time = wb_robot_get_time();
    sample.obstacle_contact = native_contact_observation(craft);
    sample.completed = parse_completion(data, mission.attempt);
    if (!position || !velocity) {
      sample.x = NAN;
    } else {
      sample.x = position[0]; sample.y = position[1]; sample.z = position[2];
      sample.vx = velocity[0]; sample.vy = velocity[1]; sample.vz = velocity[2];
    }
    wb_alt_verdict result = wb_alt_sample_mission(&mission, &sample);
    if (result != WB_ALT_WAIT)
      publish(channel, mission.attempt, result, &mission);
  }
  wb_robot_cleanup();
  return 0;
}

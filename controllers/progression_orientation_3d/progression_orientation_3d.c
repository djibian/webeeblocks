/* Activity 3: independent Webots R2025a C supervisor for simulated flight.
 * No Python installation, no Blockly AST, no flight commands and no changes
 * to the physically qualified shared runtime. Scene-specific process only.
 */
#include "orientation_core.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <webots/robot.h>
#include <webots/supervisor.h>

#define WB_ORIENT_SCENE_DEF "WEBEEBLOCKS_ORIENTATION_SCENE"
#define WB_ORIENT_CRAFT_NAME "Crazyflie WebeeBlocks"

static int verify_scene(void) {
  WbNodeRef scene = wb_supervisor_node_get_from_def(WB_ORIENT_SCENE_DEF);
  const char *type = scene ? wb_supervisor_node_get_type_name(scene) : NULL;
  WbFieldRef children = scene ? wb_supervisor_node_get_field(scene, "children") : NULL;
  if (!type || strcmp(type, "Group") != 0 || !children ||
      wb_supervisor_field_get_count(children) != WB_ORIENT_CHILDREN)
    return 0;
  for (int i = 0; i < WB_ORIENT_CHILDREN; ++i)
    if (!wb_supervisor_field_get_mf_node(children, i)) return 0;
  /* No legacy/sequence/altitude evaluator may compete for the same channel. */
  return !wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_SCENE") &&
         !wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_EVALUATORS") &&
         !wb_supervisor_node_get_from_def("WEBEEBLOCKS_SEQUENCE_SCENE") &&
         !wb_supervisor_node_get_from_def("WEBEEBLOCKS_ALTITUDE_SCENE");
}

static WbNodeRef unique_vehicle(void) {
  WbNodeRef root = wb_supervisor_node_get_root();
  WbFieldRef children = root ? wb_supervisor_node_get_field(root, "children") : NULL;
  if (!children) return NULL;
  WbNodeRef found = NULL;
  for (int i = 0; i < wb_supervisor_field_get_count(children); ++i) {
    WbNodeRef node = wb_supervisor_field_get_mf_node(children, i);
    WbFieldRef name = node ? wb_supervisor_node_get_field(node, "name") : NULL;
    const char *value = name ? wb_supervisor_field_get_sf_string(name) : NULL;
    if (value && strcmp(value, WB_ORIENT_CRAFT_NAME) == 0) {
      if (found) return NULL;
      found = node;
    }
  }
  return found;
}

static int parse_attempt(const char *value, unsigned long long *out) {
  unsigned long long identity = 0;
  char extra = '\0';
  if (!value || !out ||
      sscanf(value, "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu%c",
             &identity, &extra) != 1 || identity == 0)
    return 0;
  char canonical[100];
  int size = snprintf(canonical, sizeof(canonical),
                      "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu", identity);
  if (size < 1 || (size_t)size >= sizeof(canonical) ||
      strcmp(value, canonical) != 0) return 0;
  *out = identity;
  return 1;
}

static int parse_completion(const char *value, unsigned long long identity) {
  char canonical[180];
  int size = snprintf(canonical, sizeof(canonical),
                      "WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=%llu oracle=%s",
                      identity, WB_ORIENT_ORACLE);
  return value && size > 0 && (size_t)size < sizeof(canonical) &&
    strcmp(value, canonical) == 0;
}

static void publish(WbFieldRef channel, const wb_orient_mission *m) {
  const char *status =
    m->result == WB_ORIENT_ACHIEVED ? "achieved" : "not-achieved";
  char result[180];
  int size = snprintf(result, sizeof(result),
      "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=%s",
      m->attempt, WB_ORIENT_ORACLE, status);
  if (size < 1 || (size_t)size >= sizeof(result)) return;
  wb_supervisor_field_set_sf_string(channel, result);
  printf("WEBEEBLOCKS_ORIENTATION_3D_RESULT attempt=%llu status=%s checkpoints=%d\n",
         m->attempt, status, m->stage);
  fflush(stdout);
}

int main(void) {
  wb_robot_init();
  const int step = (int)wb_robot_get_basic_time_step();
  if (step <= 0 || !verify_scene()) {
    fprintf(stderr, "WEBEEBLOCKS_ORIENTATION_3D_FATAL invalid scene identity\n");
    wb_robot_cleanup();
    return 2;
  }
  WbNodeRef craft = unique_vehicle();
  WbFieldRef channel = craft ? wb_supervisor_node_get_field(craft, "customData") : NULL;
  const double *origin = craft ? wb_supervisor_node_get_position(craft) : NULL;
  if (!channel || !origin || !isfinite(origin[2])) {
    fprintf(stderr, "WEBEEBLOCKS_ORIENTATION_3D_FATAL ambiguous or absent craft\n");
    wb_robot_cleanup();
    return 2;
  }
  const double origin_z = origin[2];
  wb_orient_mission mission = {0};
  unsigned long long last_identity = 0;
  printf("WEBEEBLOCKS_ORIENTATION_3D_READY scene=orientation-v1 oracle=%s\n",
         WB_ORIENT_ORACLE);
  fflush(stdout);
  while (wb_robot_step(step) != -1) {
    const char *data = wb_supervisor_field_get_sf_string(channel);
    unsigned long long identity = 0;
    if (parse_attempt(data, &identity) && identity > last_identity) {
      wb_orient_reset(&mission, identity, origin_z);
      last_identity = identity;
      printf("WEBEEBLOCKS_ORIENTATION_3D_ATTEMPT attempt=%llu\n", identity);
      fflush(stdout);
    }
    if (!last_identity || mission.result != WB_ORIENT_WAIT) continue;
    const double *position = wb_supervisor_node_get_position(craft);
    const double *velocity = wb_supervisor_node_get_velocity(craft);
    const double *orientation = wb_supervisor_node_get_orientation(craft);
    wb_orient_sample sample = {0};
    sample.time = wb_robot_get_time();
    sample.completed = parse_completion(data, mission.attempt);
    if (!position || !velocity ||
        !wb_orient_yaw(orientation, &sample.yaw)) {
      sample.x = NAN; /* Invalid native observation fails closed. */
    } else {
      sample.x = position[0]; sample.y = position[1]; sample.z = position[2];
      sample.vx = velocity[0]; sample.vy = velocity[1]; sample.vz = velocity[2];
    }
    const wb_orient_verdict before = mission.result;
    wb_orient_sample_mission(&mission, &sample);
    if (before == WB_ORIENT_WAIT && mission.result != WB_ORIENT_WAIT)
      publish(channel, &mission);
  }
  wb_robot_cleanup();
  return 0;
}

/* Activity 1: native C Webots R2025a scene-only supervisor.
 * Native observation of pose/velocity; no Python installation, flight control,
 * Blockly AST, physical runtime linkage or Grand Prix authority.
 */
#include "sequence_core.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <webots/robot.h>
#include <webots/supervisor.h>

#define WB_SEQ_SCENE_DEF "WEBEEBLOCKS_SEQUENCE_SCENE"
#define WB_SEQ_CRAFT_NAME "Crazyflie WebeeBlocks"

static int verify_scene(void) {
  WbNodeRef scene = wb_supervisor_node_get_from_def(WB_SEQ_SCENE_DEF);
  const char *type = scene ? wb_supervisor_node_get_type_name(scene) : NULL;
  WbFieldRef children = scene ? wb_supervisor_node_get_field(scene, "children") : NULL;
  if (!type || strcmp(type, "Group") != 0 || !children ||
      wb_supervisor_field_get_count(children) != WB_SEQ_CHILDREN)
    return 0;
  for (int i = 0; i < WB_SEQ_CHILDREN; ++i)
    if (!wb_supervisor_field_get_mf_node(children, i)) return 0;
  return !wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_SCENE") &&
         !wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_EVALUATORS") &&
         !wb_supervisor_node_get_from_def("WEBEEBLOCKS_ALTITUDE_SCENE") &&
         !wb_supervisor_node_get_from_def("WEBEEBLOCKS_ORIENTATION_SCENE");
}

static WbNodeRef unique_craft(void) {
  WbNodeRef root = wb_supervisor_node_get_root();
  WbFieldRef children = root ? wb_supervisor_node_get_field(root, "children") : NULL;
  if (!children) return NULL;
  WbNodeRef found = NULL;
  for (int i = 0; i < wb_supervisor_field_get_count(children); ++i) {
    WbNodeRef node = wb_supervisor_field_get_mf_node(children, i);
    WbFieldRef name = node ? wb_supervisor_node_get_field(node, "name") : NULL;
    const char *value = name ? wb_supervisor_field_get_sf_string(name) : NULL;
    if (value && strcmp(value, WB_SEQ_CRAFT_NAME) == 0) {
      if (found) return NULL;
      found = node;
    }
  }
  return found;
}

static int parse_attempt(const char *data, unsigned long long *out) {
  unsigned long long identity = 0;
  char trailing = '\0';
  if (!data || !out || sscanf(data, "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu%c",
                              &identity, &trailing) != 1 || identity == 0)
    return 0;
  char canonical[120];
  const int size = snprintf(canonical, sizeof(canonical),
                            "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu", identity);
  if (size < 1 || (size_t)size >= sizeof(canonical) ||
      strcmp(data, canonical) != 0) return 0;
  *out = identity;
  return 1;
}

static int parse_completion(const char *data, unsigned long long identity) {
  char canonical[180];
  const int size = snprintf(canonical, sizeof(canonical),
      "WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=%llu oracle=%s",
      identity, WB_SEQ_ORACLE);
  return data && size > 0 && (size_t)size < sizeof(canonical) &&
         strcmp(data, canonical) == 0;
}

static void publish(WbFieldRef channel, const wb_seq_mission *m) {
  const char *status = (m->result == WB_SEQ_ACHIEVED) ? "achieved" : "not-achieved";
  char result[180];
  const int size = snprintf(result, sizeof(result),
      "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=%s",
      m->attempt, WB_SEQ_ORACLE, status);
  if (size < 1 || (size_t)size >= sizeof(result)) return;
  wb_supervisor_field_set_sf_string(channel, result);
  printf("WEBEEBLOCKS_SEQUENCE_3D_RESULT attempt=%llu status=%s\n",
         m->attempt, status);
  fflush(stdout);
}

int main(void) {
  wb_robot_init();
  const int step = (int)wb_robot_get_basic_time_step();
  if (step <= 0 || !verify_scene()) {
    fprintf(stderr, "WEBEEBLOCKS_SEQUENCE_3D_FATAL invalid native scene\n");
    wb_robot_cleanup();
    return 2;
  }
  WbNodeRef craft = unique_craft();
  WbFieldRef channel = craft ? wb_supervisor_node_get_field(craft, "customData") : NULL;
  const double *origin = craft ? wb_supervisor_node_get_position(craft) : NULL;
  if (!channel || !origin || !isfinite(origin[2])) {
    fprintf(stderr, "WEBEEBLOCKS_SEQUENCE_3D_FATAL absent or ambiguous Crazyflie\n");
    wb_robot_cleanup();
    return 2;
  }
  const double origin_z = origin[2];
  wb_seq_mission mission = {0};
  unsigned long long last_attempt = 0;
  printf("WEBEEBLOCKS_SEQUENCE_3D_READY target_x=0.350 target_y=0.280\n");
  fflush(stdout);
  while (wb_robot_step(step) != -1) {
    const char *data = wb_supervisor_field_get_sf_string(channel);
    unsigned long long identity = 0;
    if (parse_attempt(data, &identity) && identity > last_attempt) {
      wb_seq_reset(&mission, identity, origin_z);
      last_attempt = identity;
      printf("WEBEEBLOCKS_SEQUENCE_3D_ATTEMPT attempt=%llu\n", identity);
      fflush(stdout);
    }
    if (!last_attempt || mission.result != WB_SEQ_WAIT) continue;
    const double *pose = wb_supervisor_node_get_position(craft);
    const double *velocity = wb_supervisor_node_get_velocity(craft);
    wb_seq_sample sample = {0};
    sample.time = wb_robot_get_time();
    sample.completed = parse_completion(data, mission.attempt);
    if (!pose || !velocity) {
      sample.x = NAN; /* A missing native observation cannot authorize success. */
    } else {
      sample.x = pose[0]; sample.y = pose[1]; sample.z = pose[2];
      sample.vx = velocity[0]; sample.vy = velocity[1]; sample.vz = velocity[2];
    }
    const wb_seq_verdict before = mission.result;
    wb_seq_sample_mission(&mission, &sample);
    if (before == WB_SEQ_WAIT && mission.result != WB_SEQ_WAIT)
      publish(channel, &mission);
  }
  wb_robot_cleanup();
  return 0;
}

#include "activity_scene.h"
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <cstdio>
#include <cstring>
#include <string>

namespace {
std::string legacyScene;
std::string legacyEvaluators;
std::string selected = "legacy-v1";
bool ready = true;
bool saved = false;
int legacyChildCount = -1;
int evaluatorChildCount = -1;
double oldPosition[3];
double oldOrientation[4];

std::string exported(const char *def) {
  WbNodeRef node = wb_supervisor_node_get_from_def(def);
  const char *text = node ? wb_supervisor_node_export_string(node) : nullptr;
  return text ? std::string(text) : std::string();
}
bool completeGroup(const char *def, int expected) {
  WbNodeRef node = wb_supervisor_node_get_from_def(def);
  const char *type = node ? wb_supervisor_node_get_type_name(node) : nullptr;
  WbFieldRef content = node ? wb_supervisor_node_get_field(node, "children") : nullptr;
  if (!type || std::strcmp(type, "Group") || !content || expected < 1 ||
      wb_supervisor_field_get_count(content) != expected) return false;
  for (int i = 0; i < expected; ++i)
    if (!wb_supervisor_field_get_mf_node(content, i)) return false;
  return true;
}
int groupCount(const char *def) {
  WbNodeRef node = wb_supervisor_node_get_from_def(def);
  WbFieldRef content = node ? wb_supervisor_node_get_field(node, "children") : nullptr;
  return content ? wb_supervisor_field_get_count(content) : -1;
}
void removeDef(const char *def) {
  WbNodeRef node = wb_supervisor_node_get_from_def(def);
  if (node) wb_supervisor_node_remove(node);
}
}

extern "C" int webeeblocks_activity_scene_ready(void) { return ready ? 1 : 0; }

// Called by the flight controller only while idle, landed, and at its reset
// origin. No physical backend uses this API. Never reload the world or workspace.
extern "C" int webeeblocks_select_activity_scene(const char *scene) {
  if (!scene || (std::strcmp(scene, "sequence-v1") && std::strcmp(scene, "legacy-v1"))) return 0;
  if (ready && selected == scene) return 1;
  WbFieldRef children = wb_supervisor_node_get_field(wb_supervisor_node_get_root(), "children");
  WbNodeRef view = nullptr;
  for (int i = 0; children && i < wb_supervisor_field_get_count(children); ++i) {
    WbNodeRef node = wb_supervisor_field_get_mf_node(children, i);
    const char *type = wb_supervisor_node_get_type_name(node);
    if (type && !std::strcmp(type, "Viewpoint")) { view = node; break; }
  }
  WbFieldRef position = view ? wb_supervisor_node_get_field(view, "position") : nullptr;
  WbFieldRef orientation = view ? wb_supervisor_node_get_field(view, "orientation") : nullptr;
  if (!children || !position || !orientation) return 0;
  if (!saved) {
    legacyScene = exported("WEBEEBLOCKS_LEGACY_SCENE");
    legacyEvaluators = exported("WEBEEBLOCKS_LEGACY_EVALUATORS");
    legacyChildCount = groupCount("WEBEEBLOCKS_LEGACY_SCENE");
    evaluatorChildCount = groupCount("WEBEEBLOCKS_LEGACY_EVALUATORS");
    if (legacyScene.empty() || legacyEvaluators.empty() ||
        !completeGroup("WEBEEBLOCKS_LEGACY_SCENE", legacyChildCount) ||
        !completeGroup("WEBEEBLOCKS_LEGACY_EVALUATORS", evaluatorChildCount)) return 0;
    const double *p = wb_supervisor_field_get_sf_vec3f(position);
    const double *o = wb_supervisor_field_get_sf_rotation(orientation);
    if (!p || !o) return 0;
    std::memcpy(oldPosition, p, sizeof(oldPosition));
    std::memcpy(oldOrientation, o, sizeof(oldOrientation));
    saved = true;
  }
  std::string nextScene;
  if (std::strcmp(scene, "sequence-v1") == 0) {
    const std::string path = std::string(wb_robot_get_project_path()) + "/worlds/scenes/sequence-v1.wbo";
    FILE *file = std::fopen(path.c_str(), "rb");
    if (!file) return 0;
    char buffer[32769];
    const size_t size = std::fread(buffer, 1, sizeof(buffer) - 1, file);
    const bool complete = !std::ferror(file) && std::feof(file);
    std::fclose(file);
    if (!complete || !size) return 0;
    buffer[size] = '\0';
    nextScene.assign(buffer, size);
  }
  ready = false;
  // Stop controllers before removing any node to which they hold field refs.
  removeDef("WEBEEBLOCKS_LEGACY_EVALUATORS");
  removeDef("WEBEEBLOCKS_LEGACY_SCENE");
  removeDef("WEBEEBLOCKS_SEQUENCE_SCENE");
  // Activities 7/8 currently import extra root nodes at evaluator startup.
  // Remove those too; restarting their evaluators recreates them on restoration.
  for (int i = wb_supervisor_field_get_count(children) - 1; i >= 0; --i) {
    WbNodeRef node = wb_supervisor_field_get_mf_node(children, i);
    const char *def = wb_supervisor_node_get_def(node);
    if (def && (!std::strncmp(def, "ACTIVITY7_", 10) || !std::strncmp(def, "ACTIVITY8_", 10)))
      wb_supervisor_node_remove(node);
  }
  if (std::strcmp(scene, "sequence-v1") == 0) {
    wb_supervisor_field_import_mf_node_from_string(children, -1, nextScene.c_str());
    // Two delivery markers and sixteen checkerboard tiles are required.
    ready = completeGroup("WEBEEBLOCKS_SEQUENCE_SCENE", 18);
    const double p[] = {-0.9, -1.1, 1.1};
    const double o[] = {-0.45, 0.47, 0.76, 1.05};
    wb_supervisor_field_set_sf_vec3f(position, p);
    wb_supervisor_field_set_sf_rotation(orientation, o);
  } else {
    wb_supervisor_field_import_mf_node_from_string(children, -1, legacyScene.c_str());
    if (completeGroup("WEBEEBLOCKS_LEGACY_SCENE", legacyChildCount)) {
      wb_supervisor_field_import_mf_node_from_string(children, -1, legacyEvaluators.c_str());
      ready = completeGroup("WEBEEBLOCKS_LEGACY_EVALUATORS", evaluatorChildCount);
    }
    wb_supervisor_field_set_sf_vec3f(position, oldPosition);
    wb_supervisor_field_set_sf_rotation(orientation, oldOrientation);
  }
  if (!ready) return 0;  // No partial import may authorize takeoff.
  selected = scene;
  return 1;
}

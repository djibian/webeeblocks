#include "../crazyflie_runtime_v2/activity_scene.h"
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <cstdio>
#include <cstring>
#include <cmath>
#include <string>

namespace {
std::string legacyScene;
std::string legacyEvaluators;
std::string selected;
bool ready = false;
bool observed = false;
bool saved = false;
// Trusted direct-child counts in the versioned classroom launch world.
// Never derive a trusted count from possibly damaged live scene content.
constexpr int kLegacySceneChildren = 32;
constexpr int kLegacyEvaluatorChildren = 6;
constexpr int kAltitudeSceneChildren = 22;  // 18 markers, 4 physical colliders.
constexpr int kOrientationSceneChildren = 24;  // Native observer and markers.
constexpr int kSequenceSceneChildren = 18;  // Native observer inside first Pose.
double oldPosition[3];
double oldOrientation[4];

std::string exported(const char *def) {
  WbNodeRef node = wb_supervisor_node_get_from_def(def);
  const char *text = node ? wb_supervisor_node_export_string(node) : nullptr;
  return text ? std::string(text) : std::string();
}
bool classroomStart() {
  WbNodeRef node = wb_supervisor_node_get_from_def("WEBEEBLOCKS_CLASSROOM_START_WORLD");
  const char *type = node ? wb_supervisor_node_get_type_name(node) : nullptr;
  return type && !std::strcmp(type, "WorldInfo");
}
std::string sceneFile(const char *name) {
  const std::string path = std::string(wb_robot_get_project_path()) + "/worlds/scenes/" + name;
  FILE *file = std::fopen(path.c_str(), "rb");
  if (!file) return {};
  char buffer[32769];
  const size_t size = std::fread(buffer, 1, sizeof(buffer) - 1, file);
  const bool complete = !std::ferror(file) && std::feof(file);
  std::fclose(file);
  if (!complete || !size) return {};
  buffer[size] = '\0';
  return std::string(buffer, size);
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
// Admission is based on the *actual collision geometry*, not an attractive
// visual Solid with a missing or altered boundingObject.
bool altitudeColliders() {
  struct Expected {
    const char *def;
    double position[3];
    double size[3];
  };
  const Expected colliders[] = {
    {"ACTIVITY2_START_CANOPY", {0.0, 0.0, 0.70}, {0.34, 0.86, 0.08}},
    {"ACTIVITY2_LOW_BARRIER", {0.62, 0.0, 0.31}, {0.12, 0.84, 0.62}},
    {"ACTIVITY2_LEFT_WALL", {0.68, 0.51, 0.425}, {1.65, 0.08, 0.85}},
    {"ACTIVITY2_RIGHT_WALL", {0.68, -0.51, 0.425}, {1.65, 0.08, 0.85}}
  };
  for (const Expected &c : colliders) {
    WbNodeRef node = wb_supervisor_node_get_from_def(c.def);
    const char *type = node ? wb_supervisor_node_get_type_name(node) : nullptr;
    if (!type || std::strcmp(type, "Solid") != 0) return false;
    const double *position = wb_supervisor_node_get_position(node);
    WbFieldRef field = wb_supervisor_node_get_field(node, "boundingObject");
    WbNodeRef box = field ? wb_supervisor_field_get_sf_node(field) : nullptr;
    const char *shape = box ? wb_supervisor_node_get_type_name(box) : nullptr;
    if (!shape || std::strcmp(shape, "Box") != 0) return false;
    WbFieldRef sizeField = wb_supervisor_node_get_field(box, "size");
    const double *size = sizeField ? wb_supervisor_field_get_sf_vec3f(sizeField) : nullptr;
    if (!position || !size) return false;
    for (int i = 0; i != 3; ++i) {
      if (!std::isfinite(position[i]) || !std::isfinite(size[i]) ||
          size[i] <= 0.0 || std::fabs(position[i] - c.position[i]) > 0.000001 ||
          std::fabs(size[i] - c.size[i]) > 0.000001)
        return false;
    }
    // Position and local Box size alone do NOT attest the world-space
    // collider: a rotated Solid changes the obstacle while preserving both.
    // The versioned altitude scene specifies unrotated Solids only.
    const double *rotation = wb_supervisor_node_get_orientation(node);
    if (!rotation) return false;
    for (int i = 0; i != 9; ++i) {
      const double expected = (i % 4 == 0) ? 1.0 : 0.0;
      if (!std::isfinite(rotation[i]) ||
          std::fabs(rotation[i] - expected) > 0.000001)
        return false;
    }
  }
  return true;
}
// The Activity 1 evaluator is a real nested Webots Robot. The visible
// checkerboard can retain all 18 direct children after an observer is removed:
// never authorize SCENE_OK merely from the Group count or a WBO comment.
// Unlike a textual controller token or a correct 22-child collider group,
// this native Robot identity is required before an altitude SCENE_OK.
bool altitudeObserver() {
  WbNodeRef scene = wb_supervisor_node_get_from_def("WEBEEBLOCKS_ALTITUDE_SCENE");
  WbFieldRef children = scene ? wb_supervisor_node_get_field(scene, "children") : nullptr;
  if (!children || wb_supervisor_field_get_count(children) != kAltitudeSceneChildren)
    return false;
  WbNodeRef first = wb_supervisor_field_get_mf_node(children, 0);
  const char *firstType = first ? wb_supervisor_node_get_type_name(first) : nullptr;
  if (!firstType || std::strcmp(firstType, "Pose")) return false;
  WbFieldRef nested = wb_supervisor_node_get_field(first, "children");
  if (!nested || wb_supervisor_field_get_count(nested) != 2) return false;
  WbNodeRef observer = wb_supervisor_field_get_mf_node(nested, 1);
  const char *type = observer ? wb_supervisor_node_get_type_name(observer) : nullptr;
  if (!type || std::strcmp(type, "Robot")) return false;
  WbFieldRef controllerField = wb_supervisor_node_get_field(observer, "controller");
  WbFieldRef nameField = wb_supervisor_node_get_field(observer, "name");
  WbFieldRef supervisorField = wb_supervisor_node_get_field(observer, "supervisor");
  WbFieldRef syncField = wb_supervisor_node_get_field(observer, "synchronization");
  if (!controllerField || !nameField || !supervisorField || !syncField) return false;
  const char *controller = wb_supervisor_field_get_sf_string(controllerField);
  const char *name = wb_supervisor_field_get_sf_string(nameField);
  return controller && name &&
    !std::strcmp(controller, "progression_altitude_v1") &&
    !std::strcmp(name, "Progression altitude native evaluator") &&
    wb_supervisor_field_get_sf_bool(supervisorField) &&
    wb_supervisor_field_get_sf_bool(syncField);
}
bool sequenceObserver() {
  WbNodeRef scene = wb_supervisor_node_get_from_def("WEBEEBLOCKS_SEQUENCE_SCENE");
  WbFieldRef children = scene ? wb_supervisor_node_get_field(scene, "children") : nullptr;
  if (!children || wb_supervisor_field_get_count(children) != kSequenceSceneChildren)
    return false;
  WbNodeRef first = wb_supervisor_field_get_mf_node(children, 0);
  const char *firstType = first ? wb_supervisor_node_get_type_name(first) : nullptr;
  if (!firstType || std::strcmp(firstType, "Pose")) return false;
  WbFieldRef nested = wb_supervisor_node_get_field(first, "children");
  if (!nested || wb_supervisor_field_get_count(nested) != 2) return false;
  WbNodeRef observer = wb_supervisor_field_get_mf_node(nested, 1);
  const char *type = observer ? wb_supervisor_node_get_type_name(observer) : nullptr;
  if (!type || std::strcmp(type, "Robot")) return false;
  WbFieldRef controllerField = wb_supervisor_node_get_field(observer, "controller");
  WbFieldRef nameField = wb_supervisor_node_get_field(observer, "name");
  WbFieldRef supervisorField = wb_supervisor_node_get_field(observer, "supervisor");
  WbFieldRef syncField = wb_supervisor_node_get_field(observer, "synchronization");
  if (!controllerField || !nameField || !supervisorField || !syncField) return false;
  const char *controller = wb_supervisor_field_get_sf_string(controllerField);
  const char *name = wb_supervisor_field_get_sf_string(nameField);
  return controller && name &&
    !std::strcmp(controller, "progression_sequence_3d") &&
    !std::strcmp(name, "Progression sequence 3D evaluator") &&
    wb_supervisor_field_get_sf_bool(supervisorField) &&
    wb_supervisor_field_get_sf_bool(syncField);
}
// Attest the *imported Webots nodes*, not an occurrence of controller text in
// the WBO (which can survive inside a comment without any running observer).
// In orientation-v1, the only mission observer is the second child of the
// first visual Pose; no scene or Blockly profile may supply that identity.
bool orientationObserver() {
  WbNodeRef scene = wb_supervisor_node_get_from_def("WEBEEBLOCKS_ORIENTATION_SCENE");
  WbFieldRef children = scene ? wb_supervisor_node_get_field(scene, "children") : nullptr;
  if (!children || wb_supervisor_field_get_count(children) != kOrientationSceneChildren)
    return false;
  WbNodeRef first = wb_supervisor_field_get_mf_node(children, 0);
  const char *firstType = first ? wb_supervisor_node_get_type_name(first) : nullptr;
  if (!firstType || std::strcmp(firstType, "Pose")) return false;
  WbFieldRef nested = wb_supervisor_node_get_field(first, "children");
  if (!nested || wb_supervisor_field_get_count(nested) != 2) return false;
  WbNodeRef observer = wb_supervisor_field_get_mf_node(nested, 1);
  const char *type = observer ? wb_supervisor_node_get_type_name(observer) : nullptr;
  if (!type || std::strcmp(type, "Robot")) return false;
  WbFieldRef controllerField = wb_supervisor_node_get_field(observer, "controller");
  WbFieldRef nameField = wb_supervisor_node_get_field(observer, "name");
  WbFieldRef supervisorField = wb_supervisor_node_get_field(observer, "supervisor");
  WbFieldRef syncField = wb_supervisor_node_get_field(observer, "synchronization");
  if (!controllerField || !nameField || !supervisorField || !syncField) return false;
  const char *controller = wb_supervisor_field_get_sf_string(controllerField);
  const char *name = wb_supervisor_field_get_sf_string(nameField);
  return controller && name &&
    !std::strcmp(controller, "progression_orientation_3d") &&
    !std::strcmp(name, "Progression orientation 3D evaluator") &&
    wb_supervisor_field_get_sf_bool(supervisorField) &&
    wb_supervisor_field_get_sf_bool(syncField);
}
bool liveSelection() {
  if (selected == "sequence-v1")
    return completeGroup("WEBEEBLOCKS_SEQUENCE_SCENE", kSequenceSceneChildren) &&
      sequenceObserver() &&
      !wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_SCENE") &&
      !wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_EVALUATORS") &&
      !wb_supervisor_node_get_from_def("WEBEEBLOCKS_ALTITUDE_SCENE") &&
      !wb_supervisor_node_get_from_def("WEBEEBLOCKS_ORIENTATION_SCENE");
  if (selected == "legacy-v1")
    return completeGroup("WEBEEBLOCKS_LEGACY_SCENE", kLegacySceneChildren) &&
      completeGroup("WEBEEBLOCKS_LEGACY_EVALUATORS", kLegacyEvaluatorChildren) &&
      !wb_supervisor_node_get_from_def("WEBEEBLOCKS_SEQUENCE_SCENE") &&
      !wb_supervisor_node_get_from_def("WEBEEBLOCKS_ALTITUDE_SCENE") &&
      !wb_supervisor_node_get_from_def("WEBEEBLOCKS_ORIENTATION_SCENE");
  if (selected == "altitude-v1")
    return completeGroup("WEBEEBLOCKS_ALTITUDE_SCENE", kAltitudeSceneChildren) &&
      altitudeColliders() &&
      altitudeObserver() &&
      !wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_SCENE") &&
      !wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_EVALUATORS") &&
      !wb_supervisor_node_get_from_def("WEBEEBLOCKS_SEQUENCE_SCENE") &&
      !wb_supervisor_node_get_from_def("WEBEEBLOCKS_ORIENTATION_SCENE");
  if (selected == "orientation-v1")
    return completeGroup("WEBEEBLOCKS_ORIENTATION_SCENE", kOrientationSceneChildren) &&
      orientationObserver() &&
      !wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_SCENE") &&
      !wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_EVALUATORS") &&
      !wb_supervisor_node_get_from_def("WEBEEBLOCKS_SEQUENCE_SCENE") &&
      !wb_supervisor_node_get_from_def("WEBEEBLOCKS_ALTITUDE_SCENE");
  // Absence is not identity: an interrupted managed-world import may also
  // leave zero groups. Dedicated worlds opt in through a typed world root.
  WbNodeRef world = wb_supervisor_node_get_from_def("WEBEEBLOCKS_DEDICATED_RUNTIME_WORLD");
  const char *type = world ? wb_supervisor_node_get_type_name(world) : nullptr;
  return type && !std::strcmp(type, "WorldInfo") &&
    !wb_supervisor_node_get_from_def("WEBEEBLOCKS_SEQUENCE_SCENE") &&
    !wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_SCENE") &&
    !wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_EVALUATORS") &&
    !wb_supervisor_node_get_from_def("WEBEEBLOCKS_ALTITUDE_SCENE") &&
    !wb_supervisor_node_get_from_def("WEBEEBLOCKS_ORIENTATION_SCENE");
}
void observeWorld() {
  if (observed) return;
  observed = true;
  if (wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_SCENE") ||
      wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_EVALUATORS")) {
    selected = "legacy-v1";
    ready = liveSelection();
  } else {
    // A surviving sequence scene has lost this process's legacy snapshots.
    // Only a world reload can reconstruct them; never acknowledge legacy or
    // authorize takeoff from invented process-initial state.
    ready = liveSelection();
  }
}
void removeDef(const char *def) {
  WbNodeRef node = wb_supervisor_node_get_from_def(def);
  if (node) wb_supervisor_node_remove(node);
}
}

extern "C" int webeeblocks_activity_scene_ready(void) {
  observeWorld();
  ready = ready && liveSelection();
  return ready ? 1 : 0;
}

// Called by the flight controller only while idle, landed, and at its reset
// origin. No physical backend uses this API. Never reload the world or workspace.
extern "C" int webeeblocks_select_activity_scene(const char *scene) {
  if (!scene || (std::strcmp(scene, "sequence-v1") &&
                 std::strcmp(scene, "legacy-v1") &&
                 std::strcmp(scene, "altitude-v1") &&
                 std::strcmp(scene, "orientation-v1"))) return 0;
  observeWorld();
  ready = ready && liveSelection();
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
    if (classroomStart() &&
        !wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_SCENE") &&
        !wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_EVALUATORS") &&
        !wb_supervisor_node_get_from_def("WEBEEBLOCKS_SEQUENCE_SCENE") &&
        !wb_supervisor_node_get_from_def("WEBEEBLOCKS_ALTITUDE_SCENE") &&
        !wb_supervisor_node_get_from_def("WEBEEBLOCKS_ORIENTATION_SCENE")) {
      // A typed, empty classroom launch has no live scenario to export. Its
      // versioned restoration assets remain subject to the same post-import
      // type/count/node checks. An interrupted/partial scene is never empty.
      legacyScene = sceneFile("legacy-scene-v1.wbo");
      legacyEvaluators = sceneFile("legacy-evaluators-v1.wbo");
      if (legacyScene.empty() || legacyEvaluators.empty()) return 0;
    } else if (legacyScene.empty() || legacyEvaluators.empty() ||
               !completeGroup("WEBEEBLOCKS_LEGACY_SCENE", kLegacySceneChildren) ||
               !completeGroup("WEBEEBLOCKS_LEGACY_EVALUATORS", kLegacyEvaluatorChildren)) return 0;
    const double *p = wb_supervisor_field_get_sf_vec3f(position);
    const double *o = wb_supervisor_field_get_sf_rotation(orientation);
    if (!p || !o) return 0;
    std::memcpy(oldPosition, p, sizeof(oldPosition));
    std::memcpy(oldOrientation, o, sizeof(oldOrientation));
    saved = true;
  }
  std::string nextScene;
  if (std::strcmp(scene, "sequence-v1") == 0) {
    nextScene = sceneFile("sequence-v1.wbo");
    // Fail before removing a former scenario when the versioned scene is
    // missing or cannot even name its own nested observer. The *real* imported
    // Robot identity is checked below; text alone cannot authorize READY.
    if (nextScene.empty() ||
        nextScene.find("DEF WEBEEBLOCKS_SEQUENCE_SCENE Group {") != 0 ||
        nextScene.find("controller \"progression_sequence_3d\"") == std::string::npos)
      return 0;
  } else if (std::strcmp(scene, "altitude-v1") == 0) {
    nextScene = sceneFile("altitude-v1.wbo");
    // Refuse before destructive mutation: verify a structurally typed,
    // exactly named, versioned asset (the embedded oracle verifies colliders).
    if (nextScene.empty() || nextScene.find("DEF WEBEEBLOCKS_ALTITUDE_SCENE Group {") != 0 ||
        nextScene.find("controller \"progression_altitude_v1\"") == std::string::npos)
      return 0;
  } else if (std::strcmp(scene, "orientation-v1") == 0) {
    nextScene = sceneFile("orientation-v1.wbo");
    // Fail before destruction when the versioned scene or its native observer
    // is unavailable. Flight and its AST remain separate from this observer.
    if (nextScene.empty() ||
        nextScene.find("DEF WEBEEBLOCKS_ORIENTATION_SCENE Group {") != 0 ||
        nextScene.find("controller \"progression_orientation_3d\"") == std::string::npos)
      return 0;
  }
  ready = false;
  // Stop controllers before removing any node to which they hold field refs.
  removeDef("WEBEEBLOCKS_LEGACY_EVALUATORS");
  removeDef("WEBEEBLOCKS_LEGACY_SCENE");
  removeDef("WEBEEBLOCKS_SEQUENCE_SCENE");
  removeDef("WEBEEBLOCKS_ALTITUDE_SCENE");
  removeDef("WEBEEBLOCKS_ORIENTATION_SCENE");
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
    // Two markers and sixteen checkerboard tiles are not enough: require
    // the real, correctly configured nested mission observer as well.
    ready = completeGroup("WEBEEBLOCKS_SEQUENCE_SCENE", kSequenceSceneChildren) &&
      sequenceObserver() &&
      !wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_SCENE") &&
      !wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_EVALUATORS") &&
      !wb_supervisor_node_get_from_def("WEBEEBLOCKS_ALTITUDE_SCENE") &&
      !wb_supervisor_node_get_from_def("WEBEEBLOCKS_ORIENTATION_SCENE");
    const double p[] = {-0.9, -1.1, 1.1};
    const double o[] = {-0.45, 0.47, 0.76, 1.05};
    wb_supervisor_field_set_sf_vec3f(position, p);
    wb_supervisor_field_set_sf_rotation(orientation, o);
  } else if (std::strcmp(scene, "altitude-v1") == 0) {
    wb_supervisor_field_import_mf_node_from_string(children, -1, nextScene.c_str());
    ready = liveSelection() ||
      (completeGroup("WEBEEBLOCKS_ALTITUDE_SCENE", kAltitudeSceneChildren) &&
       altitudeColliders() &&
      altitudeObserver() &&
       !wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_SCENE") &&
       !wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_EVALUATORS") &&
       !wb_supervisor_node_get_from_def("WEBEEBLOCKS_SEQUENCE_SCENE"));
    const double p[] = {-1.8, -1.6, 1.6};
    const double o[] = {-0.45, 0.47, 0.76, 1.05};
    wb_supervisor_field_set_sf_vec3f(position, p);
    wb_supervisor_field_set_sf_rotation(orientation, o);
  } else if (std::strcmp(scene, "orientation-v1") == 0) {
    wb_supervisor_field_import_mf_node_from_string(children, -1, nextScene.c_str());
    ready = completeGroup("WEBEEBLOCKS_ORIENTATION_SCENE", kOrientationSceneChildren) &&
      orientationObserver() &&
      !wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_SCENE") &&
      !wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_EVALUATORS") &&
      !wb_supervisor_node_get_from_def("WEBEEBLOCKS_SEQUENCE_SCENE") &&
      !wb_supervisor_node_get_from_def("WEBEEBLOCKS_ALTITUDE_SCENE");
    const double p[] = {-1.8, -1.6, 1.7};
    const double o[] = {-0.45, 0.47, 0.76, 1.05};
    wb_supervisor_field_set_sf_vec3f(position, p);
    wb_supervisor_field_set_sf_rotation(orientation, o);
  } else {
    wb_supervisor_field_import_mf_node_from_string(children, -1, legacyScene.c_str());
    if (completeGroup("WEBEEBLOCKS_LEGACY_SCENE", kLegacySceneChildren)) {
      wb_supervisor_field_import_mf_node_from_string(children, -1, legacyEvaluators.c_str());
      ready = completeGroup("WEBEEBLOCKS_LEGACY_EVALUATORS", kLegacyEvaluatorChildren);
    }
    wb_supervisor_field_set_sf_vec3f(position, oldPosition);
    wb_supervisor_field_set_sf_rotation(orientation, oldOrientation);
  }
  if (!ready) return 0;  // No partial import may authorize takeoff.
  selected = scene;
  return 1;
}

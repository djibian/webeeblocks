#ifndef WEBEEBLOCKS_SCHOOL_DECISION_H_SCENE_GATE_H
#define WEBEEBLOCKS_SCHOOL_DECISION_H_SCENE_GATE_H

/* Classroom-only native scene admission: no Blockly AST, motor commands or
 * physically qualified controller. Independently validate actual Webots
 * nodes before SCENE_OK and on every subsequent school-ready check.
 * The dedicated scene-local oracle attests the same geometry at startup.
 */
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <cmath>
#include <cstdio>
#include <cstring>

namespace webeeblocks_a4_gate {
constexpr int kChildren = 29;  // 23 visual Pose nodes + six physical Solids.
constexpr const char *kObserver = "Progression decision H native evaluator";
constexpr const char *kController = "progression_decision_h_v1";

inline bool near(double a, double b) {
  return std::isfinite(a) && std::fabs(a - b) <= 0.000001;
}

inline bool stringField(WbNodeRef node, const char *field, const char *value) {
  WbFieldRef f = node ? wb_supervisor_node_get_field(node, field) : nullptr;
  const char *actual = f ? wb_supervisor_field_get_sf_string(f) : nullptr;
  return actual && !std::strcmp(actual, value);
}

inline bool observer(WbNodeRef group) {
  WbFieldRef children = group ? wb_supervisor_node_get_field(group, "children") : nullptr;
  if (!children || wb_supervisor_field_get_count(children) != kChildren)
    return false;
  for (int i = 0; i < kChildren; ++i) {
    WbNodeRef node = wb_supervisor_field_get_mf_node(children, i);
    const char *type = node ? wb_supervisor_node_get_type_name(node) : nullptr;
    if (!type || std::strcmp(type, i < 23 ? "Pose" : "Solid"))
      return false;
    if (i >= 23) continue;
    WbFieldRef nested = wb_supervisor_node_get_field(node, "children");
    if (!nested || wb_supervisor_field_get_count(nested) != (i == 0 ? 2 : 1))
      return false;
    WbNodeRef glyph = wb_supervisor_field_get_mf_node(nested, 0);
    const char *glyphType = glyph ? wb_supervisor_node_get_type_name(glyph) : nullptr;
    if (!glyphType || std::strcmp(glyphType, "Shape")) return false;
    if (i != 0) continue;
    WbNodeRef actual = wb_supervisor_field_get_mf_node(nested, 1);
    const char *actualType = actual ? wb_supervisor_node_get_type_name(actual) : nullptr;
    if (!actualType || std::strcmp(actualType, "Robot") ||
        !stringField(actual, "controller", kController) ||
        !stringField(actual, "name", kObserver))
      return false;
    WbFieldRef sup = wb_supervisor_node_get_field(actual, "supervisor");
    WbFieldRef sync = wb_supervisor_node_get_field(actual, "synchronization");
    if (!sup || !sync || !wb_supervisor_field_get_sf_bool(sup) ||
        !wb_supervisor_field_get_sf_bool(sync))
      return false;
  }
  return true;
}

inline bool collider(const char *def, const double p[3], const double box[3]) {
  WbNodeRef node = wb_supervisor_node_get_from_def(def);
  const char *type = node ? wb_supervisor_node_get_type_name(node) : nullptr;
  if (!type || std::strcmp(type, "Solid")) return false;
  const double *actualP = wb_supervisor_node_get_position(node);
  const double *rot = wb_supervisor_node_get_orientation(node);
  WbFieldRef b = wb_supervisor_node_get_field(node, "boundingObject");
  WbNodeRef shape = b ? wb_supervisor_field_get_sf_node(b) : nullptr;
  const char *shapeType = shape ? wb_supervisor_node_get_type_name(shape) : nullptr;
  if (!shapeType || std::strcmp(shapeType, "Box")) return false;
  WbFieldRef size = wb_supervisor_node_get_field(shape, "size");
  const double *actualSize = size ? wb_supervisor_field_get_sf_vec3f(size) : nullptr;
  if (!actualP || !rot || !actualSize) return false;
  for (int i = 0; i < 3; ++i)
    if (!near(actualP[i], p[i]) || !near(actualSize[i], box[i]) ||
        actualSize[i] <= 0) return false;
  for (int i = 0; i < 9; ++i)
    if (!near(rot[i], i % 4 == 0 ? 1.0 : 0.0)) return false;
  return true;
}

inline bool valid(char variant) {
  if (variant != 'a' && variant != 'b') return false;
  WbNodeRef world = wb_supervisor_node_get_from_def("WEBEEBLOCKS_CLASSROOM_START_WORLD");
  const char *worldType = world ? wb_supervisor_node_get_type_name(world) : nullptr;
  if (!worldType || std::strcmp(worldType, "WorldInfo")) return false;
  const char *sceneDef = variant == 'a' ? "WEBEEBLOCKS_DECISION_A_SCENE" :
                                         "WEBEEBLOCKS_DECISION_B_SCENE";
  WbNodeRef group = wb_supervisor_node_get_from_def(sceneDef);
  const char *type = group ? wb_supervisor_node_get_type_name(group) : nullptr;
  if (!type || std::strcmp(type, "Group") || !observer(group))
    return false;
  const double hX = variant == 'a' ? .750 : 1.350;
  const double curbX = variant == 'a' ? 1.350 : .750;
  const char *names[6] = {
    "H_LEFT", "H_RIGHT", "H_BAR", "THRESHOLD",
    "CORRIDOR_LEFT", "CORRIDOR_RIGHT"
  };
  const double positions[6][3] = {
    {hX, .300, .500}, {hX, -.300, .500}, {hX, 0, .740},
    {curbX, 0, .350}, {.700, .420, .520}, {.700, -.420, .520}
  };
  const double boxes[6][3] = {
    {.070, .065, 1.00}, {.070, .065, 1.00}, {.070, .570, .240},
    {.100, .740, .700}, {1.80, .080, 1.04}, {1.80, .080, 1.04}
  };
  for (int i = 0; i < 6; ++i) {
    char def[80];
    const int n = std::snprintf(def, sizeof(def), "ACTIVITY4_%c_%s",
                                variant == 'a' ? 'A' : 'B', names[i]);
    if (n <= 0 || static_cast<size_t>(n) >= sizeof(def) ||
        !collider(def, positions[i], boxes[i])) return false;
  }
  return true;
}
}  // namespace webeeblocks_a4_gate

#endif

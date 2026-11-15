/* CI-only native R2025a exercise of the actual SCHOOL scene selector.
 * No Blockly, no motor controls, no physics or physical-flight overrides.
 * This probe is deliberately not the product student flight controller.
 */
#include "../crazyflie_runtime_v2/activity_scene.h"
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <cstdio>
#include <cstring>

static int fail(const char *reason) {
  std::fprintf(stderr, "WEBEEBLOCKS_A4_SCENE_SELECTOR_FATAL %s\n", reason);
  std::fflush(stderr);
  wb_robot_cleanup();
  return 2;
}

static bool settle(int step) {
  for (int i = 0; i < 16; ++i)
    if (wb_robot_step(step) < 0) return false;
  return true;
}

static bool only(const char *want, const char *reject) {
  return wb_supervisor_node_get_from_def(want) != nullptr &&
         wb_supervisor_node_get_from_def(reject) == nullptr &&
         webeeblocks_activity_scene_ready();
}

int main(void) {
  wb_robot_init();
  const int step = (int)wb_robot_get_basic_time_step();
  const char *name = wb_robot_get_name();
  if (step <= 0 || !name || std::strcmp(name, "A4 native selector test") ||
      wb_supervisor_node_get_from_def("WEBEEBLOCKS_DECISION_A_SCENE") ||
      wb_supervisor_node_get_from_def("WEBEEBLOCKS_DECISION_B_SCENE") ||
      webeeblocks_activity_scene_ready())
    return fail("world precondition or empty-world readiness mismatch");

  // Even at rest an unknown token must not damage/authorize a world.
  if (webeeblocks_select_activity_scene("decision-h-unknown-v1") ||
      webeeblocks_activity_scene_ready())
    return fail("unknown scene unexpectedly accepted");

  if (!webeeblocks_select_activity_scene("decision-h-a-v1") ||
      !only("WEBEEBLOCKS_DECISION_A_SCENE", "WEBEEBLOCKS_DECISION_B_SCENE") ||
      !settle(step))
    return fail("A failed native import, exact observer, or live READY");
  std::puts("WEBEEBLOCKS_A4_SCENE_SELECTOR_ACK variant=a generation=1");
  std::fflush(stdout);

  // Direct A -> B transition must stop/remove A's evaluator and colliders.
  if (!webeeblocks_select_activity_scene("decision-h-b-v1") ||
      !only("WEBEEBLOCKS_DECISION_B_SCENE", "WEBEEBLOCKS_DECISION_A_SCENE") ||
      !settle(step))
    return fail("B failed to replace A without residual nodes");
  std::puts("WEBEEBLOCKS_A4_SCENE_SELECTOR_ACK variant=b generation=1");
  std::fflush(stdout);

  // A new A observer must start with a freshly imported genuine scene.
  if (!webeeblocks_select_activity_scene("decision-h-a-v1") ||
      !only("WEBEEBLOCKS_DECISION_A_SCENE", "WEBEEBLOCKS_DECISION_B_SCENE") ||
      !settle(step))
    return fail("A reattach failed or B scene leaked");
  std::puts("WEBEEBLOCKS_A4_SCENE_SELECTOR_ACK variant=a generation=2");
  std::fflush(stdout);

  if (webeeblocks_select_activity_scene("nonsense") ||
      !only("WEBEEBLOCKS_DECISION_A_SCENE", "WEBEEBLOCKS_DECISION_B_SCENE"))
    return fail("unknown request destroyed or authorized A");
  std::puts("WEBEEBLOCKS_A4_SCENE_SELECTOR_NATIVE_PASS A-B-A, stale-free, unknown-refused");
  std::fflush(stdout);
  wb_robot_cleanup();
  return 0;
}

/* CI-only Webots R2025a front-range falsification at identical native pose.
 * Replaces the pupil flight controller in disposable CI worlds. No motors,
 * AST, Blockly project or physical Crazyflie qualification dependency.
 */
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <webots/distance_sensor.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#define WB_DH_RANGE_SENSOR "range_front"
#define WB_DH_CRAFT "Crazyflie WebeeBlocks"

static int invalid(const char *why) {
  fprintf(stderr, "WEBEEBLOCKS_DECISION_H_RANGE_FATAL %s\n", why);
  fflush(stderr);
  wb_robot_cleanup();
  return 2;
}

int main(void) {
  wb_robot_init();
  const int step = (int)wb_robot_get_basic_time_step();
  const char *name = wb_robot_get_name();
  if (step <= 0 || !name || strcmp(name, WB_DH_CRAFT) != 0)
    return invalid("invalid basic time step or craft identity");
  WbNodeRef a = wb_supervisor_node_get_from_def("WEBEEBLOCKS_DECISION_A_SCENE");
  WbNodeRef b = wb_supervisor_node_get_from_def("WEBEEBLOCKS_DECISION_B_SCENE");
  if ((!a && !b) || (a && b))
    return invalid("ambiguous scene identity");
  WbNodeRef self = wb_supervisor_node_get_self();
  WbFieldRef position_field = self ? wb_supervisor_node_get_field(self, "translation") : NULL;
  WbFieldRef rotation_field = self ? wb_supervisor_node_get_field(self, "rotation") : NULL;
  WbDeviceTag front = wb_robot_get_device(WB_DH_RANGE_SENSOR);
  if (!self || !position_field || !rotation_field || !front)
    return invalid("missing supervisor pose or real front sensor");

  const double pose[3] = {0.20, 0.0, 0.750};
  const double facing[4] = {0.0, 0.0, 1.0, 0.0};
  wb_supervisor_field_set_sf_vec3f(position_field, pose);
  wb_supervisor_field_set_sf_rotation(rotation_field, facing);
  wb_supervisor_node_reset_physics(self);
  wb_distance_sensor_enable(front, step);

  /* The first post-enable native step is fresh. Delay would allow gravity
   * to drop the sensor below the H-bar (underside z=0.620). */
  if (wb_robot_step(step) < 0)
    return invalid("first post-enable native step unavailable");
  const double *world = wb_supervisor_node_get_position(self);
  const double measured_m = wb_distance_sensor_get_value(front) / 1000.0;
  if (!world || !isfinite(world[0]) || !isfinite(world[1]) || !isfinite(world[2]) ||
      fabs(world[0] - pose[0]) > 0.035 || fabs(world[1]) > 0.035 ||
      fabs(world[2] - pose[2]) > 0.045 || !isfinite(measured_m) ||
      measured_m < 0.0 || measured_m > 2.001)
    return invalid("invalid fresh pose or sensor sample");

  /* Distinct physical bands with a 0.15 m gap; theoretical 0.515/1.115 m
   * cannot substitute for a genuine native multi-ranger measurement. */
  const int acceptable = a ? (measured_m >= 0.35 && measured_m <= 0.75) :
                            (measured_m >= 0.90 && measured_m <= 1.35);
  if (!acceptable) {
    fprintf(stderr,
      "WEBEEBLOCKS_DECISION_H_RANGE_FATAL variant=%c observed_m=%.9f\n",
      a ? 'a' : 'b', measured_m);
    fflush(stderr);
    wb_robot_cleanup();
    return 2;
  }
  printf("WEBEEBLOCKS_DECISION_H_RANGE_PASS variant=%c observed_m=%.9f "
         "pose_x=%.9f pose_y=%.9f pose_z=%.9f\n",
         a ? 'a' : 'b', measured_m, world[0], world[1], world[2]);
  fflush(stdout);
  wb_robot_cleanup();
  return 0;
}

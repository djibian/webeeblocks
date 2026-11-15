/* A5 Draft-only Webots R2025a witness: actual two Multi-ranger readings.
 * Robot is teleported by this test-only Supervisor; motors are never driven.
 * Neither a pupil program nor a physical-flight qualification is implied.
 */
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <webots/distance_sensor.h>

static int fail(const char *reason) {
  fprintf(stderr, "WEBEEBLOCKS_A5_SENSOR_FATAL %s\n", reason);
  fflush(stderr);
  wb_robot_cleanup();
  return 2;
}
static int verify_box(const char *name, const double pos[3],
                      const double dims[3]) {
  WbNodeRef solid = wb_supervisor_node_get_from_def(name);
  if (!solid || strcmp(wb_supervisor_node_get_type_name(solid), "Solid"))
    return 0;
  const double *actual = wb_supervisor_node_get_position(solid);
  WbFieldRef bound = wb_supervisor_node_get_field(solid, "boundingObject");
  WbNodeRef geom = bound ? wb_supervisor_field_get_sf_node(bound) : NULL;
  if (!actual || !geom || strcmp(wb_supervisor_node_get_type_name(geom), "Box"))
    return 0;
  WbFieldRef field = wb_supervisor_node_get_field(geom, "size");
  const double *size = field ? wb_supervisor_field_get_sf_vec3f(field) : NULL;
  if (!size) return 0;
  for (int j = 0; j < 3; ++j)
    if (!isfinite(actual[j]) || !isfinite(size[j]) ||
        fabs(actual[j]-pos[j]) > 0.000001 ||
        fabs(size[j]-dims[j]) > 0.000001) return 0;
  return 1;
}
static int observe(WbNodeRef self, WbFieldRef translation,
                   WbFieldRef rotation, WbDeviceTag front,
                   WbDeviceTag left, int step, char variant,
                   const char *stage, double x, double *range) {
  const double pose[] = {x, 0.0, 0.50};
  const double facing[] = {0.0, 0.0, 1.0, 0.0};
  wb_supervisor_field_set_sf_vec3f(translation, pose);
  wb_supervisor_field_set_sf_rotation(rotation, facing);
  wb_supervisor_node_reset_physics(self);
  /* Two real physics/sensor frames after the explicitly disclosed teleport.
   * This is NOT motorized flight and cannot prove dynamic reachability. */
  for (int i = 0; i < 2; ++i)
    if (wb_robot_step(step) == -1) return 0;
  const double *world = wb_supervisor_node_get_position(self);
  if (!world || !isfinite(world[0]) || !isfinite(world[1]) ||
      !isfinite(world[2]) || fabs(world[0]-pose[0]) > 0.04 ||
      fabs(world[1]-pose[1]) > 0.04 || fabs(world[2]-pose[2]) > 0.09)
    return 0;
  const double forward = wb_distance_sensor_get_value(front) / 1000.0;
  const double port = wb_distance_sensor_get_value(left) / 1000.0;
  if (!isfinite(forward) || !isfinite(port) || forward < 0 ||
      port < 0 || forward > 2.001 || port > 2.001)
    return 0;
  *range = !strcmp(stage,"origin") ? forward : port;
  printf("WEBEEBLOCKS_A5_SENSOR_SAMPLE variant=%c stage=%s "
         "front_m=%.9f left_m=%.9f "
         "x=%.9f y=%.9f z=%.9f time=%.9f\n",
         variant, stage, forward, port, world[0],world[1],world[2],
         wb_robot_get_time());
  fflush(stdout);
  return 1;
}
int main(void) {
  wb_robot_init();
  int step=(int)wb_robot_get_basic_time_step();
  if (step < 8 || step > 64 ||
      strcmp(wb_robot_get_name(),"Crazyflie WebeeBlocks"))
    return fail("untrusted robot identity or native timestep");
  char variant=0;
  for (char letter='A'; letter<='C'; ++letter) {
    char key[70];
    snprintf(key,sizeof key,"WEBEEBLOCKS_REACTIVE_L_%c_SCENE",letter);
    if (wb_supervisor_node_get_from_def(key)) {
      if (variant) return fail("multiple A5 scenes simultaneously imported");
      variant=letter;
    }
  }
  if (!variant) return fail("missing unique A5 scene");
  const double front_pos[] = {variant=='B'?1.42:1.02,0,0.55};
  const double front_size[] = {.08,.64,1.10};
  const double turn_x=variant=='B'?1.20:.80;
  const double sign=variant=='A'?-1.0:1.0;
  const double side_pos[] = {turn_x,sign*.320,.55};
  const double side_size[] = {.48,.08,1.10};
  const double terminal_pos[] = {turn_x,-sign*1.270,.55};
  const double terminal_size[] = {.78,.08,1.10};
  char def[90];
  snprintf(def,sizeof def,"ACTIVITY5_%c_L_FRONT",variant);
  if (!verify_box(def,front_pos,front_size))
    return fail("native first-wall collider geometry changed");
  snprintf(def,sizeof def,"ACTIVITY5_%c_L_SIDE",variant);
  if (!verify_box(def,side_pos,side_size))
    return fail("native turn-wall collider geometry changed");
  snprintf(def,sizeof def,"ACTIVITY5_%c_TERMINAL",variant);
  if (!verify_box(def,terminal_pos,terminal_size))
    return fail("native terminal collider geometry changed");
  WbNodeRef self=wb_supervisor_node_get_self();
  WbFieldRef t=self?wb_supervisor_node_get_field(self,"translation"):NULL;
  WbFieldRef r=self?wb_supervisor_node_get_field(self,"rotation"):NULL;
  WbDeviceTag front=wb_robot_get_device("range_front");
  WbDeviceTag left=wb_robot_get_device("range_left");
  if (!self||!t||!r||!front||!left)
    return fail("native supervisor or Multi-ranger device unavailable");
  wb_distance_sensor_enable(front,step);
  wb_distance_sensor_enable(left,step);
  if (wb_robot_step(step)==-1) return fail("no initial sensor frame");
  double first=0,second=0;
  if (!observe(self,t,r,front,left,step,variant,"origin",0,&first))
    return fail("unattested first native ray");
  if (!observe(self,t,r,front,left,step,variant,"junction",turn_x,&second))
    return fail("unattested junction native ray");
  printf("WEBEEBLOCKS_A5_SENSOR_DONE variant=%c first_m=%.9f second_m=%.9f "
         "test_only=true\n",variant,first,second);
  fflush(stdout);
  wb_robot_cleanup();
  return 0;
}

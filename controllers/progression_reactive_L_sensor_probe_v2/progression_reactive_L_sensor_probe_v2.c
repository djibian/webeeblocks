/* A5 Draft-only Webots R2025a witness: five staged native Multi-ranger readings.
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
  fprintf(stderr, "WEBEEBLOCKS_A5_V2_SENSOR_FATAL %s\n", reason);
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
                   const char *stage, double x, double y, double yaw,
                   double *range) {
  const double pose[] = {x, y, .50};
  const double facing[] = {0.0, 0.0, 1.0, yaw};
  wb_supervisor_field_set_sf_vec3f(translation, pose);
  wb_supervisor_field_set_sf_rotation(rotation, facing);
  wb_supervisor_node_reset_physics(self);
  /* No motor commands: two genuine physics/sensor steps after the teleport. */
  for (int i=0;i<2;++i)
    if (wb_robot_step(step)==-1) return 0;
  const double *world = wb_supervisor_node_get_position(self);
  const double *orientation = wb_supervisor_node_get_orientation(self);
  if (!world || !orientation ||
      !isfinite(orientation[0]) || !isfinite(orientation[3]) ||
      fabs(orientation[0]-cos(yaw))>.10 ||
      fabs(orientation[3]-sin(yaw))>.10 ||
      !isfinite(world[0]) || !isfinite(world[1]) ||
      !isfinite(world[2]) || fabs(world[0]-pose[0])>.04 ||
      fabs(world[1]-pose[1])>.04 || fabs(world[2]-pose[2])>.09)
    return 0;
  const double forward=wb_distance_sensor_get_value(front)/1000.0;
  const double port=wb_distance_sensor_get_value(left)/1000.0;
  if (!isfinite(forward)||!isfinite(port)||forward<0||port<0||
      forward>2.001||port>2.001)
    return 0;
  *range=strcmp(stage,"origin")==0?forward:port;
  printf("WEBEEBLOCKS_A5_V2_SENSOR_SAMPLE variant=%c stage=%s "
         "front_m=%.9f left_m=%.9f "
         "x=%.9f y=%.9f z=%.9f yaw=%.9f time=%.9f\n",
         variant,stage,forward,port,
         world[0],world[1],world[2],
         atan2(orientation[3],orientation[0]),wb_robot_get_time());
  fflush(stdout);
  return 1;
}
int main(void) {
  wb_robot_init();
  const int step=(int)wb_robot_get_basic_time_step();
  if (step<8||step>64||
      strcmp(wb_robot_get_name(),"Crazyflie WebeeBlocks")!=0)
    return fail("unexpected native craft identity or step");
  char variant=0;
  for (char v='A';v<='C';++v) {
    char name[72];
    snprintf(name,sizeof name,"WEBEEBLOCKS_REACTIVE_L_V2_%c_SCENE",v);
    if (wb_supervisor_node_get_from_def(name)) {
      if (variant) return fail("multiple A5 V2 scenes");
      variant=v;
    }
  }
  if (!variant) return fail("no attested A5 V2 scene");

  const double first_front_pos[]={1.02,0,.55};
  const double first_front_size[]={.08,.64,1.10};
  const double first_side_pos[]={.80,-.32,.55};
  const double first_side_size[]={.48,.08,1.10};
  const double second_front_pos[]={.80,1.25,.55};
  const double second_front_size[]={.64,.08,1.10};
  const double second_side_pos[]={variant=='A'?.48:1.12,1.0,.55};
  const double second_side_size[]={.08,.50,1.10};
  const double terminal_pos[]={
    variant=='A'?1.95:(variant=='B'?-1.02:-.45),
    variant=='C'?1.95:1.0,.55
  };
  const double terminal_size[]={
    variant=='C'?.72:.08,variant=='C'?.08:.72,1.10
  };
  char name[90];
  snprintf(name,sizeof name,"ACTIVITY5_V2_%c_L1_FRONT",variant);
  if (!verify_box(name,first_front_pos,first_front_size))
    return fail("bad actual first L front");
  snprintf(name,sizeof name,"ACTIVITY5_V2_%c_L1_SIDE",variant);
  if (!verify_box(name,first_side_pos,first_side_size))
    return fail("bad actual first L side");
  snprintf(name,sizeof name,"ACTIVITY5_V2_%c_L2_FRONT",variant);
  if (!verify_box(name,second_front_pos,second_front_size))
    return fail("bad actual second L front");
  snprintf(name,sizeof name,"ACTIVITY5_V2_%c_L2_SIDE",variant);
  if (!verify_box(name,second_side_pos,second_side_size))
    return fail("bad actual second L side");
  if (variant=='C') {
    const double third_front_pos[]={-.68,1.0,.55};
    const double third_front_size[]={.08,.64,1.10};
    const double third_side_pos[]={-.45,.68,.55};
    const double third_side_size[]={.48,.08,1.10};
    if (!verify_box("ACTIVITY5_V2_C_L3_FRONT",
                    third_front_pos,third_front_size) ||
        !verify_box("ACTIVITY5_V2_C_L3_SIDE",
                    third_side_pos,third_side_size))
      return fail("bad actual third L");
  }
  snprintf(name,sizeof name,"ACTIVITY5_V2_%c_TERMINAL",variant);
  if (!verify_box(name,terminal_pos,terminal_size))
    return fail("bad actual terminal obstacle");

  WbNodeRef self=wb_supervisor_node_get_self();
  WbFieldRef pos=self?wb_supervisor_node_get_field(self,"translation"):NULL;
  WbFieldRef rot=self?wb_supervisor_node_get_field(self,"rotation"):NULL;
  WbDeviceTag front=wb_robot_get_device("range_front");
  WbDeviceTag left=wb_robot_get_device("range_left");
  if (!self||!pos||!rot||!front||!left)
    return fail("native Supervisor or Multi-ranger unavailable");
  wb_distance_sensor_enable(front,step);
  wb_distance_sensor_enable(left,step);
  if (wb_robot_step(step)==-1)
    return fail("no initial genuine sensor frame");
  double first=0,second=0,third=0,after_pivot=0,after_rewind=0;
  if (!observe(self,pos,rot,front,left,step,variant,
               "origin",0,0,0,&first))
    return fail("unattested first native observation");
  if (!observe(self,pos,rot,front,left,step,variant,
               "junction",.8,0,0,&second))
    return fail("unattested first corner native observation");
  /* Facing +Y after the first left turn: left range faces global -X. */
  if (!observe(self,pos,rot,front,left,step,variant,
               "second",.8,1.0,1.5707963267948966,&third))
    return fail("unattested second corner native observation");
  /* Same x/y after an additional 90-degree turn. The left sensor now
   * faces global -Y rather than west. Real rays must establish whether the
   * historic left-range observation is still available after this pivot. */
  if (!observe(self,pos,rot,front,left,step,variant,
               "after-pivot",.8,1.0,3.1415926535897932,&after_pivot))
    return fail("unattested post-pivot native observation");
  /* Turn back to the former orientation without moving x/y. If the old
   * ray is readable again, remembering it is an efficiency advantage, NOT
   * a logically necessary condition under unrestricted pupil movement.
   * CI-only teleport isolates the sensor frame, not a flown pupil program. */
  if (!observe(self,pos,rot,front,left,step,variant,
               "after-rewind",.8,1.0,1.5707963267948966,&after_rewind))
    return fail("unattested native reobservation after reverse pivot");
  printf("WEBEEBLOCKS_A5_V2_SENSOR_DONE variant=%c first_m=%.9f "
         "second_m=%.9f third_m=%.9f fourth_m=%.9f fifth_m=%.9f test_only=true\n",
         variant,first,second,third,after_pivot,after_rewind);
  fflush(stdout);
  wb_robot_cleanup();
  return 0;
}

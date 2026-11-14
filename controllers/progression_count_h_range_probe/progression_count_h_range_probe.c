/* Negative, CI-only Webots R2025a witness: detect A6 counting leakage by
 * actual range_back from a real Crazyflie PROTO at the common landing zone.
 * No motors, Blockly, mission authority, or physical-flight binary linkage.
 * A PASS means the flaw is reproducible, NOT the activity is acceptable.
 */
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <webots/distance_sensor.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#define WB_COUNT_BACK_SENSOR "range_back"
#define WB_COUNT_CRAFT_NAME "Crazyflie WebeeBlocks"

static int invalid(const char *why) {
  fprintf(stderr, "WEBEEBLOCKS_COUNT_H_BACK_FATAL %s\n", why);
  fflush(stderr);
  wb_robot_cleanup();
  return 2;
}

int main(void) {
  wb_robot_init();
  const int step=(int)wb_robot_get_basic_time_step();
  const char *name=wb_robot_get_name();
  if (step<=0 || !name || strcmp(name,WB_COUNT_CRAFT_NAME)!=0)
    return invalid("unexpected native robot identity or step");
  int variant=0;
  for(int n=1;n<=3;n++) {
    char key[70];
    snprintf(key,sizeof key,"WEBEEBLOCKS_COUNT_%d_SCENE",n);
    if(wb_supervisor_node_get_from_def(key)) {
      if(variant) return invalid("ambiguous native A6 scene variants");
      variant=n;
    }
  }
  if(!variant) return invalid("no native A6 scene variant");
  WbNodeRef self=wb_supervisor_node_get_self();
  WbFieldRef pos=self?wb_supervisor_node_get_field(self,"translation"):NULL;
  WbFieldRef rot=self?wb_supervisor_node_get_field(self,"rotation"):NULL;
  WbDeviceTag back=wb_robot_get_device(WB_COUNT_BACK_SENSOR);
  if(!self||!pos||!rot||!back)
    return invalid("missing supervisor pose or genuine rear range sensor");

  /* Identical common landing position, with ray crossing the H top-bar band.
   * This diagnostic deliberately makes no airborne/landing claim. */
  const double pose[3]={1.48,0.0,0.750};
  const double facing[4]={0.0,0.0,1.0,0.0};
  wb_supervisor_field_set_sf_vec3f(pos,pose);
  wb_supervisor_field_set_sf_rotation(rot,facing);
  wb_supervisor_node_reset_physics(self);
  wb_distance_sensor_enable(back,step);
  if(wb_robot_step(step)<0)
    return invalid("native sensor sample unavailable after enabling");

  const double *world=wb_supervisor_node_get_position(self);
  const double range=wb_distance_sensor_get_value(back)/1000.0;
  if(!world||!isfinite(world[0])||!isfinite(world[1])||
     !isfinite(world[2])||!isfinite(range)||
     fabs(world[0]-pose[0])>.035||fabs(world[1])>.035||
     fabs(world[2]-pose[2])>.045||range<0||range>2.001)
    return invalid("stale, nonfinite or displaced rear sample");

  const int disclosed=
    (variant==1&&range>=1.85&&range<=2.001)||
    (variant==2&&range>=1.20&&range<=1.70)||
    (variant==3&&range>=0.35&&range<=0.80);
  if(!disclosed) {
    fprintf(stderr,"WEBEEBLOCKS_COUNT_H_BACK_FATAL unexpected n=%d range_m=%.9f\n",
            variant,range);
    fflush(stderr);
    wb_robot_cleanup();
    return 2;
  }
  printf("WEBEEBLOCKS_COUNT_H_BACK_OBSERVED variant=%d range_m=%.9f "
         "pose_x=%.9f pose_y=%.9f pose_z=%.9f\n",
         variant,range,world[0],world[1],world[2]);
  fflush(stdout);
  wb_robot_cleanup();
  return 0;
}

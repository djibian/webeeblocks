/* CI-only Webots R2025a physical falsification of the A6 terminal mask.
 * Sample real Crazyflie range_back at all 3 pads in all 3 count variants.
 * No motors, Blockly, mission authority, or physical-flight binary linkage.
 * A PASS only proves terminal masking at the tested poses, NOT pupil success.
 */
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <webots/distance_sensor.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#define WB_COUNT_BACK_SENSOR "range_back"
#define WB_COUNT_UP_SENSOR "range_up"
#define WB_COUNT_FRONT_SENSOR "range_front"
#define WB_COUNT_LEFT_SENSOR "range_left"
#define WB_COUNT_RIGHT_SENSOR "range_right"
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
  WbDeviceTag up=wb_robot_get_device(WB_COUNT_UP_SENSOR);
  WbDeviceTag front=wb_robot_get_device(WB_COUNT_FRONT_SENSOR);
  WbDeviceTag left=wb_robot_get_device(WB_COUNT_LEFT_SENSOR);
  WbDeviceTag right=wb_robot_get_device(WB_COUNT_RIGHT_SENSOR);
  if(!self||!pos||!rot||!back||!up||!front||!left||!right)
    return invalid("missing supervisor pose or genuine full Multi-ranger sensors");

  /* Probe ALL three possible pads in each world, before any pupil program.
   * The rear ray must see the same cyan finish ribbon independent of count.
   * The body remains parked (no flight or obstacle crossing is certified).
   */
  const double pad_y[] = {0.0, 0.55, -0.55};
  const double facing[] = {0.0, 0.0, 1.0, 0.0};
  wb_distance_sensor_enable(back, step);
  wb_distance_sensor_enable(up, step);
  wb_distance_sensor_enable(front, step);
  wb_distance_sensor_enable(left, step);
  wb_distance_sensor_enable(right, step);
  /* Track both genuine physical colliders before the experiment.
   * An all-zero contact stream cannot qualify a collision-free path. */
  char gate_def[80];
  snprintf(gate_def, sizeof gate_def, "ACTIVITY6_%d_H_1_BAR", variant);
  WbNodeRef first_bar = wb_supervisor_node_get_from_def(gate_def);
  if (!first_bar) return invalid("missing calibration H bar");
  wb_supervisor_node_enable_contact_points_tracking(self, step, true);
  wb_supervisor_node_enable_contact_points_tracking(first_bar, step, false);
  for (int pad = 0; pad < 3; ++pad) {
    const double pose[] = {1.48, pad_y[pad], 0.750};
    wb_supervisor_field_set_sf_vec3f(pos, pose);
    wb_supervisor_field_set_sf_rotation(rot, facing);
    wb_supervisor_node_reset_physics(self);
    if (wb_robot_step(step) < 0)
      return invalid("native sensor sample unavailable after enabling");
    const double *world = wb_supervisor_node_get_position(self);
    const double range = wb_distance_sensor_get_value(back) / 1000.0;
    if (!world || !isfinite(world[0]) || !isfinite(world[1]) ||
        !isfinite(world[2]) || !isfinite(range) ||
        fabs(world[0] - pose[0]) > 0.035 ||
        fabs(world[1] - pose[1]) > 0.035 ||
        fabs(world[2] - pose[2]) > 0.045 || range < 0 ||
        range > 2.001)
      return invalid("stale, nonfinite or displaced rear sample");

    /* Genuine rear ray must now intersect the terminal band. This is
     * deliberately NOT a test of passage feasibility or variable use. */
    if (range < 0.12 || range > 0.31) {
      fprintf(stderr, "WEBEEBLOCKS_COUNT_H_BACK_FATAL unmasked variant=%d "
              "pad=%d range_m=%.9f\n", variant, pad, range);
      fflush(stderr);
      wb_robot_cleanup();
      return 2;
    }
    printf("WEBEEBLOCKS_COUNT_H_BACK_MASKED variant=%d pad=%d "
           "range_m=%.9f pose_x=%.9f pose_y=%.9f pose_z=%.9f\n",
           variant, pad, range, world[0], world[1], world[2]);
    fflush(stdout);

    /* The historical screen test at z=0.750 is NOT evidence about arrival:
     * its physical cyan Solid occupies z=[0.640,0.880] whereas flight
     * approaches the pad at z~0.415 and touches Floor at z~0.015.
     * Falsify count leakage at both actual low phases with every genuine
     * Multi-ranger channel, including back and up. Teleportation remains
     * TEST ONLY and no native flight or memory result is claimed. */
    const double stages[2]={0.415,0.015};
    const char *phase_names[2]={"approach","landed"};
    const WbDeviceTag sensors[5]={front,back,left,right,up};
    for (int phase=0;phase<2;++phase) {
      const double low_pose[3]={1.48,pad_y[pad],stages[phase]};
      wb_supervisor_field_set_sf_vec3f(pos,low_pose);
      wb_supervisor_field_set_sf_rotation(rot,facing);
      wb_supervisor_node_reset_physics(self);
      if (wb_robot_step(step)<0)
        return invalid("terminal low-altitude Multi-ranger sampling failed");
      const double *seen=wb_supervisor_node_get_position(self);
      double ranges[5];
      for (int channel=0;channel<5;++channel) {
        ranges[channel]=wb_distance_sensor_get_value(sensors[channel])/1000.0;
        if (!isfinite(ranges[channel]) ||
            ranges[channel]<0 || ranges[channel]>2.001)
          return invalid("terminal low-altitude sensor absent or out of range");
      }
      if (!seen || !isfinite(seen[0]) || !isfinite(seen[1]) ||
          !isfinite(seen[2]) || fabs(seen[0]-low_pose[0])>0.035 ||
          fabs(seen[1]-low_pose[1])>0.035 ||
          fabs(seen[2]-low_pose[2])>0.045)
        return invalid("terminal low-altitude pose unavailable or displaced");
      printf("WEBEEBLOCKS_COUNT_H_TERMINAL_RANGES variant=%d pad=%d phase=%s "
             "front_m=%.9f back_m=%.9f left_m=%.9f right_m=%.9f up_m=%.9f "
             "pose_x=%.9f pose_y=%.9f pose_z=%.9f\n",
             variant,pad,phase_names[phase],ranges[0],ranges[1],
             ranges[2],ranges[3],ranges[4],seen[0],seen[1],seen[2]);
      fflush(stdout);
      /* Falsification only: a student could turn at the terminal pad and
       * reread genuine rays. Unlike the previous fixed-heading test, measure
       * three additional cardinal directions at both low phases. This does
       * NOT claim motorized turning or that all possible paths are covered. */
      const double quarter_pi=3.14159265358979323846/2.0;
      for(int heading=1;heading<=3;++heading) {
        const double yaw=heading*quarter_pi;
        const double rotated[4]={0.0,0.0,1.0,yaw};
        wb_supervisor_field_set_sf_vec3f(pos,low_pose);
        wb_supervisor_field_set_sf_rotation(rot,rotated);
        wb_supervisor_node_reset_physics(self);
        if(wb_robot_step(step)<0)
          return invalid("cardinal terminal sensor sample unavailable");
        const double *heading_pose=wb_supervisor_node_get_position(self);
        const double *heading_matrix=wb_supervisor_node_get_orientation(self);
        if(!heading_pose||!heading_matrix||
           !isfinite(heading_pose[0])||!isfinite(heading_pose[1])||
           !isfinite(heading_pose[2])||
           fabs(heading_pose[0]-low_pose[0])>.035||
           fabs(heading_pose[1]-low_pose[1])>.035||
           fabs(heading_pose[2]-low_pose[2])>.045||
           !isfinite(heading_matrix[0])||!isfinite(heading_matrix[3])||
           fabs(heading_matrix[0]-cos(yaw))>.080||
           fabs(heading_matrix[3]-sin(yaw))>.080)
          return invalid("cardinal terminal pose or heading unattested");
        double heading_ranges[5];
        for(int channel=0;channel<5;++channel) {
          heading_ranges[channel]=wb_distance_sensor_get_value(sensors[channel])/1000.0;
          if(!isfinite(heading_ranges[channel])||
             heading_ranges[channel]<0||heading_ranges[channel]>2.001)
            return invalid("cardinal terminal ray invalid");
        }
        printf("WEBEEBLOCKS_COUNT_H_HEADING_RANGES variant=%d pad=%d phase=%s "
               "yaw_deg=%d front_m=%.9f back_m=%.9f left_m=%.9f right_m=%.9f "
               "up_m=%.9f pose_x=%.9f pose_y=%.9f pose_z=%.9f\n",
               variant,pad,phase_names[phase],heading*90,
               heading_ranges[0],heading_ranges[1],heading_ranges[2],
               heading_ranges[3],heading_ranges[4],
               heading_pose[0],heading_pose[1],heading_pose[2]);
        fflush(stdout);
      }
    }
  }
  /* RESEARCH ONLY: genuine upward Multi-ranger ray at the same altitude
   * and heading immediately before, under and after EACH physical H.
   * Supervisor teleportation tests sensory observability; it DOES NOT
   * demonstrate a motor flight, state counting or a pupil algorithm.
   * Do not classify the count based on a single initial/terminal reading.
   */
  const double offsets[3]={-0.240,0.000,0.240};
  for(int gate=0;gate<variant;++gate) {
    const double centre=-0.850+0.850*gate;
    for(int phase=0;phase<3;++phase) {
      const double xyz[3]={centre+offsets[phase],0.0,0.415};
      wb_supervisor_field_set_sf_vec3f(pos,xyz);
      wb_supervisor_field_set_sf_rotation(rot,facing);
      wb_supervisor_node_reset_physics(self);
      if(wb_robot_step(step)<0)
        return invalid("native up-range observation unavailable");
      const double *seen=wb_supervisor_node_get_position(self);
      const double measured=wb_distance_sensor_get_value(up)/1000.0;
      int contacts=-1;
      const WbContactPoint *points=
        wb_supervisor_node_get_contact_points(self,true,&contacts);
      if(!seen||!isfinite(measured)||measured<0||measured>2.001 ||
         !isfinite(seen[0])||!isfinite(seen[1])||!isfinite(seen[2])||
         fabs(seen[0]-xyz[0])>.035||fabs(seen[1])>.035||
         fabs(seen[2]-xyz[2])>.045||contacts!=0||points)
        return invalid("up-ray pose, range or positive-contact control invalid");
      printf("WEBEEBLOCKS_COUNT_H_UP_SAMPLE variant=%d gate=%d phase=%d "
             "range_m=%.9f pose_x=%.9f pose_y=%.9f pose_z=%.9f\n",
             variant,gate,phase,measured,seen[0],seen[1],seen[2]);
      fflush(stdout);
    }
  }

  /* PRIVATE A6: two fixed x-checkpoints can encode which H exists without
   * a numeric Blockly counter. The exact same low, yaw=0 original-Crazyflie
   * observation is made in ALL three worlds, including where no gate exists.
   * This is SUPERVISOR sensing only, not a motorized pupil counter-program.
   */
  for(int checkpoint=0;checkpoint<2;++checkpoint) {
    const double sample_pose[3]={checkpoint==0?0.0:0.850,0.0,0.415};
    wb_supervisor_field_set_sf_vec3f(pos,sample_pose);
    wb_supervisor_field_set_sf_rotation(rot,facing);
    wb_supervisor_node_reset_physics(self);
    if(wb_robot_step(step)<0)
      return invalid("A6 fixed-checkpoint native step unavailable");
    const double *observed=wb_supervisor_node_get_position(self);
    int contact_count=-1;
    const WbContactPoint *contacts=
      wb_supervisor_node_get_contact_points(self,true,&contact_count);
    const double front_m=wb_distance_sensor_get_value(front)/1000.0;
    const double up_m=wb_distance_sensor_get_value(up)/1000.0;
    if(!observed||!isfinite(observed[0])||!isfinite(observed[1])||
       !isfinite(observed[2])||
       fabs(observed[0]-sample_pose[0])>.035||
       fabs(observed[1])>.035||
       fabs(observed[2]-sample_pose[2])>.045||
       !isfinite(front_m)||front_m<0||front_m>2.001||
       !isfinite(up_m)||up_m<0||up_m>2.001||
       contact_count!=0||(contact_count>0&&!contacts))
      return invalid("A6 fixed-checkpoint pose, contact or native ray invalid");
    printf("WEBEEBLOCKS_COUNT_H_FIXED_CHECKPOINT variant=%d slot=%d "
           "front_m=%.9f up_m=%.9f pose_x=%.9f pose_y=%.9f pose_z=%.9f\n",
           variant,checkpoint,front_m,up_m,
           observed[0],observed[1],observed[2]);
    fflush(stdout);
  }

  /* Native *geometric* collision sweep only. The supervisor explicitly
   * positions the unmodified Crazyflie PROTO at 20-mm steps. No motors
   * act, so a PASS does NOT prove actual commanded flight or stability.
   * Test all red H arches and the cyan terminal screen at low altitude,
   * then translate sideways to each landing zone. */
  int safe_samples = 0;
  const double low_z = 0.40;
  for (int i = 0; i <= 144 + 28 * 2; ++i) {
    double xyz[3] = {1.48, 0.0, low_z};
    if (i <= 144) {
      xyz[0] = -1.40 + 0.02 * i;
    } else if (i <= 172) {
      xyz[1] = 0.55 * (i - 144) / 28.0;
    } else {
      xyz[1] = -0.55 * (i - 172) / 28.0;
    }
    wb_supervisor_field_set_sf_vec3f(pos, xyz);
    wb_supervisor_field_set_sf_rotation(rot, facing);
    wb_supervisor_node_reset_physics(self);
    if (wb_robot_step(step) < 0)
      return invalid("native physics sweep step failed");
    const double *actual = wb_supervisor_node_get_position(self);
    int contact_count = -1;
    const WbContactPoint *contacts =
      wb_supervisor_node_get_contact_points(self, true, &contact_count);
    if (!actual || !isfinite(actual[0]) || !isfinite(actual[1]) ||
        !isfinite(actual[2]) || fabs(actual[0] - xyz[0]) > 0.035 ||
        fabs(actual[1] - xyz[1]) > 0.035 ||
        fabs(actual[2] - xyz[2]) > 0.045 ||
        contact_count < 0 || (contact_count > 0 && !contacts)) {
      return invalid("unattested swept pose/contact observation");
    }
    if (contact_count != 0) {
      fprintf(stderr,
              "WEBEEBLOCKS_COUNT_H_BACK_FATAL sweep_contact variant=%d "
              "i=%d count=%d x=%.6f y=%.6f z=%.6f\n",
              variant, i, contact_count, actual[0], actual[1], actual[2]);
      fflush(stderr);
      wb_robot_cleanup();
      return 2;
    }
    ++safe_samples;
  }

  /* Positive physics calibration with gravitational fall (not teleportation
   * into an overlap). Motors are OFF and no pupil code runs. Release the
   * original dynamic Crazyflie PROTO over the actual H top bar.
   * Require contacts on that H specifically; a floor contact cannot prove it. */
  const double release_pose[3] = {-0.850, 0.0, 1.280};
  wb_supervisor_field_set_sf_vec3f(pos, release_pose);
  wb_supervisor_field_set_sf_rotation(rot, facing);
  wb_supervisor_node_reset_physics(self);
  int control_contacts = 0;
  for (int k = 0; k < 80; ++k) {
    if (wb_robot_step(step) < 0)
      return invalid("gravity calibration native physics step failed");
    int self_contacts = -1, bar_contacts = -1;
    const WbContactPoint *body_points =
      wb_supervisor_node_get_contact_points(self, true, &self_contacts);
    const WbContactPoint *bar_points =
      wb_supervisor_node_get_contact_points(first_bar, false, &bar_contacts);
    const double *observed = wb_supervisor_node_get_position(self);
    const double *velocity = wb_supervisor_node_get_velocity(self);
    if (self_contacts < 0 || bar_contacts < 0 ||
        (self_contacts > 0 && !body_points) ||
        (bar_contacts > 0 && !bar_points) || !observed || !velocity ||
        !isfinite(observed[2]) || !isfinite(velocity[2]))
      return invalid("gravity contact calibration missing physical observation");
    if (bar_contacts > control_contacts) control_contacts = bar_contacts;
    if ((k % 5) == 0 || bar_contacts > 0) {
      printf("WEBEEBLOCKS_COUNT_H_CONTACT_CONTROL variant=%d k=%d "
             "body=%d bar=%d x=%.6f y=%.6f z=%.6f vz=%.6f\n",
             variant, k, self_contacts, bar_contacts, observed[0],
             observed[1], observed[2], velocity[2]);
      fflush(stdout);
    }
  }
  if (control_contacts <= 0)
    return invalid("no real H-bar contact from gravity-driven positive control");
  printf("WEBEEBLOCKS_COUNT_H_SWEEP_PASS variant=%d samples=%d "
         "control_contacts=%d low_z=%.3f\n",
         variant, safe_samples, control_contacts, low_z);
  fflush(stdout);
  wb_robot_cleanup();
  return 0;
}

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

  /* Probe ALL three possible pads in each world, before any pupil program.
   * The rear ray must see the same cyan finish ribbon independent of count.
   * The body remains parked (no flight or obstacle crossing is certified).
   */
  const double pad_y[] = {0.0, 0.55, -0.55};
  const double facing[] = {0.0, 0.0, 1.0, 0.0};
  wb_distance_sensor_enable(back, step);
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

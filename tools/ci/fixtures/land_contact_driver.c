/* Native #637 input replay. Only request transport/scene readiness is injected.
 * Sensors, motors, physics, PID and the flight state machine remain native. */
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <webots/inertial_unit.h>
#include <webots/motor.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static int ready, index_, pending, failed;
static double done = -1, stable_since = -1;
static double touchdown = -1;
static int coast_samples;
static double origin_z, origin_roll, origin_pitch, landing_x, landing_y, landing_yaw;
static const double times[] = {2.464, 6.848, 7.552, 9.536, 11.392};
static const char *commands[] = {
  "TAKEOFF 0.5", "WAIT 0.5", "MOVE forward 0.1", "MOVE forward 0.1", "LAND"
};
int webeeblocks_activity_scene_ready(void) { return 1; }
int webeeblocks_select_activity_scene(const char *scene) { (void)scene; return 0; }

const char *land_receive(void) {
  static char message[160];
  if (!ready || failed || pending || index_ >= 5 ||
      wb_robot_get_time() + 1e-8 < times[index_]) return NULL;
  if (index_ == 4) {
    const double *p = wb_supervisor_node_get_position(wb_supervisor_node_get_self());
    landing_x = p[0]; landing_y = p[1];
    landing_yaw = wb_inertial_unit_get_roll_pitch_yaw(wb_robot_get_device("inertial_unit"))[2];
  }
  snprintf(message, sizeof(message), "WEBEEBLOCKS_RUNTIME_V2 REQUEST %d %s", index_ + 1, commands[index_]);
  printf("LAND_REGRESSION_REQUEST t=%.9f %s\n", wb_robot_get_time(), message);
  fflush(stdout);
  pending = 1;
  return message;
}
void land_send(const char *message) {
  if (strstr(message, " READY")) {
    const double *p = wb_supervisor_node_get_position(wb_supervisor_node_get_self());
    origin_z = p[2];
    const double *rpy = wb_inertial_unit_get_roll_pitch_yaw(wb_robot_get_device("inertial_unit"));
    origin_roll = rpy[0]; origin_pitch = rpy[1]; ready = 1;
    return;
  }
  int id; char status[50];
  if (sscanf(message, "WEBEEBLOCKS_RUNTIME_V2 RESPONSE %d %49s", &id, status) == 2 && id == index_ + 1) {
    if (strcmp(status, "OK")) { failed = 1; done = wb_robot_get_time(); }
    else if (++index_ == 5) done = wb_robot_get_time();
    pending = 0;
  }
}
int land_step(int ms) {
  const int rc = wb_robot_step(ms);
  if (rc == -1) return rc;
  const double now = wb_robot_get_time();
  if (ready) {
    WbNodeRef self = wb_supervisor_node_get_self();
    const double *p = wb_supervisor_node_get_position(self);
    double pos[3] = {p[0], p[1], p[2]}, velocity[6], rpy[3];
    memcpy(velocity, wb_supervisor_node_get_velocity(self), sizeof(velocity));
    memcpy(rpy, wb_inertial_unit_get_roll_pitch_yaw(wb_robot_get_device("inertial_unit")), sizeof(rpy));
    int contacts = -1;
    WbContactPoint *points = wb_supervisor_node_get_contact_points(self, 1, &contacts);
    if (index_ == 4 && touchdown < 0 && fabs(pos[2] - origin_z) <= 0.05) {
      for (int i = 0; points && i < contacts; ++i)
        if (isfinite(points[i].point[2]) && points[i].point[2] <= origin_z)
          touchdown = now;
    }
    if (touchdown >= 0 && now > touchdown) {
      // These are commanded velocities, not internal measured rotor speeds.
      // The first observation precedes this tick's control; examine the next
      // tick and every later sample, including temporary loss of contact.
      const char *names[] = {"m1_motor", "m2_motor", "m3_motor", "m4_motor"};
      for (int i = 0; i < 4; ++i)
        if (fabs(wb_motor_get_velocity(wb_robot_get_device(names[i]))) > 1e-12)
          failed = 1;
      ++coast_samples;
    }
    printf("LAND_REGRESSION_OBS t=%.9f stage=%d position=%.12g,%.12g,%.12g velocity=%.12g,%.12g,%.12g,%.12g,%.12g,%.12g rpy=%.12g,%.12g,%.12g contacts=%d",
      now, index_, pos[0], pos[1], pos[2], velocity[0], velocity[1], velocity[2],
      velocity[3], velocity[4], velocity[5], rpy[0], rpy[1], rpy[2], contacts);
    for (int i = 0; points && i < contacts && i < 6; ++i)
      printf(" cp%d=%.12g,%.12g,%.12g", i, points[i].point[0], points[i].point[1], points[i].point[2]);
    puts(""); fflush(stdout);
    int finite = 1;
    for (int i = 0; i < 3; ++i) finite &= isfinite(pos[i]) && isfinite(rpy[i]);
    for (int i = 0; i < 6; ++i) finite &= isfinite(velocity[i]);
    const double angle_tol = 2 * 3.14159265358979323846 / 180;
    const int valid = finite && index_ == 5 &&
      hypot(pos[0] - landing_x, pos[1] - landing_y) < 0.03 &&
      fabs(pos[2] - origin_z) < 0.05 &&
      hypot(velocity[0], velocity[1]) < 0.12 && fabs(velocity[2]) < 0.15 &&
      fabs(rpy[0] - origin_roll) < angle_tol && fabs(rpy[1] - origin_pitch) < angle_tol &&
      fabs(remainder(rpy[2] - landing_yaw, 2 * 3.14159265358979323846)) < angle_tol &&
      fabs(velocity[3]) < 0.10 && fabs(velocity[4]) < 0.10 && fabs(velocity[5]) < 0.10;
    if (!valid) stable_since = -1;
    else if (stable_since < 0) stable_since = now;
  }
  if ((done >= 0 && now - done >= 3) || now >= 45) {
    failed |= index_ != 5 || stable_since < 0 || now - stable_since < 0.5;
    // The mandatory 32 ms fixture must actually exercise the powered-contact
    // boundary. The optional 8 ms diagnosis can complete LAND before contact.
    failed |= wb_robot_get_basic_time_step() == 32 && coast_samples == 0;
    printf("LAND_CONTACT_COAST samples=%d touchdown=%.9f\n", coast_samples, touchdown);
    printf("LAND_REGRESSION_END completed=%d failed=%d stable=%.9f\n",
      index_ == 5, failed, stable_since < 0 ? -1 : now - stable_since);
    fflush(stdout);
    wb_supervisor_simulation_quit(failed ? 1 : 0);
    return -1;
  }
  return rc;
}

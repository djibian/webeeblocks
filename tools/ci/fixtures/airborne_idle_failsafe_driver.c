/* Native R2025a guard regression: unsafe posture AFTER TAKEOFF ACK, CMD_IDLE.
 * Transport is injected, but Supervisor physics, IMU, motors and RESET are real.
 * This fixture is deliberately separate from the existing LAND contact oracle. */
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <webots/motor.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static int stage, ready, failed, injected, reset_seen, range_after_reset;
static double tilt_time = -1.0;
static int zero_motors = 0;
static double end_time = -1.0;
int webeeblocks_activity_scene_ready(void) { return 1; }
int webeeblocks_select_activity_scene(const char *scene) { (void)scene; return 0; }

static int motors_stopped(void) {
  const char *names[] = {"m1_motor", "m2_motor", "m3_motor", "m4_motor"};
  for (int i = 0; i < 4; i++) {
    const WbDeviceTag tag = wb_robot_get_device(names[i]);
    if (!tag || fabs(wb_motor_get_velocity(tag)) > 1e-12)
      return 0;
  }
  return 1;
}

const char *land_receive(void) {
  static char message[160];
  const double now = wb_robot_get_time();
  int id = -1;
  const char *command = NULL;
  if (!ready || failed)
    return NULL;
  if (stage == 0 && now >= 2.464) {
    id = 1;
    command = "TAKEOFF 0.5";
    stage = 1;
  } else if (stage == 2 && injected && now >= tilt_time + 0.512) {
    id = 2;
    command = "RANGE front";
    stage = 3;
  } else if (stage == 4) {
    id = 3;
    command = "RESET";
    stage = 5;
  } else if (stage == 6) {
    id = 4;
    command = "RANGE front";
    stage = 7;
  } else {
    return NULL;
  }
  snprintf(message, sizeof(message), "WEBEEBLOCKS_RUNTIME_V2 REQUEST %d %s", id, command);
  printf("AIRBORNE_IDLE_REQUEST time=%.9f %s\n", now, message);
  fflush(stdout);
  return message;
}

void land_send(const char *message) {
  if (strcmp(message, "WEBEEBLOCKS_RUNTIME_V2 READY") == 0) {
    if (ready) failed = 1;
    ready = 1;
    return;
  }
  int id = -1;
  char status[40] = {0}, detail[70] = {0};
  if (sscanf(message, "WEBEEBLOCKS_RUNTIME_V2 RESPONSE %d %39s %69s", &id, status, detail) < 2) {
    failed = 1; // Any unsolicited or unrecognized protocol message is a refusal.
    return;
  }
  if (stage == 1 && id == 1 && strcmp(status, "OK") == 0 && detail[0] == '\0') {
    stage = 2; // TAKEOFF has completed, so the next tick is airborne CMD_IDLE.
  } else if (stage == 3 && id == 2 && strcmp(status, "ERR") == 0 &&
             strcmp(detail, "RESET_REQUIRED") == 0) {
    zero_motors = motors_stopped();
    failed |= !zero_motors;
    stage = 4;
  } else if (stage == 5 && id == 3 && strcmp(status, "OK") == 0 && detail[0] == '\0') {
    reset_seen++;
    stage = 6;
  } else if (stage == 7 && id == 4 && strcmp(status, "VALUE") == 0) {
    double range = 0.;
    char extra;
    if (sscanf(detail, "%lf%c", &range, &extra) != 1 || !isfinite(range))
      failed = 1;
    range_after_reset++;
    stage = 8;
    end_time = wb_robot_get_time();
  } else {
    failed = 1;
  }
  printf("AIRBORNE_IDLE_RESPONSE stage=%d %s stopped=%d\n", stage, message, zero_motors);
  fflush(stdout);
}

int land_step(int ms) {
  const int result = wb_robot_step(ms);
  if (result == -1) return result;
  const double now = wb_robot_get_time();
  if (stage == 2 && !injected) {
    WbNodeRef node = wb_supervisor_node_get_self();
    WbFieldRef rotation = node ? wb_supervisor_node_get_field(node, "rotation") : 0;
    if (!rotation) {
      failed = 1;
    } else {
      const double tilt[4] = {1., 0., 0., 1.45};
      wb_supervisor_field_set_sf_rotation(rotation, tilt);
      wb_supervisor_node_reset_physics(node);
      injected = 1;
      tilt_time = now;
      printf("AIRBORNE_IDLE_TILT_INJECTED time=%.9f angle=1.45\n", now);
      fflush(stdout);
    }
  }
  if (stage == 8 || failed || now >= 40.0) {
    const int pass = !failed && injected && reset_seen == 1 &&
      range_after_reset == 1 && zero_motors && stage == 8 && end_time > tilt_time;
    printf("AIRBORNE_IDLE_FAILSAFE_END completed=%d failed=%d injected=%d reset=%d range=%d motors_stopped=%d\n",
      pass, !pass, injected, reset_seen, range_after_reset, zero_motors);
    fflush(stdout);
    wb_supervisor_simulation_quit(pass ? 0 : 1);
    return -1;
  }
  return result;
}

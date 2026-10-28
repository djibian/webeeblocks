/* Native R2025a negative: STOP after an already ACKed TAKEOFF must never
 * send USER_STOPPED for that completed request. Transport is synthetic;
 * flight, PID, IMU, RESET and sensor values use the real Webots engine. */
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static int stage = 0, ready = 0, failed = 0, seen_stop = 0, reset_seen = 0, range_after_reset = 0;
int webeeblocks_activity_scene_ready(void) { return 1; }
int webeeblocks_select_activity_scene(const char *scene) { (void)scene; return 0; }

const char *land_receive(void) {
  static char message[160];
  const double now = wb_robot_get_time();
  int id = -1;
  const char *operation = NULL;
  if (!ready || failed)
    return NULL;
  if (stage == 0 && now >= 2.464) {
    id = 1;
    operation = "TAKEOFF 0.5";
    stage = 1;
  } else if (stage == 2) {
    id = 2;
    operation = "STOP";
    stage = 3;
  } else if (stage == 4) {
    id = 3;
    operation = "RANGE front";
    stage = 5;
  } else if (stage == 6) {
    id = 4;
    operation = "RESET";
    stage = 7;
  } else if (stage == 8) {
    id = 5;
    operation = "RANGE front";
    stage = 9;
  } else {
    return NULL;
  }
  snprintf(message, sizeof(message), "WEBEEBLOCKS_RUNTIME_V2 REQUEST %d %s", id, operation);
  printf("IDLE_STOP_REQUEST t=%.9f %s\n", now, message);
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
    failed = 1;
    return;
  }
  if (stage == 1 && id == 1 && strcmp(status, "OK") == 0 && detail[0] == '\0') {
    stage = 2;
  } else if (stage == 3 && id == 2 && strcmp(status, "OK") == 0 && detail[0] == '\0') {
    seen_stop++;
    stage = 4;
  } else if (stage == 5 && id == 3 && strcmp(status, "ERR") == 0 &&
             strcmp(detail, "RESET_REQUIRED") == 0) {
    stage = 6;
  } else if (stage == 7 && id == 4 && strcmp(status, "OK") == 0 && detail[0] == '\0') {
    reset_seen++;
    stage = 8;
  } else if (stage == 9 && id == 5 && strcmp(status, "VALUE") == 0) {
    double range = 0.;
    char extra;
    if (sscanf(detail, "%lf%c", &range, &extra) != 1 || !isfinite(range))
      failed = 1;
    range_after_reset++;
    stage = 10;
  } else {
    // Including stale RESPONSE 1 ERR USER_STOPPED after TAKEOFF was ACKed.
    failed = 1;
  }
  printf("IDLE_STOP_RESPONSE stage=%d %s failed=%d\n", stage, message, failed);
  fflush(stdout);
}

int land_step(int ms) {
  const int result = wb_robot_step(ms);
  if (result == -1)
    return result;
  if (stage == 10 || failed || wb_robot_get_time() >= 40.) {
    const int pass = !failed && stage == 10 && seen_stop == 1 &&
                     reset_seen == 1 && range_after_reset == 1;
    printf("IDLE_STOP_RESPONSE_END completed=%d failed=%d stop=%d reset=%d range=%d\n",
           pass, !pass, seen_stop, reset_seen, range_after_reset);
    fflush(stdout);
    wb_supervisor_simulation_quit(pass ? 0 : 1);
    return -1;
  }
  return result;
}

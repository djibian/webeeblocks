#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "controllers/crazyflie_l_course/crazyflie_l_course.c"

OLD = r'''static int drain_runtime_done_ack(void) {
  const char *message;
  while ((message = wb_robot_wwi_receive_text())) {
    if (strcmp(message, "WEBEEBLOCKS_MISSION_V1 DONE_ACK") == 0) {
      printf("WEBEEBLOCKS_MISSION_V1 DONE_ACK_RECEIVED\n");
      fflush(stdout);
      return 1;
    }
    wb_robot_wwi_send_text("WEBEEBLOCKS_MISSION_V1 ERR BUSY");
  }
  return 0;
}

static int wait_for_runtime_done_ack(int step) {
  const double deadline = wb_robot_get_time() + DONE_ACK_TIMEOUT;
  while (wb_robot_get_time() < deadline) {
    if (drain_runtime_done_ack())
      return 1;
    if (wb_robot_step(step) == -1)
      break;
    if (drain_runtime_done_ack())
      return 1;
  }
  printf("WEBEEBLOCKS_MISSION_V1 DONE_ACK_TIMEOUT\n");
  fflush(stdout);
  return 0;
}
'''

NEW = r'''static void trace_runtime_done_ack(const char *phase, const char *payload) {
  char path[4096];
  snprintf(path, sizeof(path), "%s/ci-artifacts/crazyflie-done-ack-trace.txt", wb_robot_get_project_path());
  FILE *file = fopen(path, "a");
  if (file) {
    fprintf(file, "t=%.6f phase=%s payload=%s\n",
            wb_robot_get_time(), phase, payload ? payload : "NULL");
    fflush(file);
    fclose(file);
  }
  printf("WEBEEBLOCKS_DONE_ACK_TRACE t=%.6f phase=%s payload=%s\n",
         wb_robot_get_time(), phase, payload ? payload : "NULL");
  fflush(stdout);
}

static int drain_runtime_done_ack(const char *phase) {
  const char *message;
  int received_any = 0;
  while ((message = wb_robot_wwi_receive_text())) {
    received_any = 1;
    trace_runtime_done_ack(phase, message);
    if (strcmp(message, "WEBEEBLOCKS_MISSION_V1 DONE_ACK") == 0) {
      printf("WEBEEBLOCKS_MISSION_V1 DONE_ACK_RECEIVED\n");
      fflush(stdout);
      return 1;
    }
    wb_robot_wwi_send_text("WEBEEBLOCKS_MISSION_V1 ERR BUSY");
  }
  if (!received_any)
    trace_runtime_done_ack(phase, NULL);
  return 0;
}

static int wait_for_runtime_done_ack(int step) {
  const double deadline = wb_robot_get_time() + DONE_ACK_TIMEOUT;
  trace_runtime_done_ack("wait_begin", NULL);
  while (wb_robot_get_time() < deadline) {
    if (drain_runtime_done_ack("before_step"))
      return 1;
    if (wb_robot_step(step) == -1) {
      trace_runtime_done_ack("step_ended", NULL);
      break;
    }
    if (drain_runtime_done_ack("after_step"))
      return 1;
  }
  trace_runtime_done_ack("timeout", NULL);
  printf("WEBEEBLOCKS_MISSION_V1 DONE_ACK_TIMEOUT\n");
  fflush(stdout);
  return 0;
}
'''


def main() -> int:
    text = SOURCE.read_text(encoding="utf-8")
    if NEW in text:
        print("DONE_ACK terminal tracing already installed.")
        return 0
    if OLD not in text:
        raise SystemExit("expected DONE_ACK functions not found; refusing to patch")
    SOURCE.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("Installed CI-only terminal DONE_ACK tracing in crazyflie_l_course.c")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

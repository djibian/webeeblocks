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

UNSAFE_OLD = r'''    if (fabs(a.roll) > 1.2 || fabs(a.pitch) > 1.2 || now - t0 > TIMEOUT) {
      write_failure(now - t0 > TIMEOUT ? "TIMEOUT" : "UNSAFE_STATE", &runner, gates);
      stop(m1,m2,m3,m4); wb_supervisor_simulation_quit(2); break;
    }
'''

UNSAFE_NEW = r'''    if (fabs(a.roll) > 1.2 || fabs(a.pitch) > 1.2 || now - t0 > TIMEOUT) {
      printf("WEBEEBLOCKS_UNSAFE_DIAG elapsed=%.6f index=%zu phase=%s x=%.6f y=%.6f z=%.6f yaw=%.6f roll=%.6f pitch=%.6f vx=%.6f vy=%.6f vz=%.6f yaw_rate=%.6f target_x=%.6f target_y=%.6f target_z=%.6f target_yaw=%.6f\n",
             now - t0, runner.index, runner_phase_name(&runner), x, y, z, yaw,
             a.roll, a.pitch, a.vx, a.vy, vz, a.yaw_rate,
             target_x, target_y, target_z, target_yaw);
      fflush(stdout);
      write_failure(now - t0 > TIMEOUT ? "TIMEOUT" : "UNSAFE_STATE", &runner, gates);
      stop(m1,m2,m3,m4); wb_supervisor_simulation_quit(2); break;
    }
'''


def main() -> int:
    text = SOURCE.read_text(encoding="utf-8")
    changed = False

    if NEW not in text:
        if OLD not in text:
            raise SystemExit("expected DONE_ACK functions not found; refusing to patch")
        text = text.replace(OLD, NEW, 1)
        changed = True

    if UNSAFE_NEW not in text:
        if UNSAFE_OLD not in text:
            raise SystemExit("expected unsafe-state guard not found; refusing to patch")
        text = text.replace(UNSAFE_OLD, UNSAFE_NEW, 1)
        changed = True

    if changed:
        SOURCE.write_text(text, encoding="utf-8")
        print("Installed CI-only DONE_ACK and unsafe-state tracing in crazyflie_l_course.c")
    else:
        print("CI-only DONE_ACK and unsafe-state tracing already installed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

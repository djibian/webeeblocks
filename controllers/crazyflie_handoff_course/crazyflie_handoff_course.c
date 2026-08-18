#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <webots/gps.h>
#include <webots/gyro.h>
#include <webots/inertial_unit.h>
#include <webots/motor.h>
#include <webots/robot.h>
#include <webots/supervisor.h>
#include "pid_controller.h"
#include "webeeblocks_primitives.h"

#define PI 3.14159265358979323846
#define TARGET_Z_DELTA 1.0
#define LEG_M 1.0
#define VX_MAX 0.35
#define YAW_RATE_MAX 0.7
#define POSITION_KP 1.0
#define YAW_KP 1.5
#define POSITION_TOL 0.03
#define YAW_TOL (2.0 * PI / 180.0)
#define SPEED_TOL 0.12
#define YAW_RATE_TOL 0.10
#define VZ_TOL 0.15
#define ALTITUDE_TOL 0.05
#define STABLE_WINDOW 0.5
#define TIMEOUT 60.0
#define GATE_ALONG_M 0.90
#define GATE_HALF_WIDTH_M 0.30
#define GATE_HALF_HEIGHT_M 0.20

typedef enum { POLICY_STOP, POLICY_CHAIN } handoff_policy_t;
typedef enum { TAKEOFF, LEG1, TURN, LEG2, LAND } phase_t;

typedef struct {
  int passed;
  double lateral;
  double altitude_error;
  double x;
  double y;
  double z;
  double time;
} gate_result_t;

static double wrap(double a) { return webeeblocks_wrap_yaw(a); }

static double clip(double v, double limit) {
  if (v > limit)
    return limit;
  if (v < -limit)
    return -limit;
  return v;
}

static void clip_vector(double *x, double *y, double limit) {
  const double magnitude = hypot(*x, *y);
  if (magnitude > limit && magnitude > 0.0) {
    const double scale = limit / magnitude;
    *x *= scale;
    *y *= scale;
  }
}

static double motor(double v) {
  return v < 0.0 ? 0.0 : (v > 600.0 ? 600.0 : v);
}

static void stop(WbDeviceTag a, WbDeviceTag b, WbDeviceTag c, WbDeviceTag d) {
  wb_motor_set_velocity(a, 0.0);
  wb_motor_set_velocity(b, 0.0);
  wb_motor_set_velocity(c, 0.0);
  wb_motor_set_velocity(d, 0.0);
}

static const char *phase_name(phase_t phase) {
  switch (phase) {
    case TAKEOFF: return "TAKEOFF";
    case LEG1: return "LEG1";
    case TURN: return "TURN";
    case LEG2: return "LEG2";
    case LAND: return "LAND";
  }
  return "UNKNOWN";
}

static const char *policy_name(handoff_policy_t policy) {
  return policy == POLICY_CHAIN ? "CHAIN" : "STOP";
}

static handoff_policy_t read_policy(void) {
  const char *value = getenv("WEBEEBLOCKS_HANDOFF_POLICY");
  if (!value || strcmp(value, "STOP") == 0)
    return POLICY_STOP;
  if (strcmp(value, "CHAIN") == 0)
    return POLICY_CHAIN;
  fprintf(stderr, "Unsupported WEBEEBLOCKS_HANDOFF_POLICY=%s\n", value);
  return POLICY_STOP;
}

static int common_endpoint_stable(const actual_state_t *state,
                                  double vz,
                                  double z,
                                  double target_z) {
  return hypot(state->vx, state->vy) < SPEED_TOL &&
         fabs(state->yaw_rate) < YAW_RATE_TOL &&
         fabs(vz) < VZ_TOL &&
         fabs(z - target_z) < ALTITUDE_TOL;
}

static int handoff_ready(handoff_policy_t policy,
                         int geometric_ready,
                         int common_stable,
                         double now,
                         double *stable_since) {
  if (!geometric_ready) {
    *stable_since = -1.0;
    return 0;
  }
  if (policy == POLICY_CHAIN) {
    *stable_since = -1.0;
    return 1;
  }
  if (!common_stable) {
    *stable_since = -1.0;
    return 0;
  }
  if (*stable_since < 0.0)
    *stable_since = now;
  return now - *stable_since > STABLE_WINDOW;
}

static int check_gate(double px, double py, double pz,
                      double x, double y, double z,
                      double previous_time, double now, double mission_start,
                      double cx, double cy, double nx, double ny,
                      double lx, double ly, double target_z,
                      gate_result_t *gate) {
  if (gate->passed)
    return 0;
  const double previous = (px - cx) * nx + (py - cy) * ny;
  const double current = (x - cx) * nx + (y - cy) * ny;
  if (!(previous < 0.0 && current >= 0.0))
    return 0;
  const double denominator = current - previous;
  const double alpha = denominator == 0.0 ? 0.0 : -previous / denominator;
  const double ix = px + alpha * (x - px);
  const double iy = py + alpha * (y - py);
  const double iz = pz + alpha * (z - pz);
  const double crossing_time =
      previous_time + alpha * (now - previous_time) - mission_start;
  const double lateral = (ix - cx) * lx + (iy - cy) * ly;
  const double altitude_error = iz - target_z;
  gate->lateral = lateral;
  gate->altitude_error = altitude_error;
  gate->x = ix;
  gate->y = iy;
  gate->z = iz;
  gate->time = crossing_time;
  if (fabs(lateral) > GATE_HALF_WIDTH_M ||
      fabs(altitude_error) > GATE_HALF_HEIGHT_M)
    return -1;
  gate->passed = 1;
  return 1;
}

static void result_path(char *path, size_t size, handoff_policy_t policy) {
  snprintf(path, size, "%s/ci-artifacts/crazyflie-handoff-%s-result.txt",
           wb_robot_get_project_path(), policy_name(policy));
}

static void write_failure(const char *reason,
                          phase_t phase,
                          int gates,
                          handoff_policy_t policy) {
  char path[4096];
  result_path(path, sizeof(path), policy);
  FILE *file = fopen(path, "w");
  if (file) {
    fprintf(file,
            "WEBEEBLOCKS_CF_HANDOFF_RESULT status=failure policy=%s "
            "reason=%s phase=%s gates=%d\n",
            policy_name(policy), reason, phase_name(phase), gates);
    fflush(file);
    fclose(file);
  }
}

static void write_success(const gate_result_t *g1,
                          const gate_result_t *g2,
                          handoff_policy_t policy,
                          double corner_handoff_error,
                          double corner_handoff_speed,
                          double corner_max_overshoot,
                          double endpoint_error,
                          double yaw_error_deg,
                          double min_z,
                          double max_z,
                          double total) {
  char path[4096];
  result_path(path, sizeof(path), policy);
  FILE *file = fopen(path, "w");
  if (!file)
    return;
  fprintf(
      file,
      "WEBEEBLOCKS_CF_HANDOFF_RESULT status=success policy=%s gates=2 "
      "g1_lateral=%.6f g1_altitude_error=%.6f g1_time=%.3f "
      "g2_lateral=%.6f g2_altitude_error=%.6f g2_time=%.3f "
      "corner_handoff_error_xy=%.6f corner_handoff_speed=%.6f "
      "corner_max_overshoot=%.6f endpoint_error_xy=%.6f "
      "yaw_error_deg=%.6f altitude_min=%.6f altitude_max=%.6f total_s=%.3f\n",
      policy_name(policy),
      g1->lateral, g1->altitude_error, g1->time,
      g2->lateral, g2->altitude_error, g2->time,
      corner_handoff_error, corner_handoff_speed, corner_max_overshoot,
      endpoint_error, yaw_error_deg, min_z, max_z, total);
  fflush(file);
  fclose(file);
}

int main(void) {
  wb_robot_init();
  const handoff_policy_t policy = read_policy();
  const int step = (int)wb_robot_get_basic_time_step();

  WbDeviceTag m1 = wb_robot_get_device("m1_motor");
  WbDeviceTag m2 = wb_robot_get_device("m2_motor");
  WbDeviceTag m3 = wb_robot_get_device("m3_motor");
  WbDeviceTag m4 = wb_robot_get_device("m4_motor");
  WbDeviceTag gps = wb_robot_get_device("gps");
  WbDeviceTag imu = wb_robot_get_device("inertial_unit");
  WbDeviceTag gyro = wb_robot_get_device("gyro");

  wb_motor_set_position(m1, INFINITY);
  wb_motor_set_position(m2, INFINITY);
  wb_motor_set_position(m3, INFINITY);
  wb_motor_set_position(m4, INFINITY);
  wb_motor_set_velocity(m1, -1.0);
  wb_motor_set_velocity(m2, 1.0);
  wb_motor_set_velocity(m3, -1.0);
  wb_motor_set_velocity(m4, 1.0);
  wb_gps_enable(gps, step);
  wb_inertial_unit_enable(imu, step);
  wb_gyro_enable(gyro, step);

  while (wb_robot_step(step) != -1 && wb_robot_get_time() < 2.0) {
  }

  const double *p = wb_gps_get_values(gps);
  const double *r = wb_inertial_unit_get_roll_pitch_yaw(imu);
  const double sx = p[0];
  const double sy = p[1];
  const double sz = p[2];
  const double syaw = r[2];

  const double ux = cos(syaw);
  const double uy = sin(syaw);
  const double vx = -sin(syaw);
  const double vy = cos(syaw);
  const double g1x = sx + GATE_ALONG_M * ux;
  const double g1y = sy + GATE_ALONG_M * uy;
  const double corner_x = sx + LEG_M * ux;
  const double corner_y = sy + LEG_M * uy;
  const double g2x = corner_x + GATE_ALONG_M * vx;
  const double g2y = corner_y + GATE_ALONG_M * vy;
  const double expected_x = corner_x + LEG_M * vx;
  const double expected_y = corner_y + LEG_M * vy;
  const double expected_yaw = wrap(syaw + PI / 2.0);

  webeeblocks_target_t target =
      webeeblocks_takeoff(sx, sy, sz, syaw, TARGET_Z_DELTA);
  const double target_z = target.z;
  double target_x = target.x;
  double target_y = target.y;
  double target_yaw = target.yaw;

  double min_z = sz;
  double max_z = sz;
  double px = sx;
  double py = sy;
  double pz = sz;
  double pt = wb_robot_get_time();
  const double t0 = pt;
  double stable_since = -1.0;
  phase_t phase = TAKEOFF;
  gate_result_t gate1 = {0};
  gate_result_t gate2 = {0};
  int corner_tracking = 0;
  double corner_handoff_error = NAN;
  double corner_handoff_speed = NAN;
  double corner_max_overshoot = 0.0;

  gains_pid_t gains = {0};
  gains.kp_att_y = 1;
  gains.kd_att_y = .5;
  gains.kp_att_rp = .5;
  gains.kd_att_rp = .1;
  gains.kp_vel_xy = 2;
  gains.kd_vel_xy = .5;
  gains.kp_z = 10;
  gains.ki_z = 5;
  gains.kd_z = 5;
  init_pid_attitude_fixed_height_controller();

  actual_state_t actual = {0};
  desired_state_t desired = {0};
  motor_power_t power = {0};

  printf("WEBEEBLOCKS_CF_HANDOFF_STARTED policy=%s x=%.6f y=%.6f z=%.6f yaw=%.6f\n",
         policy_name(policy), sx, sy, sz, syaw);
  fflush(stdout);

  while (wb_robot_step(step) != -1) {
    const double now = wb_robot_get_time();
    const double dt = now - pt;
    if (dt <= 0.0)
      continue;

    p = wb_gps_get_values(gps);
    r = wb_inertial_unit_get_roll_pitch_yaw(imu);
    const double *gyro_values = wb_gyro_get_values(gyro);
    const double x = p[0];
    const double y = p[1];
    const double z = p[2];
    const double yaw = r[2];
    const double vz_world = (z - pz) / dt;
    const double vx_world = (x - px) / dt;
    const double vy_world = (y - py) / dt;
    const double cy = cos(yaw);
    const double syy = sin(yaw);

    if (z < min_z)
      min_z = z;
    if (z > max_z)
      max_z = z;

    actual.roll = r[0];
    actual.pitch = r[1];
    actual.yaw_rate = gyro_values[2];
    actual.altitude = z;
    actual.vx = vx_world * cy + vy_world * syy;
    actual.vy = -vx_world * syy + vy_world * cy;

    desired.roll = 0.0;
    desired.pitch = 0.0;
    desired.vx = 0.0;
    desired.vy = 0.0;
    desired.yaw_rate = 0.0;
    desired.altitude = target_z;

    const int gates = gate1.passed + gate2.passed;
    if (fabs(actual.roll) > 1.2 || fabs(actual.pitch) > 1.2 ||
        now - t0 > TIMEOUT) {
      write_failure(now - t0 > TIMEOUT ? "TIMEOUT" : "UNSAFE_STATE",
                    phase, gates, policy);
      stop(m1, m2, m3, m4);
      wb_supervisor_simulation_quit(2);
      break;
    }

    if (phase == LEG1) {
      const int crossed =
          check_gate(px, py, pz, x, y, z, pt, now, t0,
                     g1x, g1y, ux, uy, vx, vy, target_z, &gate1);
      if (crossed < 0) {
        write_failure("GATE1_MISS", phase, gates, policy);
        stop(m1, m2, m3, m4);
        wb_supervisor_simulation_quit(2);
        break;
      }
    } else if (phase == LEG2) {
      const int crossed =
          check_gate(px, py, pz, x, y, z, pt, now, t0,
                     g2x, g2y, vx, vy, ux, uy, target_z, &gate2);
      if (crossed < 0 || (crossed > 0 && !gate1.passed)) {
        write_failure(crossed < 0 ? "GATE2_MISS" : "GATE_ORDER",
                      phase, gates, policy);
        stop(m1, m2, m3, m4);
        wb_supervisor_simulation_quit(2);
        break;
      }
    }

    if (corner_tracking) {
      const double along = (x - corner_x) * ux + (y - corner_y) * uy;
      if (along > corner_max_overshoot)
        corner_max_overshoot = along;
    }

    if (phase == TAKEOFF) {
      const int takeoff_stable =
          fabs(z - target_z) < ALTITUDE_TOL && fabs(vz_world) < VZ_TOL;
      if (takeoff_stable) {
        if (stable_since < 0.0)
          stable_since = now;
        if (now - stable_since > STABLE_WINDOW) {
          stable_since = -1.0;
          phase = LEG1;
          target = webeeblocks_forward(x, y, target_z, yaw, LEG_M);
          target_x = target.x;
          target_y = target.y;
          target_yaw = syaw;
        }
      } else {
        stable_since = -1.0;
      }
    } else if (phase == LEG1 || phase == LEG2) {
      const double ex = target_x - x;
      const double ey = target_y - y;
      const double bx = ex * cy + ey * syy;
      const double by = -ex * syy + ey * cy;
      desired.vx = POSITION_KP * bx;
      desired.vy = POSITION_KP * by;
      clip_vector(&desired.vx, &desired.vy, VX_MAX);

      const int geometric_ready = hypot(ex, ey) <= POSITION_TOL;
      const int common_stable =
          common_endpoint_stable(&actual, vz_world, z, target_z);
      if (phase == LEG1 && geometric_ready)
        corner_tracking = 1;

      if (handoff_ready(policy, geometric_ready, common_stable,
                        now, &stable_since)) {
        stable_since = -1.0;
        if (phase == LEG1) {
          if (!gate1.passed) {
            write_failure("GATE1_NOT_CROSSED", phase, gates, policy);
            stop(m1, m2, m3, m4);
            wb_supervisor_simulation_quit(2);
            break;
          }
          corner_handoff_error = hypot(x - corner_x, y - corner_y);
          corner_handoff_speed = hypot(actual.vx, actual.vy);
          phase = TURN;
          target = webeeblocks_turn(target_x, target_y, target_z,
                                    target_yaw, PI / 2.0);
          target_yaw = target.yaw;
        } else {
          if (!gate2.passed) {
            write_failure("GATE2_NOT_CROSSED", phase, gates, policy);
            stop(m1, m2, m3, m4);
            wb_supervisor_simulation_quit(2);
            break;
          }
          phase = LAND;
        }
      }
    } else if (phase == TURN) {
      const double yaw_error = wrap(target_yaw - yaw);
      desired.yaw_rate = clip(YAW_KP * yaw_error, YAW_RATE_MAX);
      const int geometric_ready = fabs(yaw_error) <= YAW_TOL;
      const int common_stable =
          common_endpoint_stable(&actual, vz_world, z, target_z);

      if (handoff_ready(policy, geometric_ready, common_stable,
                        now, &stable_since)) {
        stable_since = -1.0;
        phase = LEG2;
        target = webeeblocks_forward(target_x, target_y, target_z,
                                     target_yaw, LEG_M);
        target_x = target.x;
        target_y = target.y;
        corner_tracking = 0;
      }
    } else if (phase == LAND) {
      const webeeblocks_target_t landing = webeeblocks_land(x, y, sz, yaw);
      desired.altitude = landing.z;
      if (z <= landing.z + ALTITUDE_TOL && fabs(vz_world) < VZ_TOL) {
        if (stable_since < 0.0)
          stable_since = now;
        if (now - stable_since > STABLE_WINDOW) {
          if (!(gate1.passed && gate2.passed)) {
            write_failure("GATES_INCOMPLETE", phase,
                          gate1.passed + gate2.passed, policy);
            stop(m1, m2, m3, m4);
            wb_supervisor_simulation_quit(2);
            break;
          }
          const double endpoint_error = hypot(x - expected_x, y - expected_y);
          const double final_yaw_error =
              fabs(wrap(yaw - expected_yaw)) * 180.0 / PI;
          write_success(&gate1, &gate2, policy,
                        corner_handoff_error, corner_handoff_speed,
                        corner_max_overshoot, endpoint_error,
                        final_yaw_error, min_z, max_z, now - t0);
          printf("WEBEEBLOCKS_CF_HANDOFF_RESULT status=success "
                 "policy=%s gates=2 total_s=%.3f\n",
                 policy_name(policy), now - t0);
          fflush(stdout);
          stop(m1, m2, m3, m4);
          wb_supervisor_simulation_quit(0);
          break;
        }
      } else {
        stable_since = -1.0;
      }
    }

    pid_velocity_fixed_height_controller(actual, &desired, gains, dt, &power);
    wb_motor_set_velocity(m1, -motor(power.m1));
    wb_motor_set_velocity(m2, motor(power.m2));
    wb_motor_set_velocity(m3, -motor(power.m3));
    wb_motor_set_velocity(m4, motor(power.m4));

    pt = now;
    px = x;
    py = y;
    pz = z;
  }

  stop(m1, m2, m3, m4);
  wb_robot_cleanup();
  return 0;
}

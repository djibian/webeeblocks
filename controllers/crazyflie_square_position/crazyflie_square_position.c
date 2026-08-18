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
#define PRIMITIVE_STABLE_WINDOW 0.5
#define PRIMITIVE_VZ_TOL 0.15
#define PRIMITIVE_ALTITUDE_TOL 0.05
#define TIMEOUT 60.0

typedef enum { TAKEOFF, LEG, TURN, SETTLE, LAND } phase_t;
typedef enum { MISSION_SQUARE, MISSION_FORWARD, MISSION_TURN } mission_t;

static double wrap(double a) {
  while (a > PI) a -= 2 * PI;
  while (a < -PI) a += 2 * PI;
  return a;
}
static double clip(double v, double limit) {
  if (v > limit) return limit;
  if (v < -limit) return -limit;
  return v;
}
static void clip_vector(double *x, double *y, double limit) {
  const double magnitude = hypot(*x, *y);
  if (magnitude > limit && magnitude > 0) {
    const double scale = limit / magnitude;
    *x *= scale;
    *y *= scale;
  }
}
static double motor(double v) { return v < 0 ? 0 : (v > 600 ? 600 : v); }
static void stop(WbDeviceTag a, WbDeviceTag b, WbDeviceTag c, WbDeviceTag d) {
  wb_motor_set_velocity(a, 0); wb_motor_set_velocity(b, 0); wb_motor_set_velocity(c, 0); wb_motor_set_velocity(d, 0);
}
static const char *phase_name(phase_t phase) {
  switch (phase) {
    case TAKEOFF: return "TAKEOFF";
    case LEG: return "LEG";
    case TURN: return "TURN";
    case SETTLE: return "SETTLE";
    case LAND: return "LAND";
  }
  return "UNKNOWN";
}
static void write_result_file(double err, double yawerr, double min_z, double max_z, double total, int legs) {
  char path[4096];
  snprintf(path, sizeof(path), "%s/ci-artifacts/crazyflie-square-position-result.txt", wb_robot_get_project_path());
  FILE *file = fopen(path, "w");
  if (!file) return;
  fprintf(file,
          "WEBEEBLOCKS_CF_POSITION_RESULT status=success error_xy=%.6f yaw_error_deg=%.6f altitude_min=%.6f altitude_max=%.6f total_s=%.3f legs=%d\n",
          err, yawerr, min_z, max_z, total, legs);
  fflush(file);
  fclose(file);
}
static void write_primitive_result(const char *kind, double command, double longitudinal, double lateral,
                                   double yaw_error_deg, double drift_xy, double duration,
                                   double residual_speed, double residual_yaw_rate, double residual_vz,
                                   double final_x, double final_y, double final_z, double final_yaw) {
  char path[4096];
  snprintf(path, sizeof(path), "%s/ci-artifacts/crazyflie-primitive-B.txt", wb_robot_get_project_path());
  FILE *file = fopen(path, "w");
  if (!file) return;
  fprintf(file,
          "WEBEEBLOCKS_CF_PRIMITIVE_B status=success kind=%s command=%.6f longitudinal_error=%.6f lateral_error=%.6f yaw_error_deg=%.6f drift_xy=%.6f primitive_s=%.3f residual_speed=%.6f residual_yaw_rate=%.6f residual_vz=%.6f final_x=%.6f final_y=%.6f final_z=%.6f final_yaw=%.6f\n",
          kind, command, longitudinal, lateral, yaw_error_deg, drift_xy, duration,
          residual_speed, residual_yaw_rate, residual_vz, final_x, final_y, final_z, final_yaw);
  fflush(file);
  fclose(file);
}

int main(int argc, char **argv) {
  mission_t mission = MISSION_SQUARE;
  double mission_value = 0.0;
  if (argc == 3 && strcmp(argv[1], "forward") == 0) {
    mission = MISSION_FORWARD;
    mission_value = strtod(argv[2], NULL);
  } else if (argc == 3 && strcmp(argv[1], "turn") == 0) {
    mission = MISSION_TURN;
    mission_value = strtod(argv[2], NULL) * PI / 180.0;
  } else if (argc != 1) {
    fprintf(stderr, "WEBEEBLOCKS_CF_POSITION_FAILED invalid controllerArgs\n");
    return 2;
  }
  if ((mission == MISSION_FORWARD && mission_value <= 0.0) ||
      (mission == MISSION_TURN && fabs(mission_value) <= 0.0)) {
    fprintf(stderr, "WEBEEBLOCKS_CF_POSITION_FAILED invalid mission value\n");
    return 2;
  }

  wb_robot_init();
  const int step = (int)wb_robot_get_basic_time_step();
  WbDeviceTag m1 = wb_robot_get_device("m1_motor"), m2 = wb_robot_get_device("m2_motor");
  WbDeviceTag m3 = wb_robot_get_device("m3_motor"), m4 = wb_robot_get_device("m4_motor");
  WbDeviceTag gps = wb_robot_get_device("gps"), imu = wb_robot_get_device("inertial_unit"), gyro = wb_robot_get_device("gyro");
  wb_motor_set_position(m1, INFINITY); wb_motor_set_position(m2, INFINITY); wb_motor_set_position(m3, INFINITY); wb_motor_set_position(m4, INFINITY);
  wb_motor_set_velocity(m1, -1); wb_motor_set_velocity(m2, 1); wb_motor_set_velocity(m3, -1); wb_motor_set_velocity(m4, 1);
  wb_gps_enable(gps, step); wb_inertial_unit_enable(imu, step); wb_gyro_enable(gyro, step);
  while (wb_robot_step(step) != -1 && wb_robot_get_time() < 2.0) {}

  const double *p = wb_gps_get_values(gps), *r = wb_inertial_unit_get_roll_pitch_yaw(imu);
  const double sx = p[0], sy = p[1], sz = p[2], syaw = r[2], target_z = sz + TARGET_Z_DELTA;
  double target_x = sx, target_y = sy, target_yaw = syaw;
  double primitive_start_x = sx, primitive_start_y = sy, primitive_start_yaw = syaw;
  double min_z = sz, max_z = sz, px = sx, py = sy, pz = sz, pt = wb_robot_get_time(), stable = -1;
  const double t0 = pt;
  double primitive_t0 = pt;
  int leg = 0;
  phase_t phase = TAKEOFF;

  gains_pid_t g = {0};
  g.kp_att_y = 1; g.kd_att_y = .5; g.kp_att_rp = .5; g.kd_att_rp = .1;
  g.kp_vel_xy = 2; g.kd_vel_xy = .5; g.kp_z = 10; g.ki_z = 5; g.kd_z = 5;
  init_pid_attitude_fixed_height_controller();
  actual_state_t a = {0}; desired_state_t d = {0}; motor_power_t power = {0};

  printf("WEBEEBLOCKS_CF_POSITION_STARTED x=%.6f y=%.6f z=%.6f yaw=%.6f\n", sx, sy, sz, syaw);
  fflush(stdout);

  int step_result;
  while ((step_result = wb_robot_step(step)) != -1) {
    double now = wb_robot_get_time(), dt = now - pt;
    if (dt <= 0) continue;
    p = wb_gps_get_values(gps); r = wb_inertial_unit_get_roll_pitch_yaw(imu); const double *gv = wb_gyro_get_values(gyro);
    double x = p[0], y = p[1], z = p[2], yaw = r[2], vz = (z - pz) / dt, vxg = (x - px) / dt, vyg = (y - py) / dt;
    double cy = cos(yaw), syy = sin(yaw);
    if (z < min_z) min_z = z;
    if (z > max_z) max_z = z;
    a.roll = r[0]; a.pitch = r[1]; a.yaw_rate = gv[2]; a.altitude = z;
    a.vx = vxg * cy + vyg * syy; a.vy = -vxg * syy + vyg * cy;
    d.roll = 0; d.pitch = 0; d.vx = 0; d.vy = 0; d.yaw_rate = 0; d.altitude = target_z;

    if (fabs(a.roll) > 1.2 || fabs(a.pitch) > 1.2 || now - t0 > TIMEOUT) {
      printf("WEBEEBLOCKS_CF_POSITION_FAILED phase=%s leg=%d t=%.3f\n", phase_name(phase), leg, now - t0);
      fflush(stdout); stop(m1, m2, m3, m4); wb_supervisor_simulation_quit(2); break;
    }

    if (phase == TAKEOFF) {
      if (fabs(z - target_z) < .05 && fabs(vz) < .15) {
        if (stable < 0) stable = now;
        if (now - stable > .5) {
          stable = -1;
          primitive_t0 = now;
          primitive_start_x = x; primitive_start_y = y; primitive_start_yaw = yaw;
          if (mission == MISSION_TURN) {
            phase = TURN;
            target_yaw = wrap(yaw + mission_value);
          } else {
            phase = LEG;
            const double distance = mission == MISSION_FORWARD ? mission_value : LEG_M;
            target_x = x + distance * cos(yaw);
            target_y = y + distance * sin(yaw);
            if (mission == MISSION_FORWARD) target_yaw = yaw;
          }
        }
      } else stable = -1;
    } else if (phase == LEG) {
      double ex = target_x - x, ey = target_y - y;
      double bx = ex * cy + ey * syy, by = -ex * syy + ey * cy;
      d.vx = POSITION_KP * bx;
      d.vy = POSITION_KP * by;
      clip_vector(&d.vx, &d.vy, VX_MAX);
      if (hypot(ex, ey) <= POSITION_TOL && hypot(a.vx, a.vy) <= SPEED_TOL) {
        if (stable < 0) stable = now;
        if (now - stable > PRIMITIVE_STABLE_WINDOW) {
          stable = -1;
          if (mission == MISSION_FORWARD) {
            phase = SETTLE;
          } else {
            phase = TURN;
            target_yaw = wrap(target_yaw + PI / 2);
          }
        }
      } else stable = -1;
    } else if (phase == TURN) {
      double eyaw = wrap(target_yaw - yaw);
      d.yaw_rate = clip(YAW_KP * eyaw, YAW_RATE_MAX);
      if (fabs(eyaw) <= YAW_TOL && fabs(a.yaw_rate) <= YAW_RATE_TOL) {
        if (stable < 0) stable = now;
        if (now - stable > PRIMITIVE_STABLE_WINDOW) {
          stable = -1;
          if (mission == MISSION_TURN) {
            phase = SETTLE;
          } else {
            leg++;
            if (leg == 4) phase = LAND;
            else {
              phase = LEG;
              target_x += LEG_M * cos(target_yaw);
              target_y += LEG_M * sin(target_yaw);
            }
          }
        }
      } else stable = -1;
    } else if (phase == SETTLE) {
      if (hypot(a.vx, a.vy) < SPEED_TOL && fabs(a.yaw_rate) < YAW_RATE_TOL &&
          fabs(vz) < PRIMITIVE_VZ_TOL && fabs(z - target_z) < PRIMITIVE_ALTITUDE_TOL) {
        if (stable < 0) stable = now;
        if (now - stable > PRIMITIVE_STABLE_WINDOW) {
          const double residual_speed = hypot(a.vx, a.vy);
          if (mission == MISSION_FORWARD) {
            const double dx=x-primitive_start_x,dy=y-primitive_start_y,cy0=cos(primitive_start_yaw),sy0=sin(primitive_start_yaw);
            const double along=dx*cy0+dy*sy0,lateral=-dx*sy0+dy*cy0;
            write_primitive_result("forward",mission_value,along-mission_value,lateral,
                                   wrap(yaw-primitive_start_yaw)*180/PI,0.0,now-primitive_t0,
                                   residual_speed,a.yaw_rate,vz,x,y,z,yaw);
          } else if (mission == MISSION_TURN) {
            write_primitive_result("turn",mission_value*180/PI,0.0,0.0,
                                   wrap(yaw-primitive_start_yaw-mission_value)*180/PI,
                                   hypot(x-primitive_start_x,y-primitive_start_y),now-primitive_t0,
                                   residual_speed,a.yaw_rate,vz,x,y,z,yaw);
          }
          phase = LAND;
          stable = -1;
        }
      } else stable = -1;
    } else {
      d.altitude = sz;
      if (z <= sz + .05 && fabs(vz) < .15) {
        if (stable < 0) stable = now;
        if (now - stable > .5) {
          double err = hypot(x - sx, y - sy), yawerr = fabs(wrap(yaw - syaw)) * 180 / PI;
          write_result_file(err, yawerr, min_z, max_z, now - t0, leg);
          printf("WEBEEBLOCKS_CF_POSITION_RESULT status=success error_xy=%.6f yaw_error_deg=%.6f altitude_min=%.6f altitude_max=%.6f total_s=%.3f legs=%d\n",
                 err, yawerr, min_z, max_z, now - t0, leg);
          fflush(stdout); stop(m1, m2, m3, m4); wb_supervisor_simulation_quit(0); break;
        }
      } else stable = -1;
    }

    pid_velocity_fixed_height_controller(a, &d, g, dt, &power);
    wb_motor_set_velocity(m1, -motor(power.m1)); wb_motor_set_velocity(m2, motor(power.m2));
    wb_motor_set_velocity(m3, -motor(power.m3)); wb_motor_set_velocity(m4, motor(power.m4));
    pt = now; px = x; py = y; pz = z;
  }

  stop(m1, m2, m3, m4); wb_robot_cleanup(); return 0;
}

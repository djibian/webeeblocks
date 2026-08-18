#include <math.h>
#include <stdio.h>
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
#define STABLE_WINDOW 0.5
#define TIMEOUT 60.0
#define GATE_ALONG_M 0.90
#define GATE_HALF_WIDTH_M 0.30
#define GATE_HALF_HEIGHT_M 0.20

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
  if (v > limit) return limit;
  if (v < -limit) return -limit;
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
static double motor(double v) { return v < 0 ? 0 : (v > 600 ? 600 : v); }
static void stop(WbDeviceTag a, WbDeviceTag b, WbDeviceTag c, WbDeviceTag d) {
  wb_motor_set_velocity(a, 0); wb_motor_set_velocity(b, 0);
  wb_motor_set_velocity(c, 0); wb_motor_set_velocity(d, 0);
}
static const char *phase_name(phase_t p) {
  switch (p) {
    case TAKEOFF: return "TAKEOFF";
    case LEG1: return "LEG1";
    case TURN: return "TURN";
    case LEG2: return "LEG2";
    case LAND: return "LAND";
  }
  return "UNKNOWN";
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
  const double crossing_time = previous_time + alpha * (now - previous_time) - mission_start;
  const double lateral = (ix - cx) * lx + (iy - cy) * ly;
  const double altitude_error = iz - target_z;
  gate->lateral = lateral;
  gate->altitude_error = altitude_error;
  gate->x = ix; gate->y = iy; gate->z = iz; gate->time = crossing_time;
  if (fabs(lateral) > GATE_HALF_WIDTH_M || fabs(altitude_error) > GATE_HALF_HEIGHT_M)
    return -1;
  gate->passed = 1;
  return 1;
}

static void write_failure(const char *reason, phase_t phase, int gates) {
  char path[4096];
  snprintf(path, sizeof(path), "%s/ci-artifacts/crazyflie-l-course-result.txt", wb_robot_get_project_path());
  FILE *file = fopen(path, "w");
  if (file) {
    fprintf(file, "WEBEEBLOCKS_CF_L_RESULT status=failure reason=%s phase=%s gates=%d\n",
            reason, phase_name(phase), gates);
    fflush(file);
    fclose(file);
  }
}

static void write_success(const gate_result_t *g1, const gate_result_t *g2,
                          double endpoint_error, double yaw_error_deg,
                          double min_z, double max_z, double total) {
  char path[4096];
  snprintf(path, sizeof(path), "%s/ci-artifacts/crazyflie-l-course-result.txt", wb_robot_get_project_path());
  FILE *file = fopen(path, "w");
  if (!file) return;
  fprintf(file,
          "WEBEEBLOCKS_CF_L_RESULT status=success gates=2 g1_lateral=%.6f g1_altitude_error=%.6f g1_time=%.3f g2_lateral=%.6f g2_altitude_error=%.6f g2_time=%.3f endpoint_error_xy=%.6f yaw_error_deg=%.6f altitude_min=%.6f altitude_max=%.6f total_s=%.3f\n",
          g1->lateral, g1->altitude_error, g1->time,
          g2->lateral, g2->altitude_error, g2->time,
          endpoint_error, yaw_error_deg, min_z, max_z, total);
  fflush(file);
  fclose(file);
}

int main(void) {
  wb_robot_init();
  const int step = (int)wb_robot_get_basic_time_step();
  WbDeviceTag m1 = wb_robot_get_device("m1_motor"), m2 = wb_robot_get_device("m2_motor");
  WbDeviceTag m3 = wb_robot_get_device("m3_motor"), m4 = wb_robot_get_device("m4_motor");
  WbDeviceTag gps = wb_robot_get_device("gps"), imu = wb_robot_get_device("inertial_unit"), gyro = wb_robot_get_device("gyro");
  wb_motor_set_position(m1, INFINITY); wb_motor_set_position(m2, INFINITY);
  wb_motor_set_position(m3, INFINITY); wb_motor_set_position(m4, INFINITY);
  wb_motor_set_velocity(m1, -1); wb_motor_set_velocity(m2, 1);
  wb_motor_set_velocity(m3, -1); wb_motor_set_velocity(m4, 1);
  wb_gps_enable(gps, step); wb_inertial_unit_enable(imu, step); wb_gyro_enable(gyro, step);
  while (wb_robot_step(step) != -1 && wb_robot_get_time() < 2.0) {}

  const double *p = wb_gps_get_values(gps), *r = wb_inertial_unit_get_roll_pitch_yaw(imu);
  const double sx = p[0], sy = p[1], sz = p[2], syaw = r[2];
  const double ux = cos(syaw), uy = sin(syaw), vx = -sin(syaw), vy = cos(syaw);
  const double g1x = sx + GATE_ALONG_M * ux, g1y = sy + GATE_ALONG_M * uy;
  const double corner_x = sx + LEG_M * ux, corner_y = sy + LEG_M * uy;
  const double g2x = corner_x + GATE_ALONG_M * vx, g2y = corner_y + GATE_ALONG_M * vy;
  const double expected_x = corner_x + LEG_M * vx, expected_y = corner_y + LEG_M * vy;
  const double expected_yaw = wrap(syaw + PI / 2.0);

  webeeblocks_target_t target = webeeblocks_takeoff(sx, sy, sz, syaw, TARGET_Z_DELTA);
  const double target_z = target.z;
  double target_x = target.x, target_y = target.y, target_yaw = target.yaw;
  double min_z = sz, max_z = sz, px = sx, py = sy, pz = sz, pt = wb_robot_get_time();
  const double t0 = pt;
  double stable = -1.0;
  phase_t phase = TAKEOFF;
  gate_result_t gate1 = {0}, gate2 = {0};

  gains_pid_t g = {0};
  g.kp_att_y = 1; g.kd_att_y = .5; g.kp_att_rp = .5; g.kd_att_rp = .1;
  g.kp_vel_xy = 2; g.kd_vel_xy = .5; g.kp_z = 10; g.ki_z = 5; g.kd_z = 5;
  init_pid_attitude_fixed_height_controller();
  actual_state_t a = {0}; desired_state_t d = {0}; motor_power_t power = {0};

  printf("WEBEEBLOCKS_CF_L_STARTED x=%.6f y=%.6f z=%.6f yaw=%.6f\n", sx, sy, sz, syaw);
  fflush(stdout);

  while (wb_robot_step(step) != -1) {
    const double now = wb_robot_get_time(), dt = now - pt;
    if (dt <= 0) continue;
    p = wb_gps_get_values(gps); r = wb_inertial_unit_get_roll_pitch_yaw(imu); const double *gv = wb_gyro_get_values(gyro);
    const double x = p[0], y = p[1], z = p[2], yaw = r[2];
    const double vz = (z - pz) / dt, vxg = (x - px) / dt, vyg = (y - py) / dt;
    const double cy = cos(yaw), syy = sin(yaw);
    if (z < min_z) min_z = z;
    if (z > max_z) max_z = z;
    a.roll = r[0]; a.pitch = r[1]; a.yaw_rate = gv[2]; a.altitude = z;
    a.vx = vxg * cy + vyg * syy; a.vy = -vxg * syy + vyg * cy;
    d.roll = 0; d.pitch = 0; d.vx = 0; d.vy = 0; d.yaw_rate = 0; d.altitude = target_z;

    const int gates = gate1.passed + gate2.passed;
    if (fabs(a.roll) > 1.2 || fabs(a.pitch) > 1.2 || now - t0 > TIMEOUT) {
      write_failure(now - t0 > TIMEOUT ? "TIMEOUT" : "UNSAFE_STATE", phase, gates);
      stop(m1,m2,m3,m4); wb_supervisor_simulation_quit(2); break;
    }

    if (phase == LEG1) {
      const int crossed = check_gate(px,py,pz,x,y,z,pt,now,t0,g1x,g1y,ux,uy,vx,vy,target_z,&gate1);
      if (crossed < 0) {
        write_failure("GATE1_MISS", phase, gates);
        stop(m1,m2,m3,m4); wb_supervisor_simulation_quit(2); break;
      }
    } else if (phase == LEG2) {
      const int crossed = check_gate(px,py,pz,x,y,z,pt,now,t0,g2x,g2y,vx,vy,ux,uy,target_z,&gate2);
      if (crossed < 0 || (crossed > 0 && !gate1.passed)) {
        write_failure(crossed < 0 ? "GATE2_MISS" : "GATE_ORDER", phase, gates);
        stop(m1,m2,m3,m4); wb_supervisor_simulation_quit(2); break;
      }
    }

    if (phase == TAKEOFF) {
      if (fabs(z-target_z) < .05 && fabs(vz) < .15) {
        if (stable < 0) stable = now;
        if (now-stable > STABLE_WINDOW) {
          stable = -1;
          phase = LEG1;
          target = webeeblocks_forward(x,y,target_z,yaw,LEG_M);
          target_x = target.x; target_y = target.y; target_yaw = syaw;
        }
      } else stable = -1;
    } else if (phase == LEG1 || phase == LEG2) {
      const double ex = target_x-x, ey = target_y-y;
      double bx = ex*cy + ey*syy, by = -ex*syy + ey*cy;
      d.vx = POSITION_KP*bx; d.vy = POSITION_KP*by;
      clip_vector(&d.vx,&d.vy,VX_MAX);
      if (hypot(ex,ey) <= POSITION_TOL && hypot(a.vx,a.vy) <= SPEED_TOL) {
        if (stable < 0) stable = now;
        if (now-stable > STABLE_WINDOW) {
          stable = -1;
          if (phase == LEG1) {
            if (!gate1.passed) {
              write_failure("GATE1_NOT_CROSSED", phase, gates);
              stop(m1,m2,m3,m4); wb_supervisor_simulation_quit(2); break;
            }
            phase = TURN;
            target = webeeblocks_turn(target_x,target_y,target_z,target_yaw,PI/2.0);
            target_yaw = target.yaw;
          } else {
            if (!gate2.passed) {
              write_failure("GATE2_NOT_CROSSED", phase, gates);
              stop(m1,m2,m3,m4); wb_supervisor_simulation_quit(2); break;
            }
            phase = LAND;
          }
        }
      } else stable = -1;
    } else if (phase == TURN) {
      const double eyaw = wrap(target_yaw-yaw);
      d.yaw_rate = clip(YAW_KP*eyaw,YAW_RATE_MAX);
      if (fabs(eyaw) <= YAW_TOL && fabs(a.yaw_rate) <= YAW_RATE_TOL) {
        if (stable < 0) stable = now;
        if (now-stable > STABLE_WINDOW) {
          stable = -1;
          phase = LEG2;
          target = webeeblocks_forward(target_x,target_y,target_z,target_yaw,LEG_M);
          target_x = target.x; target_y = target.y;
        }
      } else stable = -1;
    } else if (phase == LAND) {
      const webeeblocks_target_t landing = webeeblocks_land(x,y,sz,yaw);
      d.altitude = landing.z;
      if (z <= landing.z + .05 && fabs(vz) < .15) {
        if (stable < 0) stable = now;
        if (now-stable > STABLE_WINDOW) {
          if (!(gate1.passed && gate2.passed)) {
            write_failure("GATES_INCOMPLETE", phase, gate1.passed+gate2.passed);
            stop(m1,m2,m3,m4); wb_supervisor_simulation_quit(2); break;
          }
          const double endpoint_error = hypot(x-expected_x,y-expected_y);
          const double yaw_error = fabs(wrap(yaw-expected_yaw))*180.0/PI;
          write_success(&gate1,&gate2,endpoint_error,yaw_error,min_z,max_z,now-t0);
          printf("WEBEEBLOCKS_CF_L_RESULT status=success gates=2 endpoint_error_xy=%.6f yaw_error_deg=%.6f total_s=%.3f\n",
                 endpoint_error,yaw_error,now-t0);
          fflush(stdout);
          stop(m1,m2,m3,m4); wb_supervisor_simulation_quit(0); break;
        }
      } else stable = -1;
    }

    pid_velocity_fixed_height_controller(a,&d,g,dt,&power);
    wb_motor_set_velocity(m1,-motor(power.m1)); wb_motor_set_velocity(m2,motor(power.m2));
    wb_motor_set_velocity(m3,-motor(power.m3)); wb_motor_set_velocity(m4,motor(power.m4));
    pt = now; px = x; py = y; pz = z;
  }

  stop(m1,m2,m3,m4); wb_robot_cleanup(); return 0;
}

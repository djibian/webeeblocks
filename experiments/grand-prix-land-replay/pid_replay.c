/* Replay measured states through the unchanged production PID. No plant or
 * contact solver is simulated. The first two records only prime its history. */
#include "pid_controller.h"

void replay_init(void) { init_pid_attitude_fixed_height_controller(); }

void replay_step(double dt, double roll, double pitch, double altitude,
                 double vx, double vy, double desired_altitude,
                 double velocity_derivative_scale, double *out) {
  actual_state_t actual = {0};
  desired_state_t desired = {0};
  gains_pid_t gains = {0};
  motor_power_t power;
  actual.roll = roll;
  actual.pitch = pitch;
  actual.altitude = altitude;
  actual.vx = vx;
  actual.vy = vy;
  desired.altitude = desired_altitude;
  gains.kp_att_y = 1.0;
  gains.kd_att_y = 0.5;
  gains.kp_att_rp = 0.5;
  gains.kd_att_rp = 0.1;
  gains.kp_vel_xy = 2.0;
  gains.kd_vel_xy = 0.5 * velocity_derivative_scale;
  gains.kp_z = 10.0;
  gains.ki_z = 5.0;
  gains.kd_z = 5.0;
  pid_velocity_fixed_height_controller(actual, &desired, gains, dt, &power);
  out[0] = desired.roll;
  out[1] = desired.pitch;
  out[2] = (-power.m1-power.m2+power.m3+power.m4)/4;
  out[3] = (power.m1-power.m2-power.m3+power.m4)/4;
}

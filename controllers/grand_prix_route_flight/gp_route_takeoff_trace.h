#ifndef WEBEEBLOCKS_GP_ROUTE_TAKEOFF_TRACE_H
#define WEBEEBLOCKS_GP_ROUTE_TAKEOFF_TRACE_H

/* EXPERIMENTAL, Grand Prix route composition only. No control authority.
 * Emit one diagnostic record per 32-ms PID update when the Webots controller
 * inherits WBB_GP_TAKEOFF_TRACE=1. Never send commands or write files here.
 * Samples are measurements of simulation truth, not Flow Deck estimates.
 */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern double pastAltitudeError;
extern double altitudeIntegrator;

static struct {
  int active;
  int request_id;
  double t0;
  double ack_time;
  double origin_z;
  double target_z;
} gp_route_takeoff_diag;

static int gp_route_takeoff_diag_enabled(void) {
  static int enabled = -1;
  if (enabled == -1) {
    const char *value = getenv("WBB_GP_TAKEOFF_TRACE");
    enabled = value && strcmp(value, "1") == 0;
  }
  return enabled;
}

static void gp_route_takeoff_trace_begin(int request_id, double now,
                                          double origin_z, double target_z) {
  if (!gp_route_takeoff_diag_enabled()) return;
  gp_route_takeoff_diag.active = 1;
  gp_route_takeoff_diag.request_id = request_id;
  gp_route_takeoff_diag.t0 = now;
  gp_route_takeoff_diag.ack_time = -1.0;
  gp_route_takeoff_diag.origin_z = origin_z;
  gp_route_takeoff_diag.target_z = target_z;
  printf("GP_ROUTE_TAKEOFF_TRACE_BEGIN id=%d t=%.6f z0=%.9f target=%.9f\n",
         request_id, now, origin_z, target_z);
  fflush(stdout);
}

static void gp_route_takeoff_trace_complete(double now) {
  if (!gp_route_takeoff_diag_enabled() || !gp_route_takeoff_diag.active) return;
  gp_route_takeoff_diag.ack_time = now;
  printf("GP_ROUTE_TAKEOFF_TRACE_ACK id=%d t=%.6f\n",
         gp_route_takeoff_diag.request_id, now);
  fflush(stdout);
}

/* Motor outputs are the exact signed Webots velocity commands after the
 * existing motor-power clamp (m1/m3 negative, m2/m4 positive). PID components
 * come from the existing controller's error and integral, not a new PID.
 * 'u' is the exact unsaturated collective term recovered from the mixer.
 */
static void gp_route_takeoff_trace_sample(double now, double dt, double z,
                                           double vz, double reference_z,
                                           double target_z, double prev_error,
                                           gains_pid_t gains, motor_power_t power,
                                           int is_takeoff, int is_idle) {
  if (!gp_route_takeoff_diag_enabled() || !gp_route_takeoff_diag.active) return;
  const double ack = gp_route_takeoff_diag.ack_time;
  if (ack >= 0.0 && now > ack + 3.0) {
    gp_route_takeoff_diag.active = 0;
    return;
  }
  if (!is_takeoff && !(ack >= 0.0 && is_idle)) return;
  const double error = reference_z - z;
  const double p = gains.kp_z * fmax(-1.0, fmin(1.0, error));
  const double i = gains.ki_z * altitudeIntegrator;
  const double d = gains.kd_z * (error - prev_error) / dt;
  const double u = (power.m1 + power.m2 + power.m3 + power.m4) / 4.0;
  const double motor1 = -motor_power(power.m1);
  const double motor2 = motor_power(power.m2);
  const double motor3 = -motor_power(power.m3);
  const double motor4 = motor_power(power.m4);
  printf("GP_ROUTE_TAKEOFF_TRACE_SAMPLE id=%d t=%.6f dt=%.6f "
         "z0=%.9f z=%.9f vz=%.9f ref=%.9f target=%.9f "
         "error=%.9f p=%.9f i=%.9f d=%.9f u=%.9f "
         "m1=%.9f m2=%.9f m3=%.9f m4=%.9f phase=%s\n",
         gp_route_takeoff_diag.request_id, now, dt,
         gp_route_takeoff_diag.origin_z, z, vz, reference_z, target_z,
         error, p, i, d, u, motor1, motor2, motor3, motor4,
         ack >= 0.0 ? "post_ack" : "takeoff");
  fflush(stdout);
}
#endif

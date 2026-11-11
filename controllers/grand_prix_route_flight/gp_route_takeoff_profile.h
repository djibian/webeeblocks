#ifndef WEBEEBLOCKS_GP_ROUTE_TAKEOFF_PROFILE_H
#define WEBEEBLOCKS_GP_ROUTE_TAKEOFF_PROFILE_H

/* Grand Prix route only. Continuous altitude-reference governor for TAKEOFF.
 * No predetermined altitude waypoint, no change to the PID, oracle, physical
 * timestep, independent deadline or LAND/RESET. Inputs are native GPS/vz.
 * The reference is an acceleration-limited trajectory with feedback lead
 * limitation and anticipatory stopping based on measured upward velocity.
 */
#include <math.h>

#define GP_ROUTE_ASCENT_MAX_SPEED 0.32
#define GP_ROUTE_ASCENT_ACCEL 0.55
#define GP_ROUTE_ASCENT_DECEL 0.55
#define GP_ROUTE_ASCENT_MAX_LEAD 0.14
#define GP_ROUTE_ASCENT_REACTION 0.064

typedef struct {
  double reference_z;
  double speed;
} gp_route_takeoff_profile_t;

static void gp_route_takeoff_begin(gp_route_takeoff_profile_t *profile,
                                   double actual_z) {
  profile->reference_z = actual_z;
  profile->speed = 0.0;
}

/* The returned reference is a continuous function of time/target (not of any
 * fixed intermediate altitude); upper bounds concern the commanded reference,
 * not a claim about the realized flight. Native safety still decides. */
static double gp_route_takeoff_next(gp_route_takeoff_profile_t *profile,
                                    double requested_z, double actual_z,
                                    double actual_vz, double dt) {
  if (!profile || !isfinite(profile->reference_z) || !isfinite(profile->speed) ||
      !isfinite(requested_z) || !isfinite(actual_z) ||
      !isfinite(actual_vz) || !isfinite(dt) ||
      dt <= 0.0 || dt > 0.032001 || profile->speed < 0.0 ||
      profile->speed > GP_ROUTE_ASCENT_MAX_SPEED + 1e-9 ||
      profile->reference_z > requested_z + 1e-9)
    return NAN;

  const double upward_vz = fmax(0.0, actual_vz);
  const double remaining = fmax(0.0, requested_z -
                                      fmax(profile->reference_z, actual_z));
  /* Reserve the distance travelled while a 32-ms controller sample and the
   * next actuation take effect. A high measured vz calls for earlier braking. */
  const double braking = upward_vz * upward_vz /
                         (2.0 * GP_ROUTE_ASCENT_DECEL) +
                         upward_vz * GP_ROUTE_ASCENT_REACTION;
  const double usable = fmax(0.0, remaining - braking);
  double speed_goal = fmin(GP_ROUTE_ASCENT_MAX_SPEED,
                           sqrt(2.0 * GP_ROUTE_ASCENT_DECEL * usable));
  if (profile->reference_z - actual_z >= GP_ROUTE_ASCENT_MAX_LEAD)
    speed_goal = 0.0;

  const double change = fmax(-GP_ROUTE_ASCENT_DECEL * dt,
                             fmin(GP_ROUTE_ASCENT_ACCEL * dt,
                                  speed_goal - profile->speed));
  profile->speed = fmax(0.0, fmin(GP_ROUTE_ASCENT_MAX_SPEED,
                                  profile->speed + change));
  double next = fmin(requested_z,
                     profile->reference_z + profile->speed * dt);
  /* This measured-position lead guard bounds accumulated height error even
   * if the engine tracks slowly; never jump a reference backwards. */
  if (actual_z + GP_ROUTE_ASCENT_MAX_LEAD >= profile->reference_z)
    next = fmin(next, actual_z + GP_ROUTE_ASCENT_MAX_LEAD);
  profile->reference_z = fmax(profile->reference_z, next);
  return profile->reference_z;
}

#endif

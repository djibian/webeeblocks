/* SPDX-License-Identifier: GPL-3.0-only
 * Lab C observer. No hardware, Commander, estimator-output or range input. */
#ifndef LAB_WORLD_Z_H
#define LAB_WORLD_Z_H
#include <stdbool.h>
typedef struct {
  float x[3];                 /* relative world z, vz, acceleration bias */
  float p[3][3];
  float qa, qb;               /* continuous acceleration/bias spectral densities */
  bool healthy;
} WorldZ;
bool world_z_init(WorldZ *s, float z, float v, float bias,
                  float sz, float sv, float sb, float qa, float qb);
bool world_z_predict(WorldZ *s, float world_acc_m_s2, float dt_s);
bool world_z_baro(WorldZ *s, float relative_altitude_m, float variance_m2);
/* Alternative fixed-gain complementary observer. Bias remains the independently
 * calibrated value. omega is an explicit bandwidth assumption, not auto-tuning. */
bool world_z_slow_baro(WorldZ *s, float relative_altitude_m, float variance_m2,
                       float sample_dt_s, float omega_rad_s);
/* Caller must establish independent IMU-only attitude and synchronized inputs. */
bool world_z_project(const float q_wxyz[4], const float specific_force_g[3],
                     float *world_acc_m_s2);
/* Slant depth on one local plane, same optical axis assumption as stock model.
 * plane_valid is an external scientific precondition, NOT inferred from squal.
 * Timing/limits are explicit assumptions, not calibrated physical guarantees. */
bool local_flow_velocity(float dpixelx, float dpixely, float dt_s,
                         const float omega_rad_s[3], const float lever_m[3],
                         float slant_range_m, float range_age_s,
                         float max_age_s, float r22, bool plane_valid,
                         float velocity_body_m_s[2]);
#endif

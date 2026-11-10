"""Draft-only, source-anchored, route-only native control candidates.

This is NOT shipped code. Caller composes a fresh route runtime and compiles
this generated C inside pinned Webots R2025a. Shared PID implementation,
physical backend, evaluator, deadlines, guards and mission oracles stay
unchanged. Edits fail closed if any source anchor changes.
"""
from __future__ import annotations

from pathlib import Path

VARIANTS = ("baseline", "governor_pid_fixed", "direct_pid_fixed", "bitcraze_pid_fixed")
IDEAL_HOVER_MOTOR = 55.368085898

REF_ANCHOR = (
    "      desired.altitude = gp_route_takeoff_next(&gp_route_takeoff,\n"
    "        target_z, z, vz, dt);"
)
PID_ANCHOR = "      pid_velocity_fixed_height_controller(actual, &desired, gains, dt, &power);"
TRACE_ANCHOR = "      gp_route_takeoff_trace_sample(now, dt, z, vz, desired.altitude,"

# Keep the exact existing route-only safety guard immediately after reference
# calculation. The correction is injected only into the native control output.
PID_COMPENSATION = """
      /* ONLY EXPERIMENTAL VARIANT. Original PID already generated attitude
       * and horizontal motor mixing; change the common collective, not
       * the attitude/yaw channels, motor clamp or safety arbitration. */
      if (command == CMD_TAKEOFF || (airborne && command == CMD_IDLE)) {
        const double old_u = (power.m1 + power.m2 + power.m3 + power.m4) / 4.0;
        const double e = desired.altitude - z;
        if (altitudeIntegrator > 0.20) altitudeIntegrator = 0.20;
        if (altitudeIntegrator < -0.20) altitudeIntegrator = -0.20;
        const double p_z = gains.kp_z * fmax(-1.0, fmin(1.0, e));
        const double i_z = gains.ki_z * altitudeIntegrator;
        const double d_z = -gains.kd_z * vz;
        const double corrected_u = 55.368085898 + p_z + i_z + d_z;
        const double trim = corrected_u - old_u;
        power.m1 += trim;
        power.m2 += trim;
        power.m3 += trim;
        power.m4 += trim;
      }
"""

# Trajectory is rest-to-rest 7th degree, but its absolute reference is the
# Webots *origin + semantic takeoff height*, not physical EKF world-Z.
BCRA_REFERENCE = """      const double gp_ab_duration = (target_z - origin_z) / 0.5;
      double gp_ab_progress = (now - gp_route_takeoff_diag.t0) / gp_ab_duration;
      if (gp_ab_progress < 0.0) gp_ab_progress = 0.0;
      if (gp_ab_progress > 1.0) gp_ab_progress = 1.0;
      const double gp_ab_s = gp_ab_progress * gp_ab_progress *
        gp_ab_progress * gp_ab_progress *
        (35.0 + gp_ab_progress * (-84.0 +
           gp_ab_progress * (70.0 - 20.0 * gp_ab_progress)));
      desired.altitude = origin_z + (target_z - origin_z) * gp_ab_s;"""


def replace_one(text: str, old: str, new: str, label: str) -> str:
    occurrences = text.count(old)
    if occurrences != 1:
        raise RuntimeError(f"{label}: expected 1 route control anchor, found {occurrences}")
    return text.replace(old, new, 1)


def apply_generated_route_variant(source_file: Path, variant: str) -> None:
    if variant not in VARIANTS:
        raise ValueError("unknown route-only native variant")
    if variant == "baseline":
        return
    text = source_file.read_text()
    # Refuse an old U build, a non-route world, or missing native safety guards.
    for anchor in (REF_ANCHOR, PID_ANCHOR, TRACE_ANCHOR,
                   "gp_u_deadline(now, gp_pose_confirmed)",
                   "gp_route_observe_native(",
                   '#include "../gp_route_takeoff_trace.h"'):
        if text.count(anchor) != 1:
            raise RuntimeError("not exact known route composition: " + anchor[:50])
    if "WEBEEBLOCKS_GP_ROUTE_MODE" not in (source_file.parent.parent / "Makefile").read_text():
        raise RuntimeError("not route-only flight Makefile")
    if variant == "direct_pid_fixed":
        text = replace_one(text, REF_ANCHOR, "      desired.altitude = target_z;",
                           "direct takeoff reference")
    elif variant == "bitcraze_pid_fixed":
        text = replace_one(text, REF_ANCHOR, BCRA_REFERENCE,
                           "Bitcraze-shaped takeoff reference")
    text = replace_one(text, PID_ANCHOR, PID_ANCHOR + PID_COMPENSATION,
                       "vertical feedback compensation")
    source_file.write_text(text)


def expected_compensated_collective(row: dict) -> float:
    return (IDEAL_HOVER_MOTOR + row["p"] + row["i"] - 5.0 * row["vz"])

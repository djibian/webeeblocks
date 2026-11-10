"""Draft-only predictive headroom guard for native Grand Prix R2025a.

No shared controller, evaluator, oracle or physical-backend changes.
Guard a positive upward request BEFORE it becomes a flight instruction.
A refusal is observable as VERTICAL_LIMIT or INVALID_TAKEOFF, never a
fabricated mission PASS. This is a measured-context candidate, not an
absolute proof for arbitrary hardware/dynamics.

Calibration:
- Actual post-oracle climb in #954 ceiling failure: 0.058826 m;
- Native 32 ms PID and 8 ms oracle, observed LAND transition 24 ms;
- Representative LAND deceleration approx 0.401 m/s^2; use conservative
  0.25 m/s^2, plus explicit 64 ms observation/control reaction budget;
- 0.080 m base allowance > measured 0.058826 m tail + 0.021174 m.
The constraint is a positive margin BELOW the unchanged 1.15 m above
origin; it never moves the oracle ceiling.
"""
from __future__ import annotations
from pathlib import Path

SCOPES = ("all_active_primitives_headroom",)

_VEL_REF = """        const double next_target_z = z + (strcmp(request.direction, "up") == 0 ? request.value : -request.value);"""
_TAKEOFF_REF = """        target_z = origin_z + request.value;"""

_BRAKING_MARGIN = """gp_ceiling_headroom(vz)"""
_GUARD_FUNCTION = """
/* Route-only native candidate: conservative pre-command headroom.
 * Deceleration is a bounded SIMULATION hypothesis to verify in R2025a,
 * not an assertion of a real Crazyflie braking guarantee. */
static double gp_ceiling_headroom(double speed_z) {
  if (!isfinite(speed_z)) return NAN;
  const double ascent = fmax(0.0, speed_z);
  const double reaction_time_s = 0.064;
  const double minimum_deceleration_m_s2 = 0.25;
  const double measured_tail_plus_margin_m = 0.080;
  return measured_tail_plus_margin_m + reaction_time_s * ascent +
    ascent * ascent / (2.0 * minimum_deceleration_m_s2);
}
"""

_VERTICAL_GUARD = """
        if (strcmp(request.direction, "up") == 0) {
          const double gp_headroom = gp_ceiling_headroom(vz);
          const double gp_safe_top = origin_z + 1.15 - gp_headroom;
          if (!isfinite(gp_safe_top) || next_target_z > gp_safe_top) {
            fprintf(stderr,
              "GP_CEILING_PREFLIGHT_V1 command=VERTICAL z=%.9f vz=%.9f "
              "target=%.9f top=%.9f headroom=%.9f ceiling=%.9f "
              "code=VERTICAL_LIMIT\\n",
              z, vz, next_target_z, gp_safe_top, gp_headroom,
              origin_z + 1.15);
            response_error(request.id, "VERTICAL_LIMIT");
            continue;
          }
        }
"""

_TAKEOFF_GUARD = """
        /* Preserve strict TAKEOFF 1.0 m qualification, refuse new targets
         * insufficiently clear of the unchanged native ceiling. */
        if (!isfinite(gp_ceiling_headroom(vz)) ||
            origin_z + request.value >
              origin_z + 1.15 - gp_ceiling_headroom(vz)) {
          fprintf(stderr,
             "GP_CEILING_PREFLIGHT_V1 command=TAKEOFF z=%.9f vz=%.9f "
             "target=%.9f headroom=%.9f ceiling=%.9f "
             "code=INVALID_TAKEOFF\\n",
             z, vz, origin_z + request.value,
             gp_ceiling_headroom(vz), origin_z + 1.15);
          response_error(request.id, "INVALID_TAKEOFF");
          continue;
        }
"""


def inject_generated_headroom(path: Path, scope: str) -> None:
    if scope not in SCOPES:
        raise ValueError("unknown preventive-ceiling candidate")
    s = path.read_text()
    anchor = "static double wrap_angle(double angle) {"
    if s.count(anchor) != 1:
        raise RuntimeError("native common function anchor drift")
    s = s.replace(anchor, _GUARD_FUNCTION + "\n" + anchor, 1)
    if s.count(_VEL_REF) != 1 or s.count(_TAKEOFF_REF) != 1:
        raise RuntimeError("native request semantics drift")
    s = s.replace(_VEL_REF, _VEL_REF + _VERTICAL_GUARD, 1)
    s = s.replace(_TAKEOFF_REF, _TAKEOFF_GUARD + _TAKEOFF_REF, 1)
    for token in ("gp_u_deadline(now, gp_pose_confirmed)",
                  "gp_u_reset_complete()", "GP_ROUTE_SAMPLE_V1",
                  "land_touchdown", "GP_SEQUENCE_SAMPLE"):
        if token != "GP_ROUTE_SAMPLE_V1" and s.count(token) < 1:
            raise RuntimeError("missing safety or trace anchor: " + token)
    if s.count("GP_CEILING_PREFLIGHT_V1") != 2:
        raise RuntimeError("unexpected preventive-guard provenance")
    path.write_text(s)

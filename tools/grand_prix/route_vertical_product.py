"""Route-only, source-locked assembly of the qualified vertical pilot candidate.

This applies to the Grand Prix route native simulation C generated from
#952; the shared Crazyflie runtime, hardware backend, PID, and evaluators are
unchanged. The frozen native #954 measurements justify this *Draft candidate*
only; multi-route and velocity-envelope review remain mandatory before Ready.
"""
from __future__ import annotations


def _once(source: str, anchor: str, replacement: str, name: str) -> str:
    if source.count(anchor) != 1:
        raise RuntimeError(f"route-only control anchor drift ({name})")
    return source.replace(anchor, replacement, 1)


_CEILING_FUNCTION = """/* The existing PID owns this integral (declared by the #953 diagnostic
 * header in the native prototype); link to it without modifying the PID. */
extern double altitudeIntegrator;
/* Route simulation only: empirical request-admission clearance, not an oracle.
 * Reference: #954 R2025a native run 42878862498 (artifact 13795080041).
 * 32ms controller; 8ms physics; 64ms response budget; assumed >=0.25m/s^2
 * deceleration. The oracle's origin+1.15m ceiling remains unchanged.
 * Positive upward velocity and requested upward travel both add clearance.
 */
static double gp_route_upward_headroom(double measured_vz, double requested_up) {
  if (!isfinite(measured_vz) || !isfinite(requested_up) ||
      requested_up < 0.0) return NAN;
  const double v_up = fmax(0.0, measured_vz);
  const double amplitude_margin = requested_up > 0.0 ?
    0.095 + 0.30 * requested_up : 0.080;
  return amplitude_margin + 0.064 * v_up + v_up * v_up / 0.50;
}
"""

_TAKEOFF_PREFLIGHT = """        /* Reject before assigning active_id, target or any flight state. */
        const double gp_headroom = gp_route_upward_headroom(vz, 0.0);
        if (!isfinite(gp_headroom) ||
            origin_z + request.value > origin_z + 1.15 - gp_headroom) {
          fprintf(stderr,
             "GP_CEILING_PREFLIGHT_V1 command=TAKEOFF z=%.9f vz=%.9f "
             "target=%.9f headroom=%.9f ceiling=%.9f "
             "code=INVALID_TAKEOFF\\n",
             z, vz, origin_z + request.value, gp_headroom, origin_z + 1.15);
          response_error(request.id, "INVALID_TAKEOFF");
          continue;
        }
"""

_VERTICAL_PREFLIGHT = """        if (strcmp(request.direction, "up") == 0) {
          const double gp_headroom = gp_route_upward_headroom(vz, request.value);
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

# Compensate the COMMON collective only. Attitude/yaw mixing stays from the
# original PID. The original motor_power() clamp and the immutable LAND
# touchdown branch remain downstream and take precedence over this trim.
_COLLECTIVE_COMPENSATION = """      /* Native R2025a route-only vertical trim shared by all aerial modes.
       * Does not add a second trajectory governor to VERTICAL.
       */
      if (command == CMD_TAKEOFF ||
          (airborne && (command == CMD_IDLE || command == CMD_MOVE ||
                        command == CMD_VERTICAL || command == CMD_TURN ||
                        command == CMD_WAIT || command == CMD_LAND))) {
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


# Observational only, compiled into the very same candidate binary and
# enabled only for the native R2025a qualification environment. It never
# alters the flight state, calls the oracle, nor writes motor setpoints.
_PRODUCT_TRACE = """    if (getenv("WBB_GP_PRODUCT_TRACE") &&
        strcmp(getenv("WBB_GP_PRODUCT_TRACE"), "1") == 0) {
      int gp_contact = -1;
      WbNodeRef gp_vehicle = wb_supervisor_node_get_self();
      if (gp_vehicle) {
        int gp_n = -1;
        const WbContactPoint *gp_points =
          wb_supervisor_node_get_contact_points(gp_vehicle, true, &gp_n);
        if (gp_n >= 0 && (gp_n == 0 || gp_points != NULL)) {
          gp_contact = 0;
          for (int k = 0; k < gp_n; ++k)
            if (isfinite(gp_points[k].point[2]) &&
                gp_points[k].point[2] <= origin_z) {
              gp_contact = 1; break;
            }
        }
      }
      const char *gp_phase =
          command == CMD_TAKEOFF ? "TAKEOFF" :
          command == CMD_MOVE ? "MOVE" :
          command == CMD_VERTICAL ? "VERTICAL" :
          command == CMD_TURN ? "TURN" :
          command == CMD_WAIT ? "WAIT" :
          command == CMD_LAND ? "LAND" : "IDLE";
      printf("GP_PRODUCT_SAMPLE t=%.6f cmd=%s x=%.9f y=%.9f "
             "z=%.9f vz=%.9f yaw=%.9f ref=%.9f target=%.9f "
             "contact=%d touchdown=%d airborne=%d\\n",
             now, gp_phase, x, y, z, vz, yaw,
             desired.altitude, target_z, gp_contact, land_touchdown, airborne);
      fflush(stdout);
    }
"""


def compose_route_vertical_product(source: str) -> str:
    """Apply only after #952 route TAKEOFF composition, never to shared U."""
    if ("GP_CEILING_PREFLIGHT_V1 command=" in source or
            "gp_route_upward_headroom(" in source or
            "const double corrected_u = 55.368085898" in source):
        raise RuntimeError("duplicate route-only vertical control injection")
    required = (
        '#include "../gp_route_takeoff_profile.h"',
        "gp_route_takeoff_next(&gp_route_takeoff,",
        "gp_route_observe_native(",
        "gp_u_deadline(now, gp_pose_confirmed)",
        "gp_u_reset_complete()",
    )
    for marker in required:
        if source.count(marker) != 1:
            raise RuntimeError("route-only native safety/composition marker drift: " + marker)
    source = _once(source, "static double wrap_angle(double angle) {",
                   _CEILING_FUNCTION + "\nstatic double wrap_angle(double angle) {",
                   "ceiling helper")
    # Restrict TAKEOFF insertion to the request branch. This fixes #954's
    # experimental late guard, which had mutated active_id before refusal.
    begin = "      if (request.kind == REQUEST_TAKEOFF) {"
    after = "      if (request.kind == REQUEST_MOVE) {"
    if source.count(begin) != 1 or source.count(after) != 1:
        raise RuntimeError("TAKEOFF/next-request control boundaries changed")
    prefix, tail = source.split(begin, 1)
    body, suffix = tail.split(after, 1)
    body = _once(body, "        active_id = request.id;",
                 _TAKEOFF_PREFLIGHT + "        active_id = request.id;",
                 "TAKEOFF side-effect-free refusal")
    source = prefix + begin + body + after + suffix
    # Native H3 retest 42907396704 proved first touchdown and LAND_READY
    # could coincide (t=88.352): pre-contact pose stability had already
    # aged 1.120s. Require a FRESH continuous real-contact window. A bounced
    # or transient contact resets that window, but the existing touchdown
    # latch still keeps motors unpowered (irreversible safety).
    source = _once(source, "  double gp_ground_since = -1.0;",
                   "  double gp_ground_since = -1.0;\\n"
                   "  double gp_land_contact_since = -1.0;",
                   "separate native contact window")
    original_contact = (
        "if (!land_touchdown && land_has_ground_contact(z, origin_z)) {"
    )
    native_contact = (
        "const int gp_contact_now = land_has_ground_contact(z, origin_z);\\n"
        "      if (!gp_contact_now) gp_land_contact_since = -1.0;\\n"
        "      else if (gp_land_contact_since < 0.0) gp_land_contact_since = now;\\n"
        "      if (!land_touchdown && gp_contact_now) {"
    )
    source = _once(source, original_contact, native_contact,
                   "native contact sample refresh on every LAND cycle")
    # Reset the timer whenever the flight controller is not in LAND, so a
    # separate landing cannot reuse an old contact observation window.
    idle_anchor = "    if (command == CMD_TAKEOFF) {"
    source = _once(source, idle_anchor,
                   "    if (command != CMD_LAND) gp_land_contact_since = -1.0;\\n" +
                   idle_anchor, "separate LAND window freshness")
    # #956 H3: independent oracle observed native LAND ACK at t=87.744s
    # before any actual contact (touchdown only at t=88.416s). Tighten only
    # route-only LAND ACK: geometric ground stability cannot replace a
    # real Supervisor contact latch. The existing safety LAND and reset
    # policies remain unchanged; no oracle predicate is relaxed.
    land_anchor = (
        "if (now - stable_since >= STOP_WINDOW && gp_ground_sample &&\n"
        "            gp_ground_since >= 0.0 && now - gp_ground_since >= STOP_WINDOW) {"
    )
    land_guarded = land_anchor.replace(
        "            gp_ground_since >= 0.0",
        "            land_touchdown && gp_land_contact_since >= 0.0 && "
        "now - gp_land_contact_since >= STOP_WINDOW && gp_ground_since >= 0.0"
    )
    source = _once(source, land_anchor, land_guarded, "native contact-gated LAND")
    # VERTICAL target calculation precedes all command-state side effects.
    anchor = ('        const double next_target_z = z + '
              '(strcmp(request.direction, "up") == 0 ? request.value : -request.value);')
    source = _once(source, anchor, anchor + "\n" + _VERTICAL_PREFLIGHT,
                   "VERTICAL side-effect-free refusal")
    anchor = "      pid_velocity_fixed_height_controller(actual, &desired, gains, dt, &power);"
    source = _once(source, anchor, anchor + "\n" + _COLLECTIVE_COMPENSATION,
                   "common collective")
    # Physical contact witness is emitted at the end of the actual control
    # cycle, including unpowered settling after a transient contact.
    phase_tail = """    } else {
      stop_motors(m1, m2, m3, m4);
    }

    previous_time = now;
    previous_x = x;
    previous_y = y;
    previous_z = z;
  }

  stop_motors(m1, m2, m3, m4);"""
    source = _once(source, phase_tail,
                   phase_tail.replace("    previous_time = now;",
                                      _PRODUCT_TRACE + "    previous_time = now;"),
                   "native contact/velocity witness")
    for must in (
        "if (command == CMD_LAND && land_touchdown)",
        "stop_motors(m1, m2, m3, m4)",
        "gp_u_deadline(now, gp_pose_confirmed)",
        "gp_route_observe_native(",
        "gp_route_upward_headroom(vz, request.value)",
        "GP_CEILING_PREFLIGHT_V1 command=TAKEOFF",
        "GP_CEILING_PREFLIGHT_V1 command=VERTICAL",
    ):
        if must not in source:
            raise RuntimeError("mandatory native guard or pilot instrumentation missing: " + must)
    return source

"""Isolated R2025a cross-primitive observer; generated route C only, never shared source.

The correction used by #953 is deliberately frozen for the control arm.
This optional experiment either keeps its existing scope, or extends the same
collective trim to the other active flight modes. No oracle, broker, hardware
backend, deadline, clamp or supervisor implementation is edited.
"""
from __future__ import annotations

from pathlib import Path

from tools.grand_prix.isolated_native_takeoff_candidates import PID_COMPENSATION
from tools.grand_prix.isolated_native_ceiling_headroom import inject_generated_headroom

SCOPES = ("takeoff_idle_only", "all_active_primitives", "all_active_vertical_up_governed", "all_active_primitives_headroom")
OLD_CONDITION = "if (command == CMD_TAKEOFF || (airborne && command == CMD_IDLE))"
NEW_CONDITION = (
    "if (command == CMD_TAKEOFF || "
    "(airborne && (command == CMD_IDLE || command == CMD_MOVE || "
    "command == CMD_VERTICAL || command == CMD_TURN || "
    "command == CMD_WAIT || command == CMD_LAND)))"
)
# All fields come from the controller's own 32-ms physical simulation step.
# motor_power() is the UNMODIFIED effective per-rotor clamp.
SEQUENCE_OBSERVER = """
      if (getenv("WBB_GP_SEQUENCE_TRACE") &&
          strcmp(getenv("WBB_GP_SEQUENCE_TRACE"), "1") == 0) {
        const char *gp_phase =
          command == CMD_TAKEOFF ? "TAKEOFF" :
          command == CMD_MOVE ? "MOVE" :
          command == CMD_VERTICAL ? "VERTICAL" :
          command == CMD_TURN ? "TURN" :
          command == CMD_WAIT ? "WAIT" :
          command == CMD_LAND ? "LAND" : "IDLE";
        const double gp_collective =
          (power.m1 + power.m2 + power.m3 + power.m4) / 4.0;
        const int gp_saturation = power.m1 > 600.0 || power.m2 > 600.0 ||
          power.m3 > 600.0 || power.m4 > 600.0 ||
          power.m1 < 0.0 || power.m2 < 0.0 ||
          power.m3 < 0.0 || power.m4 < 0.0;
        int gp_contact = -1;
        WbNodeRef gp_vehicle = wb_supervisor_node_get_self();
        if (gp_vehicle) {
          int gp_count = -1;
          const WbContactPoint *gp_points =
            wb_supervisor_node_get_contact_points(gp_vehicle, true, &gp_count);
          if (gp_count >= 0 && (gp_count == 0 || gp_points != NULL)) {
            gp_contact = 0;
            for (int k = 0; k < gp_count; ++k) {
              if (isfinite(gp_points[k].point[2]) &&
                  gp_points[k].point[2] <= origin_z) {
                gp_contact = 1;
                break;
              }
            }
          }
        }
        printf("GP_SEQUENCE_SAMPLE t=%.6f dt=%.6f cmd=%s "
               "x=%.9f y=%.9f yaw=%.9f z=%.9f vz=%.9f ref=%.9f target=%.9f "
               "u=%.9f i=%.9f m1=%.9f m2=%.9f m3=%.9f m4=%.9f "
               "saturated=%d airborne=%d ground_contact=%d\\n",
               now, dt, gp_phase, x, y, yaw, z, vz, desired.altitude, target_z,
               gp_collective, altitudeIntegrator,
               motor_power(power.m1), motor_power(power.m2),
               motor_power(power.m3), motor_power(power.m4),
               gp_saturation, airborne, gp_contact);
        fflush(stdout);
      }
"""


def instrument_generated_controller(path: Path, scope: str) -> None:
    if scope not in SCOPES:
        raise ValueError("unknown cross-primitive PID scope")
    source = path.read_text(encoding="utf-8")
    if source.count(PID_COMPENSATION) != 1:
        raise RuntimeError("exact original isolated compensation absent")
    if source.count(OLD_CONDITION) != 1:
        raise RuntimeError("original scope anchor changed")
    if source.count("gp_u_deadline(now, gp_pose_confirmed)") != 1:
        raise RuntimeError("independent deadline guard changed")
    # Inject BEFORE changing the original condition; otherwise the exact
    # PID_COMPENSATION anchor disappears and str.replace does nothing.
    source = source.replace(PID_COMPENSATION, PID_COMPENSATION + SEQUENCE_OBSERVER, 1)
    if scope in ("all_active_primitives", "all_active_vertical_up_governed", "all_active_primitives_headroom"):
        source = source.replace(OLD_CONDITION, NEW_CONDITION, 1)
    if scope == "all_active_vertical_up_governed":
        # Reuse the already source-locked TAKEOFF governor only for upward
        # VERTICAL, with a fresh native position reference at request accept.
        # Descending VERTICAL retains its production reference exactly.
        begin = "        command = CMD_VERTICAL;"
        if source.count(begin) != 1:
            raise RuntimeError("native VERTICAL command anchor changed")
        source = source.replace(
            begin, "        gp_route_takeoff_begin(&gp_route_takeoff, z);\n" + begin, 1)
        before = "    } else if (command == CMD_VERTICAL) {"
        after = "    } else if (command == CMD_TURN) {"
        if source.count(before) != 1 or source.count(after) != 1:
            raise RuntimeError("unique VERTICAL control branch required")
        prefix, tail = source.split(before, 1)
        body, suffix = tail.split(after, 1)
        altitude = "      desired.altitude = target_z;"
        if body.count(altitude) != 1:
            raise RuntimeError("VERTICAL altitude source anchor changed")
        governed = """
      if (strcmp(active_direction, "up") == 0) {
        desired.altitude = gp_route_takeoff_next(
          &gp_route_takeoff, target_z, z, vz, dt);
        if (!isfinite(desired.altitude)) {
          response_error(active_id, "UNSAFE_OR_TIMEOUT");
          stop_motors(m1, m2, m3, m4);
          airborne = 0;
          simulation_clock_revoke(&program_clock);
          failsafe_latched = 1;
          command = CMD_IDLE;
          active_id = -1;
          stable_since = -1.0;
          previous_time = now; previous_x = x; previous_y = y; previous_z = z;
          continue;
        }
      }
"""
        body = body.replace(altitude, altitude + governed, 1)
        source = prefix + before + body + after + suffix
    if source.count("GP_SEQUENCE_SAMPLE") != 1:
        raise RuntimeError("mandatory native observer not injected exactly once")
    if scope == "all_active_primitives_headroom":
        # Native H3 counterexample: LAND ACK at 87.744 while contact only at
        # 88.416; unconfirmed-native-landing at 88.384. Without changing the
        # oracle, require the existing physical contact latch before ACK.
        land_before = (
            "if (now - stable_since >= STOP_WINDOW && gp_ground_sample &&\n"
            "            gp_ground_since >= 0.0 && now - gp_ground_since >= STOP_WINDOW) {"
        )
        land_after = land_before.replace(
            "            gp_ground_since >= 0.0",
            "            land_touchdown && gp_ground_since >= 0.0"
        )
        if source.count(land_before) != 1:
            raise RuntimeError("route-only LAND contact assertion anchor changed")
        source = source.replace(land_before, land_after, 1)
    path.write_text(source, encoding="utf-8")
    if scope == "all_active_primitives_headroom":
        inject_generated_headroom(path, scope)

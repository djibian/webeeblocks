"""Isolated R2025a cross-primitive observer; generated route C only, never shared source.

The correction used by #953 is deliberately frozen for the control arm.
This optional experiment either keeps its existing scope, or extends the same
collective trim to the other active flight modes. No oracle, broker, hardware
backend, deadline, clamp or supervisor implementation is edited.
"""
from __future__ import annotations

from pathlib import Path

from tools.grand_prix.isolated_native_takeoff_candidates import PID_COMPENSATION

SCOPES = ("takeoff_idle_only", "all_active_primitives")
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
        printf("GP_SEQUENCE_SAMPLE t=%.6f dt=%.6f cmd=%s "
               "z=%.9f vz=%.9f ref=%.9f target=%.9f "
               "u=%.9f i=%.9f m1=%.9f m2=%.9f m3=%.9f m4=%.9f "
               "saturated=%d airborne=%d\\n",
               now, dt, gp_phase, z, vz, desired.altitude, target_z,
               gp_collective, altitudeIntegrator,
               motor_power(power.m1), motor_power(power.m2),
               motor_power(power.m3), motor_power(power.m4),
               gp_saturation, airborne);
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
    if scope == "all_active_primitives":
        source = source.replace(OLD_CONDITION, NEW_CONDITION, 1)
    source = source.replace(PID_COMPENSATION, PID_COMPENSATION + SEQUENCE_OBSERVER, 1)
    path.write_text(source, encoding="utf-8")

#!/usr/bin/env python3
"""Pinned Bitcraze 2026.08 TAKEOFF_WITH_VELOCITY nominal reference ONLY.

Derived from cf2 firmware commit 54f31e243a0b28b67efef5ba20dbb6d9890a5478:
crtp_commander_high_level.c::takeoff_with_velocity duration=abs(h-pos.z)/v;
planner.c::plan_takeoff -> plan_takeoff_or_landing;
pptraj.c::piecewise_plan_7th_order_no_jerk.
This is an ideal setpoint, NOT a measured actual trajectory or qualified flight.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

FIRMWARE_SHA = "54f31e243a0b28b67efef5ba20dbb6d9890a5478"
TAKEOFF_VELOCITY_M_S = 0.5
HEIGHTS_M = (0.5, 0.8, 1.0)
NOMINAL_PEAK_FACTOR = 35.0 / 16.0


def normalized_position(u: float) -> float:
    if u <= 0.0:
        return 0.0
    if u >= 1.0:
        return 1.0
    return u ** 4 * (35.0 + u * (-84.0 + u * (70.0 - 20.0 * u)))


def normalized_speed(u: float) -> float:
    if not 0.0 < u < 1.0:
        return 0.0
    return 140.0 * u ** 3 * (1.0 - u) ** 3


def nominal_takeoff(
    absolute_target_z_m: float, initial_estimated_z_m: float, t_seconds: float
) -> tuple[float, float, float]:
    """(z_ref [m], vz_ref [m/s], duration [s]) for a stationary EKF origin.

    The firmware starts from its ESTIMATED current position, not Webots GPS.
    The absolute target is the AST height (heightIsRelative=False). Nominal
    Bitcraze generated goal is not a guaranteed realized speed or trajectory.
    """
    for name, value in (("target", absolute_target_z_m),
                        ("initial_estimated_z", initial_estimated_z_m),
                        ("time", t_seconds)):
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
    if not 0 <= initial_estimated_z_m < absolute_target_z_m <= 1.5 or t_seconds < 0:
        raise ValueError("strict positive takeoff from a bounded estimated altitude required")
    duration = (absolute_target_z_m - initial_estimated_z_m) / TAKEOFF_VELOCITY_M_S
    u = min(1.0, t_seconds / duration)
    distance = absolute_target_z_m - initial_estimated_z_m
    return (
        initial_estimated_z_m + distance * normalized_position(u),
        (distance / duration) * normalized_speed(u),
        duration,
    )


def rows(initial_estimated_z_m: float = 0.0, step_s: float = 0.032) -> list[dict]:
    """Consistent time grid, plus exact terminal knots for each height."""
    if type(step_s) not in (int, float) or not math.isfinite(step_s) or not 0 < step_s <= .1:
        raise ValueError("positive time step <= 0.1s required")
    if not 0 <= initial_estimated_z_m < min(HEIGHTS_M):
        raise ValueError("initial EKF z must be smaller than every target")
    end = max((h - initial_estimated_z_m) / TAKEOFF_VELOCITY_M_S for h in HEIGHTS_M) + 1.5
    result = []
    for height in HEIGHTS_M:
        duration = (height - initial_estimated_z_m) / TAKEOFF_VELOCITY_M_S
        stamps = sorted(set([round(i * step_s, 9) for i in range(int(end / step_s) + 1)] +
                            [round(duration, 9), round(end, 9)]))
        for t in stamps:
            z, vz, _ = nominal_takeoff(height, initial_estimated_z_m, t)
            result.append(dict(firmware_sha=FIRMWARE_SHA, ast_height_m=height,
                               initial_estimated_z_m=initial_estimated_z_m,
                               t_s=t, z_ref_m=round(z, 9), vz_ref_m_s=round(vz, 9),
                               nominal_duration_s=round(duration, 9)))
    return result


def write_curves(output: Path, initial_estimated_z_m: float = 0.0) -> None:
    output.mkdir(parents=True, exist_ok=False)
    dataset = rows(initial_estimated_z_m)
    csv_path = output / "bitcraze_takeoff_nominal.csv"
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(dataset[0]))
        writer.writeheader()
        writer.writerows(dataset)
    meta = {
        "source": FIRMWARE_SHA,
        "semantic": "TAKEOFF_WITH_VELOCITY_command_9_absolute_height",
        "physical_takeoff_velocity_field_m_s": TAKEOFF_VELOCITY_M_S,
        "nominal_peak_velocity_m_s": round(NOMINAL_PEAK_FACTOR * TAKEOFF_VELOCITY_M_S, 9),
        "reference_not_observed_hardware": True,
        "relative_to": "firmware_EKF_estimated_initial_position",
        "initial_estimated_z_m_assumed": initial_estimated_z_m,
        "heights_m": HEIGHTS_M,
        "nominal_durations_s": {
            str(h): round((h - initial_estimated_z_m) / TAKEOFF_VELOCITY_M_S, 6)
            for h in HEIGHTS_M
        },
        "no_simulation_measured": True,
    }
    (output / "reference.json").write_text(json.dumps(meta, sort_keys=True, indent=2) + "\n")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return  # CSV remains the reproducible mandatory evidence
    for key, ylabel, filename in (
        ("z_ref_m", "Altitude de consigne embarquée (m)", "nominal_z.png"),
        ("vz_ref_m_s", "Vitesse verticale de consigne (m/s)", "nominal_vz.png"),
    ):
        fig, ax = plt.subplots(figsize=(8, 4.5))
        for h in HEIGHTS_M:
            values = [entry for entry in dataset if entry["ast_height_m"] == h]
            ax.plot([v["t_s"] for v in values],
                    [v[key] for v in values],
                    label=f"TAKEOFF {h:.1f} m")
        ax.set_xlabel("Temps depuis la commande (s)")
        ax.set_ylabel(ylabel)
        ax.set_title("Bitcraze 2026.08 — CONSIGNE NOMINALE, PAS UN VOL MESURÉ")
        ax.grid(True, alpha=.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(output / filename, dpi=150)
        plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new directory")
    parser.add_argument("--initial-estimated-z", type=float, default=0.0,
                        help="assumed firmware EKF initial Z (not Webots GPS), default 0")
    args = parser.parse_args()
    write_curves(args.output, args.initial_estimated_z)


if __name__ == "__main__":
    main()

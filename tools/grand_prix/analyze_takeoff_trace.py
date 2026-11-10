#!/usr/bin/env python3
"""Analyze read-only Grand Prix native Webots takeoff traces.

A trace is evidence only of the exact simulated run in its log.  This program
does not certify hardware fidelity, inspect mission oracles, or emit commands.
No substitutions for absent samples or completion events are permitted.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import statistics

MARKER = re.compile(r"\bGP_ROUTE_TAKEOFF_TRACE_(BEGIN|SAMPLE|ACK)\b")
PAIR = re.compile(r"([a-z][a-z0-9_]*)=([^\s]+)")
SAMPLE_KEYS = ("t", "dt", "z0", "z", "vz", "ref", "target", "error",
               "p", "i", "d", "u", "m1", "m2", "m3", "m4")
MIN_LIFT_M = 0.020  # observed elevation proxy, NOT a physical contact sensor
MIN_ASCENT_M_S = 0.030
POSITION_TOL_M = 0.030  # vertical part only of native command ACK predicate
VERTICAL_SPEED_TOL_M_S = 0.150
STABLE_WINDOW_S = 0.5
SAMPLE_GAP_S = 0.040
# Derived ideal level-flight estimate from unchanged QualificationCrazyflie
# model: 0.05 kg, gravity 9.81, four |k_thrust| = 4e-5. NOT a measurement.
MODEL_HOVER_OMEGA = math.sqrt(0.05 * 9.81 / (4.0 * 4e-5))


class TraceError(ValueError):
    pass


def parse_lines(lines: list[str]) -> list[dict]:
    runs: list[dict] = []
    live: dict[int, dict] = {}
    for lineno, line in enumerate(lines, 1):
        match = MARKER.search(line)
        if not match:
            continue
        kind = match.group(1)
        data = dict(PAIR.findall(line[match.end():]))
        try:
            request_id = int(data["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TraceError(f"line {lineno}: missing/invalid id") from exc
        if request_id <= 0:
            raise TraceError(f"line {lineno}: invalid request id")
        if kind == "BEGIN":
            if request_id in live:
                raise TraceError(f"line {lineno}: duplicate request id within log")
            for key in ("t", "z0", "target"):
                try:
                    value = float(data[key])
                except (ValueError, KeyError) as exc:
                    raise TraceError(f"line {lineno}: missing {key}") from exc
                if not math.isfinite(value):
                    raise TraceError(f"line {lineno}: non-finite {key}")
                data[key] = value
            run = {"id": request_id, "begin": data, "samples": [], "ack": None}
            runs.append(run)
            live[request_id] = run
        else:
            run = live.get(request_id)
            if run is None:
                raise TraceError(f"line {lineno}: {kind} without matching BEGIN")
            if kind == "ACK":
                if run["ack"] is not None:
                    raise TraceError(f"line {lineno}: duplicate ACK")
                try:
                    t = float(data["t"])
                except (KeyError, ValueError) as exc:
                    raise TraceError(f"line {lineno}: missing ACK time") from exc
                if not math.isfinite(t) or t < run["begin"]["t"]:
                    raise TraceError(f"line {lineno}: invalid ACK time")
                run["ack"] = t
            else:
                parsed = {}
                for key in SAMPLE_KEYS:
                    try:
                        val = float(data[key])
                    except (KeyError, ValueError) as exc:
                        raise TraceError(f"line {lineno}: invalid {key}") from exc
                    if not math.isfinite(val):
                        raise TraceError(f"line {lineno}: non-finite {key}")
                    parsed[key] = val
                try:
                    parsed["ground_contact"] = int(data["ground_contact"])
                except (KeyError, ValueError) as exc:
                    raise TraceError(f"line {lineno}: invalid ground_contact") from exc
                if parsed["ground_contact"] not in (-1, 0, 1):
                    raise TraceError(f"line {lineno}: out-of-domain ground_contact")
                parsed["phase"] = data.get("phase", "")
                if parsed["phase"] not in ("takeoff", "post_ack"):
                    raise TraceError(f"line {lineno}: invalid phase")
                if parsed["dt"] <= 0 or parsed["dt"] > 0.032001:
                    raise TraceError(f"line {lineno}: invalid controller dt")
                if parsed["t"] < run["begin"]["t"] or (
                    run["samples"] and parsed["t"] <= run["samples"][-1]["t"]
                ):
                    raise TraceError(f"line {lineno}: non-monotone time")
                run["samples"].append(parsed)
    return runs


def first_stable_window(samples: list[dict], *, start_t: float,
                        requested_z: float) -> float | None:
    """First onset of continuous vertical-only observed stability window."""
    onset = None
    previous_t = None
    for row in samples:
        if row["t"] < start_t:
            continue
        ok = (abs(row["z"] - requested_z) <= POSITION_TOL_M
              and abs(row["vz"]) < VERTICAL_SPEED_TOL_M_S)
        if previous_t is not None and row["t"] - previous_t > SAMPLE_GAP_S:
            onset = None
        if ok:
            if onset is None:
                onset = row["t"]
            if row["t"] - onset >= STABLE_WINDOW_S:
                return onset
        else:
            onset = None
        previous_t = row["t"]
    return None


def summarize(run: dict) -> dict:
    start = run["begin"]
    samples = run["samples"]
    ack = run["ack"]
    if not samples:
        return {"id": run["id"], "status": "NO_NATIVE_SAMPLES", "ack_observed": ack is not None}
    t0, origin, target = start["t"], start["z0"], start["target"]
    if any(abs(row["z0"] - origin) > 1e-8 or
           abs(row["target"] - target) > 1e-8 for row in samples):
        raise TraceError(f"id {run['id']}: target/origin changed within flight trace")
    if ack is not None and samples[0]["t"] > ack:
        raise TraceError(f"id {run['id']}: ACK precedes all samples")
    lift = next((row["t"] for row in samples if
                 row["z"] - origin >= MIN_LIFT_M
                 and row["vz"] > MIN_ASCENT_M_S), None)
    # A witnessed contact-to-no-contact transition is the first sampled
    # loss of ground contact, bracketed by the 32-ms observation period.
    # If contact was never seen, loss of contact is NOT established.
    seen_contact = False
    contact_loss = None
    for row in samples:
        if row["ground_contact"] == 1:
            seen_contact = True
        elif seen_contact and row["ground_contact"] == 0:
            contact_loss = row["t"]
            break
    rotor = next((row["t"] for row in samples if
                  sum(abs(row[k]) for k in ("m1", "m2", "m3", "m4")) / 4
                  >= MODEL_HOVER_OMEGA), None)
    gap = [round(row["t"] - prev["t"], 6)
           for prev, row in zip(samples, samples[1:])
           if row["t"] - prev["t"] > SAMPLE_GAP_S]
    stable = first_stable_window(samples, start_t=t0, requested_z=target)
    z_max = max(row["z"] for row in samples)
    peak_motors = max(abs(row[k]) for row in samples for k in ("m1", "m2", "m3", "m4"))
    return {
        "id": run["id"],
        "status": "TRACE_WITH_ACK" if ack is not None else "TRACE_CENSORED_NO_ACK",
        "scope": "simulation_ground_truth_not_real_crazyflie_fidelity",
        "time_origin_s": t0,
        "target_relative_m": round(target - origin, 7),
        "samples": len(samples),
        "last_sample_elapsed_s": round(samples[-1]["t"] - t0, 6),
        "sampling_gaps_over_40ms_s": gap,
        "ack_observed": ack is not None,
        "takeoff_ack_elapsed_s": None if ack is None else round(ack - t0, 6),
        "first_lift_2cm_proxy_elapsed_s": None if lift is None else round(lift - t0, 6),
        "first_observed_ground_contact_loss_elapsed_s":
            None if contact_loss is None else round(contact_loss - t0, 6),
        "contact_witness_status":
            ("CONTACT_LOSS_OBSERVED" if contact_loss is not None
             else "GROUND_CONTACT_OBSERVED_NO_LOSS" if seen_contact
             else "CONTACT_LOSS_UNPROVEN"),
        "first_model_hover_omega_proxy_elapsed_s": None if rotor is None else round(rotor - t0, 6),
        "model_hover_omega_not_measured_rad_s": round(MODEL_HOVER_OMEGA, 6),
        "maximum_observed_altitude_m": round(z_max, 8),
        "maximum_observed_overshoot_m": round(max(0.0, z_max - target), 8),
        "max_observed_upward_speed_m_s": round(max(row["vz"] for row in samples), 6),
        "first_vertical_stability_window_elapsed_s":
            None if stable is None else round(stable - t0, 6),
        "max_abs_pid_integral_output": round(max(abs(row["i"]) for row in samples), 6),
        "max_abs_pid_d_output": round(max(abs(row["d"]) for row in samples), 6),
        "max_abs_motor_command_rad_s": round(peak_motors, 6),
        "max_pid_reconstruction_residual": round(max(
            abs(row["u"] - (48.0 + row["p"] + row["i"] + row["d"]))
            for row in samples), 6),
        "steady_state_settling": (
            "OBSERVED_VERTICAL_ONLY" if stable is not None
            else "NOT_OBSERVED_IN_CAPTURE"
        ),
        "complete_3d_ack_guaranteed_by_this_trace": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="Raw console log for one exact Webots run")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON path")
    args = parser.parse_args()
    try:
        runs = parse_lines(args.log.read_text(encoding="utf-8", errors="replace").splitlines())
        results = [summarize(run) for run in runs]
    except (TraceError, OSError) as exc:
        parser.error(str(exc))
    payload = {"source_log": str(args.log), "analysis":"observational_only_no_fidelity_pass",
               "runs": results}
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

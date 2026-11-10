#!/usr/bin/env python3
"""Run read-only native full-flight sequences on isolated generated route candidates.

Each scenario uses a fresh identical Grand Prix world, real route evaluator and
normal WWI backend. Refusals, missing traces and independent LAND are never
reported as mission success. Existing source, oracles, physical sender and
clamps are not modified.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.grand_prix.run_takeoff_native_r2025a import (
    ROOT, FLIGHT, COURSE_INDEX, sha256, require_source, prerequisites, webots_home,
    compile_production, available_port, stop_owned_process,
)
from tools.grand_prix.isolated_native_sequence import SCOPES, instrument_generated_controller
from tools.grand_prix.course_active_world_v2 import active_course_world
from tools.grand_prix.route_courses_v2 import reference_course

SCENARIOS = ("primitives", "ceiling", "ceiling_safe_ascent", "ceiling_takeoff", "route_lh", "stop", "deadline", "reset")
SAMPLE = re.compile(r"\bGP_SEQUENCE_SAMPLE\b")
PAIR = re.compile(r"([a-z][a-z0-9_]*)=([^\s]+)")
FIELDS = ("t", "dt", "x", "y", "yaw", "z", "vz", "ref", "target", "u", "i",
          "m1", "m2", "m3", "m4")
MODES = frozenset(("TAKEOFF", "IDLE", "MOVE", "VERTICAL", "TURN", "WAIT", "LAND"))


def decode_samples(lines: list[str]) -> list[dict]:
    samples = []
    for line in lines:
        mark = SAMPLE.search(line)
        if not mark:
            continue
        pairs = dict(PAIR.findall(line[mark.end():]))
        row = {key: float(pairs[key]) for key in FIELDS}
        row["cmd"] = pairs["cmd"]
        row["saturated"] = int(pairs["saturated"])
        row["airborne"] = int(pairs["airborne"])
        row["ground_contact"] = int(pairs["ground_contact"])
        if row["cmd"] not in MODES or row["saturated"] not in (0, 1) or row["ground_contact"] not in (-1,0,1):
            raise ValueError("malformed native mode/saturation")
        if not all(__import__("math").isfinite(value) for key, value in row.items()
                   if isinstance(value, float)):
            raise ValueError("non-finite native observation")
        if samples and row["t"] <= samples[-1]["t"]:
            raise ValueError("native time not increasing")
        samples.append(row)
    return samples


def metrics(samples: list[dict]) -> dict:
    if not samples:
        return {"status": "NO_NATIVE_SAMPLES"}
    transitions = []
    for a, b in zip(samples, samples[1:]):
        if a["cmd"] != b["cmd"]:
            transitions.append({
                "from": a["cmd"], "to": b["cmd"],
                "t_s": b["t"], "collective_jump": round(b["u"] - a["u"], 9),
                "reference_jump_m": round(b["ref"] - a["ref"], 9),
                "vertical_velocity_jump_m_s": round(b["vz"] - a["vz"], 9),
                "target_jump_m": round(b["target"] - a["target"], 9),
            })
    return {
        "status": "RAW_NATIVE_SAMPLES_NOT_MISSION_PASS",
        "sample_count": len(samples),
        "duration_s": round(samples[-1]["t"] - samples[0]["t"], 6),
        "modes": list(dict.fromkeys(row["cmd"] for row in samples)),
        "max_altitude_m": max(row["z"] for row in samples),
        "final_pose_native": {key: samples[-1][key] for key in ("x","y","z","yaw")},
        "min_altitude_m": min(row["z"] for row in samples),
        "max_abs_vz_m_s": max(abs(row["vz"]) for row in samples),
        "max_collective": max(row["u"] for row in samples),
        "min_collective": min(row["u"] for row in samples),
        "max_abs_motor_rad_s": max(abs(row[k]) for row in samples
                                 for k in ("m1", "m2", "m3", "m4")),
        "saturated_samples": sum(row["saturated"] for row in samples),
        "observed_ground_contact_samples": sum(row["ground_contact"]==1 for row in samples),
        "observed_contact_loss_samples": sum(row["ground_contact"]==0 for row in samples),
        "max_sampling_gap_s": round(max(
            [b["t"] - a["t"] for a, b in zip(samples, samples[1:])] or [0]), 6),
        "phase_transitions": transitions,
    }


def build(home: Path, scope: str) -> dict:
    result = compile_production(home, "governor_pid_fixed")
    generated = FLIGHT / "build/runtime_u.c"
    before = sha256(generated)
    instrument_generated_controller(generated, scope)
    if before == sha256(generated):
        raise RuntimeError("sequence observer injection absent")
    env = dict(os.environ, WEBOTS_HOME=str(home))
    subprocess.run(["make", "-C", str(FLIGHT), "release"],
                   env=env, cwd=ROOT, timeout=180, check=True)
    if "GP_SEQUENCE_SAMPLE" not in generated.read_text():
        raise RuntimeError("native observer disappeared during build")
    result["sequence_source_sha256"] = sha256(generated)
    result["sequence_binary_sha256"] = sha256(FLIGHT / "grand_prix_route_flight")
    result["scope"] = scope
    return result


def one(home: Path, scope: str, scenario: str, root: Path, sha: str) -> dict:
    out = root / scope / scenario
    out.mkdir(parents=True, exist_ok=False)
    world = ROOT / "worlds" / ("ci_gp_sequence_" + uuid.uuid4().hex[:12] + ".wbt")
    scene = active_course_world(reference_course(COURSE_INDEX)).replace(
        "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/", "webots://")
    world.write_text(scene)
    (out / "world.wbt").write_text(scene)
    script = ROOT / "tools/grand_prix/native_control_sequence_stimulus.js"
    port = available_port()
    webots_log = out / "webots.log"
    node_log = out / "node.log"
    events_log = out / "events.jsonl"
    status = {"scope":scope, "scenario":scenario, "source_sha":sha,
              "world_sha256":sha256(out / "world.wbt"),
              "controller_source": "generated_only_route_flight",
              "oracle": "production_unmodified", "status":"INCOMPLETE"}
    webots = node = None
    try:
        with tempfile.TemporaryDirectory(prefix="gp-sequence-") as temp:
            env = os.environ.copy()
            env.update(WEBOTS_HOME=str(home), WBB_GP_TAKEOFF_TRACE="1",
                       WBB_GP_SEQUENCE_TRACE="1",
                       LIBGL_ALWAYS_SOFTWARE="true",
                       WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE="true")
            for name, sub in (("XDG_CONFIG_HOME","config"),("XDG_CACHE_HOME","cache"),
                              ("XDG_RUNTIME_DIR","runtime")):
                p = Path(temp) / sub
                p.mkdir(mode=0o700)
                env[name] = str(p)
            command = ["xvfb-run","-a",str(home / "webots"),"--batch","--mode=fast",
                       "--no-rendering","--minimize","--stdout","--stderr",
                       f"--port={port}",str(world)]
            with webots_log.open("w") as capture, node_log.open("w") as node_output:
                webots = subprocess.Popen(command, cwd=ROOT, env=env,
                    stdout=capture, stderr=subprocess.STDOUT, start_new_session=True)
                deadline = time.monotonic() + 70
                while time.monotonic() < deadline:
                    if webots.poll() is not None:
                        raise RuntimeError("native Webots exited before READY")
                    if "WEBEEBLOCKS_RUNTIME_V2 READY" in webots_log.read_text(errors="replace"):
                        break
                    time.sleep(.2)
                else:
                    raise RuntimeError("no native READY")
                node = subprocess.Popen(["node",str(script),str(port),scenario,str(events_log)],
                    cwd=ROOT,env=env,stdout=node_output,stderr=subprocess.STDOUT,
                    start_new_session=True)
                try:
                    status["stimulus_exit"] = node.wait(timeout=600)
                except subprocess.TimeoutExpired:
                    status["error"] = "bounded native stimulus timeout"
    except Exception as exc:
        status["error"] = type(exc).__name__ + ": " + str(exc)
    finally:
        stop_owned_process(node)
        stop_owned_process(webots)
        world.unlink(missing_ok=True)
    lines = webots_log.read_text(errors="replace").splitlines() if webots_log.exists() else []
    event_lines = events_log.read_text(errors="replace").splitlines() if events_log.exists() else []
    status["native_guard_events"] = [line[-500:] for line in lines if any(
        marker in line for marker in ("GP_ROUTE_EVALUATOR_CLOSED","GP_ROUTE_SAFETY_LAND",
            "GP_ROUTE_ALTITUDE_WITNESS","GP_U_DEADLINE",
            "FATAL unsafe","TIME_LIMIT","TRACE LAND_TOUCHDOWN"))][:30]
    events = []
    for line in event_lines:
        try:
            events.append(json.loads(line))
        except ValueError as exc:
            status["events_error"] = str(exc)
    status["events"] = events
    try:
        samples = decode_samples(lines)
        status["metrics"] = metrics(samples)
        if samples:
            with (out / "native-sequence.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(samples[0]))
                writer.writeheader()
                writer.writerows(samples)
        completed = (bool(samples) and status.get("stimulus_exit") == 0 and
            any(e.get("kind")=="scenario-finished" for e in events) and
            not status.get("error"))
        # A transport ACK is insufficient: retain the independent native
        # LAND witness and the exact expected refusal as separate obligations.
        native_text = "\\n".join(lines)
        if scenario in ("stop", "deadline"):
            completed = completed and all(marker in native_text for marker in (
                "GP_U_DEADLINE ", "GP_U_LAND_GROUND_READY ",
                "WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1"))
        if scenario == "primitives":
            required_steps = (
                "takeoff-0.5", "wait-0.1", "move-forward-0.04",
                "vertical-up-0.10", "turn-5", "vertical-down-0.10",
                "land-within-takeoff-exception", "strict-reset-after-land",
                "takeoff-after-reset-0.5", "stop-after-reset-takeoff")
            observed_steps = [e.get("value",{}).get("name")
                for e in events if e.get("kind")=="step-ok"
                and isinstance(e.get("value"),dict)]
            completed = completed and observed_steps == list(required_steps) and all(
                marker in native_text for marker in (
                    "GP_U_LAND_GROUND_READY ", "WEBEEBLOCKS_RUNTIME_V2 TRACE RESET ",
                    "GP_U_ADMISSION attempt=2 "))
        if scenario == "route_lh":
            reached = [e.get("value",{}).get("name") for e in events
                if e.get("kind")=="step-ok" and isinstance(e.get("value"),dict)]
            required = (
                "route-takeoff-0.8",
                "leg0-approach-h", "leg0-descend-for-h",
                "leg0-cross-open-h", "leg0-climb-after-h",
                "leg0-to-l-corner", "corner0-left-90",
                "leg1-forward-1.9", "leg1-forward-0.58",
                "corner1-right-90", "leg2-approach-h",
                "leg2-descend-for-h", "leg2-cross-open-h",
                "leg2-climb-after-h", "leg2-approach-landing",
                "terminal-left-offset-0.50", "terminal-low-landing-zone",
                "route-land", "oracle-complete", "route-outcome")
            land_line = next((i for i,line in enumerate(lines)
                if "WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1" in line), -1)
            revocations = [i for i,line in enumerate(lines)
                if "GP_ROUTE_EVALUATOR_CLOSED" in line]
            # A genuine STATE achieved response from the ordinary backend
            # is the authoritative student-visible result. The evaluator may
            # revoke observation after that positive result has been latched;
            # retain it explicitly, never invent a log line that does not exist.
            status["post_landing_observation_revocation"] = (
                bool(revocations) and land_line >= 0 and all(
                    i > land_line for i in revocations))
            completed = completed and tuple(reached)==required and any(
                e.get("kind")=="route-native-outcome" and
                isinstance(e.get("value"),dict) and
                e["value"].get("status")=="achieved" for e in events) and all(
                marker in native_text for marker in (
                    "GP_U_LAND_GROUND_READY ",
                    "WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1")) and (
                        not revocations or status["post_landing_observation_revocation"])
            status["course_lh_oracle_achieved"] = bool(completed)
        if scenario == "reset":
            completed = completed and any(e.get("kind")=="strict-airborne-reset-refused"
                and e.get("value")=="LANDING_UNCONFIRMED" for e in events)
        if scenario in ("ceiling", "ceiling_safe_ascent", "ceiling_takeoff"):
            ceiling = samples[0]["z"] + 1.15 if samples else 1.165
            # This exact world has the vehicle's physical origin near .015 m.
            # Read the native world witness and require an unviolated absolute
            # ceiling; never turn an oracle refusal into a positive flight.
            ceiling = 1.165
            completed = completed and bool(samples) and (
                max(row["z"] for row in samples) <= ceiling) and all(
                "reason=altitude" not in line for line in lines) and all(
                marker in native_text for marker in (
                    "GP_U_LAND_GROUND_READY ",
                    "WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1"))
            if scenario == "ceiling":
                completed = completed and any(
                    e.get("kind") == "preventive-ceiling-refusal" and
                    e.get("value") == "VERTICAL_LIMIT" for e in events)
                completed = completed and any(
                    "GP_CEILING_PREFLIGHT_V1 command=VERTICAL" in line for line in lines)
            elif scenario == "ceiling_safe_ascent":
                completed = completed and any(
                    e.get("kind") == "step-ok" and
                    isinstance(e.get("value"),dict) and
                    e["value"].get("name") == "vertical-safe-up-0.10"
                    for e in events)
            else:
                completed = completed and any(
                    e.get("kind") == "preventive-takeoff-refusal" and
                    e.get("value") == "INVALID_TAKEOFF" for e in events)
                completed = completed and any(
                    "GP_CEILING_PREFLIGHT_V1 command=TAKEOFF" in line for line in lines)
        status["native_ceiling_m"] = 1.165
        status["minimum_native_ceiling_clearance_m"] = (
            1.165 - max(row["z"] for row in samples)) if samples else None
        status["native_ceiling_violation_observed"] = (
            any(row["z"]>1.165 for row in samples) if samples else None)
        expected_negative = (scenario == "ceiling" and
            any("reason=altitude" in line for line in lines
                if "GP_ROUTE_EVALUATOR_CLOSED" in line) and
            any("GP_ROUTE_ALTITUDE_WITNESS " in line for line in lines) and
            any("GP_ROUTE_SAFETY_LAND " in line for line in lines) and
            any(e.get("kind")=="step-refused" and
                isinstance(e.get("value"),dict) and
                e["value"].get("name")=="vertical-near-ceiling-up-0.1" and
                e["value"].get("code")=="TIME_LIMIT" for e in events) and
            not any(e.get("kind")=="unexpected-ceiling-acceptance" for e in events))
        status["expected_native_altitude_refusal"] = expected_negative
        status["independent_native_land_confirmed"] = (
            "GP_U_LAND_GROUND_READY " in native_text and
            "WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1" in native_text)
        status["status"] = (
            "EXPECTED_NATIVE_ALTITUDE_REFUSAL" if expected_negative
            else "NATIVE_SAMPLES_COMPLETE_STIMULUS" if completed
            else "NATIVE_PARTIAL_OR_REFUSAL")
    except Exception as exc:
        status["status"] = "INVALID_OR_MISSING_NATIVE_TRACE"
        status["trace_error"] = str(exc)
    status["log_sha256"] = sha256(webots_log) if webots_log.exists() else None
    status["event_sha256"] = sha256(events_log) if events_log.exists() else None
    (out / "summary.json").write_text(json.dumps(status,indent=2,sort_keys=True)+"\n")
    print("GP_NATIVE_SEQUENCE " + json.dumps({
        "scope":scope, "scenario":scenario, "status":status["status"],
        "modes":status.get("metrics",{}).get("modes"),
        "guards":status["native_guard_events"],
        "samples":status.get("metrics",{}).get("sample_count",0)
    }), flush=True)
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-head",required=True)
    parser.add_argument("--webots-home",type=str)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--scenarios", nargs="+", choices=SCENARIOS, default=None,
                        help="run isolated bounded scenarios only")
    parser.add_argument("--scope", choices=SCOPES, default=None,
                        help="run one isolated scope; compare with archived same-world control run")
    args = parser.parse_args()
    sha = require_source(args.expected_head)
    home = webots_home(args.webots_home)
    prerequisites(home)
    output = args.output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    results = []
    builds = {}
    for scope in (SCOPES if args.scope is None else (args.scope,)):
        builds[scope] = build(home,scope)
        for scenario in (SCENARIOS if args.scenarios is None else args.scenarios):
            results.append(one(home,scope,scenario,output,sha))
    report = {
        "status":"RAW_NATIVE_SEQUENCE_COMPARISON_NOT_ACCEPTANCE",
        "exact_source_sha":sha,
        "world_equal":len({r["world_sha256"] for r in results})==1,
        "results":results,
        "builds":builds,
        "safety_relaxation":False,
        "full_mission_success_claim":False,
        "all_scenarios_completed":all(
             x["status"] in ("NATIVE_SAMPLES_COMPLETE_STIMULUS",
                              "EXPECTED_NATIVE_ALTITUDE_REFUSAL")
             for x in results),
    }
    (output / "index.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    if not report["world_equal"]:
        raise RuntimeError("world source differs across isolated candidates")
    print("GP_NATIVE_SEQUENCE_REPORT " + json.dumps({
        "source":sha,"world_equal":report["world_equal"],
        "all_completed":report["all_scenarios_completed"],"out":str(output)
    }), flush=True)
    # A native refusal is an observed outcome, not a CI Gate success.
    return 0 if report["all_scenarios_completed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

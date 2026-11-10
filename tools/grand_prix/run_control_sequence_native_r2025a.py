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

SCENARIOS = ("primitives", "ceiling", "stop", "deadline")
SAMPLE = re.compile(r"\bGP_SEQUENCE_SAMPLE\b")
PAIR = re.compile(r"([a-z][a-z0-9_]*)=([^\s]+)")
FIELDS = ("t", "dt", "z", "vz", "ref", "target", "u", "i",
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
        if row["cmd"] not in MODES or row["saturated"] not in (0, 1):
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
        "min_altitude_m": min(row["z"] for row in samples),
        "max_abs_vz_m_s": max(abs(row["vz"]) for row in samples),
        "max_collective": max(row["u"] for row in samples),
        "min_collective": min(row["u"] for row in samples),
        "max_abs_motor_rad_s": max(abs(row[k]) for row in samples
                                 for k in ("m1", "m2", "m3", "m4")),
        "saturated_samples": sum(row["saturated"] for row in samples),
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
        status["status"] = (
            "NATIVE_SAMPLES_COMPLETE_STIMULUS" if
            samples and status.get("stimulus_exit") == 0 and
            any(e.get("kind")=="scenario-finished" for e in events) and
            not status.get("error") else "NATIVE_PARTIAL_OR_REFUSAL")
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
    args = parser.parse_args()
    sha = require_source(args.expected_head)
    home = webots_home(args.webots_home)
    prerequisites(home)
    output = args.output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    results = []
    builds = {}
    for scope in SCOPES:
        builds[scope] = build(home,scope)
        for scenario in SCENARIOS:
            results.append(one(home,scope,scenario,output,sha))
    report = {
        "status":"RAW_NATIVE_SEQUENCE_COMPARISON_NOT_ACCEPTANCE",
        "exact_source_sha":sha,
        "world_equal":len({r["world_sha256"] for r in results})==1,
        "results":results,
        "builds":builds,
        "safety_relaxation":False,
        "full_mission_success_claim":False,
        "all_scenarios_completed":all(x["status"]=="NATIVE_SAMPLES_COMPLETE_STIMULUS"
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

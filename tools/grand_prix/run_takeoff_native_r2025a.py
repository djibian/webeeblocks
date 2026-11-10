#!/usr/bin/env python3
"""R2025a-only, three independent Grand Prix TAKEOFF measurements.

No safety/oracle/backend modification, no real-radio execution, no simulation
success assertion from a synthetic fixture. Requires the existing native
production pilot, production evaluator, normal WWI admission and fresh world per
height. Raw failing/partial measurements are preserved in --output.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.analyze_takeoff_trace import parse_lines, summarize, TraceError
from tools.grand_prix.isolated_native_takeoff_candidates import (
    VARIANTS, apply_generated_route_variant, expected_compensated_collective,
)
from tools.grand_prix.course_active_world_v2 import active_course_world
from tools.grand_prix.launch_linux import ensure_webots_assets, ensure_blockly_assets, webots_home
from tools.grand_prix.route_courses_v2 import reference_course

HEIGHTS = (0.5, 0.8, 1.0)
COURSE_INDEX = 5
MAX_WALL_SECONDS = 420
FLIGHT = ROOT / "controllers/grand_prix_route_flight"
TRACE_START = "GP_ROUTE_TAKEOFF_TRACE_BEGIN"
TRACE_SAMPLE = "GP_ROUTE_TAKEOFF_TRACE_SAMPLE"
REQUEST_START = "GP_TAKEOFF_NATIVE_STIMULUS "


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_source(expected: str) -> str:
    if not re.fullmatch("[0-9a-f]{40}", expected):
        raise RuntimeError("exact 40-character git commit required")
    actual = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    if actual != expected:
        raise RuntimeError(f"exact HEAD mismatch: expected={expected} actual={actual}")
    dirty = subprocess.check_output(["git", "-C", str(ROOT), "status", "--porcelain",
                                     "--untracked-files=no"], text=True).strip()
    if dirty:
        raise RuntimeError("tracked working tree is dirty: no trustworthy exact source")
    return actual


def prerequisites(home: Path) -> None:
    if (home / "resources/version.txt").read_text().strip() != "R2025a":
        raise RuntimeError("native Webots R2025a required")
    if not shutil.which("xvfb-run"):
        raise RuntimeError("xvfb-run required for isolated noninteractive Webots world")
    if not shutil.which("node"):
        raise RuntimeError("Node >=22 required")
    release = subprocess.check_output(["node", "--version"], text=True).strip()
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", release)
    if not match or int(match.group(1)) < 22:
        raise RuntimeError("Node >=22 required: " + release)
    ensure_webots_assets(home)
    ensure_blockly_assets()


def compile_production(home: Path, variant: str) -> dict:
    env = os.environ.copy()
    env["WEBOTS_HOME"] = str(home)
    subprocess.run([sys.executable, str(ROOT / "tools/grand_prix/prepare_route_runtime.py")],
                   cwd=ROOT, env=env, check=True, timeout=90)
    # Fresh build avoids trusting a stale executable when only a generated
    # diagnostic header has changed and make has no explicit header dep.
    subprocess.run(["make", "-C", str(FLIGHT), "clean"],
                   cwd=ROOT, env=env, check=True, timeout=90)
    if variant != "baseline":
        subprocess.run([sys.executable, str(ROOT / "tools/grand_prix/prepare_route_runtime.py")],
                       cwd=ROOT, env=env, check=True, timeout=90)
        apply_generated_route_variant(FLIGHT / "build/runtime_u.c", variant)
    subprocess.run(["make", "-C", str(FLIGHT), "release"],
                   cwd=ROOT, env=env, check=True, timeout=180)
    binary = FLIGHT / "grand_prix_route_flight"
    source = FLIGHT / "build/runtime_u.c"
    if not binary.is_file() or not source.is_file():
        raise RuntimeError("native production flight executable/source missing")
    text = source.read_text()
    for marker in ("gp_route_takeoff_trace_sample(now", "gp_route_takeoff_trace_begin",
                   "gp_u_deadline(now, gp_pose_confirmed)", "gp_u_reset_complete()",
                   "gp_route_takeoff_next(&gp_route_takeoff"):
        if text.count(marker) != 1:
            raise RuntimeError("native composition provenance unexpected: " + marker)
    return {"flight_binary_sha256": sha256(binary), "flight_c_sha256": sha256(source),
            "native_evaluator_sha256": sha256(ROOT / "controllers/grand_prix_route_evaluator/grand_prix_route_evaluator.py")}


def available_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def stop_owned_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def read_jsonlines(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    result = []
    for line in path.read_text().splitlines():
        result.append(json.loads(line))
    return result


def make_native_curves(samples: list[dict], directory: Path) -> None:
    fields = ("t", "dt", "z0", "z", "vz", "ref", "target", "error",
              "p", "i", "d", "u", "m1", "m2", "m3", "m4", "ground_contact", "phase")
    with (directory / "native-takeoff.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(samples)


def plot_native_case(samples: list[dict], directory: Path, height: float) -> str:
    """Render ONLY actual logged samples; missing plots never imply a PASS."""
    if not samples:
        return "NO_SAMPLES"
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return "MISSING_MATPLOTLIB_CSV_PRESERVED"
    t0 = samples[0]["t"]
    times = [row["t"] - t0 for row in samples]
    plots = [
        (("z", "ref", "target"), "Altitude / cible (m)", "native-z-vs-reference.png"),
        (("vz",), "Vitesse verticale mesurée (m/s)", "native-vz.png"),
        (("p", "i", "d", "u"), "Contributions PID / commande collective", "native-pid.png"),
        (("m1", "m2", "m3", "m4"), "Commandes rotor signées (rad/s)", "native-motors.png"),
        (("ground_contact",), "Contact inférieur (1=observé, 0=absent, -1=inconnu)",
         "native-contact.png"),
    ]
    for columns, label, filename in plots:
        fig, ax = plt.subplots(figsize=(8.5, 4.5))
        for field in columns:
            values = [row[field] for row in samples]
            if field == "ground_contact":
                ax.step(times, values, where="post", label=field)
            else:
                ax.plot(times, values, label=field)
        ax.set_title(f"Webots R2025a — trace brute TAKEOFF {height:.1f} m, non validée")
        ax.set_xlabel("Temps depuis premier échantillon (s)")
        ax.set_ylabel(label)
        ax.grid(True, alpha=.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(directory / filename, dpi=150)
        plt.close(fig)
    return "OBSERVED_SAMPLES_RENDERED_NOT_VALIDATED"


def run_case(home: Path, index: int, height: float, output: Path,
             evidence: dict, source_sha: str, *, variant: str = "baseline") -> dict:
    directory = output / f"{index:02d}-takeoff-{height:.1f}m"
    directory.mkdir(exist_ok=False)
    token = uuid.uuid4().hex[:12]
    world = ROOT / "worlds" / f"ci_gp_takeoff_{token}.wbt"
    source_world = active_course_world(reference_course(COURSE_INDEX)).replace(
        "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/", "webots://")
    # Preserve the complete production course, robot, solids, evaluator and safety.
    world.write_text(source_world)
    (directory / "world.wbt").write_text(source_world)
    world_hash = sha256(directory / "world.wbt")
    port = available_port()
    trace_path = directory / "webots.log"
    node_path = directory / "node.log"
    events_path = directory / "stimulus.jsonl"
    webots = node = None
    status = {"height_m": height, "variant": variant, "world_sha256": world_hash, "course": reference_course(COURSE_INDEX).identifier,
              "source_sha": source_sha, "webots_version": "R2025a",
              "native_8ms_world": True, "native_32ms_pid": True,
              "pilot_and_evaluator": "production_unmodified",
              "claim": "raw_native_measurement_not_pedagogical_or_physical_pass",
              "status": "INCOMPLETE"}
    try:
        with tempfile.TemporaryDirectory(prefix="gp-takeoff-qt-") as state:
            env = os.environ.copy()
            env.update(WEBOTS_HOME=str(home), WBB_GP_TAKEOFF_TRACE="1",
                       LIBGL_ALWAYS_SOFTWARE="true",
                       WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE="true")
            for variable, subfolder in (("XDG_CONFIG_HOME", "config"),
                                        ("XDG_CACHE_HOME", "cache"),
                                        ("XDG_RUNTIME_DIR", "runtime")):
                p = Path(state) / subfolder
                p.mkdir(mode=0o700)
                env[variable] = str(p)
            env["LP_NUM_THREADS"] = "1"
            cmd = ["xvfb-run", "-a", str(home / "webots"), "--batch",
                   "--mode=fast", "--no-rendering", "--minimize", "--stdout",
                   "--stderr", f"--port={port}", str(world)]
            status["launch_command"] = cmd
            with trace_path.open("w") as webots_output, node_path.open("w") as node_output:
                webots = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=webots_output,
                                          stderr=subprocess.STDOUT, start_new_session=True)
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    if webots.poll() is not None:
                        raise RuntimeError(f"native Webots exited before READY ({webots.returncode})")
                    if "WEBEEBLOCKS_RUNTIME_V2 READY" in trace_path.read_text(errors="replace"):
                        break
                    time.sleep(0.2)
                else:
                    raise RuntimeError("native production flight READY not observed")
                node = subprocess.Popen(
                    ["node", str(ROOT / "tools/grand_prix/native_takeoff_stimulus.js"),
                     str(port), str(height), str(events_path)],
                    cwd=ROOT, env=env, stdout=node_output, stderr=subprocess.STDOUT,
                    start_new_session=True)
                try:
                    status["stimulus_exit_code"] = node.wait(timeout=MAX_WALL_SECONDS)
                except subprocess.TimeoutExpired:
                    status["stimulus_exit_code"] = None
                    status["error"] = "bounded native stimulus wall timeout"
                if webots.poll() is not None:
                    status["error"] = f"Webots exited during native flight ({webots.returncode})"
    except Exception as exc:
        status["error"] = type(exc).__name__ + ": " + str(exc)
    finally:
        stop_owned_process(node)
        stop_owned_process(webots)
        world.unlink(missing_ok=True)

    # Preserve refusal events and censored traces; never convert missing data
    # into a fabricated successful liftoff or mission.
    events = read_jsonlines(events_path)
    status["stimulus_events"] = [e.get("kind") for e in events]
    log = trace_path.read_text(errors="replace") if trace_path.exists() else ""
    status["first_oracle_closed"] = [s for s in log.splitlines()
                                     if s.startswith("GP_ROUTE_EVALUATOR_CLOSED ")][:1]
    status["safety_land_events"] = [s for s in log.splitlines()
                                    if s.startswith("GP_ROUTE_SAFETY_LAND ")][:3]
    try:
        records = parse_lines(log.splitlines())
        if len(records) != 1:
            raise TraceError(f"exactly one diagnostic TAKEOFF required, observed {len(records)}")
        status["metrics"] = summarize(records[0])
        if variant != "baseline" and records[0]["samples"]:
            status["pid_corrected_reconstruction_residual"] = round(
                max(abs(row["u"] - expected_compensated_collective(row))
                    for row in records[0]["samples"] if row["phase"] == "takeoff"), 7)
        make_native_curves(records[0]["samples"], directory)
        status["plots"] = plot_native_case(records[0]["samples"], directory, height)
        status["status"] = "TRACE_WITH_ACK" if (
            status["metrics"]["ack_observed"] and
            status["metrics"]["target_relative_m"] is not None and
            abs(status["metrics"]["target_relative_m"] - height) < .000001 and
            status["metrics"]["first_observed_ground_contact_loss_elapsed_s"] is not None and
            status["metrics"]["first_vertical_stability_window_elapsed_s"] is not None and
            status["metrics"]["maximum_observed_altitude_m"] <=
                records[0]["begin"]["z0"] + 1.15 + .000001 and
            status["stimulus_events"].count("takeoff-ack") == 1 and
            status["stimulus_events"].count("observed-window") == 1 and
            "native-refusal-or-error" not in status["stimulus_events"] and
            status.get("error") is None and
            not status["first_oracle_closed"] and
            not status["safety_land_events"] and
            status.get("stimulus_exit_code") == 0 and
            not status["metrics"]["sampling_gaps_over_40ms_s"] and
            (status["metrics"]["max_pid_reconstruction_residual"] < .0001
             if variant == "baseline" else
             status.get("pid_corrected_reconstruction_residual", 1.0) < .0001)
        ) else "TRACE_PARTIAL_OR_SAFETY_REFUSAL"
    except (TraceError, ValueError) as exc:
        status["status"] = "MISSING_OR_INVALID_TRACE"
        status["trace_error"] = str(exc)
    status["webots_log_sha256"] = sha256(trace_path) if trace_path.exists() else None
    status["node_log_sha256"] = sha256(node_path) if node_path.exists() else None
    status["stimulus_sha256"] = sha256(events_path) if events_path.exists() else None
    (directory / "summary.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-head", required=True, help="exact experiment commit SHA")
    parser.add_argument("--webots-home", help="installed R2025a home")
    parser.add_argument("--output", required=True, type=Path, help="new, non-existing evidence directory")
    parser.add_argument("--variant", choices=VARIANTS, default="baseline",
                        help="draft-only route control candidate; never shipped")
    parser.add_argument("--preflight-only", action="store_true",
                        help="validate native dependencies; no simulation or flight")
    args = parser.parse_args(argv)
    source_sha = require_source(args.expected_head)
    home = webots_home(args.webots_home)
    prerequisites(home)
    if args.preflight_only:
        print("R2025a native dependencies present; no simulation executed")
        return 0
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    evidence = compile_production(home, args.variant)
    evidence.update(source_sha=source_sha, variant=args.variant, course=reference_course(COURSE_INDEX).identifier,
                    trace_environment="WBB_GP_TAKEOFF_TRACE=1",
                    qualification="native_source_and_logs_only")
    (output / "build.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    results = [run_case(home, index, height, output, evidence, source_sha, variant=args.variant)
               for index, height in enumerate(HEIGHTS, 1)]
    if len({item["world_sha256"] for item in results}) != 1:
        raise RuntimeError("three-height world bytes differ: no valid paired comparison")
    report = {"schema": 1, "scope": "native_webots_only_not_real_hardware",
              "source_sha": source_sha, "variant": args.variant, "course": reference_course(COURSE_INDEX).identifier,
              "heights_m": HEIGHTS, "results": results,
              "status": "THREE_NATIVE_TRACES" if all(
                  x["status"] == "TRACE_WITH_ACK" for x in results)
                  else "INCOMPLETE_OR_NATIVE_REFUSAL",
              "safety_relaxation": False}
    (output / "index.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("GP_TAKEOFF_NATIVE_CAPTURE " + json.dumps(
        {"status": report["status"], "evidence": str(output),
         "source_sha": source_sha, "heights_m": HEIGHTS}))
    return 0 if report["status"] == "THREE_NATIVE_TRACES" else 1


if __name__ == "__main__":
    raise SystemExit(main())

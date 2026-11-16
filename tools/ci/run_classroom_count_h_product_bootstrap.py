#!/usr/bin/env python3
"""A6 Draft-only: open the actual school WBT and attest native SCENE import.

This is a product-bootstrap smoke test, NOT a pupil mission/Save/Open proof.
It never edits the world, runs a Blockly solution, or authorizes hardware.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / "worlds/crazyflie_classroom_count_h_start.wbt"
PROJECT = ROOT / "worlds/.crazyflie_classroom_count_h_start.wbproj"
ARTIFACT = ROOT / "ci-artifacts/progression-count-h-product-bootstrap"
BROWSER_MARKER = "blockly_count_h.html"
NATIVE_READY = "WEBEEBLOCKS_A6_MOTOR_READY n=1"
RUNTIME_READY = "WEBEEBLOCKS_RUNTIME_V2 READY"
FATAL_MARKERS = ("WEBEEBLOCKS_RUNTIME_V2 FATAL", "WEBEEBLOCKS_A6_MOTOR_FATAL")


def run() -> int:
    source = WORLD.read_text(encoding="utf-8")
    project = PROJECT.read_text(encoding="utf-8")
    if project != "Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n":
        raise ValueError("A6 Webots project must select precisely the school Crazyflie Robot Window")
    if (source.count('window "blockly_count_h"') != 1
            or source.count('controller "crazyflie_classroom_v2"') != 1
            or any(f'DEF WEBEEBLOCKS_COUNT_{n}_SCENE' in source for n in (1, 2, 3))
            or 'DEF WEBEEBLOCKS_A6_MOTOR_OBSERVER' in source
            or 'translation -1.40 0 0.055' not in source):
        raise ValueError("A6 school launcher world identity/empty-scene precondition failed")
    # Fail before starting a 140-second Webots process if the Blockly bundle
    # required by the actual Robot Window is not built in the CI checkout.
    for relative in ("vendor/blockly_compressed.js",
                     "vendor/blocks_compressed.js", "vendor/msg/fr.js"):
        asset = ROOT / "plugins/robot_windows/blockly_v2" / relative
        if not asset.is_file() or asset.stat().st_size == 0:
            raise FileNotFoundError(f"A6 browser dependency missing before Webots: {asset}")
    ARTIFACT.mkdir(parents=True, exist_ok=True)
    log_path = ARTIFACT / "webots.log"
    browser_path = ARTIFACT / "browser-launch.log"
    if browser_path.exists():
        raise FileExistsError("stale browser evidence: isolated CI artifact directory required")
    env = dict(os.environ)
    env["WEBOTS_WEB_BROWSER"] = "/workspace/tools/ci/webots_runtime_v2_browser.sh"
    env["WEBEEBLOCKS_CI_ARTIFACT_DIR"] = str(ARTIFACT)
    env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"] = "true"
    process = None
    status = "not-started"
    try:
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                ["timeout", "-k", "5s", "140s", "xvfb-run", "-a", "webots",
                 "--stdout", "--stderr", "--batch", "--mode=realtime", str(WORLD)],
                cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True)
            deadline = time.monotonic() + 135
            while time.monotonic() < deadline:
                trace = log_path.read_text(encoding="utf-8", errors="replace")
                browser = (browser_path.read_text(encoding="utf-8", errors="replace")
                           if browser_path.exists() else "")
                if any(marker in trace for marker in FATAL_MARKERS):
                    status = "native-fatal"
                    break
                if (NATIVE_READY in trace and RUNTIME_READY in trace
                        and BROWSER_MARKER in browser):
                    status = "native-scene-imported"
                    break
                if process.poll() is not None:
                    status = "webots-exited-before-ready"
                    break
                time.sleep(0.25)
            else:
                status = "bootstrap-timeout"
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=8)
    trace = log_path.read_text(encoding="utf-8", errors="replace")
    browser = (browser_path.read_text(encoding="utf-8", errors="replace")
               if browser_path.exists() else "")
    evidence = {
        "status": status,
        "world_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "webots_project_sha256": hashlib.sha256(project.encode("utf-8")).hexdigest(),
        "runtime_ready": RUNTIME_READY in trace,
        "native_count_h_1_ready": NATIVE_READY in trace,
        "actual_browser_launched": BROWSER_MARKER in browser,
        "native_fatal": any(x in trace for x in FATAL_MARKERS),
        "no_pupil_flight": "WEBEEBLOCKS_A6_MOTOR_RESULT status=achieved" not in trace,
        "no_preloaded_h": all(f"DEF WEBEEBLOCKS_COUNT_{n}_SCENE" not in source for n in (1, 2, 3)),
        "limitations": "No UI button, variant change, Save/Open, RESET, Windows or pupil mission attested"
    }
    (ARTIFACT / "summary.json").write_text(
        json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    passed = (status == "native-scene-imported" and
              evidence["no_pupil_flight"] and evidence["no_preloaded_h"] and
              not evidence["native_fatal"])
    if passed:
        print("A6_PRODUCT_BOOTSTRAP_NATIVE_PASS scene=count-h-1-v1 WBT=unchanged "
              "browser=blockly_count_h native=observer", flush=True)
        return 0
    print("A6_PRODUCT_BOOTSTRAP_NATIVE_FAIL " + json.dumps(evidence, sort_keys=True),
          file=sys.stderr, flush=True)
    print(trace[-7000:], file=sys.stderr, flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(run())

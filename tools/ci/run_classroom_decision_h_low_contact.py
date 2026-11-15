#!/usr/bin/env python3
"""Native A4 low-altitude Solid contacts, not a pupil flight or route PASS.

Uses the existing real Crazyflie range probe as a CI-only unpowered physics
contact probe. Starting on the ordinary floor proves benign ground contact;
then teleports across official low-height obstacle boundaries (both scenes).
The independent C mission observer must report the same physical Solid-side
contact even when the contact point is at <=2.5 cm. Invalid non-blue
teleports deliberately cannot qualify a mission; only their contact provenance
is asserted, never a success/failure caused solely by the contact.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import time

import run_classroom_decision_h_range as range_witness

ROOT = range_witness.ROOT
ARTIFACTS = ROOT / "ci-artifacts/progression-decision-h-low-contact"
MARKER = "# WEBEEBLOCKS_A4_LOW_CONTACT_NATIVE_CI_ONLY"
PARTS = ("H_LEFT", "THRESHOLD", "CORRIDOR_LEFT")
PROBE_DONE = "WEBEEBLOCKS_DECISION_H_LOW_END"


def compose(letter: str) -> str:
    if letter not in ("a", "b"):
        raise ValueError("unknown A4 variant")
    source = range_witness.compose(letter)
    controller = 'controller "progression_decision_h_range_probe"'
    if (source.count(controller) != 1 or
            source.count('controller "progression_decision_h_v1"') != 1 or
            source.count(range_witness.MARKER) != 1 or
            source.count(" Solid {") != 6 or
            source.count("boundingObject Box") != 6 or
            MARKER in source):
        raise ValueError("untrusted real school geometry for low contact")
    replacement = controller + '\n  customData "WEBEEBLOCKS_A4_LOW_CONTACT_V1"'
    result = source.replace(controller, replacement, 1)
    if (result.count(replacement) != 1 or
            result.count(" Solid {") != 6 or
            result.count("boundingObject Box") != 6):
        raise ValueError("collision fixture mutated actual geometry")
    return result.rstrip() + "\n" + MARKER + "\n"


def run_one(letter: str) -> dict:
    source = compose(letter)
    world = ROOT / "worlds" / f"ci_classroom_decision_h_low_contact_{letter}.wbt"
    project = ROOT / "worlds" / f".ci_classroom_decision_h_low_contact_{letter}.wbproj"
    log_path = ARTIFACTS / letter / "webots.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if world.exists() or project.exists():
        raise FileExistsError("refusing overwrite of existing native fixture")
    for name in ("controllers/progression_decision_h_v1/progression_decision_h_v1",
                 "controllers/progression_decision_h_range_probe/"
                 "progression_decision_h_range_probe"):
        if not (ROOT / name).is_file() or (ROOT / name).stat().st_size == 0:
            raise FileNotFoundError("missing actual native observer/probe: " + name)

    process = None
    try:
        world.write_text(source, encoding="utf-8")
        project.write_text(range_witness.PROJECT_TEXT, encoding="utf-8")
        env = {**os.environ, "LIBGL_ALWAYS_SOFTWARE": "true",
               "WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE": "true"}
        with log_path.open("w", encoding="utf-8") as output:
            process = subprocess.Popen(
                ["timeout", "-k", "5s", "115s", "xvfb-run", "-a", "webots",
                 "--stdout", "--stderr", "--batch", "--mode=fast", str(world)],
                cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT,
                start_new_session=True)
            until = time.monotonic() + 100
            while time.monotonic() < until:
                output.flush()
                log = log_path.read_text(encoding="utf-8", errors="replace")
                if (log.count(PROBE_DONE) >= len(PARTS) or
                        "WEBEEBLOCKS_DECISION_H_RANGE_FATAL" in log or
                        "WEBEEBLOCKS_DECISION_H_FATAL" in log or
                        process.poll() is not None):
                    break
                time.sleep(.20)
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=8)
        if world.exists():
            if world.read_text(encoding="utf-8") != source:
                raise RuntimeError("refusing cleanup of altered physical world")
            world.unlink()
        if project.exists():
            if project.read_text(encoding="utf-8") != range_witness.PROJECT_TEXT:
                raise RuntimeError("refusing cleanup of altered native Webots project")
            project.unlink()

    log = log_path.read_text(encoding="utf-8", errors="replace")
    physical = re.findall(
        r"WEBEEBLOCKS_DECISION_H_LOW_PHYSICAL variant=([AB]) "
        r"type=([A-Z_]+) z=(-?[0-9.]+) node_id=(\d+) obstacle_id=(\d+)",
        log)
    observed = re.findall(
        r"WEBEEBLOCKS_DECISION_H_COLLIDER_CONTACT "
        r"type=([A-Z_]+) z=(-?[0-9.]+) node_id=(\d+)", log)
    ends = re.findall(
        r"WEBEEBLOCKS_DECISION_H_LOW_END variant=([AB]) "
        r"type=([A-Z_]+) low_contacts=(\d+) motors=OFF", log)
    first = re.findall(
        r"WEBEEBLOCKS_DECISION_H_FIRST_SAMPLE attempt=1 "
        r"time=[^\n]+ contact=([01-]+) completed=([01])", log)
    proven = []
    for part in PARTS:
        p = [(float(z), int(node), int(official))
             for variant, name, z, node, official in physical
             if variant == letter.upper() and name == part and
                math.isfinite(float(z)) and abs(float(z)) <= .025]
        n = [(float(z), int(node))
             for name, z, node in observed
             if name == part and math.isfinite(float(z)) and abs(float(z)) <= .025]
        stop = [(int(count)) for variant, name, count in ends
                if variant == letter.upper() and name == part]
        if not p or not n or len(stop) != 1 or stop[0] < 1 or not any(
                node == expected and node > 0 for _, node, expected in p):
            raise AssertionError(
                f"native low contact unproved variant={letter} part={part} "
                f"physical={p} observer={n} stop={stop}; log={log_path}")
        proven.append({"part": part, "probe_z_m": p[0][0],
                       "observer_z_m": n[0][0], "node_id": p[0][2],
                       "number_of_probe_low_contacts": stop[0]})
    if (first != [("0", "0")] or
            "WEBEEBLOCKS_DECISION_H_RANGE_FATAL" in log or
            "WEBEEBLOCKS_DECISION_H_FATAL" in log or
            "status=achieved" in log):
        raise AssertionError("native low-contact/floor control invalid " +
                             str(log_path) + " tail=" + log[-3500:])
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    print(f"A4_LOW_NATIVE_OBSTACLES_DETECTED variant={letter.upper()} "
          f"floor_only_accepted=true parts={','.join(PARTS)} "
          f"world_sha256={digest} motors=OFF", flush=True)
    return {"variant": letter.upper(), "contacts": proven,
            "floor_only_first_sample": True, "world_sha256": digest,
            "physical_pupil_flight": False}


def main() -> None:
    rows = [run_one(letter) for letter in ("a", "b")]
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "summary.json").write_text(
        json.dumps({"schema": "webeeblocks-a4-low-native-contact-v1",
                    "real_webots": "R2025a", "six_verified_obstacle_cases": 6,
                    "no_pupil_flight_or_mission_success_claim": True,
                    "variants": rows}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print("A4_LOW_NATIVE_CONTACT_ALL_DETECTED A/B H_LEFT, THRESHOLD, CORRIDOR_LEFT",
          flush=True)


if __name__ == "__main__":
    main()

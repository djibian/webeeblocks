#!/usr/bin/env python3
"""A7 Draft-only genuine R2025a colliders, rays and contact probe.

Two independent real Webots launches, original Crazyflie PROTO + Multi-ranger.
Test-only Supervisor teleports the craft and calibrates contact with gravity.
Never a flown pupil .wbb, PID feasibility test or native mission GO.
"""
from pathlib import Path
import hashlib
import json
import math
import os
import re
import signal
import subprocess
import time

import prepare_classroom_altitude_scene_ack as classroom

ROOT = classroom.ROOT
ARTIFACT = ROOT / "ci-artifacts/progression-mini-gp-geometry"
PROJECT_TEXT = "Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n"
MARKER = "# WEBEEBLOCKS_A7_NATIVE_GEOMETRY_CI_ONLY"
TOKEN = "WEBEEBLOCKS_A7_NATIVE_PASS"
FATAL = "WEBEEBLOCKS_A7_NATIVE_FATAL"
BASE_CONTROLLER = 'controller "crazyflie_classroom_v2"'
BASE_WINDOW = 'window "altitude_scene_ack_probe"'
PROBE_CONTROLLER = 'controller "progression_mini_gp_geometry_probe"'


def compose(letter, source=None, scene=None):
    if type(letter) is not str or letter not in ("L", "R"):
        raise ValueError("invalid Mini Grand Prix variant")
    base = classroom.compose(classroom.SOURCE.read_text(encoding="utf-8")
                             if source is None else source)
    if scene is None:
        scene = (ROOT / f"worlds/scenes/mini-grand-prix-{letter.lower()}-v1.wbo").read_text(
            encoding="utf-8")
    if (base.count(BASE_CONTROLLER) != 1 or base.count(BASE_WINDOW) != 1 or
            'WEBEEBLOCKS_MINI_GP_' in base or
            scene.count(f"DEF WEBEEBLOCKS_MINI_GP_{letter}_SCENE Group") != 1 or
            scene.count(" Solid {") != 9 or scene.count("boundingObject Box") != 9 or
            scene.count("Robot {") != 1 or
            scene.count('name "Mini Grand Prix native evaluator"') != 1 or
            scene.count('controller "progression_mini_grand_prix_v1"') != 1 or
            scene.count("supervisor TRUE") != 1 or
            scene.count("synchronization TRUE") != 1 or
            "TouchSensor" in scene or
            f"DEF WEBEEBLOCKS_MINI_GP_{'R' if letter == 'L' else 'L'}_SCENE" in scene):
        raise ValueError("unattested or ambiguous classroom/mini-GP source")
    out = (base.replace(BASE_CONTROLLER, PROBE_CONTROLLER, 1)
           .replace(BASE_WINDOW, 'window ""', 1))
    if (out.count(PROBE_CONTROLLER) != 1 or BASE_CONTROLLER in out or
            'controller "crazyflie_runtime_v2"' in out or
            'WEBEEBLOCKS_MINI_GP_' in out):
        raise ValueError("untrusted native controller substitution")
    return out.rstrip() + "\n" + MARKER + "\n" + scene.rstrip() + "\n"


def run_one(letter):
    source = compose(letter)
    world = ROOT / f"worlds/ci_mini_gp_geometry_{letter.lower()}.wbt"
    project = ROOT / f"worlds/.ci_mini_gp_geometry_{letter.lower()}.wbproj"
    log = ARTIFACT / letter / "webots.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    if world.exists() or project.exists():
        raise FileExistsError("refusing to overwrite native experiment")
    proc = None
    try:
        world.write_text(source, encoding="utf-8")
        project.write_text(PROJECT_TEXT, encoding="utf-8")
        print(f"A7_GEOMETRY_WORLD_SHA256 {letter} {hashlib.sha256(source.encode()).hexdigest()}",
              flush=True)
        env = dict(os.environ)
        env["LIBGL_ALWAYS_SOFTWARE"] = "true"
        env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"] = "true"
        with log.open("w", encoding="utf-8") as output:
            proc = subprocess.Popen(
                ["timeout", "-k", "5s", "125s", "xvfb-run", "-a", "webots",
                 "--stdout", "--stderr", "--batch", "--mode=fast", str(world)],
                cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT,
                start_new_session=True)
            deadline = time.monotonic() + 115
            while time.monotonic() < deadline:
                output.flush()
                t = log.read_text(encoding="utf-8", errors="replace")
                if TOKEN in t or FATAL in t or proc.poll() is not None:
                    break
                time.sleep(.25)
    finally:
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=7)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=7)
            # The xvfb-run wrapper may exit while native descendants survive.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if world.exists():
            if world.read_text(encoding="utf-8") != source or source.count(MARKER) != 1:
                raise RuntimeError("refusing to delete altered native scene")
            world.unlink()
        if project.exists():
            if project.read_text(encoding="utf-8") != PROJECT_TEXT:
                raise RuntimeError("refusing to delete altered Webots project")
            project.unlink()
    data = log.read_text(encoding="utf-8", errors="replace")
    m = re.findall(
        r"WEBEEBLOCKS_A7_NATIVE_PASS variant=([LR]) safe=(\d+) "
        r"bar_contact=(\d+) closed_contact=(\d+) "
        r"front_low_m=([0-9.]+) front_high_m=([0-9.]+) "
        r"closed_front_m=([0-9.]+) motors=OFF pupil_wbb=UNPROVEN", data)
    if (FATAL in data or len(m) != 1 or m[0][0] != letter or
            any("ERROR:" in line for line in data.splitlines())):
        raise AssertionError(f"native Webots A7 geometry unproven in {log}")
    row = m[0]
    safe, bar, panel = map(int, row[1:4])
    low, high, closed = map(float, row[4:7])
    if (safe != (130 if letter == "L" else 145) or bar < 1 or panel < 1 or
            not all(math.isfinite(v) for v in (low, high, closed)) or
            not 1.3 < low <= 2.001 or not .20 < high < 1.25 or
            low - high < .35 or not .20 < closed < .70):
        raise AssertionError("native A7 collision/range attestation incomplete")
    print(f"A7_NATIVE_GEOMETRY_CONFIRMED variant={letter} safe={safe} "
          f"bar_contact={bar} closed_contact={panel} "
          f"open_low_m={low:.6f} open_high_m={high:.6f} "
          f"closed_m={closed:.6f}", flush=True)
    return {"variant": letter, "safe_geometry_samples": safe,
            "open_bar_gravity_contacts": bar, "closed_panel_gravity_contacts": panel,
            "open_h_low_range_m": low, "open_h_high_range_m": high,
            "closed_h_front_range_m": closed}


def main():
    observations = [run_one(letter) for letter in "LR"]
    ARTIFACT.mkdir(parents=True, exist_ok=True)
    result = {"schema": "webeeblocks-a7-draft-native-geometry-v1",
              "webots": "R2025a", "physical_colliders_attested": True,
              "two_independent_worlds": True, "motorized_flight": False,
              "pupil_program_tested": False,
              "not_pedagogical_or_physical_flight_pass": True,
              "variants": observations}
    (ARTIFACT / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                                             encoding="utf-8")
    print("WEBEEBLOCKS_A7_NATIVE_GEOMETRY_BOTH_PASS variants=L,R "
          "physical=contacts_and_rays flight=NOT_TESTED pupil=UNPROVEN", flush=True)


if __name__ == "__main__":
    main()

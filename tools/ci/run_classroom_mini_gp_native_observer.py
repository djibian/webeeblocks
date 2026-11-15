#!/usr/bin/env python3
"""Draft-only real-Webots A7 observer boundary; negative start evidence.

Runs the true C supervisor inside each independently built physical L/R scene.
The separate geometry supervisor teleports the craft (MOTORS OFF) and a
test-only attempt token is preseeded into the ordinary Webots customData field.
This is NEVER evidence that pupil Blockly or physical flight has succeeded.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import signal
import subprocess
import time

import run_classroom_mini_gp_geometry as geometry

ROOT = geometry.ROOT
ARTIFACT = ROOT / "ci-artifacts/progression-mini-gp-native-observer"
PROJECT = "Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n"
MARKER = "# WEBEEBLOCKS_A7_NATIVE_OBSERVER_START_NEGATIVE_CI_ONLY"
CONTROLLER = 'controller "progression_mini_gp_geometry_probe"'
FIRST = "] } # start"
ROBOT = """    Robot {
      name "Mini Grand Prix native evaluator"
      controller "progression_mini_grand_prix_v1"
      supervisor TRUE
      synchronization TRUE
    }
  ] } # start"""
CRAFT = '  name "Crazyflie WebeeBlocks"\n'


def compose(letter):
    if letter not in ("L", "R"):
        raise ValueError("untrusted Mini GP variant")
    source = geometry.compose(letter)
    if (source.count(FIRST) != 1 or source.count(CONTROLLER) != 1 or
            source.count(CRAFT) != 1 or
            "Mini Grand Prix native evaluator" in source or
            "WB_MINI_NATIVE_READY" in source or
            "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1" in source):
        raise ValueError("already mutated native baseline")
    source = source.replace(FIRST, ROBOT, 1)
    source = source.replace(CRAFT,
        CRAFT + '  customData "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1"\n', 1)
    if (source.count('controller "progression_mini_grand_prix_v1"') != 1 or
            source.count(MARKER) != 0 or source.count(CONTROLLER) != 1):
        raise ValueError("missing independent observer or modified flight authority")
    return source.rstrip() + "\n" + MARKER + "\n"


def run_one(letter):
    source = compose(letter)
    suffix = letter.lower()
    world = ROOT / f"worlds/ci_mini_gp_native_observer_{suffix}.wbt"
    project = ROOT / f"worlds/.ci_mini_gp_native_observer_{suffix}.wbproj"
    log = ARTIFACT / letter / "webots.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    if world.exists() or project.exists():
        raise FileExistsError("refusing to overwrite another Webots experiment")
    proc = None
    try:
        world.write_text(source, encoding="utf-8")
        project.write_text(PROJECT, encoding="utf-8")
        print("A7_NATIVE_OBSERVER_WORLD_SHA256", letter,
              hashlib.sha256(source.encode()).hexdigest(), flush=True)
        env = dict(os.environ)
        env["LIBGL_ALWAYS_SOFTWARE"] = "true"
        env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"] = "true"
        with log.open("w", encoding="utf-8") as output:
            proc = subprocess.Popen(
                ["timeout", "-k", "5s", "130s", "xvfb-run", "-a", "webots",
                 "--stdout", "--stderr", "--batch", "--mode=fast", str(world)],
                cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT,
                start_new_session=True)
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                output.flush()
                data = log.read_text(encoding="utf-8", errors="replace")
                if "WB_MINI_NATIVE_FATAL" in data:
                    break
                if (f"WB_MINI_NATIVE_RESULT variant={letter} attempt=1" in data and
                        f"WEBEEBLOCKS_A7_NATIVE_PASS variant={letter} " in data):
                    break
                if proc.poll() is not None:
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
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if world.exists():
            if world.read_text(encoding="utf-8") != source or source.count(MARKER) != 1:
                raise RuntimeError("refusing removal of altered native observer world")
            world.unlink()
        if project.exists():
            if project.read_text(encoding="utf-8") != PROJECT:
                raise RuntimeError("refusing removal of altered Webots project")
            project.unlink()

    data = log.read_text(encoding="utf-8", errors="replace")
    ready = re.findall(
        rf"WB_MINI_NATIVE_READY variant={letter} "
        r"oracle=progression-mini-grand-prix-v1 origin_z=([0-9.]+) step=(\d+)",
        data)
    first = re.findall(
        rf"WB_MINI_NATIVE_FIRST variant={letter} attempt=1 "
        r"time=([0-9.]+) x=(-?[0-9.]+) y=(-?[0-9.]+) "
        r"z=(-?[0-9.]+) contact=(-?\d+)", data)
    finished = f"WB_MINI_NATIVE_RESULT variant={letter} attempt=1 status=not-achieved"
    probe = f"WEBEEBLOCKS_A7_NATIVE_PASS variant={letter} "
    if (len(ready) != 1 or len(first) != 1 or
            data.count(f"WB_MINI_NATIVE_ATTEMPT variant={letter} attempt=1") != 1 or
            data.count(finished) != 1 or probe not in data or
            "WB_MINI_NATIVE_FATAL" in data or
            "status=achieved" in data or
            any("ERROR:" in line for line in data.splitlines())):
        raise AssertionError(f"native A7 observer failure or spoof in {log}")
    origin, step = float(ready[0][0]), int(ready[0][1])
    t, x, y, z, contact = first[0]
    t, x, y, z, contact = float(t), float(x), float(y), float(z), int(contact)
    if (not 0 <= origin < .060 or step != 32 or t < 0 or
            not all(map(lambda v: abs(v) < 10, (x, y, z))) or
            (abs(x+1.4) <= .080 and abs(y) <= .080 and
             abs(z-.015) <= .040 and contact == 0)):
        raise AssertionError("adversarial first native observation was legitimate")
    print(f"A7_NATIVE_OBSERVER_REJECTED variant={letter} attempt=1 "
          f"x={x:.6f} y={y:.6f} z={z:.6f} contact={contact} "
          "motors=OFF pupil_wbb=UNPROVEN", flush=True)
    return {"variant": letter, "native_observer": True,
            "native_first_sample_xyz_m": [x, y, z],
            "observed_attempt": 1, "terminal_status": "not-achieved",
            "motorized_flight": False, "pupil_program_tested": False}


def main():
    rows = [run_one(letter) for letter in "LR"]
    ARTIFACT.mkdir(parents=True, exist_ok=True)
    summary = {"schema": "webeeblocks-a7-native-observer-negative-v1",
               "webots": "R2025a", "native_supervisor": True,
               "same_pupil_wbb": False, "motorized_flight": False,
               "pupil_program_tested": False, "not_release_evidence": True,
               "variants": rows}
    (ARTIFACT / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("A7_NATIVE_OBSERVER_NEGATIVE_BOTH_PASS variants=L,R "
          "physical=sampled-native pupil=UNPROVEN motor=OFF", flush=True)


if __name__ == "__main__":
    main()

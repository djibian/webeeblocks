#!/usr/bin/env python3
"""A7 Draft: native positive blue-ground start, NOT pupil or motor flight.

Two physical R2025a worlds L/R, same nine collision solids and genuine
Crazyflie PROTO. The CI-only craft controller performs ZERO displacement
and ZERO motor actions. The independent mission observer must accept the
initial position as a nonterminal WAIT. Floor contacts are physically
observed (rather than inferring 'grounded' from a magic altitude constant).
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

import run_classroom_mini_gp_native_observer as observer

ROOT = observer.ROOT
ARTIFACT = ROOT / "ci-artifacts/progression-mini-gp-ground-start"
MARKER = "# WEBEEBLOCKS_A7_NATIVE_GROUND_START_CI_ONLY"
INITIAL = "Crazyflie {\n"
ATTEMPT_OLD = 'customData "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1"'
ATTEMPT_NEW = 'customData "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2"'
PROJECT = observer.PROJECT


def compose(letter):
    if type(letter) is not str or letter not in ("L", "R"):
        raise ValueError("untrusted A7 variant")
    source = observer.compose(letter)
    if (source.count(INITIAL) != 1 or
            source.count(ATTEMPT_OLD) != 1 or
            source.count(observer.MARKER) != 1 or
            "translation -1.4 0 0.015" in source or
            MARKER in source or
            source.count('controller "progression_mini_gp_geometry_probe"') != 1 or
            source.count('controller "progression_mini_grand_prix_v1"') != 1):
        raise ValueError("untrusted starting world or controller pair")
    source = source.replace(INITIAL, INITIAL + "  translation -1.4 0 0.015\n", 1)
    source = source.replace(ATTEMPT_OLD, ATTEMPT_NEW, 1)
    source = source.replace(observer.MARKER, MARKER, 1)
    if (source.count(MARKER) != 1 or
            source.count(ATTEMPT_NEW) != 1 or ATTEMPT_OLD in source or
            'controller "crazyflie_classroom_v2"' in source or
            'controller "crazyflie_runtime_v2"' in source):
        raise ValueError("native ground witness cannot use shared flight runtime")
    return source


def run_one(letter):
    source = compose(letter)
    suffix = letter.lower()
    world = ROOT / f"worlds/ci_mini_gp_ground_{suffix}.wbt"
    project = ROOT / f"worlds/.ci_mini_gp_ground_{suffix}.wbproj"
    log = ARTIFACT / letter / "webots.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    if world.exists() or project.exists():
        raise FileExistsError("refuse overwrite of an existing Webots experiment")
    proc = None
    try:
        world.write_text(source, encoding="utf-8")
        project.write_text(PROJECT, encoding="utf-8")
        print("A7_GROUND_WORLD_SHA256", letter,
              hashlib.sha256(source.encode()).hexdigest(), flush=True)
        env = dict(os.environ)
        env["LIBGL_ALWAYS_SOFTWARE"] = "true"
        env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"] = "true"
        with log.open("w", encoding="utf-8") as output:
            proc = subprocess.Popen(
                ["timeout", "-k", "5s", "95s", "xvfb-run", "-a", "webots",
                 "--stdout", "--stderr", "--batch", "--mode=fast", str(world)],
                cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT,
                start_new_session=True)
            deadline = time.monotonic() + 85
            while time.monotonic() < deadline:
                output.flush()
                text = log.read_text(encoding="utf-8", errors="replace")
                if ("WB_MINI_NATIVE_FATAL" in text or
                        "WEBEEBLOCKS_A7_NATIVE_FATAL" in text or
                        "WB_MINI_NATIVE_RESULT " in text or
                        "A7_NATIVE_GROUND_VALID variant=" + letter in text and
                        "WB_MINI_NATIVE_FIRST variant=" + letter in text):
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
                raise RuntimeError("refuse cleanup of altered positive world")
            world.unlink()
        if project.exists():
            if project.read_text(encoding="utf-8") != PROJECT:
                raise RuntimeError("refuse cleanup of altered Webots project")
            project.unlink()

    text = log.read_text(encoding="utf-8", errors="replace")
    ready = re.findall(
        rf"WB_MINI_NATIVE_READY variant={letter} "
        r"oracle=progression-mini-grand-prix-v1 origin_z=([0-9.]+) step=(\d+)",
        text)
    first = re.findall(
        rf"WB_MINI_NATIVE_FIRST variant={letter} attempt=2 "
        r"time=([0-9.]+) x=(-?[0-9.]+) y=(-?[0-9.]+) "
        r"z=(-?[0-9.]+) contact=(-?\d+)", text)
    probe = re.findall(
        rf"A7_NATIVE_GROUND_VALID variant={letter} idle_steps=48 "
        r"start_z=([0-9.]+) end_z=([0-9.]+) "
        r"floor_contacts=(\d+) motors=OFF", text)
    if (len(ready) != 1 or len(first) != 1 or len(probe) != 1 or
            text.count(f"WB_MINI_NATIVE_ATTEMPT variant={letter} attempt=2") != 1 or
            "WB_MINI_NATIVE_RESULT " in text or
            "WB_MINI_NATIVE_FATAL" in text or
            "WEBEEBLOCKS_A7_NATIVE_FATAL" in text or
            any("ERROR:" in line for line in text.splitlines())):
        raise AssertionError(f"native positive ground witness not proven: {log}")
    origin, step = float(ready[0][0]), int(ready[0][1])
    t, x, y, z, contact = first[0]
    t, x, y, z, contact = float(t), float(x), float(y), float(z), int(contact)
    start_z, end_z, floor_hits = probe[0]
    start_z, end_z, floor_hits = float(start_z), float(end_z), int(floor_hits)
    values = (origin, t, x, y, z, start_z, end_z)
    if (not all(math.isfinite(v) for v in values) or
            step != 32 or t < 0 or
            not 0 <= origin < .055 or
            abs(x + 1.4) > .08 or abs(y) > .08 or
            abs(z - .015) > .04 or contact != 0 or
            abs(start_z - .015) > .04 or
            abs(end_z - .015) > .05 or
            floor_hits < 1):
        raise AssertionError(f"native grounded attempt not attested: {log}")
    print(f"A7_NATIVE_GROUND_ACCEPTED variant={letter} attempt=2 "
          f"x={x:.6f} y={y:.6f} z={z:.6f} floor_contacts={floor_hits} "
          "mission=WAIT motors=OFF pupil_wbb=UNPROVEN", flush=True)
    return {"variant": letter, "attempt": 2, "native_ground_start": True,
            "first_pose_xyz_m": [x, y, z],
            "floor_contacts": floor_hits, "mission": "WAIT",
            "motorized_flight": False, "pupil_program_tested": False}


def main():
    variants = [run_one(letter) for letter in "LR"]
    ARTIFACT.mkdir(parents=True, exist_ok=True)
    result = {"schema": "webeeblocks-a7-native-ground-positive-v1",
              "webots": "R2025a", "real_floor_contacts": True,
              "two_independent_worlds": True, "native_ground_start": True,
              "motorized_flight": False, "pupil_program_tested": False,
              "not_release_evidence": True, "variants": variants}
    (ARTIFACT / "summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("A7_NATIVE_GROUND_BOTH_PASS variants=L,R attempts=2,2 "
          "mission=WAIT motor=OFF pupil=UNPROVEN", flush=True)


if __name__ == "__main__":
    main()

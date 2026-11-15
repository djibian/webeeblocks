#!/usr/bin/env python3
"""Real R2025a A4 startup for both scenes, malformed collider and 64-ms physics.

No pupil program, flight or mocked sensor is run: native READY from the
independent Webots supervisor is the only positive evidence here.
"""
from pathlib import Path
import hashlib
import os
import signal
import subprocess
import time

import prepare_classroom_altitude_scene_ack as classroom

ROOT = classroom.ROOT
ARTIFACTS = ROOT / "ci-artifacts/progression-decision-h-native-start"
PROJECT_TEXT = "Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n"
MARKER = "# WEBEEBLOCKS_A4_NATIVE_START_CI_ONLY"


def compose(case):
    if case not in ("a", "b", "bad-a", "bad-step-a", "bad-step-b"):
        raise ValueError("unknown case")
    letter = "a" if case == "bad-a" else case.removeprefix("bad-step-")
    base = classroom.compose(classroom.SOURCE.read_text(encoding="utf-8"))
    scene = (ROOT / "worlds/scenes" / ("decision-h-" + letter + "-v1.wbo")).read_text(encoding="utf-8")
    if (base.count('controller "crazyflie_classroom_v2"') != 1 or
        base.count('window "altitude_scene_ack_probe"') != 1 or
        scene.count('controller "progression_decision_h_v1"') != 1 or
        scene.count("boundingObject Box") != 6 or
        scene.count("Robot {") != 1):
        raise ValueError("unsafe or ambiguous startup source")
    if case == "bad-a":
        before = "translation 0.750 0.300 0.50"
        if scene.count(before) != 1:
            raise ValueError("unexpected collider for negative proof")
        scene = scene.replace(before, "translation 0.750 0.300 0.55")
    if case.startswith("bad-step-"):
        # Change only WorldInfo.basicTimeStep, not any physical collider.
        if base.count("basicTimeStep 32") != 1 or "basicTimeStep 64" in base:
            raise ValueError("unexpected native physics step in canonical world")
        base = base.replace("basicTimeStep 32", "basicTimeStep 64", 1)
    base = base.replace('controller "crazyflie_classroom_v2"', 'controller "<none>"')
    base = base.replace('window "altitude_scene_ack_probe"', 'window ""')
    if ('controller "crazyflie_runtime_v2"' in base or
        'controller "crazyflie_classroom_v2"' in base or
        "DEF WEBEEBLOCKS_DECISION_" in base):
        raise ValueError("competing flight or stale imported scene")
    return base.rstrip() + "\n" + MARKER + "\n" + scene.rstrip() + "\n"


def run(case):
    letter = "a" if case == "bad-a" else case.removeprefix("bad-step-")
    world = ROOT / "worlds" / ("ci_classroom_decision_h_" + case + ".wbt")
    project = ROOT / "worlds" / (".ci_classroom_decision_h_" + case + ".wbproj")
    log_path = ARTIFACTS / case / "webots.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if world.exists() or project.exists():
        raise FileExistsError("refusing to overwrite a preexisting CI world")
    body = compose(case)
    print("A4_WORLD_SHA256 case=" + case + " " +
          hashlib.sha256(body.encode("utf-8")).hexdigest(), flush=True)
    proc = None
    ready = ("WEBEEBLOCKS_DECISION_H_READY scene=decision-h-" + letter +
             "-v1 oracle=progression-decision-h-v1")
    fatal = "WEBEEBLOCKS_DECISION_H_FATAL invalid scene/observer/colliders"
    try:
        world.write_text(body, encoding="utf-8")
        project.write_text(PROJECT_TEXT, encoding="utf-8")
        env = dict(os.environ)
        env["LIBGL_ALWAYS_SOFTWARE"] = "true"
        env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"] = "true"
        with log_path.open("w", encoding="utf-8") as log:
            proc = subprocess.Popen(
                ["timeout", "-k", "5s", "95s", "xvfb-run", "-a", "webots",
                 "--stdout", "--stderr", "--batch", "--mode=fast", str(world)],
                cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True)
            until = time.monotonic() + 85
            while time.monotonic() < until:
                log.flush()
                text = log_path.read_text(encoding="utf-8", errors="replace")
                if ready in text or fatal in text or proc.poll() is not None:
                    break
                time.sleep(0.25)
    finally:
        if proc is not None and proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=8)
        if world.exists():
            if world.read_text(encoding="utf-8") != body or body.count(MARKER) != 1:
                raise ValueError("refusing to delete modified CI world")
            world.unlink()
        if project.exists():
            if project.read_text(encoding="utf-8") != PROJECT_TEXT:
                raise ValueError("refusing to delete modified CI project")
            project.unlink()
    text = log_path.read_text(encoding="utf-8", errors="replace")
    negative = case == "bad-a" or case.startswith("bad-step-")
    ok = (text.count(fatal) == 1 and ready not in text) if negative else (
        text.count(ready) == 1 and "WEBEEBLOCKS_DECISION_H_FATAL" not in text)
    if (not ok or "WEBEEBLOCKS_DECISION_H_RESULT" in text or
            (negative and "WEBEEBLOCKS_DECISION_H_ATTEMPT" in text)):
        raise AssertionError("native A4 startup not proved: " + case +
                             " (see " + str(log_path) + ")")
    print("A4_NATIVE_START_OK case=" + case, flush=True)


if __name__ == "__main__":
    for item in ("a", "b", "bad-a", "bad-step-a", "bad-step-b"):
        run(item)
    print("A4_NATIVE_START_PASS cases=a,b,bad-a,bad-step-a,bad-step-b", flush=True)

#!/usr/bin/env python3
"""A7 Draft R2025a school selector proof L->R->L, real imported WBO.

Uses compiled school C++ adapter, genuine imported native observer/colliders.
No flight controller, motor command, Blockly AST or pupil .wbb is executed.
"""
from pathlib import Path
import hashlib
import json
import os
import signal
import subprocess
import time

import prepare_classroom_altitude_scene_ack as classroom

ROOT = classroom.ROOT
ARTIFACTS = ROOT / "ci-artifacts/progression-mini-gp-scene-selector"
WORLD = ROOT / "worlds/ci_classroom_mini_gp_scene_selector.wbt"
PROJECT = ROOT / "worlds/.ci_classroom_mini_gp_scene_selector.wbproj"
PROJECT_TEXT = "Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n"
MARKER = "# WEBEEBLOCKS_A7_NATIVE_SCENE_SELECTOR_CI_ONLY"


def compose():
    source = classroom.SOURCE.read_text(encoding="utf-8")
    base = classroom.compose(source)
    if (base.count('controller "crazyflie_classroom_v2"') != 1 or
            base.count('window "altitude_scene_ack_probe"') != 1 or
            "WEBEEBLOCKS_MINI_GP_L_SCENE" in base or
            "WEBEEBLOCKS_MINI_GP_R_SCENE" in base):
        raise ValueError("untrusted A7 managed classroom source")
    base = base.replace('controller "crazyflie_classroom_v2"',
                        'controller "<none>"', 1)
    base = base.replace('window "altitude_scene_ack_probe"',
                        'window ""', 1)
    probe = """
Robot {
  name "A7 native selector test"
  controller "progression_mini_gp_scene_probe"
  supervisor TRUE
  synchronization TRUE
}
"""
    out = base.rstrip() + "\n" + MARKER + "\n" + probe
    if (out.count('controller "progression_mini_gp_scene_probe"') != 1 or
            'controller "crazyflie_runtime_v2"' in out or
            'controller "crazyflie_classroom_v2"' in out or
            "DEF WEBEEBLOCKS_MINI_GP_" in out):
        raise ValueError("unknown controller or preloaded A7 scene")
    return out


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    log_path = ARTIFACTS / "webots.log"
    if WORLD.exists() or PROJECT.exists():
        raise FileExistsError("refusing overwrite of native A7 selector world")
    body = compose()
    print("A7_SELECTOR_WORLD_SHA256 " +
          hashlib.sha256(body.encode("utf-8")).hexdigest(), flush=True)
    process = None
    try:
        WORLD.write_text(body, encoding="utf-8")
        PROJECT.write_text(PROJECT_TEXT, encoding="utf-8")
        env = dict(os.environ)
        env["LIBGL_ALWAYS_SOFTWARE"] = "true"
        env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"] = "true"
        with log_path.open("w", encoding="utf-8") as output:
            process = subprocess.Popen(
                ["timeout", "-k", "5s", "110s", "xvfb-run", "-a", "webots",
                 "--stdout", "--stderr", "--batch", "--mode=fast", str(WORLD)],
                cwd=ROOT, stdout=output, stderr=subprocess.STDOUT,
                env=env, start_new_session=True)
            deadline = time.monotonic() + 100
            while time.monotonic() < deadline:
                output.flush()
                log = log_path.read_text(encoding="utf-8", errors="replace")
                if ("WEBEEBLOCKS_A7_SCENE_SELECTOR_NATIVE_PASS" in log or
                        "WEBEEBLOCKS_A7_SCENE_SELECTOR_FATAL" in log or
                        process.poll() is not None):
                    break
                time.sleep(.25)
    finally:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=7)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=7)
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if WORLD.exists():
            if WORLD.read_text(encoding="utf-8") != body or body.count(MARKER) != 1:
                raise RuntimeError("refusing cleanup of mutated selector world")
            WORLD.unlink()
        if PROJECT.exists():
            if PROJECT.read_text(encoding="utf-8") != PROJECT_TEXT:
                raise RuntimeError("refusing cleanup of mutated Webots project")
            PROJECT.unlink()
    data = log_path.read_text(encoding="utf-8", errors="replace")
    expected = [
        "WEBEEBLOCKS_A7_SCENE_SELECTOR_ACK variant=L generation=1",
        "WEBEEBLOCKS_A7_SCENE_SELECTOR_ACK variant=R generation=1",
        "WEBEEBLOCKS_A7_SCENE_SELECTOR_ACK variant=L generation=2",
        "WEBEEBLOCKS_A7_SCENE_SELECTOR_NATIVE_PASS"
    ]
    found = [data.find(e) for e in expected]
    ready_l = "WB_MINI_NATIVE_READY variant=L oracle=progression-mini-grand-prix-v1"
    ready_r = "WB_MINI_NATIVE_READY variant=R oracle=progression-mini-grand-prix-v1"
    if (not all(data.count(token) == 1 for token in expected) or
            not all(pos >= 0 for pos in found) or found != sorted(found) or
            data.count(ready_l) < 2 or data.count(ready_r) < 1 or
            "WEBEEBLOCKS_A7_SCENE_SELECTOR_FATAL" in data or
            "WB_MINI_NATIVE_FATAL" in data or
            "WB_MINI_NATIVE_RESULT " in data or
            any("ERROR:" in line for line in data.splitlines())):
        raise AssertionError("native Mini GP selector or observer startup unproven: " +
                             str(log_path))
    summary = {"schema": "webeeblocks-a7-native-selector-v1",
               "variants": ["L", "R", "L"],
               "real_school_selector": True, "native_observer_starts": [2, 1],
               "real_scene_import": True, "motorized_flight": False,
               "same_pupil_wbb": False, "pupil_program_tested": False}
    (ARTIFACTS / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("A7_SELECTOR_NATIVE_PASS L-R-L real_imports=true "
          "typed_observers=true motors=OFF pupil=UNPROVEN", flush=True)


if __name__ == "__main__":
    main()

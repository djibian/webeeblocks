#!/usr/bin/env python3
"""R2025a live school C++ selector A->B->A, zero student/motor code.

Starts from typed classroom without any scene and imports the real versioned
WBO assets through the actual school adapter, not a mock or preloaded world.
"""
import hashlib
import os
from pathlib import Path
import signal
import subprocess
import time

import prepare_classroom_altitude_scene_ack as classroom

ROOT = classroom.ROOT
ARTIFACTS = ROOT / "ci-artifacts/progression-decision-h-scene-selector"
WORLD = ROOT / "worlds/ci_classroom_decision_h_scene_selector.wbt"
PROJECT = ROOT / "worlds/.ci_classroom_decision_h_scene_selector.wbproj"
PROJECT_TEXT = "Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n"
MARKER = "# WEBEEBLOCKS_A4_NATIVE_SCENE_SELECTOR_CI_ONLY"


def compose():
    source = classroom.SOURCE.read_text(encoding="utf-8")
    base = classroom.compose(source)
    if (base.count('controller "crazyflie_classroom_v2"') != 1 or
        base.count('window "altitude_scene_ack_probe"') != 1 or
        "WEBEEBLOCKS_DECISION_A_SCENE" in base or
        "WEBEEBLOCKS_DECISION_B_SCENE" in base):
        raise ValueError("unexpected classroom source, no safe starting world")
    base = base.replace('controller "crazyflie_classroom_v2"',
                        'controller "<none>"')
    base = base.replace('window "altitude_scene_ack_probe"', 'window ""')
    probe = """
Robot {
  name "A4 native selector test"
  controller "progression_decision_h_scene_probe"
  supervisor TRUE
  synchronization TRUE
}
"""
    out = base.rstrip() + "\n" + MARKER + "\n" + probe
    if (out.count('controller "progression_decision_h_scene_probe"') != 1 or
        'controller "crazyflie_runtime_v2"' in out or
        'controller "crazyflie_classroom_v2"' in out):
        raise ValueError("test world could execute a competing flight controller")
    return out


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    log_path = ARTIFACTS / "webots.log"
    if WORLD.exists() or PROJECT.exists():
        raise FileExistsError("refusing to overwrite native selector witness files")
    body = compose()
    print("A4_SELECTOR_WORLD_SHA256 " +
          hashlib.sha256(body.encode("utf-8")).hexdigest(), flush=True)
    process = None
    try:
        WORLD.write_text(body, encoding="utf-8")
        PROJECT.write_text(PROJECT_TEXT, encoding="utf-8")
        env = dict(os.environ)
        env["LIBGL_ALWAYS_SOFTWARE"] = "true"
        env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"] = "true"
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                ["timeout", "-k", "5s", "95s", "xvfb-run", "-a", "webots",
                 "--stdout", "--stderr", "--batch", "--mode=fast", str(WORLD)],
                cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True)
            end = time.monotonic() + 85
            while time.monotonic() < end:
                log.flush()
                data = log_path.read_text(encoding="utf-8", errors="replace")
                if ("WEBEEBLOCKS_A4_SCENE_SELECTOR_NATIVE_PASS" in data or
                    "WEBEEBLOCKS_A4_SCENE_SELECTOR_FATAL" in data or
                    process.poll() is not None):
                    break
                time.sleep(.25)
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=8)
        if WORLD.exists():
            if WORLD.read_text(encoding="utf-8") != body or body.count(MARKER) != 1:
                raise ValueError("refusing to delete a modified test world")
            WORLD.unlink()
        if PROJECT.exists():
            if PROJECT.read_text(encoding="utf-8") != PROJECT_TEXT:
                raise ValueError("refusing to delete a modified test project")
            PROJECT.unlink()
    text = log_path.read_text(encoding="utf-8", errors="replace")
    expected = (
        "WEBEEBLOCKS_A4_SCENE_SELECTOR_ACK variant=a generation=1",
        "WEBEEBLOCKS_A4_SCENE_SELECTOR_ACK variant=b generation=1",
        "WEBEEBLOCKS_A4_SCENE_SELECTOR_ACK variant=a generation=2",
        "WEBEEBLOCKS_A4_SCENE_SELECTOR_NATIVE_PASS",
    )
    ready_a = "WEBEEBLOCKS_DECISION_H_READY scene=decision-h-a-v1"
    ready_b = "WEBEEBLOCKS_DECISION_H_READY scene=decision-h-b-v1"
    if (any(text.count(k) != 1 for k in expected) or
        text.count(ready_a) < 2 or text.count(ready_b) < 1 or
        "WEBEEBLOCKS_A4_SCENE_SELECTOR_FATAL" in text or
        "WEBEEBLOCKS_DECISION_H_FATAL" in text):
        raise AssertionError("not proven: native A/B/A selector or observer startups "
                             "(see " + str(log_path) + ")")
    print("A4_SELECTOR_NATIVE_PASS A-B-A; real A native READY twice and B once",
          flush=True)


if __name__ == "__main__":
    main()

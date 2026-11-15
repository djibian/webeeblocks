#!/usr/bin/env python3
"""Native R2025a front-distance observation at identical A/B decision poses.

Disposable Crazyflie controller reads the genuine PROTO range_front sensor.
No Blockly, motor actuation, student flight or mission PASS is inferred.
"""
import hashlib
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import run_classroom_decision_h_native_start as startup

ROOT = startup.ROOT
ARTIFACTS = ROOT / "ci-artifacts/progression-decision-h-range"
MARKER = "# WEBEEBLOCKS_A4_NATIVE_RANGE_CI_ONLY"
PROJECT_TEXT = startup.PROJECT_TEXT
CASES = ("a", "b")


def compose(letter):
    if letter not in CASES:
        raise ValueError("unknown variant")
    body = startup.compose(letter)
    old = 'controller "<none>"'
    if body.count(old) != 1 or body.count('controller "progression_decision_h_v1"') != 1:
        raise ValueError("invalid isolated native world, no unique test craft")
    body = body.replace(old, 'controller "progression_decision_h_range_probe"')
    if ('controller "crazyflie_classroom_v2"' in body or
        'controller "crazyflie_runtime_v2"' in body or
        body.count('controller "progression_decision_h_range_probe"') != 1):
        raise ValueError("flight or probe duplication in world")
    return body.rstrip() + "\n" + MARKER + "\n"


def run_one(letter):
    body = compose(letter)
    world = ROOT / "worlds" / ("ci_classroom_decision_h_range_" + letter + ".wbt")
    project = ROOT / "worlds" / (".ci_classroom_decision_h_range_" + letter + ".wbproj")
    log_path = ARTIFACTS / letter / "webots.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if world.exists() or project.exists():
        raise FileExistsError("refusing to overwrite an existing CI world")
    print("A4_RANGE_WORLD_SHA256 case=" + letter + " " +
          hashlib.sha256(body.encode("utf-8")).hexdigest(), flush=True)
    proc = None
    pattern = re.compile(r"WEBEEBLOCKS_DECISION_H_RANGE_PASS variant=([ab]) "
                         r"observed_m=([0-9]+(?:\.[0-9]+)?) "
                         r"pose_x=([0-9.]+) pose_y=([0-9.]+) pose_z=([0-9.]+)")
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
                if ("WEBEEBLOCKS_DECISION_H_RANGE_PASS" in text or
                    "WEBEEBLOCKS_DECISION_H_RANGE_FATAL" in text or
                    proc.poll() is not None):
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
                raise ValueError("refusing cleanup of modified Webots world")
            world.unlink()
        if project.exists():
            if project.read_text(encoding="utf-8") != PROJECT_TEXT:
                raise ValueError("refusing cleanup of modified Webots project")
            project.unlink()
    transcript = log_path.read_text(encoding="utf-8", errors="replace")
    found = pattern.findall(transcript)
    if (len(found) != 1 or found[0][0] != letter or
        "WEBEEBLOCKS_DECISION_H_RANGE_FATAL" in transcript or
        "WEBEEBLOCKS_DECISION_H_RESULT" in transcript):
        raise AssertionError("unproved real native front ray, inspect " + str(log_path))
    value = float(found[0][1])
    xyz = tuple(map(float, found[0][2:]))
    if (abs(xyz[0] - 0.20) > 0.035 or abs(xyz[1]) > 0.035 or
        abs(xyz[2] - 0.75) > 0.045):
        raise AssertionError("not the same decision-point pose")
    print("A4_RANGE_REAL_OK variant=" + letter + " meters=" + str(value), flush=True)
    return value, xyz


def main():
    a, apos = run_one("a")
    b, bpos = run_one("b")
    if not (0.35 <= a <= 0.75 and 0.90 <= b <= 1.35 and b - a > 0.40 and
            all(abs(x - y) <= 0.02 for x, y in zip(apos, bpos))):
        raise AssertionError("A/B native rays are not discriminable at the same pose")
    print("A4_RANGE_REAL_PASS cases=a,b same_pose=true separated_m=" + str(b - a), flush=True)


if __name__ == "__main__":
    main()

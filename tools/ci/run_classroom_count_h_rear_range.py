#!/usr/bin/env python3
"""Measure, rather than guess, rear-range leakage at the A6 landing position.

The same authentic Webots R2025a Crazyflie PROTO is placed at the same pose
in three disposable original-collider scenes, with a test-only sensor
controller. This is a NEGATIVE PEDAGOGICAL WITNESS, not a flight PASS.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import signal
import subprocess
import time
import prepare_classroom_altitude_scene_ack as classroom

ROOT=classroom.ROOT
ARTIFACTS=ROOT/"ci-artifacts/progression-count-h-rear-range"
MARKER="# WEBEEBLOCKS_A6_REAR_RANGE_NEGATIVE_CI_ONLY"
PROJECT_TEXT="Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n"
EXPECTED={1:(1.85,2.001),2:(1.20,1.70),3:(0.35,0.80)}
TOKEN="WEBEEBLOCKS_COUNT_H_BACK_OBSERVED"


def compose(n,source=None):
    if type(n) is not int or n not in EXPECTED:
        raise ValueError("unknown Activity 6 count scene")
    start=(classroom.SOURCE.read_text(encoding="utf-8")
           if source is None else source)
    base=classroom.compose(start)
    scene=(ROOT/f"worlds/scenes/count-h-{n}-v1.wbo").read_text(encoding="utf-8")
    if (base.count('controller "crazyflie_classroom_v2"')!=1 or
        base.count('window "altitude_scene_ack_probe"')!=1 or
        scene.count(f"DEF WEBEEBLOCKS_COUNT_{n}_SCENE Group")!=1 or
        scene.count(" Solid {")!=3*n+1 or
        scene.count("boundingObject Box")!=3*n+1 or
        "Robot {" in scene or
        any(f"DEF WEBEEBLOCKS_COUNT_{other}_SCENE Group" in scene
            for other in EXPECTED if other!=n)):
        raise ValueError("unexpected A6 native scene, collider or craft identity")
    base=base.replace('controller "crazyflie_classroom_v2"',
                      'controller "progression_count_h_range_probe"')
    base=base.replace('window "altitude_scene_ack_probe"','window ""')
    if (base.count('controller "progression_count_h_range_probe"')!=1 or
        'controller "crazyflie_runtime_v2"' in base or
        'controller "crazyflie_classroom_v2"' in base or
        "DEF WEBEEBLOCKS_COUNT_" in base):
        raise ValueError("untrusted shared runtime or stale scene")
    return base.rstrip()+"\n"+MARKER+"\n"+scene.rstrip()+"\n"


def run_one(n):
    body=compose(n)
    world=ROOT/f"worlds/ci_classroom_count_h_rear_{n}.wbt"
    project=ROOT/f"worlds/.ci_classroom_count_h_rear_{n}.wbproj"
    log=ARTIFACTS/f"n{n}"/"webots.log"
    log.parent.mkdir(parents=True,exist_ok=True)
    if world.exists() or project.exists():
        raise FileExistsError("refusing to overwrite existing Webots world")
    print(f"A6_BACK_RANGE_WORLD_SHA256 count={n} "+
          hashlib.sha256(body.encode("utf-8")).hexdigest(),flush=True)
    proc=None
    pattern=re.compile(
        r"WEBEEBLOCKS_COUNT_H_BACK_OBSERVED variant=(\d) "
        r"range_m=([0-9.]+) pose_x=([0-9.]+) "
        r"pose_y=([0-9.]+) pose_z=([0-9.]+)")
    try:
        world.write_text(body,encoding="utf-8")
        project.write_text(PROJECT_TEXT,encoding="utf-8")
        env=dict(os.environ)
        env["LIBGL_ALWAYS_SOFTWARE"]="true"
        env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"]="true"
        with log.open("w",encoding="utf-8") as output:
            proc=subprocess.Popen(
                ["timeout","-k","5s","95s","xvfb-run","-a","webots",
                 "--stdout","--stderr","--batch","--mode=fast",str(world)],
                cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT,
                start_new_session=True)
            until=time.monotonic()+85
            while time.monotonic()<until:
                output.flush()
                txt=log.read_text(encoding="utf-8",errors="replace")
                if (TOKEN in txt or "WEBEEBLOCKS_COUNT_H_BACK_FATAL" in txt or
                    proc.poll() is not None):
                    break
                time.sleep(0.25)
    finally:
        if proc is not None and proc.poll() is None:
            os.killpg(proc.pid,signal.SIGTERM)
            try:proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL)
                proc.wait(timeout=8)
        if world.exists():
            if world.read_text(encoding="utf-8")!=body or body.count(MARKER)!=1:
                raise ValueError("refusing cleanup of modified Webots world")
            world.unlink()
        if project.exists():
            if project.read_text(encoding="utf-8")!=PROJECT_TEXT:
                raise ValueError("refusing cleanup of altered Webots project")
            project.unlink()
    txt=log.read_text(encoding="utf-8",errors="replace")
    findings=pattern.findall(txt)
    if (len(findings)!=1 or findings[0][0]!=str(n) or
        "WEBEEBLOCKS_COUNT_H_BACK_FATAL" in txt or
        "WEBEEBLOCKS_COUNT_H_RESULT" in txt):
        raise AssertionError("native rear range not observed: "+str(log))
    reading=float(findings[0][1])
    xyz=tuple(map(float,findings[0][2:]))
    low,high=EXPECTED[n]
    if (not low<=reading<=high or
        abs(xyz[0]-1.48)>.035 or abs(xyz[1])>.035 or
        abs(xyz[2]-.75)>.045):
        raise AssertionError("native rear sensor pose/distance inconsistent: "+str(log))
    print(f"A6_BACK_RANGE_REAL_OBSERVED n={n} meters={reading:.9f}",flush=True)
    return reading,xyz


def main():
    observations={n:run_one(n) for n in EXPECTED}
    readings=[observations[n][0] for n in EXPECTED]
    poses=[observations[n][1] for n in EXPECTED]
    if (readings[0]-readings[1]<=.20 or
        readings[1]-readings[2]<=.20 or
        any(abs(left-right)>.02 for row in poses[1:]
            for left,right in zip(row,poses[0]))):
        raise AssertionError("back-range counting leak not independently distinguished")
    payload={
        "schema":"webeeblocks-a6-negative-rear-range-v1",
        "native_leak_observed":True,
        "not_a_pedagogical_or_flight_pass":True,
        "variants":[{"count":n,"range_m":observations[n][0],
                     "pose_xyz":list(observations[n][1])} for n in EXPECTED]
    }
    ARTIFACTS.mkdir(parents=True,exist_ok=True)
    (ARTIFACTS/"summary.json").write_text(
        json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("A6_BACK_RANGE_NATIVE_LEAK_CONFIRMED counts=1,2,3 same_pose=true",flush=True)


if __name__=="__main__":
    main()

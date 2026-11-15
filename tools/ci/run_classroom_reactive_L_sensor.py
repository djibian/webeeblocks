#!/usr/bin/env python3
"""A5 Draft-only genuine Webots R2025a range measurements.

Teleporting the original Crazyflie only proves two actual sensor rays at
attested locations; it is NOT a flown .wbb, a loop requirement or pupil PASS.
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

ROOT=classroom.ROOT
ARTIFACTS=ROOT/"ci-artifacts/progression-reactive-L-sensor"
TOKEN="WEBEEBLOCKS_A5_SENSOR_DONE"
FATAL="WEBEEBLOCKS_A5_SENSOR_FATAL"
MARKER="# WEBEEBLOCKS_A5_SENSOR_NATIVE_CI_ONLY"
PROJECT_TEXT="Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n"
BASE_CONTROLLER='controller "crazyflie_classroom_v2"'
TEST_CONTROLLER='controller "progression_reactive_L_sensor_probe"'
BASE_WINDOW='window "altitude_scene_ack_probe"'
LETTERS="ABC"


def compose(letter, source=None, scene=None):
    if letter not in LETTERS or not isinstance(letter,str) or len(letter)!=1:
        raise ValueError("unknown A5 variant")
    base=classroom.compose(classroom.SOURCE.read_text(encoding="utf-8")
                           if source is None else source)
    expected=f"DEF WEBEEBLOCKS_REACTIVE_L_{letter}_SCENE Group"
    if scene is None:
        scene=(ROOT/f"worlds/scenes/reactive-L-{letter.lower()}-v1.wbo").read_text(
            encoding="utf-8")
    if (base.count(BASE_CONTROLLER)!=1 or base.count(BASE_WINDOW)!=1 or
        scene.count(expected)!=1 or scene.count(" Solid {")!=3 or
        scene.count("boundingObject Box")!=3 or
        "Robot {" in scene or
        any(f"DEF WEBEEBLOCKS_REACTIVE_L_{other}_SCENE" in scene
            for other in LETTERS if other!=letter)):
        raise ValueError("unattested pupil source or A5 obstacle inventory")
    text=base.replace(BASE_CONTROLLER,TEST_CONTROLLER,1).replace(BASE_WINDOW,
                                                                   'window ""',1)
    if (text.count(TEST_CONTROLLER)!=1 or
        BASE_CONTROLLER in text or BASE_WINDOW in text or
        'controller "crazyflie_runtime_v2"' in text or
        'DEF WEBEEBLOCKS_REACTIVE_L_' in text):
        raise ValueError("test cannot uniquely substitute the original craft")
    return text.rstrip()+"\n"+MARKER+"\n"+scene.rstrip()+"\n"


def run_one(letter):
    body=compose(letter)
    suffix=letter.lower()
    world=ROOT/f"worlds/ci_reactive_L_sensor_{suffix}.wbt"
    project=ROOT/f"worlds/.ci_reactive_L_sensor_{suffix}.wbproj"
    log=ARTIFACTS/letter/"webots.log"
    log.parent.mkdir(parents=True,exist_ok=True)
    if world.exists() or project.exists():
        raise FileExistsError("refuse to overwrite existing Webots project")
    proc=None
    try:
        world.write_text(body,encoding="utf-8")
        project.write_text(PROJECT_TEXT,encoding="utf-8")
        print(f"A5_NATIVE_WORLD_SHA256 variant={letter} " +
              hashlib.sha256(body.encode("utf-8")).hexdigest(),flush=True)
        env=dict(os.environ)
        env["LIBGL_ALWAYS_SOFTWARE"]="true"
        env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"]="true"
        with log.open("w",encoding="utf-8") as output:
            proc=subprocess.Popen(
                ["timeout","-k","5s","85s","xvfb-run","-a","webots",
                 "--stdout","--stderr","--batch","--mode=fast",str(world)],
                cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT,
                start_new_session=True)
            until=time.monotonic()+78
            while time.monotonic()<until:
                output.flush()
                txt=log.read_text(encoding="utf-8",errors="replace")
                if TOKEN in txt or FATAL in txt or proc.poll() is not None:
                    break
                time.sleep(0.25)
    finally:
        if proc is not None:
            # A returned xvfb-run leader can leave Webots descendants alive.
            # Retire the whole test-only process group, never a shared process.
            try:
                os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                proc.wait(timeout=5)
            # The wrapper may have exited but native children may remain.
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        if world.exists():
            if world.read_text(encoding="utf-8")!=body:
                raise RuntimeError("refusing cleanup of modified native world")
            world.unlink()
        if project.exists():
            if project.read_text(encoding="utf-8")!=PROJECT_TEXT:
                raise RuntimeError("refusing cleanup of modified project file")
            project.unlink()
    txt=log.read_text(encoding="utf-8",errors="replace")
    expression=(r"WEBEEBLOCKS_A5_SENSOR_SAMPLE variant=([ABC]) "
                r"stage=(origin|junction) front_m=([0-9.]+) "
                r"left_m=([0-9.]+) x=(-?[0-9.]+) y=(-?[0-9.]+) "
                r"z=(-?[0-9.]+) time=([0-9.]+)")
    hits=re.findall(expression,txt)
    final=re.findall(
        r"WEBEEBLOCKS_A5_SENSOR_DONE variant=([ABC]) first_m=([0-9.]+) "
        r"second_m=([0-9.]+) test_only=true",txt)
    if FATAL in txt or len(hits)!=2 or len(final)!=1 or (
        [(v,stage) for v,stage,*_ in hits] !=
        [(letter,"origin"),(letter,"junction")]) or final[0][0]!=letter:
        raise AssertionError("native A5 sensor witness missing or refused: "+str(log))
    readings=[]
    for row in hits:
        front,left,x,y,z,t=map(float,row[2:])
        stage=row[1]
        expected_x=0.0 if stage=="origin" else (1.2 if letter=="B" else .8)
        if (not all(math.isfinite(n) for n in (front,left,x,y,z,t)) or
            abs(x-expected_x)>.04 or abs(y)>.04 or abs(z-.5)>.09 or
            min(front,left)<0 or max(front,left)>2.001):
            raise AssertionError("native A5 observation ungrounded: "+str(log))
        readings.append(front if stage=="origin" else left)
    if any(abs(float(final[0][j+1])-readings[j])>1e-6 for j in (0,1)):
        raise AssertionError("native final and staged observations diverge")
    print("A5_REAL_SENSOR_READINGS variant="+letter+
          f" front={readings[0]:.6f} left={readings[1]:.6f}",flush=True)
    return readings


def classify_with_two_fixed_observations(readings):
    """Deliberate diagnostic counter-strategy; NOT a pupil algorithm."""
    first,second=readings
    return "B" if first>1.16 else ("A" if second>.70 else "C")


def main():
    measurements={letter:run_one(letter) for letter in LETTERS}
    a,b,c=[measurements[k] for k in LETTERS]
    # Non-vacuous native readings, not just geometry or all-saturated 2m.
    if not (.60<a[0]<1.20 and .60<c[0]<1.20 and
            1.15<b[0]<1.85 and abs(a[0]-c[0])<.10 and
            b[0]-a[0]>.20 and b[0]-c[0]>.20 and
            .70<a[1]<1.75 and .08<b[1]<.60 and
            .08<c[1]<.60 and a[1]-b[1]>.25 and a[1]-c[1]>.25):
        raise AssertionError("native ray signatures not proven distinct: "+
                             repr(measurements))
    if any(classify_with_two_fixed_observations(pair)!=letter
           for letter,pair in measurements.items()):
        raise AssertionError("two-measure adversarial classifier did not work")
    ARTIFACTS.mkdir(parents=True,exist_ok=True)
    payload={
        "schema":"webeeblocks-a5-two-ray-native-counterexample-v1",
        "source":"real unmodified R2025a Crazyflie Multi-ranger",
        "method":"CI-only supervisor teleport at two positions, no motors",
        "variants":measurements,
        "two_fixed_measurements_distinguish_all_three":True,
        "does_not_prove_drone_flight_or_student_solution":True,
        "does_not_prove_loop_or_variable_necessary":True,
    }
    (ARTIFACTS/"summary.json").write_text(
        json.dumps(payload,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print("WEBEEBLOCKS_A5_NATIVE_TWO_RAY_COUNTEREXAMPLE "
          "A_B_C_distinguished=true flight=NOT_TESTED",flush=True)


if __name__=="__main__":
    main()

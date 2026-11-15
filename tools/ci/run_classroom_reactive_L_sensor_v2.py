#!/usr/bin/env python3
"""A5 v2 Draft-only sequential genuine Webots R2025a range measurements.

Teleporting the original Crazyflie only proves four actual sensor rays at
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
ARTIFACTS=ROOT/"ci-artifacts/progression-reactive-L-sensor-v2"
TOKEN="WEBEEBLOCKS_A5_V2_SENSOR_DONE"
FATAL="WEBEEBLOCKS_A5_V2_SENSOR_FATAL"
MARKER="# WEBEEBLOCKS_A5_V2_SENSOR_NATIVE_CI_ONLY"
PROJECT_TEXT="Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n"
BASE_CONTROLLER='controller "crazyflie_classroom_v2"'
TEST_CONTROLLER='controller "progression_reactive_L_sensor_probe_v2"'
BASE_WINDOW='window "altitude_scene_ack_probe"'
LETTERS="ABC"


def compose(letter, source=None, scene=None):
    if not isinstance(letter,str) or len(letter)!=1 or letter not in LETTERS:
        raise ValueError("unknown A5 variant")
    base=classroom.compose(classroom.SOURCE.read_text(encoding="utf-8")
                           if source is None else source)
    expected=f"DEF WEBEEBLOCKS_REACTIVE_L_V2_{letter}_SCENE Group"
    if scene is None:
        scene=(ROOT/f"worlds/scenes/reactive-L-{letter.lower()}-v2.wbo").read_text(
            encoding="utf-8")
    if (base.count(BASE_CONTROLLER)!=1 or base.count(BASE_WINDOW)!=1 or
        scene.count(expected)!=1 or scene.count(" Solid {")!=(7 if letter=="C" else 5) or
        scene.count("boundingObject Box")!=(7 if letter=="C" else 5) or
        "Robot {" in scene or
        any(f"DEF WEBEEBLOCKS_REACTIVE_L_V2_{other}_SCENE" in scene
            for other in LETTERS if other!=letter)):
        raise ValueError("unattested pupil source or A5 obstacle inventory")
    text=base.replace(BASE_CONTROLLER,TEST_CONTROLLER,1).replace(BASE_WINDOW,
                                                                   'window ""',1)
    if (text.count(TEST_CONTROLLER)!=1 or
        BASE_CONTROLLER in text or BASE_WINDOW in text or
        'controller "crazyflie_runtime_v2"' in text or
        'DEF WEBEEBLOCKS_REACTIVE_L_V2_' in text):
        raise ValueError("test cannot uniquely substitute the original craft")
    return text.rstrip()+"\n"+MARKER+"\n"+scene.rstrip()+"\n"


def run_one(letter):
    body=compose(letter)
    suffix=letter.lower()
    world=ROOT/f"worlds/ci_reactive_L_sensor_v2_{suffix}.wbt"
    project=ROOT/f"worlds/.ci_reactive_L_sensor_v2_{suffix}.wbproj"
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
    expression=(r"WEBEEBLOCKS_A5_V2_SENSOR_SAMPLE variant=([ABC]) "
                r"stage=(origin|junction|second|after-pivot) front_m=([0-9.]+) "
                r"left_m=([0-9.]+) x=(-?[0-9.]+) y=(-?[0-9.]+) "
                r"z=(-?[0-9.]+) yaw=(-?[0-9.]+) time=([0-9.]+)")
    hits=re.findall(expression,txt)
    final=re.findall(
        r"WEBEEBLOCKS_A5_V2_SENSOR_DONE variant=([ABC]) first_m=([0-9.]+) "
        r"second_m=([0-9.]+) third_m=([0-9.]+) fourth_m=([0-9.]+) test_only=true",txt)
    expected=[(letter,"origin"),(letter,"junction"),(letter,"second"),
              (letter,"after-pivot")]
    if (FATAL in txt or len(hits)!=4 or len(final)!=1 or
        [(v,stage) for v,stage,*_ in hits] != expected or
        final[0][0]!=letter):
        raise AssertionError("missing real v2 observation or fatal: "+str(log))
    readings=[]
    previous_t=-1.
    for row in hits:
        front,left,x,y,z,yaw,t=map(float,row[2:])
        stage=row[1]
        ex=0.0 if stage=="origin" else .8
        ey=1.0 if stage in ("second","after-pivot") else 0.
        eyaw=math.pi if stage=="after-pivot" else (math.pi/2 if stage=="second" else 0.)
        if (not all(math.isfinite(n) for n in (front,left,x,y,z,yaw,t)) or
            t<=previous_t or abs(x-ex)>.04 or abs(y-ey)>.04 or
            abs(z-.5)>.09 or abs(yaw-eyaw)>.10 or
            min(front,left)<0 or max(front,left)>2.001):
            raise AssertionError("untrusted native V2 pose/range: "+str(log))
        previous_t=t
        readings.append(front if stage=="origin" else left)
    if any(abs(float(final[0][j+1])-readings[j])>1e-6 for j in range(4)):
        raise AssertionError("V2 terminal and staged observations disagree")
    print("A5_V2_REAL_SENSOR_READINGS variant="+letter+
          f" first={readings[0]:.6f} second={readings[1]:.6f} "
          f"third={readings[2]:.6f} after_pivot={readings[3]:.6f}",flush=True)
    return readings

def classify_with_two_fixed_observations(readings):
    """Deliberate diagnostic counter-strategy; NOT a pupil algorithm."""
    first,second=readings
    return "B" if first>1.16 else ("A" if second>.70 else "C")


def main():
    values={v:run_one(v) for v in LETTERS}
    a,b,c=[values[v] for v in LETTERS]
    for stage in (0,1):
        readings=[values[v][stage] for v in LETTERS]
        target=.98 if stage==0 else 1.21
        if not all(abs(x-target)<.09 for x in readings) or (
            max(readings)-min(readings)>.05):
            raise AssertionError(
                f"native v2 indistinguishable prefix failed stage={stage} {readings}")
    # Later native measurement must be informative and genuinely unsaturated.
    expected={"A":.28,"B":1.78,"C":1.44}
    for letter,reading in values.items():
        if abs(reading[2]-expected[letter])>.12:
            raise AssertionError("third real ray does not distinguish later L: "+
                                 repr(values))
    if len({round(row[2],1) for row in values.values()})!=3:
        raise AssertionError("third real range not discriminative: "+repr(values))
    # After the COMMON 90-degree pivot, the native left sensor looks south.
    # It should no longer carry the three distinct westward readings observed
    # before the turn; the previously stored value is therefore useful in
    # the demonstration without imposing a variable-block requirement.
    post=[values[v][3] for v in LETTERS]
    if not all(math.isfinite(x) and 0.05<x<2.001 for x in post) or (
        max(post)-min(post)>.08):
        raise AssertionError("native after-pivot left ray still distinguishes "
                             "A/B/C or was unavailable: "+repr(values))
    late_guesses={v:("A" if row[3]<.6 else ("B" if row[3]>1.6 else "C"))
                  for v,row in values.items()}
    if all(late_guesses[v]==v for v in LETTERS):
        raise AssertionError("post-pivot sensor substitution unexpectedly "
                             "resolves every variant: "+repr(late_guesses))
    # The formerly successful two-reading V1 shortcut is experimentally
    # refuted for V2 without requiring a particular Blockly/AST shape.
    old_guesses={letter:classify_with_two_fixed_observations(row[:2])
                 for letter,row in values.items()}
    if len(set(old_guesses.values()))!=1 or all(
        old_guesses[letter]==letter for letter in LETTERS):
        raise AssertionError("V1 fixed-two-ray strategy not refuted: "+
                             repr(old_guesses))
    ARTIFACTS.mkdir(parents=True,exist_ok=True)
    payload={
        "schema":"webeeblocks-a5-v2-memory-pivot-native-v1",
        "method":"original R2025a Crazyflie, native rays at 4 attested poses including after-pivot",
        "v2_all_first_two_native_readings_indistinguishable":True,
        "later_third_native_observation_distinguishes_variants":True,
        "post_pivot_left_readings_no_longer_distinguish_variants":True,
        "post_pivot_without_memory_predictions":late_guesses,
        "v1_two_measure_classifier_predictions":old_guesses,
        "v1_two_measure_classifier_no_longer_succeeds":True,
        "does_not_prove_drone_flight_or_student_solution":True,
        "does_not_prove_loop_or_variable_necessary":True,
        "does_not_prove_historical_reobservation_impossible":True,
        "variants":values
    }
    (ARTIFACTS/"summary.json").write_text(
        json.dumps(payload,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print("WEBEEBLOCKS_A5_V2_PREFIX_NATIVE_CONFIRMED "
          "two_original_rays_same=true later_third_ray_differs=true "
          "post_pivot_left_nondiscriminating=true flight=NOT_TESTED",flush=True)


if __name__=="__main__":
    main()

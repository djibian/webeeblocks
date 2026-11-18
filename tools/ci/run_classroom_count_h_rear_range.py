#!/usr/bin/env python3
"""Physically falsify the old A6 rear-range leak after terminal masking.

The same authentic Webots R2025a Crazyflie PROTO is placed at the same pose
at all three pads in each of three worlds, with a test-only controller.
The test checks physical ray masking, NOT pupil coding or flight success.
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
ARTIFACTS=ROOT/"ci-artifacts/progression-count-h-rear-range"
MARKER="# WEBEEBLOCKS_A6_REAR_RANGE_NEGATIVE_CI_ONLY"
PROJECT_TEXT="Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n"
EXPECTED={1:(0.12,0.31),2:(0.12,0.31),3:(0.12,0.31)}
PADS=(0.0,0.55,-0.55)
TERMINAL_STAGES={"approach":0.415,"landed":0.015}
TERMINAL_CHANNELS=("front","back","left","right","up")
TERMINAL_HEADINGS=(90,180,270)
TOKEN="WEBEEBLOCKS_COUNT_H_SWEEP_PASS"


def validate_terminal_indistinguishability(terminal):
    """Refuse any single genuine terminal ray that distinguishes 1/2/3 H.

    Called ONLY with native observations at matched 3D poses; mock arrays
    are allowed in pure-Python adversarial tests but never give native PASS.
    """
    if set(terminal)!=set(EXPECTED):
        raise AssertionError("missing A6 count variant for terminal senses")
    for pad in range(len(PADS)):
        for stage in TERMINAL_STAGES:
            key=(pad,stage)
            measurements=[]
            for n in EXPECTED:
                if key not in terminal[n]:
                    raise AssertionError(f"missing native terminal sense {n}:{key}")
                values=terminal[n][key]
                if (type(values) not in (tuple,list) or
                    len(values)!=len(TERMINAL_CHANNELS) or
                    any(type(v) not in (int,float) or not 0<=v<=2.001 or
                        not math.isfinite(v) for v in values)):
                    raise AssertionError(f"invalid native terminal sense {n}:{key}")
                measurements.append(values)
            for channel, label in enumerate(TERMINAL_CHANNELS):
                observed=[values[channel] for values in measurements]
                if max(observed)-min(observed)>.025:
                    raise AssertionError(
                        f"A6 terminal {label} leaks H count at pad={pad}, "
                        f"stage={stage}: {observed}")
    return True


def validate_heading_indistinguishability(headings):
    """Falsify memory need against terminal 90/180/270-degree sensor views.

    Strictly tests matched TEST-ONLY poses, never proves every reachable
    no-memory control strategy fails. Pure-Python mocks are not native evidence.
    """
    if set(headings)!=set(EXPECTED):
        raise AssertionError("missing A6 count variant for cardinal senses")
    for pad in range(len(PADS)):
        for stage in TERMINAL_STAGES:
            for yaw in TERMINAL_HEADINGS:
                key=(pad,stage,yaw)
                measurements=[]
                for n in EXPECTED:
                    if key not in headings[n]:
                        raise AssertionError(f"missing native cardinal sense {n}:{key}")
                    values=headings[n][key]
                    if (type(values) not in (tuple,list) or
                        len(values)!=len(TERMINAL_CHANNELS) or
                        any(type(v) not in (int,float) or not 0<=v<=2.001 or
                            not math.isfinite(v) for v in values)):
                        raise AssertionError(f"invalid native cardinal sense {n}:{key}")
                    measurements.append(values)
                for channel,label in enumerate(TERMINAL_CHANNELS):
                    observed=[values[channel] for values in measurements]
                    if max(observed)-min(observed)>.025:
                        raise AssertionError(
                            f"A6 cardinal {label} leaks H count at pad={pad}, "
                            f"stage={stage}, yaw={yaw}: {observed}")
    return True


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
        scene.count(f"DEF ACTIVITY6_{n}_FINISH_SCREEN Solid")!=1 or
        scene.count(" Solid {")!=3*n+2 or
        scene.count("boundingObject Box")!=3*n+2 or
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
        r"WEBEEBLOCKS_COUNT_H_BACK_MASKED variant=(\d) pad=(\d) "
        r"range_m=([0-9.]+) pose_x=([0-9.]+) "
        r"pose_y=(-?[0-9.]+) pose_z=([0-9.]+)")
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
    terminal_rows=re.findall(
        r"WEBEEBLOCKS_COUNT_H_TERMINAL_RANGES variant=(\d) pad=(\d) "
        r"phase=(approach|landed) front_m=([0-9.]+) back_m=([0-9.]+) "
        r"left_m=([0-9.]+) right_m=([0-9.]+) up_m=([0-9.]+) "
        r"pose_x=([0-9.]+) pose_y=(-?[0-9.]+) pose_z=([0-9.]+)",txt)
    if len(terminal_rows)!=len(PADS)*len(TERMINAL_STAGES):
        raise AssertionError("native terminal full Multi-ranger samples missing: "+str(log))
    terminal={}
    for index,row in enumerate(terminal_rows):
        ntext,ptext,stage,*numeric=row
        pad=index//len(TERMINAL_STAGES)
        expected_phase=list(TERMINAL_STAGES)[index%len(TERMINAL_STAGES)]
        readings=tuple(float(x) for x in numeric[:5])
        xyz=tuple(float(x) for x in numeric[5:])
        if (ntext!=str(n) or int(ptext)!=pad or stage!=expected_phase or
            any(not math.isfinite(v) or not 0<=v<=2.001 for v in readings) or
            any(not math.isfinite(v) for v in xyz) or
            abs(xyz[0]-1.48)>.035 or abs(xyz[1]-PADS[pad])>.035 or
            abs(xyz[2]-TERMINAL_STAGES[stage])>.045):
            raise AssertionError("mismatched actual terminal Multi-ranger pose or channel: "+str(log))
        terminal[(pad,stage)]=readings
    heading_rows=re.findall(
        r"WEBEEBLOCKS_COUNT_H_HEADING_RANGES variant=(\d) pad=(\d) "
        r"phase=(approach|landed) yaw_deg=(90|180|270) "
        r"front_m=([0-9.]+) back_m=([0-9.]+) "
        r"left_m=([0-9.]+) right_m=([0-9.]+) up_m=([0-9.]+) "
        r"pose_x=([0-9.]+) pose_y=(-?[0-9.]+) pose_z=([0-9.]+)",txt)
    if len(heading_rows)!=len(PADS)*len(TERMINAL_STAGES)*len(TERMINAL_HEADINGS):
        raise AssertionError("cardinal native Multi-ranger samples missing: "+str(log))
    headings={}
    for index,row in enumerate(heading_rows):
        ntext,ptext,stage,yaw_text,*numeric=row
        expected_pad=index//(len(TERMINAL_STAGES)*len(TERMINAL_HEADINGS))
        expected_phase=list(TERMINAL_STAGES)[
            (index//len(TERMINAL_HEADINGS))%len(TERMINAL_STAGES)]
        expected_yaw=TERMINAL_HEADINGS[index%len(TERMINAL_HEADINGS)]
        readings=tuple(float(x) for x in numeric[:5])
        xyz=tuple(float(x) for x in numeric[5:])
        if (ntext!=str(n) or int(ptext)!=expected_pad or
            stage!=expected_phase or int(yaw_text)!=expected_yaw or
            any(not math.isfinite(v) or not 0<=v<=2.001 for v in readings) or
            any(not math.isfinite(v) for v in xyz) or
            abs(xyz[0]-1.48)>.035 or abs(xyz[1]-PADS[expected_pad])>.035 or
            abs(xyz[2]-TERMINAL_STAGES[stage])>.045):
            raise AssertionError("native cardinal Multi-ranger pose/heading mismatch: "+str(log))
        headings[(expected_pad,stage,expected_yaw)]=readings
    upper_rows=re.findall(
        r"WEBEEBLOCKS_COUNT_H_UP_SAMPLE variant=(\d) gate=(\d) phase=(\d) "
        r"range_m=([0-9.]+) pose_x=(-?[0-9.]+) "
        r"pose_y=(-?[0-9.]+) pose_z=([0-9.]+)",txt)
    if len(upper_rows)!=n*3:
        raise AssertionError("missing one or more native upward sensor samples: "+str(log))
    upper_samples=[]
    for gate in range(n):
        phases=[]
        for phase in range(3):
            variant_index,gate_index,phase_index,raw_range,raw_x,raw_y,raw_z=(
                upper_rows[3*gate+phase])
            range_m=float(raw_range)
            xyz=(float(raw_x),float(raw_y),float(raw_z))
            expected_x=-.850+.850*gate+(-.240,0,.240)[phase]
            if (variant_index!=str(n) or int(gate_index)!=gate or
                int(phase_index)!=phase or not 0<=range_m<=2.001 or
                abs(xyz[0]-expected_x)>.035 or abs(xyz[1])>.035 or
                abs(xyz[2]-.415)>.045):
                raise AssertionError("native upward ray not sampled at matched H pose: "+str(log))
            phases.append(range_m)
        upper_samples.append(phases)
    print(f"A6_UP_RANGE_NATIVE_OBSERVED n={n} before_under_after={upper_samples} "
          "flight=NOT_TESTED pedagogy=UNPROVEN",flush=True)
    sweep=re.findall(r"WEBEEBLOCKS_COUNT_H_SWEEP_PASS variant=(\d) "
                     r"samples=(\d+) control_contacts=(\d+) low_z=([0-9.]+)",txt)
    if (len(sweep)!=1 or sweep[0][0]!=str(n) or
        int(sweep[0][1])!=201 or int(sweep[0][2])<1 or
        abs(float(sweep[0][3])-0.40)>.001):
        raise AssertionError("native contact sweep and positive collision calibration failed: "+str(log))
    print(f"A6_CONTACT_SWEEP_NATIVE_OK n={n} samples={sweep[0][1]} control_contacts={sweep[0][2]}",flush=True)
    if (len(findings)!=3 or any(row[0]!=str(n) or row[1]!=str(i)
                                 for i,row in enumerate(findings)) or
        "WEBEEBLOCKS_COUNT_H_BACK_FATAL" in txt or
        "WEBEEBLOCKS_COUNT_H_RESULT" in txt):
        raise AssertionError("three native rear rays not observed: "+str(log))
    readings=[]
    coordinates=[]
    low,high=EXPECTED[n]
    for i,row in enumerate(findings):
        reading=float(row[2])
        xyz=tuple(map(float,row[3:]))
        if (not low<=reading<=high or
            abs(xyz[0]-1.48)>.035 or abs(xyz[1]-PADS[i])>.035 or
            abs(xyz[2]-.75)>.045):
            raise AssertionError("rear sensor not masked at pad: "+str(log))
        readings.append(reading)
        coordinates.append(xyz)
        print(f"A6_BACK_RANGE_MASKED n={n} pad={i} meters={reading:.9f}",flush=True)
    return readings,coordinates,upper_samples,terminal,headings


def main():
    observations={n:run_one(n) for n in EXPECTED}
    all_values=[]
    for pad in range(len(PADS)):
        values=[observations[n][0][pad] for n in EXPECTED]
        poses=[observations[n][1][pad] for n in EXPECTED]
        if (max(values)-min(values) > .025 or
            any(abs(left-right)>.02 for row in poses[1:]
                for left,right in zip(row,poses[0]))):
            raise AssertionError(
                f"count information still leaks at terminal pad {pad}: {values}")
        all_values.append(values)
    full_terminal={n:observations[n][3] for n in EXPECTED}
    validate_terminal_indistinguishability(full_terminal)
    full_headings={n:observations[n][4] for n in EXPECTED}
    validate_heading_indistinguishability(full_headings)
    payload={
        "schema":"webeeblocks-a6-terminal-multiranger-v3",
        "native_rear_mask_observed_at_0_75m":True,
        "all_five_native_rays_compared_at_0_415m_and_0_015m":True,
        "cardinal_turns_90_180_270_tested_at_both_low_phases":True,
        "not_an_information_security_proof":True,
        "not_a_pedagogical_or_flight_pass":True,
        "upward_sensor_observability_only":True,
        "variable_counting_or_generic_wbb_unproven":True,
        "variants":[{"count":n,"pad_readings_m":observations[n][0],
                     "pad_poses_xyz":[list(x) for x in observations[n][1]],
                     "native_up_before_under_after_m":observations[n][2],
                     "terminal_multiranger_m":{
                       f"pad{pad}_{stage}":list(observations[n][3][(pad,stage)])
                       for pad in range(len(PADS)) for stage in TERMINAL_STAGES},
                     "cardinal_multiranger_m":{
                       f"pad{pad}_{stage}_{yaw}deg":list(observations[n][4][(pad,stage,yaw)])
                       for pad in range(len(PADS)) for stage in TERMINAL_STAGES
                       for yaw in TERMINAL_HEADINGS}}
                    for n in EXPECTED]
    }
    ARTIFACTS.mkdir(parents=True,exist_ok=True)
    (ARTIFACTS/"summary.json").write_text(
        json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("A6_CARDINAL_MULTIRANGER_NATIVE_INVARIANT "
          "counts=1,2,3 pads=0,+0.55,-0.55 stages=approach,landed "
          "yaw_deg=90,180,270 channels=front,back,left,right,up "
          "same_pose_and_heading=true pupil_flight=UNPROVEN",flush=True)
    print("A6_TERMINAL_MULTIRANGER_NATIVE_INVARIANT "
          "counts=1,2,3 pads=0,+0.55,-0.55 stages=approach,landed "
          "channels=front,back,left,right,up same_pose_per_pad=true "
          "pupil_flight=UNPROVEN",flush=True)


if __name__=="__main__":
    main()

#!/usr/bin/env python3
"""R2025a native A5 H-near/far × G-left/right 2x2 sensor experiment, NOT a motor test.

Four physically distinct WBOs, original Crazyflie/Deck and native ray values.
The Supervisor sets sample poses; no pupil Blockly, mission oracle or real drone.
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
OUT=ROOT/"ci-artifacts/progression-reactive-L-factor"
SOURCE_CONTROLLER='controller "crazyflie_classroom_v2"'
SENSOR_CONTROLLER='controller "progression_reactive_L_factor_probe"'
SOURCE_WINDOW='window "altitude_scene_ack_probe"'
MARKER="# WEBEEBLOCKS_A5_HFIXED_GBINARY_NATIVE_CI_ONLY"
PROJECT="Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n"
PHASES=(("early",0.,0.),("approach",2.50,0.),
        ("gap_left",2.50,.80),("gap_right",2.50,-.80))
SAMPLE=re.compile(
    r"WEBEEBLOCKS_A5_FACTOR_SAMPLE variant=([LR]) cue=([NF]) "
    r"phase=(early|approach|gap_left|gap_right) "
    r"front=([0-9.]+) left=([0-9.]+) right=([0-9.]+) "
    r"x=(-?[0-9.]+) y=(-?[0-9.]+) z=(-?[0-9.]+) time=([0-9.]+)")
DONE=re.compile(
    r"WEBEEBLOCKS_A5_FACTOR_DONE variant=([LR]) samples=4 "
    r"teleport_only=true motorized=false")
FATAL="WEBEEBLOCKS_A5_FACTOR_FATAL"

def scene_path(variant):
    if type(variant) is not str or variant not in ("L","R","FL","FR"):
        raise ValueError("only H-near/far × G-left/right factors allowed")
    suffix="left" if variant[-1]=="L" else "right"
    cue="far" if variant.startswith("F") else "near"
    return ROOT/f"worlds/scenes/reactive-L-factor-h{cue}-g{suffix}-proto.wbo"

def compose(variant,scene=None):
    base=classroom.compose(classroom.SOURCE.read_text(encoding="utf-8"))
    content=(scene_path(variant).read_text(encoding="utf-8")
             if scene is None else scene)
    expected=f"DEF WEBEEBLOCKS_A5_FACTOR_G{variant[-1]}_SCENE Group"
    if (base.count(SOURCE_CONTROLLER)!=1 or base.count(SOURCE_WINDOW)!=1
        or base.count(classroom.MARKER)!=1
        or base.count("Floor { size 4 4 }")!=1
        or content.count(expected)!=1 or
        content.count(" Solid {")!=7 or
        content.count("boundingObject Box")!=7 or
        "Robot {" in content or 'controller "' in content or
        any(f"WEBEEBLOCKS_A5_FACTOR_G{other}_SCENE" in content
            for other in "LR" if other!=variant[-1])):
        raise ValueError("original world or physical G fixture untrusted")
    base=base.replace(SOURCE_CONTROLLER,SENSOR_CONTROLLER,1)
    base=base.replace("Floor { size 4 4 }","Floor { size 12 6 }",1)
    base=base.replace(classroom.MARKER,MARKER,1)
    out=base.rstrip()+"\n"+content.rstrip()+"\n"
    if (out.count(SENSOR_CONTROLLER)!=1 or out.count(MARKER)!=1
        or SOURCE_CONTROLLER in out):
        raise ValueError("unexpected active native controller")
    return out

def run_one(variant):
    folder=OUT/variant
    folder.mkdir(parents=True,exist_ok=True)
    world=ROOT/f"worlds/ci_a5_factor_g{variant.lower()}.wbt"
    project=ROOT/f"worlds/.ci_a5_factor_g{variant.lower()}.wbproj"
    body=compose(variant)
    if (world.exists() or project.exists() or
        world.is_symlink() or project.is_symlink()):
        raise FileExistsError("refuse existing native A5 fixture")
    process=None
    try:
        world.write_text(body,encoding="utf-8")
        project.write_text(PROJECT,encoding="utf-8")
        (folder/"world.sha256").write_text(
            hashlib.sha256(body.encode()).hexdigest()+"\n",encoding="utf-8")
        log=folder/"webots.log"
        env=dict(os.environ)
        env["LIBGL_ALWAYS_SOFTWARE"]="true"
        env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"]="true"
        with log.open("w",encoding="utf-8") as stream:
            process=subprocess.Popen(
                ["timeout","-k","5s","85s","xvfb-run","-a","webots",
                 "--stdout","--stderr","--batch","--mode=fast",str(world)],
                cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,
                start_new_session=True)
            deadline=time.monotonic()+78
            while time.monotonic()<deadline:
                stream.flush()
                source=log.read_text(encoding="utf-8",errors="replace")
                if DONE.search(source) or FATAL in source or process.poll() is not None:
                    break
                time.sleep(.25)
    finally:
        if process:
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                process.wait(timeout=5)
        if world.exists():
            if world.read_text(encoding="utf-8")!=body:
                raise RuntimeError("refuse cleanup of modified Webots world")
            world.unlink()
        if project.exists():
            raw=project.read_text(encoding="utf-8")
            if (len(raw)>65536 or
                not raw.startswith("Webots Project File version R2025a\n")):
                raise RuntimeError("refuse unexpected Webots project")
            project.unlink()
    text=(folder/"webots.log").read_text(encoding="utf-8",errors="replace")
    rows=SAMPLE.findall(text)
    gate=variant[-1]
    cue="F" if variant.startswith("F") else "N"
    if (FATAL in text or DONE.findall(text)!=[gate] or len(rows)!=4 or
        [(v,c,phase) for v,c,phase,*_ in rows]!=
        [(gate,cue,name) for name,_,_ in PHASES]):
        raise AssertionError("missing real R2025a H-fixed G-binary measurements")
    samples=[]
    previous_time=-1.0
    for row,(name,x0,y0) in zip(rows,PHASES):
        v,c,phase,*raw=row
        front,left,right,x,y,z,now=map(float,raw)
        if (not all(math.isfinite(q) for q in
                    (front,left,right,x,y,z,now)) or
            now<=previous_time or min(front,left,right)<0 or
            max(front,left,right)>2.001 or
            abs(x-x0)>.035 or abs(y-y0)>.035 or abs(z-.50)>.09):
            raise AssertionError("invalid native sensor, pose or time")
        samples.append(dict(phase=phase,front_m=front,left_m=left,
                            right_m=right,x=x,y=y,z=z,time=now))
        previous_time=now
    (folder/"samples.json").write_text(json.dumps({
        "variant":variant,"cue":cue,"gate":gate,"native_original_multiranger":True,
        "physical_Solids_attested":True,"motorized":False,
        "samples":samples},sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(f"WEBEEBLOCKS_A5_FACTOR_NATIVE variant={variant} "
          f"early_left_m={samples[0]['left_m']:.6f} "
          f"approach_left_m={samples[1]['left_m']:.6f}",flush=True)
    return samples

def main():
    data={v:run_one(v) for v in ("L","R","FL","FR")}
    L,R=data["L"],data["R"]
    FL,FR=data["FL"],data["FR"]
    early=max(abs(L[0][d]-R[0][d]) for d in
              ("front_m","left_m","right_m"))
    approach=abs(L[1]["left_m"]-R[1]["left_m"])
    # Open aperture must have the FARTHER unobstructed frontal ray.
    # G-L opens on the left; G-R opens on the right. Do not invert this sign.
    gap_left=L[2]["front_m"]-R[2]["front_m"]
    gap_right=R[3]["front_m"]-L[3]["front_m"]
    dims=("front_m","left_m","right_m")
    early_far=max(abs(FL[0][d]-FR[0][d]) for d in dims)
    approach_far=abs(FL[1]["left_m"]-FR[1]["left_m"])
    gap_left_far=FL[2]["front_m"]-FR[2]["front_m"]
    gap_right_far=FR[3]["front_m"]-FL[3]["front_m"]
    h_initial_left_deltas=[abs(data[n][0]["left_m"]-data[f][0]["left_m"])
                           for n,f in (("L","FL"),("R","FR"))]
    h_initial_other_delta=max(abs(data[n][0][d]-data[f][0][d])
                              for n,f in (("L","FL"),("R","FR"))
                              for d in ("front_m","right_m"))
    h_late_delta=max(abs(data[n][i][d]-data[f][i][d])
                     for n,f in (("L","FL"),("R","FR"))
                     for i in (1,2,3) for d in dims)
    report=dict(schema="webeeblocks-a5-hg-factor-2x2-native-v1",
                h_initial_left_deltas_m=h_initial_left_deltas,
                h_initial_other_delta_m=h_initial_other_delta,
                h_late_local_delta_m=h_late_delta,
                early_far_max_delta_m=early_far,
                approach_far_left_delta_m=approach_far,
                gap_left_far_front_delta_m=gap_left_far,
                gap_right_far_front_delta_m=gap_right_far,
                early_max_delta_m=early,
                approach_left_delta_m=approach,
                gap_left_front_delta_m=gap_left,
                gap_right_front_delta_m=gap_right,
                native_sensors=True,physical_Solids_attested=True,
                supervisor_only=True,motorized_passage_proven=False,
                reactively_observed_program_proven=False,
                useful_state_variable_proven=False,
                pupil_wbb_or_mission_proven=False)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(
        json.dumps(report,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    if (early>.035 or not .45<L[0]["left_m"]<.70 or
        L[0]["front_m"]<1.95 or R[0]["front_m"]<1.95 or
        approach<.35 or gap_left<.35 or gap_right<.35):
        raise AssertionError("G information leaks at start or gate is not natively distinguishable")
    if (early_far>.035 or approach_far<.35 or
        gap_left_far<.35 or gap_right_far<.35 or
        min(h_initial_left_deltas)<.35 or
        max(h_initial_left_deltas)>1.50 or
        h_initial_other_delta>.035 or h_late_delta>.035):
        raise AssertionError("H/G independence refuted by genuine R2025a rays")
    print("WEBEEBLOCKS_A5_FACTOR_HG_2X2_NATIVE_PASS "
          "early_H_observed=true late_H_local_alias=true "
          "G_observed_after_approach=true teleport_only=true "
          "motor_Hfactor_unproven=true pupil_wbb=false",flush=True)
    print("WEBEEBLOCKS_A5_FACTOR_G_NATIVE_PASS "
          "early_indistinguishable=true later_observable=true "
          "motorized=false pupil_wbb=false",flush=True)

if __name__=="__main__":
    main()

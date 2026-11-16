#!/usr/bin/env python3
"""R2025a native A5 fixed-H/G-binary sensor experiment, NOT a motor test.

Two physically distinct WBOs, original Crazyflie/Deck and native ray values.
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
    r"WEBEEBLOCKS_A5_FACTOR_SAMPLE variant=([LR]) "
    r"phase=(early|approach|gap_left|gap_right) "
    r"front=([0-9.]+) left=([0-9.]+) right=([0-9.]+) "
    r"x=(-?[0-9.]+) y=(-?[0-9.]+) z=(-?[0-9.]+) time=([0-9.]+)")
DONE=re.compile(
    r"WEBEEBLOCKS_A5_FACTOR_DONE variant=([LR]) samples=4 "
    r"teleport_only=true motorized=false")
FATAL="WEBEEBLOCKS_A5_FACTOR_FATAL"

def scene_path(variant):
    if not isinstance(variant,str) or variant not in ("L","R"):
        raise ValueError("only fixed-H G-left/G-right are authorized")
    suffix="left" if variant=="L" else "right"
    return ROOT/f"worlds/scenes/reactive-L-factor-hnear-g{suffix}-proto.wbo"

def compose(variant,scene=None):
    base=classroom.compose(classroom.SOURCE.read_text(encoding="utf-8"))
    content=(scene_path(variant).read_text(encoding="utf-8")
             if scene is None else scene)
    expected=f"DEF WEBEEBLOCKS_A5_FACTOR_G{variant}_SCENE Group"
    if (base.count(SOURCE_CONTROLLER)!=1 or base.count(SOURCE_WINDOW)!=1
        or base.count(classroom.MARKER)!=1
        or base.count("Floor { size 4 4 }")!=1
        or content.count(expected)!=1 or
        content.count(" Solid {")!=7 or
        content.count("boundingObject Box")!=7 or
        "Robot {" in content or 'controller "' in content or
        any(f"WEBEEBLOCKS_A5_FACTOR_G{other}_SCENE" in content
            for other in "LR" if other!=variant)):
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
    if (FATAL in text or DONE.findall(text)!=[variant] or len(rows)!=4 or
        [(v,phase) for v,phase,*_ in rows]!=
        [(variant,name) for name,_,_ in PHASES]):
        raise AssertionError("missing real R2025a H-fixed G-binary measurements")
    samples=[]
    previous_time=-1.0
    for row,(name,x0,y0) in zip(rows,PHASES):
        v,phase,*raw=row
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
        "variant":variant,"native_original_multiranger":True,
        "physical_Solids_attested":True,"motorized":False,
        "samples":samples},sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(f"WEBEEBLOCKS_A5_FACTOR_NATIVE variant={variant} "
          f"early_left_m={samples[0]['left_m']:.6f} "
          f"approach_left_m={samples[1]['left_m']:.6f}",flush=True)
    return samples

def main():
    data={v:run_one(v) for v in ("L","R")}
    L,R=data["L"],data["R"]
    early=max(abs(L[0][d]-R[0][d]) for d in
              ("front_m","left_m","right_m"))
    approach=abs(L[1]["left_m"]-R[1]["left_m"])
    # Open aperture must have the FARTHER unobstructed frontal ray.
    # G-L opens on the left; G-R opens on the right. Do not invert this sign.
    gap_left=L[2]["front_m"]-R[2]["front_m"]
    gap_right=R[3]["front_m"]-L[3]["front_m"]
    report=dict(schema="webeeblocks-a5-gfactor-native-v1",
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
    print("WEBEEBLOCKS_A5_FACTOR_G_NATIVE_PASS "
          "early_indistinguishable=true later_observable=true "
          "motorized=false pupil_wbb=false",flush=True)

if __name__=="__main__":
    main()

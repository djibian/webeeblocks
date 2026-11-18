#!/usr/bin/env python3
"""A5 Draft-only R2025a original Multi-ranger experiment: L lengths x side.

Only controlled Supervisor poses to measure the REAL native sensor response.
NO pupil program, no real motor flight, no mission oracle. Source contract
and C native geometry gate must BOTH agree with the expected four worlds.
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
ARTIFACT=ROOT/"ci-artifacts/progression-reactive-L-length"
SOURCE_CONTROLLER='controller "crazyflie_classroom_v2"'
PROBE_CONTROLLER='controller "progression_reactive_L_length_probe"'
MARKER="# WEBEEBLOCKS_A5_LENGTH_NATIVE_CI_ONLY"
PROJECT="Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n"
SAMPLE=re.compile(
    r"(?m)^WEBEEBLOCKS_A5_LENGTH_SAMPLE length=([SL]) side=([LR]) "
    r"phase=(early|survey|decision|gap_left|gap_right) "
    r"front=([0-9.]+) left=([0-9.]+) right=([0-9.]+) "
    r"x=(-?[0-9.]+) y=(-?[0-9.]+) z=(-?[0-9.]+) time=([0-9.]+)$")
DONE=re.compile(
    r"(?m)^WEBEEBLOCKS_A5_LENGTH_DONE length=([SL]) side=([LR]) "
    r"samples=5 supervisor_only=true motors=false$")
FATAL="WEBEEBLOCKS_A5_LENGTH_FATAL"
KNOWN=("SL","SR","LL","LR")

def scene_file(variant):
    if type(variant) is not str or variant not in KNOWN:
        raise ValueError("four length/side sensor-only variants only")
    length="short" if variant[0]=="S" else "long"
    side="left" if variant[1]=="L" else "right"
    return ROOT/f"worlds/scenes/reactive-L-length-{length}-g{side}-proto.wbo"

def compose(variant,scene=None):
    if type(variant) is not str or variant not in KNOWN:
        raise ValueError("native length probe restricted to S/L x L/R")
    original=classroom.SOURCE.read_text(encoding="utf-8")
    world=classroom.compose(original)
    body=scene_file(variant).read_text(encoding="utf-8") if scene is None else scene
    expected=("DEF WEBEEBLOCKS_A5_LENGTH_"+
              ("SHORT" if variant[0]=="S" else "LONG")+"_G"+variant[1]+"_SCENE Group")
    if (world.count(SOURCE_CONTROLLER)!=1 or
        world.count(classroom.MARKER)!=1 or
        world.count("Floor { size 4 4 }")!=1 or
        world.count('Crazyflie {\n  name "Crazyflie WebeeBlocks"')!=1 or
        body.count(expected)!=1 or body.count(" Solid {")!=7 or
        body.count("boundingObject Box")!=7 or
        body.count(" Pose {")!=4 or
        " Robot {" in body or 'controller "' in body or
        any("WEBEEBLOCKS_A5_LENGTH_"+size+"_G"+side+"_SCENE" in body
            for size in ("SHORT","LONG") for side in ("L","R")
            if size!=("SHORT" if variant[0]=="S" else "LONG")
            or side!=variant[1])):
        raise ValueError("unexpected native original world or physical L")
    world=world.replace(SOURCE_CONTROLLER,PROBE_CONTROLLER,1)
    world=world.replace(classroom.MARKER,MARKER,1)
    world=world.replace("Floor { size 4 4 }","Floor { size 12 6 }",1)
    result=world.rstrip()+"\n"+body.rstrip()+"\n"
    if (result.count(PROBE_CONTROLLER)!=1 or
        result.count(MARKER)!=1 or SOURCE_CONTROLLER in result):
        raise ValueError("unexpected extra active native controller")
    return result

def phases(variant):
    gate=2.9 if variant[0]=="S" else 3.3
    return (("early",0.,0.),("survey",1.8,0.),
            ("decision",2.25,0.),
            ("gap_left",gate-.6,.8),("gap_right",gate-.6,-.8))

def run_one(variant):
    folder=ARTIFACT/variant
    folder.mkdir(parents=True,exist_ok=True)
    wbt=ROOT/f"worlds/ci_a5_length_{variant.lower()}.wbt"
    proj=ROOT/f"worlds/.ci_a5_length_{variant.lower()}.wbproj"
    data=compose(variant)
    if (wbt.exists() or proj.exists() or
        wbt.is_symlink() or proj.is_symlink()):
        raise FileExistsError("refuse to overwrite native A5 source")
    process=None
    log=folder/"webots.log"
    try:
        wbt.write_text(data,encoding="utf-8")
        proj.write_text(PROJECT,encoding="utf-8")
        (folder/"world.sha256").write_text(
            hashlib.sha256(data.encode()).hexdigest()+"\n",encoding="utf-8")
        env=dict(os.environ)
        env["LIBGL_ALWAYS_SOFTWARE"]="true"
        env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"]="true"
        with log.open("w",encoding="utf-8") as stream:
            process=subprocess.Popen(
                ["timeout","-k","5s","85s","xvfb-run","-a","webots",
                 "--stdout","--stderr","--batch","--mode=fast",str(wbt)],
                cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,
                start_new_session=True)
            deadline=time.monotonic()+78
            while time.monotonic()<deadline:
                stream.flush()
                text=log.read_text(encoding="utf-8",errors="replace")
                if DONE.search(text) or FATAL in text or process.poll() is not None:
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
        if wbt.exists():
            if wbt.read_text(encoding="utf-8")!=data:
                raise RuntimeError("refuse to remove unexpectedly altered WBT")
            wbt.unlink()
        if proj.exists():
            raw=proj.read_text(encoding="utf-8")
            if (len(raw)>65536 or
                not raw.startswith("Webots Project File version R2025a\n")):
                raise RuntimeError("refuse altered Webots private project")
            proj.unlink()
    text=log.read_text(encoding="utf-8",errors="replace")
    rows=SAMPLE.findall(text)
    if (FATAL in text or DONE.findall(text)!=[(variant[0],variant[1])]
        or len(rows)!=5 or
        [(length,side,name) for length,side,name,*_ in rows]!=
        [(variant[0],variant[1],name) for name,_,_ in phases(variant)]):
        print(text[-5000:],flush=True)
        raise AssertionError("original R2025a L-length sensor proof unavailable")
    observed=[]
    prev=-1.
    for row,(name,tx,ty) in zip(rows,phases(variant)):
        _len,_side,_phase,*values=row
        front,left,right,x,y,z,t=map(float,values)
        if (not all(math.isfinite(q) for q in
             (front,left,right,x,y,z,t)) or
            min(front,left,right)<0 or max(front,left,right)>2.001 or
            t<=prev or abs(x-tx)>.035 or abs(y-ty)>.035 or
            abs(z-.50)>.09):
            raise AssertionError("untrusted C pose/sensor/clock")
        prev=t
        observed.append({"phase":name,"front_m":front,"left_m":left,
                         "right_m":right,"xyz":[x,y,z],"time_s":t})
    (folder/"samples.json").write_text(json.dumps({
        "variant":variant,"samples":observed,"source_only":False,
        "genuine_original_multiranger":True,"native_box_gate":True,
        "supervisor_only":True,"motorized":False,"mission_oracle":False
    },indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("WEBEEBLOCKS_A5_LENGTH_NATIVE_SAMPLES "+
          f"variant={variant} early_front={observed[0]['front_m']:.6f} "+
          f"survey_front={observed[1]['front_m']:.6f} "+
          f"decision_left={observed[2]['left_m']:.6f}",flush=True)
    return observed

def main():
    data={v:run_one(v) for v in KNOWN}
    first=data["SL"][0]
    early_delta=max(abs(data[v][0][d]-first[d]) for v in KNOWN
                    for d in ("front_m","left_m","right_m"))
    survey_contrast={
       side:data["L"+side][1]["front_m"]-data["S"+side][1]["front_m"]
       for side in ("L","R")}
    turn_contrast={
       length:data[length+"L"][2]["left_m"]-data[length+"R"][2]["left_m"]
       for length in ("S","L")}
    length_leak_into_turn=max(
       abs(data["S"+side][2]["left_m"]-data["L"+side][2]["left_m"])
       for side in ("L","R"))
    gaps={v:(data[v][3]["front_m"]-data[(v[0]+"R")][3]["front_m"]
             if v[1]=="L" else
             data[v][4]["front_m"]-data[(v[0]+"L")][4]["front_m"])
          for v in KNOWN}
    report={"schema":"webeeblocks-a5-L-length-x-side-native-v1",
       "early_max_delta_m":early_delta,
       "survey_long_minus_short_front_m":survey_contrast,
       "decision_left_minus_right_sensor_m":turn_contrast,
       "length_leak_into_side_sensor_m":length_leak_into_turn,
       "gap_front_contrast_m":gaps,
       "native_original_sensors":True,
       "native_collision_boxes_attested":True,
       "motorized":False,
       "pupil_wbb_pass":False,
       "activity5_pedagogical_pass":False}
    ARTIFACT.mkdir(parents=True,exist_ok=True)
    (ARTIFACT/"summary.json").write_text(
        json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    if (early_delta>.035 or
        not .45<first["left_m"]<.70 or
        first["front_m"]<1.95 or
        min(survey_contrast.values())<=.25 or
        max(survey_contrast.values())>=.65 or
        min(turn_contrast.values())<=.35 or
        length_leak_into_turn>.035 or
        min(gaps.values())<=.35):
        raise AssertionError("L length/side not independently observable by native rays")
    print("WEBEEBLOCKS_A5_LENGTH_X_SIDE_NATIVE_PASS "+
          "four_real_WBO=true native_telemetry=true "
          "length_requires_later_front=true opening_requires_left=true "
          "motorized=false pupil_unpublished=true",flush=True)

if __name__=="__main__":
    main()

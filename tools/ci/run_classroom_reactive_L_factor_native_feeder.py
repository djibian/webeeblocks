#!/usr/bin/env python3
"""Draft A5 native WWI-feeder proof: ORIGINAL R2025a product motor/PID.

No Robot Window or browser: a private C interposer supplies the same WWI
REQUEST protocol and consumes actual runtime responses. This can establish
motor physics but NOT pupil Blockly, Robot Window, hardware or a mission oracle.
"""
import argparse
import hashlib
import json
import math
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
import prepare_classroom_reactive_L_factor_motor as world
from run_classroom_reactive_L_factor_motor import native_collision_coverage

ROOT=world.ROOT
ARTIFACT=ROOT/"ci-artifacts/progression-reactive-L-factor-native-feeder"
PREFIX="WEBEEBLOCKS_A5_FACTOR_FEEDER_"
FATAL="WEBEEBLOCKS_A5_FACTOR_MOTOR_FATAL"
OTHER_FATAL="WEBEEBLOCKS_RUNTIME_V2 FATAL"

def runtime_env(mode):
    home=Path(os.getenv("WEBOTS_HOME","/usr/local/webots"))
    exe=ROOT/"controllers/progression_reactive_L_factor_motor_pilot"/(
        "progression_reactive_L_factor_motor_pilot")
    qt=home/"lib/webots"
    ctl=home/"lib/controller"
    if not exe.is_file() or not (qt/"libQt6Core.so.6").is_file() or not (ctl/"libController.so").is_file():
        raise FileNotFoundError("real private motor/PID and linked Webots libraries required")
    env=dict(os.environ)
    env["LD_LIBRARY_PATH"]=":".join([str(qt),str(ctl),env.get("LD_LIBRARY_PATH","")]).rstrip(":")
    env["WEBEEBLOCKS_A5_FACTOR_NATIVE_FEEDER"]=mode
    env["LIBGL_ALWAYS_SOFTWARE"]="true"
    env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"]="true"
    # Native-only: browser integration stays a DISTINCT, still-red job.
    ARTIFACT.mkdir(parents=True,exist_ok=True)
    deps=subprocess.run(["ldd",str(exe)],env=env,text=True,capture_output=True,timeout=15)
    (ARTIFACT/"native-loader.txt").write_text(deps.stdout+deps.stderr)
    if deps.returncode or "not found" in deps.stdout+deps.stderr:
        raise RuntimeError("native product/PID not loadable; no fake motion allowed")
    return env

def run(variant,mode):
    if variant not in ("A","B") or mode not in ("positive","blind") or (mode=="blind" and variant!="B"):
        raise ValueError("native gate experiment only permits A/B and blind B")
    folder=ARTIFACT/(f"{variant}-{mode}")
    folder.mkdir(parents=True,exist_ok=True)
    log=folder/"webots.log"
    resultfile=folder/"result.json"
    expected=world.compose(variant)
    env=runtime_env(mode)
    wbt,proj=world.paths(variant)
    proc=stream=None
    try:
        world.prepare(variant)
        (folder/"world.sha256").write_text(hashlib.sha256(expected.encode()).hexdigest()+"\n")
        stream=log.open("w",encoding="utf-8")
        proc=subprocess.Popen(
            ["timeout","-k","5s","145s","xvfb-run","-a","webots",
             "--stdout","--stderr","--batch","--mode=fast",str(wbt)],
            cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,
            start_new_session=True)
        deadline=time.monotonic()+140
        while time.monotonic()<deadline:
            stream.flush()
            raw=log.read_text(errors="replace")
            done="WEBEEBLOCKS_A5_FACTOR_FEEDER_DONE" in raw
            floor=f"WEBEEBLOCKS_A5_FACTOR_MOTOR_NATIVE_FLOOR variant={variant}" in raw
            fail=any(k in raw for k in (PREFIX+"FATAL",FATAL,OTHER_FATAL))
            if (done and floor) or fail or proc.poll() is not None:break
            time.sleep(.20)
    finally:
        if proc:
            if proc.poll() is None:
                try:os.killpg(proc.pid,signal.SIGTERM)
                except ProcessLookupError:pass
                try:proc.wait(timeout=6)
                except subprocess.TimeoutExpired:
                    try:os.killpg(proc.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    proc.wait(timeout=6)
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        if stream:stream.close()
        world.cleanup(variant,original=expected)
    data=log.read_text(errors="replace")
    startup=re.findall(
        rf"(?m)^WEBEEBLOCKS_A5_FACTOR_FEEDER_INIT variant={variant} "
        rf"mode={mode} browser_bypassed=true physical_pid_original=true$",data)
    collisions=re.findall(
        rf"(?m)^WEBEEBLOCKS_A5_FACTOR_MOTOR_SWEPT_COLLISION "
        rf"variant={variant} collider=([A-Z_]+) t=([0-9.]+)$",data)
    if mode=="blind":
        # The pilot must try the WRONG physical gap after an authentic late ray.
        wrong=re.findall(
            r"(?m)^WEBEEBLOCKS_A5_FACTOR_FEEDER_LATE_RANGE variant=B "
            r"left_m=([0-9.]+) route=left mode=blind$",data)
        failed=(startup==[""] and len(wrong)==1 and float(wrong[0])<.70 and
                len(collisions)>=1 and collisions[0][0] in ("G_SIDE_ARM","G_UPPER") and
                "WEBEEBLOCKS_A5_FACTOR_MOTOR_FATAL reason=swept_physical_box_intersection" in data and
                "WEBEEBLOCKS_A5_FACTOR_MOTOR_NATIVE_FLOOR" not in data and
                "WEBEEBLOCKS_A5_FACTOR_FEEDER_DONE" not in data)
        output={"variant":variant,"mode":mode,"pass":failed,
                "physical_collision_rejected":bool(collisions),
                "native_range_m":float(wrong[0]) if len(wrong)==1 else None,
                "browser_not_used":True,"student_wbb":False}
        resultfile.write_text(json.dumps(output,indent=2,sort_keys=True)+"\n")
        if not failed:
            print("WEBEEBLOCKS_A5_FACTOR_FEEDER_BLIND_UNPROVEN "+
                  json.dumps(output),file=sys.stderr)
            print(data[-7000:],file=sys.stderr)
            raise AssertionError("blind G-right native contact not rejected")
        print("WEBEEBLOCKS_A5_FACTOR_FEEDER_BLIND_NATIVE_REJECTED "
              "G_right_wrong_left=true physical_collision=true",flush=True)
        return output
    expected_route="left" if variant=="A" else "right"
    expected_last=13 if variant=="A" else 15
    init_ok=len(startup)==1
    observed=re.findall(
        rf"(?m)^WEBEEBLOCKS_A5_FACTOR_FEEDER_LATE_RANGE variant={variant} "
        rf"left_m=([0-9.]+) route={expected_route} mode=positive$",data)
    raw_range=re.findall(r"(?m)^WEBEEBLOCKS_RUNTIME_V2 TRACE RANGE left value=([0-9.]+)$",data)
    reply=re.findall(r"(?m)^WEBEEBLOCKS_RUNTIME_V2 RESPONSE 7 VALUE ([0-9.]+)$",data)
    acks=[int(x) for x in re.findall(
        r"(?m)^WEBEEBLOCKS_A5_FACTOR_FEEDER_ACK id=(\d+) kind=[A-Z_]+$",data)]
    done=re.findall(
        rf"(?m)^WEBEEBLOCKS_A5_FACTOR_FEEDER_DONE variant={variant} "
        rf"route={expected_route} last_id={expected_last} "
        rf"late_left_m=([0-9.]+) original_pid=true$",data)
    floor=re.findall(
        rf"(?m)^WEBEEBLOCKS_A5_FACTOR_MOTOR_NATIVE_FLOOR variant={variant} "
        r"x=(-?[0-9.]+) y=(-?[0-9.]+) z=(-?[0-9.]+) t=([0-9.]+)$",data)
    xyz=list(map(float,floor[0])) if len(floor)==1 else None
    coverage=native_collision_coverage(data,variant)
    landed=data.rfind("WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1")
    land_ack=(landed>=0 and
              re.search(
                  rf"(?m)^WEBEEBLOCKS_RUNTIME_V2 RESPONSE {expected_last} OK$",
                  data[landed:]) is not None)
    values=[float(z[0]) for z in (observed,raw_range,reply,done) if len(z)==1]
    invalid=any(mark in data for mark in (
        FATAL,OTHER_FATAL,PREFIX+"FATAL",
        "WEBEEBLOCKS_A5_FACTOR_MOTOR_OBSTACLE_CONTACT",
        "WEBEEBLOCKS_A5_FACTOR_MOTOR_SWEPT_COLLISION"))
    good=(init_ok and len(values)==4 and
          all(math.isfinite(v) for v in values) and
          max(values)-min(values)<1e-6 and
          abs(values[0]-(1.41 if variant=="A" else .54))<.12 and
          acks==list(range(1,expected_last+1)) and
          xyz is not None and abs(xyz[0]-4.15)<.10 and
          abs(xyz[1]-.62)<.10 and 0<=xyz[2]<=.025 and xyz[3]>2 and
          coverage is not None and land_ack and not invalid and
          f"WEBEEBLOCKS_A5_FACTOR_MOTOR_SCENE_OK variant={variant}" in data and
          f"WEBEEBLOCKS_RUNTIME_V2 RESPONSE 1 SCENE_OK " in data and
          "WEBEEBLOCKS_RUNTIME_V2 READY" in data)
    output={"schema":"webeeblocks-a5-native-pid-gfactor-v1",
            "variant":variant,"mode":mode,"pass":good,
            "late_left_m":values[0] if values else None,
            "route":expected_route,"H_fixed_landing_left":True,
            "floor_xyzt":xyz,"monitor":coverage,"native_land":land_ack,
            "native_acks":acks,"actual_runtime_pid":True,
            "browser_not_used":True,"pupil_wbb":False,
            "school_mission_oracle":False,"no_early_G_read":True,
            "feeder_source_sha256":hashlib.sha256(
                (ROOT/"controllers/progression_reactive_L_factor_motor_pilot"/
                 "factor_motor_feeder.c").read_bytes()).hexdigest()}
    resultfile.write_text(json.dumps(output,indent=2,sort_keys=True)+"\n")
    if not good:
        print("WEBEEBLOCKS_A5_FACTOR_FEEDER_NATIVE_UNPROVEN "+
              json.dumps(output),file=sys.stderr)
        print(data[-9000:],file=sys.stderr)
        raise AssertionError("native original product PID passage or actual Floor unproven")
    print(f"WEBEEBLOCKS_A5_FACTOR_FEEDER_NATIVE_PASS variant={variant} "
          f"late_left_m={values[0]:.9f} floor_contact=true "
          f"ticks={coverage['continuous_native_steps']} "
          "browser=UNPROVEN pupil_wbb=UNPROVEN",flush=True)
    return output

def main():
    a=run("A","positive")
    b=run("B","positive")
    if (not a["pass"] or not b["pass"] or
        a["feeder_source_sha256"]!=b["feeder_source_sha256"] or
        a["late_left_m"]-b["late_left_m"]<.35 or
        a["route"]!="left" or b["route"]!="right"):
        raise AssertionError("physical G route not proven to depend on native G sensor")
    (ARTIFACT/"summary.json").write_text(json.dumps({
        "schema":"webeeblocks-a5-native-feeder-two-worlds-v1",
        "pass":True,"same_native_test_program":True,
        "two_runtime_pid_real_floor_contacts":True,
        "browser_integration_proven":False,"student_wbb_proven":False,
        "complete_classroom_mission_proven":False,
        "variants":[a,b]},sort_keys=True,indent=2)+"\n")
    print("WEBEEBLOCKS_A5_FACTOR_FEEDER_TWO_NATIVE_PASS "
          "A_B=true G_obs=true same_pid=true browser=UNPROVEN",flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--blind",action="store_true")
    args=p.parse_args()
    if args.blind:run("B","blind")
    else:main()

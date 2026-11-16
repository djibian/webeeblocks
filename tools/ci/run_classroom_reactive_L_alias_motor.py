#!/usr/bin/env python3
"""Draft-only physical motor/PID feasibility in new A5 information-alias worlds.

This intentionally runs a private same-JS pilot against two genuine Webots
R2025a worlds. The independent Webots Floor contact and normal WWI LAND ACK
are required: a browser-side success or a low GPS altitude alone never passes.
No student .wbb, no runtime product activity profile, no behavioral oracle.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import re
import signal
import subprocess
import sys
import threading
import time
import run_classroom_altitude_scene_ack as events
import prepare_classroom_reactive_L_alias_motor as world

ROOT=world.ROOT
ARTIFACT=ROOT/"ci-artifacts/progression-reactive-L-alias-motor"
REQUIRED=(
    "A5_ALIAS_HTML_LOADED",
    "A5_ALIAS_MOTOR_JS_STARTED",
    "A5_ALIAS_MOTOR_READY",
    "A5_ALIAS_MOTOR_SCENE_ACK",
    "A5_ALIAS_MOTOR_EARLY_CUE",
    "A5_ALIAS_MOTOR_TAKEOFF",
    "A5_ALIAS_MOTOR_COMMON_APPROACH",
    "A5_ALIAS_MOTOR_PAD_SELECTED",
    "A5_ALIAS_MOTOR_LAND_ACK",
    "A5_ALIAS_MOTOR_TEST_COMPLETE",
)

class Handler(events.Handler):
    variant="A"
    def do_GET(self):
        if self.path!="/variant":
            self.send_error(404)
            return
        raw=json.dumps({"variant":self.variant}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

def native_loader_env():
    """Validate the isolated C++ Qt dependencies BEFORE launching Webots.

    R2025a's Qt .so files live in WEBOTS_HOME/lib/webots; mere successful
    compilation with -L does not make that directory discoverable by ld.so.
    This is CI-only, never a modification of product or native flight code.
    """
    home=Path(os.environ.get("WEBOTS_HOME","/usr/local/webots"))
    qt_lib=home/"lib/webots"
    controller_lib=home/"lib/controller"
    executable=ROOT/"controllers/progression_reactive_L_alias_motor_pilot"/(
        "progression_reactive_L_alias_motor_pilot")
    if (not executable.is_file() or
        not (qt_lib/"libQt6Core.so.6").is_file() or
        not (controller_lib/"libController.so").is_file()):
        raise FileNotFoundError("missing private pilot, Qt6 or native Webots controller library")
    env=dict(os.environ)
    original=env.get("LD_LIBRARY_PATH","")
    # libController.so is NOT in lib/webots; omitting lib/controller leaves a
    # compiled C/C++ binary unable to start (verified artifact #14230587226).
    env["LD_LIBRARY_PATH"]=str(qt_lib)+":"+str(controller_lib)+(
        ":"+original if original else "")
    check=subprocess.run(["ldd",str(executable)],env=env,
                         capture_output=True,text=True,timeout=15,check=False)
    ARTIFACT.mkdir(parents=True,exist_ok=True)
    (ARTIFACT/"native-loader-dependencies.txt").write_text(
        check.stdout+check.stderr,encoding="utf-8")
    if check.returncode!=0 or "not found" in check.stdout+check.stderr:
        raise RuntimeError("unresolved A5 native pilot runtime library: "+
                           (check.stdout+check.stderr)[-2800:])
    # Webots may construct a fresh environment for Robot controllers; an
    # inherited LD_LIBRARY_PATH proves only our Python subprocess, not the
    # dynamically linked controller. Require embedded direct library RPATH.
    dynamic=subprocess.run(["readelf","-d",str(executable)],capture_output=True,
                           text=True,timeout=15,check=False)
    (ARTIFACT/"native-loader-dynamic.txt").write_text(
        dynamic.stdout+dynamic.stderr,encoding="utf-8")
    if (dynamic.returncode!=0 or
        not ("(RUNPATH)" in dynamic.stdout or "(RPATH)" in dynamic.stdout) or
        str(qt_lib) not in dynamic.stdout or str(controller_lib) not in dynamic.stdout):
        raise RuntimeError("native Robot executable lacks embedded Qt and Webots controller search paths")
    return env

def native_collision_coverage(transcript,variant):
    """Fail closed if any native physics step is unobserved up to the true LAND.

    Logger emits one heartbeat per 16 real 32-ms WB steps, plus a terminal
    heartbeat after physical contact. A browser success cannot forge these
    markers, which come from the isolated, physically linked C observer.
    """
    if variant not in ("A","B"):
        return None
    pattern=re.compile(
        r"(?m)^WEBEEBLOCKS_A5_ALIAS_MOTOR_MONITOR variant=([AB]) "
        r"ticks=(\d+) t=([0-9.]+) no_obstacle_contacts=true$")
    rows=pattern.findall(transcript)
    final=re.findall(
        r"(?m)^WEBEEBLOCKS_A5_ALIAS_MOTOR_MONITOR_COMPLETE "
        r"variant=([AB]) native_ticks=(\d+) all_contacts_checked=true "
        r"swept_boxes_checked=3$",transcript)
    if len(rows)<4 or len(final)!=1 or final[0][0]!=variant:
        return None
    prev_tick=0
    prev_time=-1.0
    for observed, ticks, moment in rows:
        n=int(ticks)
        t=float(moment)
        if (observed!=variant or n!=prev_tick+16 or
            not math.isfinite(t) or t<=prev_time or
            (prev_time>=0 and not .49<=t-prev_time<=.54)):
            return None
        prev_tick=n
        prev_time=t
    final_tick=int(final[0][1])
    if final_tick<64 or final_tick<prev_tick or final_tick>=prev_tick+16:
        return None
    if ("WEBEEBLOCKS_A5_ALIAS_MOTOR_OBSTACLE_CONTACT" in transcript or
        "WEBEEBLOCKS_A5_ALIAS_MOTOR_SWEPT_COLLISION" in transcript or
        "WEBEEBLOCKS_A5_ALIAS_MOTOR_FATAL" in transcript):
        return None
    return {"continuous_native_steps":final_tick,
            "native_heartbeat_count":len(rows),
            "three_physical_boxes_and_craft_contacts_each_step":True,
            "conservative_swept_boxes_per_step":True}

def run(variant):
    if not isinstance(variant,str) or variant not in "AB" or len(variant)!=1:
        raise ValueError("unexpected native A5 motor variant")
    folder=ARTIFACT/variant
    folder.mkdir(parents=True,exist_ok=True)
    log=folder/"webots.log"
    event_path=folder/"events.json"
    summary_file=folder/"summary.json"
    body=world.compose(variant)
    # Fail fast with a precise dependent-library diagnosis, not a misleading
    # 90-s browser READY timeout while the native controller cannot start.
    checked_env=native_loader_env()
    events.EVENTS.clear()
    Handler.variant=variant
    server=proc=stream=None
    try:
        world.prepare(variant)
        server=events.http.server.ThreadingHTTPServer(("127.0.0.1",8765),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        env=checked_env
        env["WEBOTS_WEB_BROWSER"]="/workspace/tools/ci/webots_runtime_v2_browser.sh"
        env["LIBGL_ALWAYS_SOFTWARE"]="true"
        env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"]="true"
        scene,_=world.paths(variant)
        stream=log.open("w",encoding="utf-8")
        proc=subprocess.Popen(
            ["timeout","-k","5s","145s","xvfb-run","-a","webots",
             "--stdout","--stderr","--batch","--mode=fast",str(scene)],
            cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,
            start_new_session=True)
        limit=time.monotonic()+140
        while time.monotonic()<limit:
            stream.flush()
            txt=log.read_text(encoding="utf-8",errors="replace")
            finished=any(e["event"]=="A5_ALIAS_MOTOR_TEST_COMPLETE"
                         for e in events.EVENTS)
            floor=(f"WEBEEBLOCKS_A5_ALIAS_MOTOR_NATIVE_FLOOR variant={variant} "
                   in txt)
            if (finished and floor) or "WEBEEBLOCKS_A5_ALIAS_MOTOR_FATAL" in txt or (
                "WEBEEBLOCKS_RUNTIME_V2 FATAL" in txt) or any(
                    e["event"]=="A5_ALIAS_MOTOR_ERROR" for e in events.EVENTS):
                break
            if proc.poll() is not None:
                break
            time.sleep(.25)
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
        if server:
            server.shutdown()
            server.server_close()
        event_path.write_text(json.dumps(events.EVENTS,indent=2,sort_keys=True)+"\n",
                              encoding="utf-8")
        world.cleanup(variant,original=body)
    text=log.read_text(encoding="utf-8",errors="replace")
    names=[e["event"] for e in events.EVENTS]
    missing=[x for x in REQUIRED if names.count(x)!=1]
    ordered=not missing and [
        names.index(x) for x in REQUIRED]==sorted(names.index(x) for x in REQUIRED)
    event=lambda key: next((v.get("detail") for v in events.EVENTS
                          if v.get("event")==key),None)
    cue=event("A5_ALIAS_MOTOR_EARLY_CUE")
    pad=event("A5_ALIAS_MOTOR_PAD_SELECTED")
    selected=pad.get("side") if isinstance(pad,dict) else None
    measured=cue.get("range_m") if isinstance(cue,dict) else None
    pose_pattern=re.compile(r"WEBEEBLOCKS_A5_ALIAS_MOTOR_POSE variant=([AB]) "
                            r"t=([0-9.]+) x=(-?[0-9.]+) y=(-?[0-9.]+) "
                            r"z=(-?[0-9.]+) step=([0-9]+)")
    pose=pose_pattern.findall(text)
    contact_pattern=re.compile(
        rf"WEBEEBLOCKS_A5_ALIAS_MOTOR_NATIVE_FLOOR variant={variant} "
        r"x=(-?[0-9.]+) y=(-?[0-9.]+) z=(-?[0-9.]+) t=([0-9.]+)")
    contact=contact_pattern.findall(text)
    expected_side="left" if variant=="A" else "right"
    gps=None
    if len(contact)==1:
        gps=[float(v) for v in contact[0]]
    final_id=10  # SCENE + RANGE + SPEED + TAKEOFF + 3 MOVE + TURN + MOVE + LAND.
    land_pos=text.rfind("WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1")
    ack_after_land=land_pos>=0 and re.search(
        rf"(?m)^WEBEEBLOCKS_RUNTIME_V2 RESPONSE {final_id} OK$",
        text[land_pos:]) is not None
    native_coverage=native_collision_coverage(text,variant)
    fatal_tokens=("WEBEEBLOCKS_A5_ALIAS_MOTOR_FATAL",
                  "WEBEEBLOCKS_RUNTIME_V2 FATAL",
                  "WEBEEBLOCKS_A5_ALIAS_MOTOR_OBSTACLE_CONTACT",
                  "WEBEEBLOCKS_A5_ALIAS_MOTOR_SWEPT_COLLISION")
    errors=[token for token in fatal_tokens if token in text]
    good=(not missing and ordered and names.count("A5_ALIAS_MOTOR_ERROR")==0 and
          isinstance(measured,(float,int)) and math.isfinite(measured) and
          abs(measured-(.54 if variant=="A" else 1.14))<.07 and
          selected==expected_side and
          isinstance(pad,dict) and pad.get("decision_source")==
          "retained_early_sensor" and
          len(pose)>15 and all(v==variant for v,*_ in pose) and
          len(contact)==1 and gps is not None and
          abs(gps[0]-1.50)<=.075 and
          abs(gps[1]-(.62 if variant=="A" else -.62))<=.075 and
          gps[2]<=.025 and gps[2]>=0 and
          gps[3]>2.0 and ack_after_land and not errors and
          native_coverage is not None and
          "WEBEEBLOCKS_RUNTIME_V2 READY" in text and
          f"WEBEEBLOCKS_A5_ALIAS_MOTOR_SCENE_OK variant={variant}" in text)
    summary={"schema":"webeeblocks-a5-alias-motor-feasibility-draft-v1",
             "variant":variant,"pass":good,"same_pilot_js":True,
             "pupil_wbb":False,"mission_oracle":False,
             "motorized_runtime_v2":len(pose)>15,
             "native_floor_contact":len(contact)==1,
             "native_land_ack":ack_after_land,
             "native_collision_coverage":native_coverage,
             "selected_pad":selected,"early_left_m":measured,
             "gps_contact_xyzt":gps,"pose_samples":len(pose),
             "missing_events":missing,"ordered":ordered,"fatal":errors,
             "events":names,"private_source_sha256":hashlib.sha256(
               (ROOT/"plugins/robot_windows/a5_alias_motor_probe/a5_alias_motor_probe.js"
                ).read_bytes()).hexdigest()}
    summary_file.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",
                            encoding="utf-8")
    if not good:
        print("WEBEEBLOCKS_A5_ALIAS_MOTOR_UNPROVEN "+json.dumps(summary),
              file=sys.stderr,flush=True)
        print(text[-5000:],file=sys.stderr)
        raise AssertionError("A5 native motor/PID proof missing on "+variant)
    print(f"WEBEEBLOCKS_A5_ALIAS_MOTOR_PASS variant={variant} "
          f"early_left_m={measured:.6f} real_floor=true native_LAND=true "
          f"fully_checked_steps={native_coverage['continuous_native_steps']} "
          "pupil_wbb=UNPROVEN",flush=True)
    return summary

def main():
    a=run("A")
    b=run("B")
    if (a["private_source_sha256"]!=b["private_source_sha256"] or
        b["early_left_m"]-a["early_left_m"]<.35 or
        a["selected_pad"]!="left" or b["selected_pad"]!="right"):
        raise AssertionError("A/B private motor witness did not prove two choices")
    ARTIFACT.mkdir(parents=True,exist_ok=True)
    (ARTIFACT/"summary.json").write_text(json.dumps({
        "schema":"webeeblocks-a5-alias-physical-feasibility-v1",
        "pass":True,"variants":[a,b],"single_private_js":True,
        "real_native_motor_flight":True,
        "true_physical_floor_contacts":2,
        "full_native_contact_monitoring":True,
        "conservative_swept_aabb_proof_not_full_craft_kinematics":True,
        "student_blockly_and_mission_oracle_NOT_PROVEN":True,
        "no_memory_competitor_NOT_TESTED":True
    },indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("WEBEEBLOCKS_A5_ALIAS_MOTOR_TWO_VARIANT_NATIVE_PASS "
          "same_private_js=true true_floor_contacts=2 "
          "student_mission_oracle=UNPROVEN",flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--variant",choices=["A","B","both"],default="both")
    args=parser.parse_args()
    if args.variant=="both":main()
    else:run(args.variant)

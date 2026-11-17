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
import prepare_classroom_reactive_L_factor_motor as world

ROOT=world.ROOT
ARTIFACT=ROOT/"ci-artifacts/progression-reactive-L-alias-motor"
REQUIRED=(
    "A5_FACTOR_HTML_LOADED","A5_FACTOR_MOTOR_JS_STARTED",
    "A5_FACTOR_MOTOR_READY","A5_FACTOR_MOTOR_SCENE_ACK",
    "A5_FACTOR_MOTOR_TAKEOFF","A5_FACTOR_MOTOR_APPROACH",
    "A5_FACTOR_MOTOR_G_OBSERVATION","A5_FACTOR_MOTOR_GATE_PASSED",
    "A5_FACTOR_MOTOR_PAD_SELECTED","A5_FACTOR_MOTOR_LAND_ACK",
    "A5_FACTOR_MOTOR_TEST_COMPLETE"
)

class Handler(events.Handler):
    variant="A"
    mode="positive"
    def do_GET(self):
        if self.path!="/variant":
            self.send_error(404)
            return
        raw=json.dumps({"variant":self.variant,"mode":self.mode}).encode("utf-8")
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
    executable=ROOT/"controllers/progression_reactive_L_factor_motor_pilot"/(
        "progression_reactive_L_factor_motor_pilot")
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
        r"(?m)^WEBEEBLOCKS_A5_FACTOR_MOTOR_MONITOR variant=([AB]) "
        r"ticks=(\d+) t=([0-9.]+) no_obstacle_contacts=true$")
    rows=pattern.findall(transcript)
    final=re.findall(
        r"(?m)^WEBEEBLOCKS_A5_FACTOR_MOTOR_MONITOR_COMPLETE "
        r"variant=([AB]) native_ticks=(\d+) all_contacts_checked=true "
        r"swept_boxes_checked=7$",transcript)
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
    # Webots keeps stepping for native LAND confirmation and the browser's
    # final event AFTER first real Floor contact. The one-time terminal marker
    # is therefore sandwiched by heartbeats, not necessarily the final one.
    ticks=[int(n) for _,n,_ in rows]
    before=[n for n in ticks if n<=final_tick]
    after=[n for n in ticks if n>final_tick]
    if (final_tick<64 or not before or
        final_tick-before[-1]>=16 or
        (after and after[0]-final_tick>16)):
        return None
    if ("WEBEEBLOCKS_A5_FACTOR_MOTOR_OBSTACLE_CONTACT" in transcript or
        "WEBEEBLOCKS_A5_FACTOR_MOTOR_SWEPT_COLLISION" in transcript or
        "WEBEEBLOCKS_A5_FACTOR_MOTOR_FATAL" in transcript):
        return None
    return {"continuous_native_steps":final_tick,
            "native_heartbeat_count":len(rows),
            "seven_physical_boxes_and_craft_contacts_each_step":True,
            "conservative_swept_boxes_per_step":True}

def run(variant,mode="positive"):
    if variant not in ("A","B") or mode not in ("positive","blind"):
        raise ValueError("wrong fixed-H independent-G native test")
    if mode=="blind" and variant!="B":
        raise ValueError("blind gate rejection tested only against G-right")
    folder=ARTIFACT/("blind-B" if mode=="blind" else variant)
    folder.mkdir(parents=True,exist_ok=True)
    log=folder/"webots.log"
    event_path=folder/"events.json"
    summary_path=folder/"summary.json"
    body=world.compose(variant)
    env=native_loader_env()
    events.EVENTS.clear()
    Handler.variant=variant
    Handler.mode=mode
    server=proc=stream=None
    try:
        world.prepare(variant)
        server=events.http.server.ThreadingHTTPServer(("127.0.0.1",8765),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        env["WEBOTS_WEB_BROWSER"]="/workspace/tools/ci/webots_runtime_v2_browser.sh"
        env["LIBGL_ALWAYS_SOFTWARE"]="true"
        env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"]="true"
        wbt,_=world.paths(variant)
        stream=log.open("w",encoding="utf-8")
        proc=subprocess.Popen(
            ["timeout","-k","5s","180s","xvfb-run","-a","webots",
             "--stdout","--stderr","--batch","--mode=fast",str(wbt)],
            cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,
            start_new_session=True)
        deadline=time.monotonic()+175
        while time.monotonic()<deadline:
            stream.flush()
            trace=log.read_text(encoding="utf-8",errors="replace")
            finished=any(v.get("event")=="A5_FACTOR_MOTOR_TEST_COMPLETE"
                         for v in events.EVENTS)
            floor=f"WEBEEBLOCKS_A5_FACTOR_MOTOR_NATIVE_FLOOR variant={variant} " in trace
            native_fatal=("WEBEEBLOCKS_A5_FACTOR_MOTOR_FATAL" in trace or
                          "WEBEEBLOCKS_RUNTIME_V2 FATAL" in trace)
            browser_error=any(v.get("event")=="A5_FACTOR_MOTOR_ERROR"
                              for v in events.EVENTS)
            if (finished and floor) or native_fatal or browser_error or proc.poll() is not None:
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
    trace=log.read_text(encoding="utf-8",errors="replace")
    names=[v["event"] for v in events.EVENTS]
    if mode=="blind":
        # A fixed left-side G choice in G-right MUST physically hit a Solid.
        collision=re.search(
            r"WEBEEBLOCKS_A5_FACTOR_MOTOR_SWEPT_COLLISION "
            r"variant=B collider=(G_SIDE_ARM|G_UPPER) ",
            trace) is not None
        native_fatal="WEBEEBLOCKS_A5_FACTOR_MOTOR_FATAL reason=swept_physical_box_intersection" in trace
        good=(collision and native_fatal and
              "A5_FACTOR_MOTOR_G_OBSERVATION" in names and
              "A5_FACTOR_MOTOR_LAND_ACK" not in names and
              "WEBEEBLOCKS_A5_FACTOR_MOTOR_NATIVE_FLOOR" not in trace)
        summary={"variant":variant,"mode":mode,"pass":good,
                 "native_collision":collision,"swept_rejection":native_fatal,
                 "student_wbb":False,"events":names}
        summary_path.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
        if not good:
            print("A5_FACTOR_BLIND_PHYSICAL_REJECTION_UNPROVEN "+
                  json.dumps(summary),file=sys.stderr)
            print(trace[-6500:],file=sys.stderr)
            raise AssertionError("blind G-right did not prove physical invalidity")
        print("WEBEEBLOCKS_A5_FACTOR_MOTOR_BLIND_NATIVE_REJECTED "
              "variant=B collider=G test_only=true",flush=True)
        return summary
    missing=[k for k in REQUIRED if names.count(k)!=1]
    ordered=not missing and [names.index(k) for k in REQUIRED]==sorted(
        names.index(k) for k in REQUIRED)
    detail=lambda key:next((v.get("detail") for v in events.EVENTS
                            if v.get("event")==key),None)
    sensor=detail("A5_FACTOR_MOTOR_G_OBSERVATION")
    pad=detail("A5_FACTOR_MOTOR_PAD_SELECTED")
    measured=sensor.get("left_m") if isinstance(sensor,dict) else None
    native_read=re.findall(
        r"(?m)^WEBEEBLOCKS_RUNTIME_V2 TRACE RANGE left value=([0-9.]+)$",
        trace)
    native_reply=re.findall(
        r"(?m)^WEBEEBLOCKS_RUNTIME_V2 RESPONSE 7 VALUE ([0-9.]+)$",
        trace)
    contact=re.findall(
        rf"WEBEEBLOCKS_A5_FACTOR_MOTOR_NATIVE_FLOOR variant={variant} "
        r"x=(-?[0-9.]+) y=(-?[0-9.]+) z=(-?[0-9.]+) t=([0-9.]+)",
        trace)
    xyz=[float(v) for v in contact[0]] if len(contact)==1 else None
    land_at=trace.rfind("WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1")
    last_command=13 if variant=="A" else 15
    landed=land_at>=0 and re.search(
        rf"(?m)^WEBEEBLOCKS_RUNTIME_V2 RESPONSE {last_command} OK$",
        trace[land_at:]) is not None
    coverage=native_collision_coverage(trace,variant)
    expected_route="left" if variant=="A" else "right"
    expected_value=1.41 if variant=="A" else .54
    errors=any(marker in trace for marker in (
        "WEBEEBLOCKS_A5_FACTOR_MOTOR_FATAL",
        "WEBEEBLOCKS_RUNTIME_V2 FATAL",
        "WEBEEBLOCKS_A5_FACTOR_MOTOR_OBSTACLE_CONTACT",
        "WEBEEBLOCKS_A5_FACTOR_MOTOR_SWEPT_COLLISION"))
    good=(not missing and ordered and
          names.count("A5_FACTOR_MOTOR_ERROR")==0 and
          "WEBEEBLOCKS_RUNTIME_V2 READY" in trace and
          f"WEBEEBLOCKS_A5_FACTOR_MOTOR_SCENE_OK variant={variant}" in trace and
          isinstance(sensor,dict) and sensor.get("route")==expected_route and
          sensor.get("decision_source")=="late_left_only" and
          isinstance(pad,dict) and pad.get("side")=="left" and
          pad.get("decision_source")=="fixed_H_experimental" and
          isinstance(measured,(int,float)) and math.isfinite(measured) and
          abs(measured-expected_value)<.12 and
          len(native_read)==1 and len(native_reply)==1 and
          abs(float(native_read[0])-measured)<1e-6 and
          abs(float(native_reply[0])-measured)<1e-6 and
          xyz is not None and abs(xyz[0]-4.15)<.10 and
          abs(xyz[1]-.62)<.10 and 0<=xyz[2]<=.025 and xyz[3]>2.0 and
          coverage is not None and landed and not errors and
          "TRACE RANGE left" in trace and
          "WEBEEBLOCKS_RUNTIME_V2 TRACE TAKEOFF" in trace and
          trace.count("WEBEEBLOCKS_RUNTIME_V2 TRACE TURN angle_deg=")>=2 and
          "WEBEEBLOCKS_RUNTIME_V2 TRACE MOVE forward distance=0.600000000" in trace)
    summary={"schema":"webeeblocks-a5-gfactor-pid-private-v1",
             "variant":variant,"mode":mode,"pass":good,
             "actual_pid":True,"native_range_left_m":measured,
             "native_floor_xyzt":xyz,"native_land_ack":landed,
             "collision_coverage":coverage,"selected_G_route":expected_route,
             "selected_H_pad":"left","early_G_read":False,
             "same_private_js":True,"student_wbb":False,
             "mission_oracle":False,"events":names,
             "missing_events":missing,"ordered":ordered,"fatal":errors,
             "private_js_sha256":hashlib.sha256(
                 (ROOT/"plugins/robot_windows/a5_factor_motor_probe/a5_factor_motor_probe.js"
                 ).read_bytes()).hexdigest()}
    summary_path.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",
                            encoding="utf-8")
    if not good:
        print("WEBEEBLOCKS_A5_FACTOR_MOTOR_UNPROVEN "+
              json.dumps(summary),file=sys.stderr,flush=True)
        print(trace[-8500:],file=sys.stderr)
        raise AssertionError("native motor G route, real Floor or noncollision unproven")
    print(f"WEBEEBLOCKS_A5_FACTOR_MOTOR_NATIVE_PASS variant={variant} "
          f"late_left_m={measured:.9f} "
          f"steps={coverage['continuous_native_steps']} "
          "true_floor=true collision_free=true pupil_wbb=UNPROVEN",flush=True)
    return summary

def main():
    a=run("A")
    b=run("B")
    if (not a["pass"] or not b["pass"] or
        a["private_js_sha256"]!=b["private_js_sha256"] or
        a["native_range_left_m"]-b["native_range_left_m"]<.35 or
        a["selected_G_route"]!="left" or b["selected_G_route"]!="right" or
        a["selected_H_pad"]!="left" or b["selected_H_pad"]!="left"):
        raise AssertionError("native G choice not independent of fixed H")
    OUT_SUM=ARTIFACT/"summary.json"
    OUT_SUM.write_text(json.dumps({
        "schema":"webeeblocks-a5-hfixed-gbinary-motor-v1",
        "pass":True,"variants":[a,b],"single_private_js":True,
        "genuine_motors_and_pid":True,"two_real_floor_contacts":True,
        "native_swept_and_contact_7_solid":True,
        "pupil_wbb_or_full_mission_proven":False
    },sort_keys=True,indent=2)+"\n")
    print("WEBEEBLOCKS_A5_FACTOR_G_TWO_REAL_MOTOR_PASS "
          "native_swept_7=true same_js=true h_fixed=true pupil_wbb=false",
          flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--variant",choices=["A","B","both"],default="both")
    parser.add_argument("--blind",action="store_true")
    args=parser.parse_args()
    if args.blind:
        if args.variant!="both":parser.error("--blind checks only G-right")
        run("B","blind")
    elif args.variant=="both":main()
    else:run(args.variant)

#!/usr/bin/env python3
"""Draft-only physical motor/PID feasibility in A5 independently varying H/G worlds.

This intentionally runs a private same-JS pilot against four genuine Webots
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
ARTIFACT=ROOT/"ci-artifacts/progression-reactive-L-factor-motor"
REQUIRED=(
    "A5_FACTOR_HTML_LOADED","A5_FACTOR_MOTOR_JS_STARTED",
    "A5_FACTOR_MOTOR_READY","A5_FACTOR_MOTOR_SCENE_ACK",
    "A5_FACTOR_MOTOR_TAKEOFF","A5_FACTOR_MOTOR_H_OBSERVATION",
    "A5_FACTOR_MOTOR_APPROACH",
    "A5_FACTOR_MOTOR_G_OBSERVATION","A5_FACTOR_MOTOR_GATE_PASSED",
    "A5_FACTOR_MOTOR_PAD_SELECTED","A5_FACTOR_MOTOR_LAND_ACK",
    "A5_FACTOR_MOTOR_TEST_COMPLETE"
)

class Handler(events.Handler):
    variant="A"
    mode="positive"
    def do_GET(self):
        if self.path=="/a5-private-wbb" and self.mode in ("blockly","blockly_fixed"):
            source=ROOT/"ci-artifacts/progression-reactive-L-factor-blockly"/(
                "a5-private-fixed-front-ci-only.wbb" if
                self.mode=="blockly_fixed" else
                "a5-private-loop-state-ci-only.wbb")
            if not source.is_file() or not 100<=source.stat().st_size<=1048576:
                self.send_error(404,"bounded canonical private WBB absent")
                return
            raw=source.read_bytes()
        elif self.path=="/variant":
            raw=json.dumps({"variant":self.variant,"mode":self.mode}).encode("utf-8")
        else:
            self.send_error(404)
            return
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
    if variant not in ("A","B","C","D"):
        return None
    pattern=re.compile(
        r"(?m)^WEBEEBLOCKS_A5_FACTOR_MOTOR_MONITOR variant=([ABCD]) "
        r"ticks=(\d+) t=([0-9.]+) no_obstacle_contacts=true$")
    rows=pattern.findall(transcript)
    final=re.findall(
        r"(?m)^WEBEEBLOCKS_A5_FACTOR_MOTOR_MONITOR_COMPLETE "
        r"variant=([ABCD]) native_ticks=(\d+) all_contacts_checked=true "
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
    if variant not in ("A","B","C","D") or mode not in (
            "positive","blind","blind_h","blockly","blockly_fixed"):
        raise ValueError("wrong factorial H/G native test")
    if mode=="blind" and variant!="B":
        raise ValueError("blind gate rejection tested only against G-right")
    if mode=="blind_h" and variant!="C":
        raise ValueError("blind H rejection tested only against far-H / G-left")
    folder=ARTIFACT/("blind-B" if mode=="blind" else
                     "blind-h-C" if mode=="blind_h" else
                     "blockly-"+variant if mode=="blockly" else
                     "fixed-"+variant if mode=="blockly_fixed" else variant)
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
        # Capture the actual Chrome-launch boundary in the per-run archive.
        env["WEBEEBLOCKS_CI_ARTIFACT_DIR"]=str(folder)
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
        startup_deadline=time.monotonic()+28
        launch_log=folder/"browser-launch.log"
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
            if time.monotonic()>=startup_deadline and not events.EVENTS:
                print("WEBEEBLOCKS_A5_FACTOR_MOTOR_BROWSER_BOUNDARY_MISSING "
                      f"variant={variant} launched={launch_log.exists()} "
                      f"runtime_ready={'WEBEEBLOCKS_RUNTIME_V2 READY' in trace} "
                      "no_browser_event=true",file=sys.stderr,flush=True)
                break
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
    # The Webots GUI may discard env vars when launching Chrome. Preserve
    # the wrapper's fallback launch record rather than claiming launch=false.
    fallback=ROOT/"ci-artifacts/runtime-v2-webots/browser-launch.log"
    local=folder/"browser-launch.log"
    if fallback.exists() and not local.exists():
        import shutil
        shutil.copy2(fallback,local)
    names=[v["event"] for v in events.EVENTS]
    if not names:
        # Do not reinterpret a missing browser as a motor or physics failure.
        launch=folder/"browser-launch.log"
        diagnostic={"schema":"webeeblocks-a5-browser-boundary-v1",
                    "variant":variant,"mode":mode,
                    "runtime_ready":"WEBEEBLOCKS_RUNTIME_V2 READY" in trace,
                    "web_browser_invoked":launch.exists(),
                    "browser_events":0,"native_motor_attempted":False,
                    "physical_gate_refuted":False}
        summary_path.write_text(json.dumps(diagnostic,indent=2,sort_keys=True)+"\n")
        raise AssertionError("browser boundary unobserved; motor trial NOT RUN")
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
    if mode=="blind_h":
        # The wrong pad is attested ONLY by actual native Floor contact and
        # physical XYZ in the independent C monitor, never by JavaScript.
        wrong=re.findall(
            r"(?m)^WEBEEBLOCKS_A5_FACTOR_MOTOR_WRONG_PAD_NATIVE "
            r"variant=C x=(-?[0-9.]+) y=(-?[0-9.]+) "
            r"z=(-?[0-9.]+) t=([0-9.]+)$",trace)
        contact=list(map(float,wrong[0])) if len(wrong)==1 else None
        def observed(key):
            matches=[e.get("detail") for e in events.EVENTS if e.get("event")==key]
            return matches[0] if len(matches)==1 else None
        h=observed("A5_FACTOR_MOTOR_H_OBSERVATION")
        g=observed("A5_FACTOR_MOTOR_G_OBSERVATION")
        pad=observed("A5_FACTOR_MOTOR_PAD_SELECTED")
        # LAND ACK attests execution of a primitive, not a successful
        # classroom mission. A wrong-pad flight can acknowledge LAND and
        # complete its private script while the native observer rejects it.
        land=observed("A5_FACTOR_MOTOR_LAND_ACK")
        finished=observed("A5_FACTOR_MOTOR_TEST_COMPLETE")
        good=(contact is not None and all(math.isfinite(v) for v in contact) and
              abs(contact[0]-4.15)<.10 and abs(contact[1]-.62)<.10 and
              0<=contact[2]<=.025 and contact[3]>2 and
              isinstance(h,dict) and
              isinstance(h.get("left_m"),(float,int)) and
              abs(h["left_m"]-1.14)<.12 and
              h.get("destination")=="left" and
              h.get("decision_source")=="blind_fixed_left" and
              isinstance(g,dict) and
              isinstance(g.get("left_m"),(float,int)) and
              abs(g["left_m"]-1.41)<.12 and
              g.get("route")=="left" and
              g.get("decision_source")=="late_left_only" and
              isinstance(pad,dict) and pad.get("side")=="left" and
              pad.get("decision_source")=="blind_fixed_left" and
              "A5_FACTOR_MOTOR_GATE_PASSED" in names and
              "WEBEEBLOCKS_A5_FACTOR_MOTOR_FATAL reason=premature_floor_contact" in trace and
              "WEBEEBLOCKS_A5_FACTOR_MOTOR_OBSTACLE_CONTACT" not in trace and
              "WEBEEBLOCKS_A5_FACTOR_MOTOR_SWEPT_COLLISION" not in trace and
              "WEBEEBLOCKS_A5_FACTOR_MOTOR_NATIVE_FLOOR" not in trace and
              isinstance(land,dict) and land.get("nativeReply") is True and
              isinstance(finished,dict) and
              finished.get("nativeReply") is True and
              finished.get("pupilWbb") is False and
              finished.get("missionOracle") is False)
        summary={"schema":"webeeblocks-a5-hblind-native-negative-v1",
                 "variant":variant,"mode":mode,"pass":good,
                 "real_wrong_pad_floor":contact,"h_sensor_seen":h,
                 "g_sensor_seen":g,"pad_selected":pad,
                 "no_false_mission_success":good,"student_wbb":False,
                 "land_command_ack":land,
                 "private_program_completed":finished,
                 "mission_oracle":False,"events":names}
        summary_path.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
        if not good:
            print("A5_FACTOR_H_BLIND_NATIVE_REJECTION_UNPROVEN "+
                  json.dumps(summary),file=sys.stderr)
            print(trace[-6500:],file=sys.stderr)
            raise AssertionError("blind H did not reach a genuine wrong Floor pad")
        print("WEBEEBLOCKS_A5_FACTOR_H_BLIND_NATIVE_REJECTED "
              "variant=C wrong_pad=left H_requires_right true_floor=true",
              flush=True)
        return summary
    if mode in ("blockly","blockly_fixed"):
        # Real pupil-format Blockly, never scene metadata or an AST shortcut.
        # One adversary omits ALL front readings; same H/G/Pad C monitor.
        fixed=mode=="blockly_fixed"
        wbb=ROOT/"ci-artifacts/progression-reactive-L-factor-blockly"/(
            "a5-private-fixed-front-ci-only.wbb" if fixed else
            "a5-private-loop-state-ci-only.wbb")
        expected_sha=hashlib.sha256(wbb.read_bytes()).hexdigest()
        def single(name):
            found=[e.get("detail") for e in events.EVENTS if e.get("event")==name]
            return found[0] if len(found)==1 else None
        reopened=single("A5_FACTOR_MOTOR_WBB_REOPENED")
        h=single("A5_FACTOR_MOTOR_H_OBSERVATION")
        approach=single("A5_FACTOR_MOTOR_APPROACH")
        g=single("A5_FACTOR_MOTOR_G_OBSERVATION")
        passed=single("A5_FACTOR_MOTOR_GATE_PASSED")
        pad=single("A5_FACTOR_MOTOR_PAD_SELECTED")
        land=single("A5_FACTOR_MOTOR_LAND_ACK")
        finished=single("A5_FACTOR_MOTOR_TEST_COMPLETE")
        left_reads=re.findall(
            r"(?m)^WEBEEBLOCKS_RUNTIME_V2 TRACE RANGE left value=([0-9.]+)$",
            trace)
        front_reads=re.findall(
            r"(?m)^WEBEEBLOCKS_RUNTIME_V2 TRACE RANGE front value=([0-9.]+)$",
            trace)
        contact=re.findall(
            rf"(?m)^WEBEEBLOCKS_A5_FACTOR_MOTOR_NATIVE_FLOOR variant={variant} "
            r"x=(-?[0-9.]+) y=(-?[0-9.]+) z=(-?[0-9.]+) t=([0-9.]+)$",trace)
        xyz=[float(v) for v in contact[0]] if len(contact)==1 else None
        coverage=native_collision_coverage(trace,variant)
        expected_h=.54 if variant in ("A","B") else 1.14
        expected_g=1.41 if variant in ("A","C") else .54
        route="left" if variant in ("A","C") else "right"
        destination="left" if variant in ("A","B") else "right"
        good=(
            reopened is not None and reopened.get("sha256")==expected_sha and
            reopened.get("one_variable") is True and
            reopened.get("fresh_front_loop") is (not fixed) and
            reopened.get("fixed_front_blind") is fixed and
            isinstance(h,dict) and isinstance(h.get("left_m"),(float,int)) and
            abs(h["left_m"]-expected_h)<.12 and
            h.get("destination")==destination and
            isinstance(approach,dict) and
            approach.get("fresh_condition") is (not fixed) and
            approach.get("fixed_blind_front") is fixed and
            isinstance(g,dict) and isinstance(g.get("left_m"),(float,int)) and
            abs(g["left_m"]-expected_g)<.12 and
            g.get("route")==route and
            isinstance(passed,dict) and passed.get("route")==route and
            isinstance(pad,dict) and pad.get("side")==destination and
            isinstance(land,dict) and land.get("nativeReply") is True and
            isinstance(finished,dict) and
            finished.get("sha256")==expected_sha and
            finished.get("blockly") is True and
            finished.get("fixed_front_blind") is fixed and
            finished.get("missionOracle") is False and
            len(left_reads)==2 and
            all(math.isfinite(float(v)) for v in left_reads) and
            abs(float(left_reads[0])-h["left_m"])<1e-6 and
            abs(float(left_reads[1])-g["left_m"])<1e-6 and
            (len(front_reads)==0 if fixed else
             21<=len(front_reads)<=33) and
            approach.get("front_reads")==len(front_reads) and
            finished.get("front_reads")==len(front_reads) and
            xyz is not None and abs(xyz[0]-4.15)<.10 and
            abs(xyz[1]-(.62 if destination=="left" else -.62))<.10 and
            0<=xyz[2]<=.025 and
            coverage is not None and
            "WEBEEBLOCKS_RUNTIME_V2 TRACE TAKEOFF" in trace and
            "WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1" in trace and
            f"WEBEEBLOCKS_A5_FACTOR_MOTOR_SCENE_OK variant={variant}" in trace and
            "WEBEEBLOCKS_RUNTIME_V2 READY" in trace and
            "A5_FACTOR_MOTOR_ERROR" not in names and
            not any(marker in trace for marker in (
                "WEBEEBLOCKS_A5_FACTOR_MOTOR_FATAL",
                "WEBEEBLOCKS_RUNTIME_V2 FATAL",
                "WEBEEBLOCKS_A5_FACTOR_MOTOR_OBSTACLE_CONTACT",
                "WEBEEBLOCKS_A5_FACTOR_MOTOR_SWEPT_COLLISION"))
        )
        summary={"schema":"webeeblocks-a5-hg-private-real-wbb-r2025a-v1",
                 "variant":variant,"mode":mode,"pass":bool(good),
                 "sha256":expected_sha,"source":"real Blockly .wbb",
                 "front_native_reads":len(front_reads),
                 "fixed_front_blind":fixed,
                 "left_native_reads":len(left_reads),
                 "native_floor_xyzt":xyz,"collision_coverage":coverage,
                 "native_motor_attempted":True,
                 "pupil_published":False,"mission_oracle_proven":False,
                 "windows_save_open_proven":False,"events":names}
        summary_path.write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
        if not good:
            print("WEBEEBLOCKS_A5_PRIVATE_REAL_WBB_NATIVE_UNPROVEN "+
                  json.dumps(summary),file=sys.stderr,flush=True)
            print(trace[-8500:],file=sys.stderr)
            raise AssertionError("A5 genuine private WBB flight not fully proven")
        marker=("WEBEEBLOCKS_A5_PRIVATE_FIXED_FRONT_NATIVE_PASS" if fixed
                else "WEBEEBLOCKS_A5_PRIVATE_REAL_WBB_NATIVE_PASS")
        print(marker+" "+
              f"variant={variant} real_floor=true front_reads={len(front_reads)} "+
              "same_wbb=true physical_swept_7=true pupil_published=false",
              flush=True)
        return summary
    missing=[k for k in REQUIRED if names.count(k)!=1]
    ordered=not missing and [names.index(k) for k in REQUIRED]==sorted(
        names.index(k) for k in REQUIRED)
    detail=lambda key:next((v.get("detail") for v in events.EVENTS
                            if v.get("event")==key),None)
    sensor=detail("A5_FACTOR_MOTOR_G_OBSERVATION")
    h=detail("A5_FACTOR_MOTOR_H_OBSERVATION")
    pad=detail("A5_FACTOR_MOTOR_PAD_SELECTED")
    measured=sensor.get("left_m") if isinstance(sensor,dict) else None
    initial=h.get("left_m") if isinstance(h,dict) else None
    native_read=re.findall(
        r"(?m)^WEBEEBLOCKS_RUNTIME_V2 TRACE RANGE left value=([0-9.]+)$",
        trace)
    native_h_reply=re.findall(
        r"(?m)^WEBEEBLOCKS_RUNTIME_V2 RESPONSE 4 VALUE ([0-9.]+)$",
        trace)
    native_g_reply=re.findall(
        r"(?m)^WEBEEBLOCKS_RUNTIME_V2 RESPONSE 8 VALUE ([0-9.]+)$",
        trace)
    contact=re.findall(
        rf"WEBEEBLOCKS_A5_FACTOR_MOTOR_NATIVE_FLOOR variant={variant} "
        r"x=(-?[0-9.]+) y=(-?[0-9.]+) z=(-?[0-9.]+) t=([0-9.]+)",
        trace)
    xyz=[float(v) for v in contact[0]] if len(contact)==1 else None
    land_at=trace.rfind("WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1")
    # Extra genuine H range is WWI request 4, G is request 8.
    # An opposite landing side needs two more genuine commands.
    shifted=variant in ("B","C")
    last_command=16 if shifted else 14
    landed=land_at>=0 and re.search(
        rf"(?m)^WEBEEBLOCKS_RUNTIME_V2 RESPONSE {last_command} OK$",
        trace[land_at:]) is not None
    coverage=native_collision_coverage(trace,variant)
    expected_route="left" if variant in ("A","C") else "right"
    expected_value=1.41 if variant in ("A","C") else .54
    expected_initial=.54 if variant in ("A","B") else 1.14
    expected_pad="left" if variant in ("A","B") else "right"
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
          isinstance(h,dict) and h.get("destination")==expected_pad and
          h.get("decision_source")=="initial_left_only" and
          isinstance(pad,dict) and pad.get("side")==expected_pad and
          pad.get("decision_source")=="initial_left_only" and
          isinstance(initial,(int,float)) and math.isfinite(initial) and
          abs(initial-expected_initial)<.12 and
          isinstance(measured,(int,float)) and math.isfinite(measured) and
          abs(measured-expected_value)<.12 and
          len(native_read)==2 and len(native_h_reply)==1 and
          len(native_g_reply)==1 and
          abs(float(native_read[0])-initial)<1e-6 and
          abs(float(native_h_reply[0])-initial)<1e-6 and
          abs(float(native_read[1])-measured)<1e-6 and
          abs(float(native_g_reply[0])-measured)<1e-6 and
          xyz is not None and abs(xyz[0]-4.15)<.10 and
          abs(xyz[1]-(.62 if expected_pad=="left" else -.62))<.10 and
          0<=xyz[2]<=.025 and xyz[3]>2.0 and
          coverage is not None and landed and not errors and
          "TRACE RANGE left" in trace and
          "WEBEEBLOCKS_RUNTIME_V2 TRACE TAKEOFF" in trace and
          trace.count("WEBEEBLOCKS_RUNTIME_V2 TRACE TURN angle_deg=")>=2 and
          "WEBEEBLOCKS_RUNTIME_V2 TRACE MOVE forward distance=0.600000000" in trace)
    summary={"schema":"webeeblocks-a5-hg-factor-pid-private-v1",
             "variant":variant,"mode":mode,"pass":good,
             "actual_pid":True,
             "native_initial_h_left_m":initial,
             "native_range_left_m":measured,
             "native_floor_xyzt":xyz,"native_land_ack":landed,
             "collision_coverage":coverage,"selected_G_route":expected_route,
             "selected_H_pad":expected_pad,"early_G_read":False,
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
    results=[run(var) for var in ("A","B","C","D")]
    a,b,c,d=results
    if (not all(r["pass"] for r in results) or
        len({r["private_js_sha256"] for r in results})!=1 or
        any(results[i]["native_range_left_m"]-
            results[i+1]["native_range_left_m"]<.35 for i in (0,2)) or
        abs(a["native_initial_h_left_m"]-c["native_initial_h_left_m"])<.35 or
        abs(b["native_initial_h_left_m"]-d["native_initial_h_left_m"])<.35 or
        a["selected_G_route"]!="left" or b["selected_G_route"]!="right" or
        c["selected_G_route"]!="left" or d["selected_G_route"]!="right" or
        [r["selected_H_pad"] for r in results]!=["left","left","right","right"]):
        raise AssertionError("actual PID H/G factors not independently handled")
    OUT_SUM=ARTIFACT/"summary.json"
    OUT_SUM.write_text(json.dumps({
        "schema":"webeeblocks-a5-hg-four-world-motor-v1",
        "pass":True,"variants":results,"single_private_js":True,
        "genuine_motors_and_pid":True,"four_real_floor_contacts":True,
        "native_swept_and_contact_7_solid":True,
        "pupil_wbb_or_full_mission_proven":False
    },sort_keys=True,indent=2)+"\n")
    print("WEBEEBLOCKS_A5_FACTOR_HG_FOUR_REAL_MOTOR_PASS "
          "native_swept_7=true same_js=true "
          "H_and_G_read_at_distinct_times=true pupil_wbb=false",
          flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--variant",choices=["A","B","C","D","both"],default="both")
    parser.add_argument("--blind",action="store_true")
    parser.add_argument("--blind-h",action="store_true")
    parser.add_argument("--blockly",action="store_true")
    parser.add_argument("--blockly-fixed",action="store_true")
    args=parser.parse_args()
    if sum((args.blind,args.blind_h,args.blockly,args.blockly_fixed))>1:
        parser.error("modes are mutually exclusive")
    if args.blockly or args.blockly_fixed:
        if args.variant!="both":parser.error("private Blockly must test all A/B/C/D")
        mode="blockly_fixed" if args.blockly_fixed else "blockly"
        results=[run(v,mode) for v in "ABCD"]
        if len({r["sha256"] for r in results})!=1:
            raise AssertionError("A5 four real same-strategy .wbb files differ")
        if args.blockly_fixed:
            if any(r["front_native_reads"]!=0 or
                   r["fixed_front_blind"] is not True for r in results):
                raise AssertionError("fixed competitor unexpectedly used front")
            print("WEBEEBLOCKS_A5_PRIVATE_FOUR_REAL_FIXED_WBB_NATIVE_PASS "+
                  "same_wbb=true front_reads=0 real_webots=true "
                  "pupil_unpublished=true",flush=True)
        else:
            print("WEBEEBLOCKS_A5_PRIVATE_FOUR_REAL_WBB_NATIVE_PASS "+
                  "same_wbb=true real_webots=true pupil_unpublished=true",flush=True)
    elif args.blind_h:
        if args.variant!="both":parser.error("--blind-h checks only H-far G-left")
        run("C","blind_h")
    elif args.blind:
        if args.variant!="both":parser.error("--blind checks only G-right")
        run("B","blind")
    elif args.variant=="both":main()
    else:run(args.variant)

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
import prepare_classroom_reactive_L_length_motor as world

ROOT=world.ROOT
ARTIFACT=ROOT/"ci-artifacts/progression-reactive-L-length-motor"
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
        if self.path=="/a5-private-wbb" and self.mode in ("blockly","blockly_fixed","blockly_snapshot","blockly_no_variable"):
            source=ROOT/"ci-artifacts/progression-reactive-L-factor-blockly"/(
                "a5-private-fixed-front-ci-only.wbb" if
                self.mode=="blockly_fixed" else
                "a5-private-single-snapshot-ci-only.wbb" if
                self.mode=="blockly_snapshot" else
                "a5-private-no-variable-ci-only.wbb" if
                self.mode=="blockly_no_variable" else
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
    executable=ROOT/"controllers/progression_reactive_L_length_motor_pilot"/(
        "progression_reactive_L_length_motor_pilot")
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
        r"(?m)^WEBEEBLOCKS_A5_LENGTH_MOTOR_MONITOR variant=([ABCD]) "
        r"ticks=(\d+) t=([0-9.]+) no_obstacle_contacts=true$")
    rows=pattern.findall(transcript)
    final=re.findall(
        r"(?m)^WEBEEBLOCKS_A5_LENGTH_MOTOR_MONITOR_COMPLETE "
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
    if ("WEBEEBLOCKS_A5_LENGTH_MOTOR_OBSTACLE_CONTACT" in transcript or
        "WEBEEBLOCKS_A5_LENGTH_MOTOR_SWEPT_COLLISION" in transcript or
        "WEBEEBLOCKS_A5_LENGTH_MOTOR_FATAL" in transcript):
        return None
    return {"continuous_native_steps":final_tick,
            "native_heartbeat_count":len(rows),
            "seven_physical_boxes_and_craft_contacts_each_step":True,
            "conservative_swept_boxes_per_step":True}

def run(variant,mode="positive"):
    if variant not in ("A","B","C","D") or mode not in ("blockly","blockly_fixed","blockly_snapshot","blockly_no_variable"):
        raise ValueError("only two private genuine Blockly length modes")
    folder=ARTIFACT/({"blockly":"reactive","blockly_fixed":"fixed",
      "blockly_snapshot":"snapshot","blockly_no_variable":"no-variable"}[mode]+"-"+variant)
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
            floor=f"WEBEEBLOCKS_A5_LENGTH_MOTOR_NATIVE_FLOOR variant={variant} " in trace
            native_fatal=("WEBEEBLOCKS_A5_LENGTH_MOTOR_FATAL" in trace or
                          "WEBEEBLOCKS_RUNTIME_V2 FATAL" in trace)
            browser_error=any(v.get("event")=="A5_FACTOR_MOTOR_ERROR"
                              for v in events.EVENTS)
            if time.monotonic()>=startup_deadline and not events.EVENTS:
                print("WEBEEBLOCKS_A5_LENGTH_MOTOR_BROWSER_BOUNDARY_MISSING "
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

    # Student-format bytes are actually reopened inside Chrome's Robot Window;
    # only the native independent C monitor can attest physical success/failure.
    fixed=mode=="blockly_fixed"
    snapshot=mode=="blockly_snapshot"
    no_variable=mode=="blockly_no_variable"
    reactive=mode=="blockly"
    path=ROOT/"ci-artifacts/progression-reactive-L-factor-blockly"/(
        "a5-private-fixed-front-ci-only.wbb" if fixed else
        "a5-private-single-snapshot-ci-only.wbb" if snapshot else
        "a5-private-no-variable-ci-only.wbb" if no_variable else
        "a5-private-loop-state-ci-only.wbb")
    if not path.is_file() or not 100<=path.stat().st_size<=1048576:
        raise AssertionError("expected private canonical WBB missing")
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    def unique(name):
        vals=[e.get("detail") for e in events.EVENTS if e.get("event")==name]
        return vals[0] if len(vals)==1 and isinstance(vals[0],dict) else {}
    opened=unique("A5_FACTOR_MOTOR_WBB_REOPENED")
    h=unique("A5_FACTOR_MOTOR_H_OBSERVATION")
    g=unique("A5_FACTOR_MOTOR_G_OBSERVATION")
    approach=unique("A5_FACTOR_MOTOR_APPROACH")
    passed=unique("A5_FACTOR_MOTOR_GATE_PASSED")
    pad=unique("A5_FACTOR_MOTOR_PAD_SELECTED")
    land=unique("A5_FACTOR_MOTOR_LAND_ACK")
    complete=unique("A5_FACTOR_MOTOR_TEST_COMPLETE")
    left=[float(v) for v in re.findall(
        r"(?m)^WEBEEBLOCKS_RUNTIME_V2 TRACE RANGE left value=([0-9.]+)$",trace)]
    fronts=[float(v) for v in re.findall(
        r"(?m)^WEBEEBLOCKS_RUNTIME_V2 TRACE RANGE front value=([0-9.]+)$",trace)]
    def physical(marker):
        rows=re.findall(
            rf"(?m)^WEBEEBLOCKS_A5_LENGTH_MOTOR_{marker} variant={variant} "
            r"x=(-?[0-9.]+) y=(-?[0-9.]+) z=(-?[0-9.]+) t=([0-9.]+)$",trace)
        return list(map(float,rows[0])) if len(rows)==1 else None
    floor=physical("NATIVE_FLOOR")
    wrong=physical("WRONG_X_NATIVE")
    target_x=3.95 if variant in ("A","B") else 4.35
    side="left" if variant in ("A","C") else "right"
    expected_g=1.41 if side=="left" else .54
    cover=native_collision_coverage(trace,variant)
    common=(opened.get("sha256")==sha and
       opened.get("one_variable") is (not no_variable) and
       opened.get("no_variable") is no_variable and
       opened.get("fresh_front_loop") is (reactive or no_variable) and
       opened.get("fixed_front_blind") is fixed and
       opened.get("single_front_snapshot") is snapshot and
       ((not h and "A5_FACTOR_MOTOR_H_OBSERVATION" not in names)
        if no_variable else
        (isinstance(h.get("left_m"),(int,float)) and
         abs(h["left_m"]-.54)<.12 and h.get("destination")=="left")) and
       isinstance(g.get("left_m"),(int,float)) and
       abs(g["left_m"]-expected_g)<.12 and g.get("route")==side and
       approach.get("fresh_condition") is (reactive or no_variable) and
       approach.get("no_variable") is no_variable and
       approach.get("fixed_blind_front") is fixed and
       approach.get("single_front_snapshot") is snapshot and
       passed.get("route")==side and pad.get("side")=="left" and
       pad.get("decision_source")==("constant_left_no_H_read" if no_variable
                                    else "initial_left_only") and
       ((len(left)==1 and abs(left[0]-expected_g)<.12) if no_variable else
        (len(left)==2 and abs(left[0]-.54)<.12 and
         abs(left[1]-expected_g)<.12)) and
       (len(fronts)==0 if fixed else
        len(fronts)==1 if snapshot else 20<=len(fronts)<=32) and
       f"WEBEEBLOCKS_A5_LENGTH_MOTOR_SCENE_OK variant={variant} " in trace and
       "WEBEEBLOCKS_RUNTIME_V2 TRACE TAKEOFF" in trace and
       "WEBEEBLOCKS_RUNTIME_V2 READY" in trace and
       "WEBEEBLOCKS_A5_LENGTH_MOTOR_OBSTACLE_CONTACT" not in trace and
       "WEBEEBLOCKS_A5_LENGTH_MOTOR_SWEPT_COLLISION" not in trace and
       "WEBEEBLOCKS_RUNTIME_V2 FATAL" not in trace and
       "A5_FACTOR_MOTOR_ERROR" not in names)
    if fixed:
        good=(common and floor is None and wrong is not None and
              all(math.isfinite(v) for v in wrong) and
              abs(wrong[0]-target_x)>.10 and abs(wrong[1]-.62)<=.10 and
              0<=wrong[2]<=.025 and wrong[3]>0 and
              "WEBEEBLOCKS_A5_LENGTH_MOTOR_FATAL reason=premature_floor_contact" in trace and
              "WEBEEBLOCKS_A5_LENGTH_MOTOR_NATIVE_FLOOR" not in trace and
              "WEBEEBLOCKS_A5_LENGTH_MOTOR_MONITOR_COMPLETE" not in trace)
    else:
        good=(common and wrong is None and floor is not None and
              all(math.isfinite(v) for v in floor) and
              abs(floor[0]-target_x)<=.10 and abs(floor[1]-.62)<=.10 and
              0<=floor[2]<=.025 and cover is not None and
              "WEBEEBLOCKS_A5_LENGTH_MOTOR_FATAL" not in trace and
              land.get("nativeReply") is True and
              complete.get("sha256")==sha and
              complete.get("missionOracle") is False and
              complete.get("fixed_front_blind") is False and
              complete.get("single_front_snapshot") is snapshot and
              complete.get("no_variable") is no_variable and
              "WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1" in trace)
    summary={"schema":"webeeblocks-a5-length-motor-private-native-v1",
             "variant":variant,"mode":mode,"pass":bool(good),
             "sha256":sha,"target_x":target_x,
             "native_floor_xyzt":floor,"native_wrong_x_xyzt":wrong,
             "native_coverage":cover,"front_native_reads":len(fronts),
             "left_native_reads":len(left),"no_variable":no_variable,
             "pupil_published":False,"mission_oracle":False}
    summary_path.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    if not good:
        print("WEBEEBLOCKS_A5_LENGTH_MOTOR_NATIVE_UNPROVEN "+
              json.dumps(summary),file=sys.stderr,flush=True)
        print(trace[-8500:],file=sys.stderr,flush=True)
        raise AssertionError("length motorized experiment did not prove expected physical result")
    label=("WEBEEBLOCKS_A5_LENGTH_FIXED_PHYSICAL_REJECTED" if fixed
           else "WEBEEBLOCKS_A5_LENGTH_NO_VARIABLE_NATIVE_PASS" if no_variable
            else "WEBEEBLOCKS_A5_LENGTH_SNAPSHOT_NATIVE_PASS" if snapshot
           else "WEBEEBLOCKS_A5_LENGTH_REACTIVE_NATIVE_PASS")
    print(label+f" variant={variant} front_native_reads={len(fronts)} "
          "native_32ms=true swept_7=true pupil_unpublished=true",flush=True)
    return summary

def main():
    # Independent falsification of loop necessity: four more genuine flights,
    # using exactly one front range read at a shared in-flight survey point.
    # The existing 8 positive/negative native trials remain unchanged.
    if len(sys.argv)>1:
        if sys.argv[1:]==["--no-variable"]:
            no_variable=[run(v,"blockly_no_variable") for v in "ABCD"]
            if len({r["sha256"] for r in no_variable})!=1:
                raise AssertionError("no-variable WBB changed between native worlds")
            if any(r["left_native_reads"]!=1 or r["no_variable"] is not True
                   for r in no_variable):
                raise AssertionError("no-variable WBB read H or stored state")
            print("WEBEEBLOCKS_A5_LENGTH_NO_VARIABLE_FOUR_PASS "
                  "one_late_left_per_world=true same_wbb=true independent_floor=true "
                  "native_32ms=true swept_7=true pupil_unpublished=true",flush=True)
            return
        if sys.argv[1:]!=["--snapshot"]:
            raise ValueError("only --snapshot or --no-variable private mode allowed")
        snapshot=[run(v,"blockly_snapshot") for v in "ABCD"]
        if len({r["sha256"] for r in snapshot})!=1:
            raise AssertionError("snapshot WBB changed between four native worlds")
        if any(r["front_native_reads"]!=1 for r in snapshot):
            raise AssertionError("single-snapshot program did not read front exactly once")
        print("WEBEEBLOCKS_A5_LENGTH_SINGLE_SNAPSHOT_NATIVE_FOUR_PASS "
              "one_front_per_world=true same_wbb=true independent_floor=true "
              "native_32ms=true swept_7=true pupil_unpublished=true",flush=True)
        return
    reactive=[run(v,"blockly") for v in "ABCD"]
    fixed=[run(v,"blockly_fixed") for v in "ABCD"]
    if (len({r["sha256"] for r in reactive})!=1 or
        len({r["sha256"] for r in fixed})!=1 or
        reactive[0]["sha256"]==fixed[0]["sha256"]):
        raise AssertionError("candidate changed across worlds or strategies")
    if any(r["front_native_reads"]!=0 for r in fixed):
        raise AssertionError("fixed program read front")
    print("WEBEEBLOCKS_A5_LENGTH_TWO_REAL_WBB_PHYSICAL_DISCRIMINATION_PASS "
          "four_reactive_floor=true four_fixed_wrong_x=true "
          "same_wbb_per_strategy=true real_webots=true pupil_unpublished=true",flush=True)

if __name__=="__main__":
    main()

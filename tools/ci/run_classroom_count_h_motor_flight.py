#!/usr/bin/env python3
"""A6 n=1..3 genuine motor-flight witness (diagnostic, NOT a pupil .wbb PASS)."""
from __future__ import annotations
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import http.client
import argparse

import prepare_classroom_count_h_motor_flight as world
from analyze_count_h_up_motor_evidence import attest_up_motor_trace
from analyze_count_h_dual_motor_sensor import inspect_motor_sensor_count
import run_classroom_altitude_scene_ack as observer

ARTIFACT=world.ARTIFACT
# Read-only HTTP probe to a candidate local Webots resource endpoint.
# Connection refusal or HTTP 404 is diagnostic; no availability is presumed.
# An HTTP 200 alone is never evidence that the Robot Window actually opened.
HTTP_PROBE_PATHS=(
    "/robot_windows/count_h_flight_probe/count_h_flight_probe.html",
    "/robot_windows/orientation_flight_probe/orientation_flight_probe.html",
)

def diagnose_webots_window_http():
    observed={}
    for path in HTTP_PROBE_PATHS:
        conn=http.client.HTTPConnection("127.0.0.1",1234,timeout=2)
        try:
            conn.request("GET",path)
            resp=conn.getresponse()
            observed[path]={"status":resp.status,
                            "content_type":resp.getheader("Content-Type")}
            resp.read()
        except (OSError,TimeoutError,http.client.HTTPException) as error:
            observed[path]={"error_type":type(error).__name__}
        finally:
            conn.close()
    return observed

class A6VariantHandler(observer.Handler):
    """Only CI launch configuration; native Webots re-attests identity."""
    variant = 1
    mode = "reference"

    def do_GET(self):
        if self.path == "/a6-private-wbb":
            project=world.ROOT/"ci-artifacts/progression-count-h-private-blockly/a6-private.wbb"
            if (self.mode!="blockly" or not project.is_file() or project.is_symlink()
                    or project.stat().st_size<100 or project.stat().st_size>1048576):
                self.send_error(404)
                return
            data=project.read_bytes()
        elif self.path == "/a6-variant":
            data=json.dumps({"variant":self.variant,"mode":self.mode},
                            sort_keys=True).encode("utf-8")
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Length",str(len(data)))
        self.end_headers()
        self.wfile.write(data)

REQUIRED=("A6_HTML_LOADED","A6_JS_STARTED","A6_RUNTIME_READY",
          "A6_SCENE_ACK","A6_TAKEOFF","A6_CORRIDOR_DONE",
          "A6_PAD_SELECTED","A6_LANDED","A6_NATIVE_COMPLETION_ACK",
          "A6_TEST_COMPLETE")

def terminal_native_ack_logged(native_log, variant, mode="reference"):
    """Never kill Webots between C physical success and native LAND ACK."""
    if variant not in (1,2,3) or mode not in ("reference","sensor","blockly"):
        return False
    if f"WEBEEBLOCKS_A6_MOTOR_RESULT status=achieved n={variant} " not in native_log:
        return False
    if mode=="reference":
        final_id=11+(1 if variant!=1 else 0)
        return ("WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1" in native_log and
                re.search(rf"(?m)^WEBEEBLOCKS_RUNTIME_V2 RESPONSE {final_id} OK$",
                          native_log) is not None)
    pos=native_log.rfind("WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1")
    if pos<0:return False
    ack=re.search(r"(?m)^WEBEEBLOCKS_RUNTIME_V2 RESPONSE (\d+) OK$",
                  native_log[pos:])
    return ack is not None and int(ack[1])>=20


def run(variant=1,mode="reference",family=None):
    if type(variant) is not int or variant not in (1,2,3):
        raise ValueError("A6 experimental motor variant must be 1/2/3")
    if mode not in ("reference","sensor","blockly","replay"):
        raise ValueError("invalid bounded A6 pilot mode")
    if family is not None and (family not in ("matched","sampling") or mode!="reference"):
        raise ValueError("B private geometry witness accepts reference pilot only")
    global ARTIFACT
    ARTIFACT=(world.ARTIFACT/f"b-{family}-reference-n{variant}" if family is not None
              else world.ARTIFACT/f"n{variant}" if mode=="reference"
              else world.ARTIFACT/f"{mode}-n{variant}")
    ARTIFACT.mkdir(parents=True,exist_ok=True)
    if mode=="blockly":
        private=world.ROOT/"ci-artifacts/progression-count-h-private-blockly/a6-private.wbb"
        if (not private.is_file() or private.is_symlink() or
            private.stat().st_size<100 or private.stat().st_size>1048576):
            raise FileNotFoundError("canonical private Blockly CI witness missing")
    log=ARTIFACT/"webots.log"
    observer.EVENTS.clear()
    server=None; proc=None; output=None
    ready_since=None; http_diagnosis=None; early_browser_refusal=False
    manual_browser=None; browser_output=None; manual_started_at=None
    browser_auto_seen=False; manual_external_window=False
    try:
        for path in (
            world.ROOT/"controllers/progression_count_h_school_pilot/progression_count_h_school_pilot",
            world.ROOT/"controllers/progression_count_h_flight_observer/progression_count_h_flight_observer"
        ):
            if not path.is_file() or not path.stat().st_size:
                raise FileNotFoundError("native motor flight binary unavailable: "+str(path))
        world.prepare(variant=variant,family=family)
        A6VariantHandler.variant=variant
        A6VariantHandler.mode=mode
        server=observer.http.server.ThreadingHTTPServer(("127.0.0.1",8765),A6VariantHandler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        env=dict(os.environ)
        env["WEBOTS_WEB_BROWSER"]="/workspace/tools/ci/webots_runtime_v2_browser.sh"
        env["LIBGL_ALWAYS_SOFTWARE"]="true"
        env["WEBEEBLOCKS_CI_ARTIFACT_DIR"]=str(ARTIFACT)
        output=log.open("w",encoding="utf-8")
        proc=subprocess.Popen(
            ["timeout","-k","5s","390s","xvfb-run","-a","webots",
             "--stdout","--stderr","--batch","--mode=realtime",str(world.WORLD)],
            cwd=world.ROOT,env=env,stdout=output,
            stderr=subprocess.STDOUT,start_new_session=True)
        end=time.monotonic()+370
        while time.monotonic()<end:
            seen=[entry.get("event") for entry in observer.EVENTS]
            txt=log.read_text(encoding="utf-8",errors="replace")
            if ("WEBEEBLOCKS_RUNTIME_V2 READY" in txt and ready_since is None):
                ready_since=time.monotonic()
            if ready_since is not None:
                browserlog=ARTIFACT/"browser-launch.log"
                launched=(browserlog.is_file() and
                          "count_h_flight_probe.html" in browserlog.read_text(
                              encoding="utf-8",errors="replace"))
                if launched and manual_started_at is None:
                    browser_auto_seen=True
                if not launched and http_diagnosis is None and (
                        time.monotonic()-ready_since>=8):
                    http_diagnosis=diagnose_webots_window_http()
                # A CI-initiated browser is not evidence of product autolaunch.
                # Only native WWI, motor PID and the C oracle can prove flight.
                if not launched and not manual_external_window and (
                        time.monotonic()-ready_since>=10) and http_diagnosis:
                    target=HTTP_PROBE_PATHS[0]
                    if http_diagnosis.get(target,{}).get("status")==200:
                        page=("http://localhost:1234"+target+
                              "?name=Crazyflie%20WebeeBlocks")
                        browser_output=(ARTIFACT/"manual-browser.log").open(
                            "w",encoding="utf-8")
                        manual_browser=subprocess.Popen(
                            ["bash","/workspace/tools/ci/webots_runtime_v2_browser.sh",page],
                            cwd=world.ROOT,env=env,stdout=browser_output,
                            stderr=subprocess.STDOUT,start_new_session=True)
                        manual_started_at=time.monotonic()
                        manual_external_window=True
                        print("WEBEEBLOCKS_A6_MOTOR_WINDOW_MANUAL_CI "
                              "http_status=200 product_autolaunch=false",flush=True)
                if (manual_started_at is not None and
                    "A6_HTML_LOADED" not in seen and
                    time.monotonic()-manual_started_at>=35):
                    early_browser_refusal=True
                    print("WEBEEBLOCKS_A6_MOTOR_WINDOW_REFUSED "
                          "reason=manual_browser_no_html_event seconds=35",
                          flush=True)
                    break
                if not launched and manual_started_at is None and (
                        time.monotonic()-ready_since>=60):
                    early_browser_refusal=True
                    print("WEBEEBLOCKS_A6_MOTOR_WINDOW_REFUSED "
                          "reason=browser_missing_after_native_READY "
                          "seconds=60",flush=True)
                    break
            if ((("A6_TEST_COMPLETE" in seen and
                  terminal_native_ack_logged(txt,variant,mode)) or
                 (mode=="replay" and "A6_REPLAY_TEST_COMPLETE" in seen and
                  "WEBEEBLOCKS_A6_MOTOR_NATIVE_COMPLETION attempt=3 " in txt))
                or "A6_ERROR" in seen
                or "WEBEEBLOCKS_A6_MOTOR_FATAL" in txt
                or "WEBEEBLOCKS_RUNTIME_V2 FATAL" in txt
                or proc.poll() is not None):
                break
            time.sleep(.25)
    finally:
        if manual_browser is not None and manual_browser.poll() is None:
            os.killpg(manual_browser.pid,signal.SIGTERM)
            try: manual_browser.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(manual_browser.pid,signal.SIGKILL)
                manual_browser.wait(timeout=5)
        if browser_output is not None:
            browser_output.close()
        if proc is not None and proc.poll() is None:
            os.killpg(proc.pid,signal.SIGTERM)
            try:proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL)
                proc.wait(timeout=8)
        if output is not None:output.close()
        if server is not None:
            server.shutdown()
            server.server_close()
        (ARTIFACT/"events.json").write_text(
            json.dumps(observer.EVENTS,indent=2,sort_keys=True)+"\n",
            encoding="utf-8")
        (ARTIFACT/"robot-window-http-diagnostic.json").write_text(
            json.dumps({
                "schema":"webeeblocks-a6-window-http-diag-v1",
                "ready_seen":ready_since is not None,
                "early_browser_refusal":early_browser_refusal,
                "http_resources":http_diagnosis,
                "manual_external_window":manual_external_window,
                "product_autolaunch_seen":browser_auto_seen,
                "browser_only_proven_by_launch_and_events":True,
            },indent=2,sort_keys=True)+"\n",encoding="utf-8")
        world.cleanup(artifacts=ARTIFACT)

    txt=log.read_text(encoding="utf-8",errors="replace")
    events=[x.get("event") for x in observer.EVENTS]
    missing=[e for e in REQUIRED if events.count(e)!=1]
    ordered=not missing and [events.index(x) for x in REQUIRED]==sorted(
        events.index(x) for x in REQUIRED)

    if mode=="replay":
        # No second Webots process is launched: this one log contains the
        # three broker epochs and two genuine motorized landing outcomes.
        epochs=re.findall(
            rf"WEBEEBLOCKS_A6_MOTOR_FRESH_EPOCH attempt=(\d+) variant={variant}\b",txt)
        positives=re.findall(
            rf"WEBEEBLOCKS_A6_MOTOR_RESULT status=achieved n={variant} "
            rf"crossed={variant} screen=1 observations=(\d+) "
            r"x=(-?[0-9.]+) y=(-?[0-9.]+) z=(-?[0-9.]+)",txt)
        pad_y={1:0.0,2:0.55,3:-0.55}[variant]
        completed=re.findall(
            r"WEBEEBLOCKS_A6_MOTOR_NATIVE_COMPLETION attempt=(\d+) "
            r"oracle=progression-count-h-v1 ",txt)
        expected=[
            "A6_HTML_LOADED","A6_JS_STARTED","A6_RUNTIME_READY",
            "A6_SCENE_ACK","A6_REPLAY_FIRST_NEGATIVE",
            "A6_REPLAY_RESET_ACK","A6_REPLAY_STALE_DENIED",
            "A6_REPLAY_POSITIVE","A6_REPLAY_RESET_ACK",
            "A6_REPLAY_STALE_DENIED","A6_REPLAY_POSITIVE",
            "A6_REPLAY_TEST_COMPLETE"]
        filtered=[e for e in events if e in set(expected)]
        pass_replay=(
            filtered==expected and events.count("A6_ERROR")==0 and
            epochs==["2","3"] and completed==["1","2","3"] and
            len(positives)==2 and
            all(int(obs)>100 and abs(float(x)-1.480)<=.060 and
                abs(float(y)-pad_y)<=.060 and 0.0<=float(z)<=.020
                for obs,x,y,z in positives) and
            txt.count(f"WEBEEBLOCKS_A6_MOTOR_NATIVE_FLOOR_CONTACT n={variant} ")==2 and
            txt.count("WEBEEBLOCKS_A6_MOTOR_RESULT status=achieved")==2 and
            txt.count("WEBEEBLOCKS_A6_MOTOR_REJECT attempt=1 behavioral_oracle=1")==1 and
            txt.count("WEBEEBLOCKS_RUNTIME_V2 TRACE RESET ")==2 and
            txt.count("WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1")==2 and
            "WEBEEBLOCKS_A6_MOTOR_FATAL" not in txt and
            "WEBEEBLOCKS_RUNTIME_V2 FATAL" not in txt and
            not early_browser_refusal and "ERROR:" not in txt)
        evidence={
            "schema":"webeeblocks-a6-same-world-reset-replay-native-v1",
            "pass":bool(pass_replay),"head_mode":"draft-only",
            "variant":variant,"target_pad_y":pad_y,
            "real_same_webots_incarnation":True,
            "first_native_failure_before_takeoff":True,
            "exact_broker_epoch_acks":epochs,
            "authenticated_completions":completed,
            "motorized_positive_count":len(positives),
            "genuine_reset_traces":txt.count("WEBEEBLOCKS_RUNTIME_V2 TRACE RESET "),
            "pupil_wbb_replay_not_proven":True,
            "events":events,
        }
        (ARTIFACT/"replay-summary.json").write_text(
            json.dumps(evidence,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        if not pass_replay:
            print("A6_SAME_WORLD_REPLAY_UNPROVEN "+json.dumps(evidence),
                  file=sys.stderr)
            print(txt[-13000:],file=sys.stderr)
            return 1
        print(f"A6_SAME_WORLD_NATIVE_REPLAY_PASS n={variant} epoch_1=negative "
              "epoch_2=motor_achieved epoch_3=motor_achieved "
              "single_webots_instance=true pupil_wbb=UNPROVEN",flush=True)
        return 0
    # The native observer independently evaluates physical contact and pose.
    true_flight=re.search(
        r"WEBEEBLOCKS_A6_MOTOR_RESULT status=achieved n=(\d+) "
        r"crossed=(\d+) screen=1 observations=(\d+) "
        r"x=(-?[0-9.]+) y=(-?[0-9.]+) z=(-?[0-9.]+)",txt)
    responses=re.findall(
        r"WEBEEBLOCKS_RUNTIME_V2 RESPONSE (\d+) (?:OK|SCENE_OK [0-9a-f]{64})",txt)
    moves=re.findall(
        r"WEBEEBLOCKS_RUNTIME_V2 TRACE MOVE (forward|left|right) "
        r"distance=([0-9.]+) stop=1",txt)
    expected_moves=[("forward","0.480000000")]*6+[("forward","0.120000000")]
    if variant in (2,3):
        expected_moves.append(("left" if variant==2 else "right","0.550000000"))
    pad_y={1:0.0,2:0.55,3:-0.55}[variant]
    # Only SCENE, SPEED, TAKEOFF, 7 forward MOVEs, optional lateral
    # MOVE and LAND have numbered WWI responses. Native completion is an
    # independently attested customData signal, not an extra WWI response.
    expected_responses=11+(1 if variant!=1 else 0)
    all_response_ids=re.findall(
        r"WEBEEBLOCKS_RUNTIME_V2 RESPONSE (\d+) "
        r"(?:OK|VALUE -?[0-9.]+|SCENE_OK [0-9a-f]{64})",txt)
    sensor_records=[e for e in observer.EVENTS
                    if e.get("event")=="A6_SENSOR_COUNT"]
    sensor_detail=(sensor_records[0].get("detail") or {}
                   if len(sensor_records)==1 else {})
    sensor_steps=sensor_detail.get("steps")
    sensor_count=sensor_detail.get("count")
    sensor_front=sensor_detail.get("front_m")
    sensor_protocol=(
        len(sensor_records)==1 and
        type(sensor_steps) is int and 20<=sensor_steps<=80 and
        type(sensor_count) is int and sensor_count==variant and
        type(sensor_front) in (float,int) and 0.3<=sensor_front<=.82 and
        len(all_response_ids)>50 and
        all_response_ids==[str(i) for i in range(1,len(all_response_ids)+1)] and
        len(moves)==sensor_steps+1+(1 if variant!=1 else 0) and
        moves[:sensor_steps]==[("forward","0.080000000")]*sensor_steps and
        moves[sensor_steps][0]=="forward" and
        .10<=float(moves[sensor_steps][1])<=.70 and
        moves[sensor_steps+1:]==(
            [("left" if variant==2 else "right","0.550000000")]
            if variant!=1 else []))
    reference_protocol=(
        responses==[str(i) for i in range(1,expected_responses+1)]
        and moves==expected_moves)
    authenticated_completion=(
        "WEBEEBLOCKS_A6_MOTOR_NATIVE_COMPLETION attempt=1 oracle=progression-count-h-v1 " in txt)
    native_achieved=(
        authenticated_completion and
        true_flight is not None and
        int(true_flight[1])==variant and int(true_flight[2])==variant and
        int(true_flight[3])>100 and
        abs(float(true_flight[4])-1.48)<=.06 and
        abs(float(true_flight[5])-pad_y)<=.06)
    try:
        up_motor=attest_up_motor_trace(txt,variant)
    except ValueError as problem:
        up_motor={
            "schema":"webeeblocks-a6-native-up-motor-v1",
            "variant":variant,
            "native_motor_ray_observed":False,
            "failure":str(problem),
            "not_pupil_wbb_or_counter_qualification":True,
        }
    (ARTIFACT/"up-motor-evidence.json").write_text(
        json.dumps(up_motor,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    try:
        dual=inspect_motor_sensor_count(txt)
    except ValueError as problem:
        dual={"schema":"webeeblocks-a6-dual-motor-sensor-v1",
              "variant_blind_two_sensor_evidence":False,
              "failure":str(problem),
              "no_pupil_wbb_or_backtracking_proof":True}
    (ARTIFACT/"dual-motor-sensor.json").write_text(
        json.dumps(dual,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    launch=ARTIFACT/"browser-launch.log"
    launched=launch.read_text(encoding="utf-8",errors="replace") if launch.exists() else ""
    browser="BROWSER_LAUNCHED args=" in launched and "count_h_flight_probe.html" in launched
    succeeded=(dual.get("terminal_detected",False) and
               dual.get("count")==variant and
               up_motor["native_motor_ray_observed"] and
               not missing and ordered and events.count("A6_ERROR")==0
               and native_achieved
               and (reference_protocol if mode=="reference"
                    else sensor_protocol)
               and (mode!="blockly" or events.count("A6_PRIVATE_WBB_REOPENED")==1)
               and f"WEBEEBLOCKS_A6_FLIGHT_SCENE_OK variant={variant} native_colliders={3*variant+2}" in txt
               and "WEBEEBLOCKS_RUNTIME_V2 TRACE TAKEOFF height=0.400000000 stop=1" in txt
               and "LAND_TOUCHDOWN" in txt and browser
               and "WEBEEBLOCKS_A6_MOTOR_FATAL" not in txt
               and "WEBEEBLOCKS_RUNTIME_V2 FATAL" not in txt
               and "ERROR:" not in txt)
    # This separate B geometric flight is not an algorithm/counting PASS.
    # Old up/dual-sensor diagnostic parsers assume historical H locations;
    # here ONLY the physically attested C oracle, true motors and Floor
    # contact can decide. Never treat an AST or scene title as authority.
    if family is not None:
        b_attested=(
            f"WEBEEBLOCKS_A6_B_MOTOR_GEOMETRY_ATTESTED family="
            f"{0 if family=='matched' else 1} n={variant} "
            f"verified_colliders={3*variant+2} test_only=true" in txt)
        succeeded=(
            b_attested and native_achieved and
            not missing and ordered and events.count("A6_ERROR")==0 and
            reference_protocol and
            f"WEBEEBLOCKS_A6_FLIGHT_SCENE_OK variant={variant} native_colliders={3*variant+2}" in txt and
            "WEBEEBLOCKS_RUNTIME_V2 TRACE TAKEOFF height=0.400000000 stop=1" in txt and
            "LAND_TOUCHDOWN" in txt and browser and
            "WEBEEBLOCKS_A6_MOTOR_FATAL" not in txt and
            "WEBEEBLOCKS_RUNTIME_V2 FATAL" not in txt and
            "WEBEEBLOCKS_A6_MOTOR_REJECT" not in txt and
            "ERROR:" not in txt and not early_browser_refusal)
    (ARTIFACT/"summary.json").write_text(json.dumps({
        "schema":"webeeblocks-a6-native-motor-physics-draft-v1",
        "pass":bool(succeeded),"variant":variant,"mode":mode,
        "b_private_family":family,
        "b_native_holdout_geometry_test_only":family is not None,
        "b_no_variable_or_counter_qualification":family is not None,
        "sensor_command_program_pass":bool(sensor_protocol if mode in ("sensor","blockly")
                                          else False),
        "private_blockly_webots_pass":bool(succeeded and mode=="blockly"),
        "private_wbb_sha256":(
            hashlib.sha256((world.ROOT/
              "ci-artifacts/progression-count-h-private-blockly/a6-private.wbb")
              .read_bytes()).hexdigest() if mode=="blockly" else None),
        "sensor_reported_count":sensor_count if mode in ("sensor","blockly") else None,
        "native_up_during_motor_flight":bool(up_motor["native_motor_ray_observed"]),
        "variant_blind_two_sensor_count_correct":bool(
            dual.get("terminal_detected",False) and dual.get("count")==variant),
        "native_up_trace_schema":"webeeblocks-a6-native-up-motor-v1",
        "real_motorized_flight":bool(native_achieved),
        "native_exact_attempt_completion":bool(authenticated_completion),
        "not_pupil_wbb_or_product_scene_qualification":True,
        "not_real_crazyflie_qualification":True,
        "product_window_autolaunch_qualified":False,
        "manual_external_window":manual_external_window,
        "events":events,"missing":missing,"ordered":bool(ordered),
        "native_command_acks":responses,"all_native_ack_ids":all_response_ids,
        "moves":moves,"browser":bool(browser)
    },indent=2,sort_keys=True)+"\n",encoding="utf-8")
    if not succeeded:
        print("A6_MOTOR_FLIGHT_UNPROVEN "+json.dumps({
            "variant":variant,"mode":mode,
            "sensor_protocol":sensor_protocol,
            "sensor_detail":sensor_detail,
            "up_motor":up_motor,"dual_motor_sensor":dual,
            "missing":missing,"ordered":ordered,"native":bool(native_achieved),
            "responses":responses,"moves":moves,"expected_moves":expected_moves,
            "browser":browser,
            "lastEvents":observer.EVENTS[-4:]}),file=sys.stderr)
        print(txt[-14000:],file=sys.stderr)
        return 1
    if mode=="sensor":
        print(f"WEBEEBLOCKS_A6_SENSOR_COMMANDS_PASS n={variant} "
              f"count={sensor_count} moves={sensor_steps} "
              "same_test_pilot=true pupil_wbb=UNPROVEN",flush=True)
    if mode=="blockly":
        project=world.ROOT/"ci-artifacts/progression-count-h-private-blockly/a6-private.wbb"
        print(f"WEBEEBLOCKS_A6_PRIVATE_WBB_MOTOR_PASS n={variant} "
              f"count={sensor_count} project_sha256={hashlib.sha256(project.read_bytes()).hexdigest()} "
              "native_PID=true Blockly13=true pupil_product=UNPROVEN",flush=True)
    if family is None:
        print(f"WEBEEBLOCKS_A6_TWO_SENSOR_COUNT_OK native={variant} "
              f"count={dual['count']} terminal={dual['terminal_detected']} "
              "controller=real_motor sensor_only=true pupil_wbb=UNPROVEN",flush=True)
        print(f"WEBEEBLOCKS_A6_UP_MOTOR_OBSERVED n={variant} "
              f"gates={len(up_motor['gates'])} samples={up_motor['total_32ms_samples']} "
              "sensor=authentic_range_up pupil_wbb=UNPROVEN",flush=True)
        print(f"WEBEEBLOCKS_A6_MOTOR_PASS native={variant} count={variant} "
              "corridor=real_PID_and_motors contacts=none screen=passed "
              "pupil_wbb=UNPROVEN",flush=True)
    else:
        print(f"WEBEEBLOCKS_A6_B_PRIVATE_REFERENCE_MOTOR_PASS family={family} "
              f"n={variant} real_PID=true native_contact_oracle=achieved "
              "counter_and_blockly=UNPROVEN",flush=True)
    return 0

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--variant",type=int,choices=(1,2,3),default=1)
    parser.add_argument("--family",choices=("matched","sampling"),default=None)
    parser.add_argument("--mode",choices=("reference","sensor","blockly","replay"),default="reference")
    args=parser.parse_args()
    raise SystemExit(run(variant=args.variant,mode=args.mode,family=args.family))

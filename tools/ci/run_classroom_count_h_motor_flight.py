#!/usr/bin/env python3
"""A6 first real motor-flight witness (diagnostic, NOT a pupil .wbb PASS)."""
from __future__ import annotations
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import http.client

import prepare_classroom_count_h_motor_flight as world
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

REQUIRED=("A6_HTML_LOADED","A6_JS_STARTED","A6_RUNTIME_READY",
          "A6_SCENE_ACK","A6_TAKEOFF","A6_CORRIDOR_DONE",
          "A6_LANDED","A6_TEST_COMPLETE")

def run():
    ARTIFACT.mkdir(parents=True,exist_ok=True)
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
        world.prepare()
        server=observer.http.server.ThreadingHTTPServer(("127.0.0.1",8765),observer.Handler)
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
            if (("A6_TEST_COMPLETE" in seen and
                 "WEBEEBLOCKS_A6_MOTOR_RESULT status=achieved" in txt)
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
        world.cleanup()

    txt=log.read_text(encoding="utf-8",errors="replace")
    events=[x.get("event") for x in observer.EVENTS]
    missing=[e for e in REQUIRED if events.count(e)!=1]
    ordered=not missing and [events.index(x) for x in REQUIRED]==sorted(
        events.index(x) for x in REQUIRED)
    # The native observer independently evaluates physical contact and pose.
    true_flight=re.search(
        r"WEBEEBLOCKS_A6_MOTOR_RESULT status=achieved n=1 "
        r"crossed=1 screen=1 observations=(\d+) "
        r"x=(-?[0-9.]+) y=(-?[0-9.]+) z=(-?[0-9.]+)",txt)
    responses=re.findall(
        r"WEBEEBLOCKS_RUNTIME_V2 RESPONSE (\d+) (?:OK|SCENE_OK [0-9a-f]{64})",txt)
    moves=re.findall(
        r"WEBEEBLOCKS_RUNTIME_V2 TRACE MOVE forward distance=([0-9.]+) stop=1",txt)
    launch=ARTIFACT/"browser-launch.log"
    launched=launch.read_text(encoding="utf-8",errors="replace") if launch.exists() else ""
    browser="BROWSER_LAUNCHED args=" in launched and "count_h_flight_probe.html" in launched
    succeeded=(not missing and ordered and events.count("A6_ERROR")==0
               and true_flight is not None and int(true_flight[1])>100
               and responses==[str(i) for i in range(1,11)]
               and moves==["0.480000000"]*6
               and "WEBEEBLOCKS_A6_FLIGHT_SCENE_OK variant=1 native_colliders=5" in txt
               and "WEBEEBLOCKS_RUNTIME_V2 TRACE TAKEOFF height=0.400000000 stop=1" in txt
               and "LAND_TOUCHDOWN" in txt and browser
               and "WEBEEBLOCKS_A6_MOTOR_FATAL" not in txt
               and "WEBEEBLOCKS_RUNTIME_V2 FATAL" not in txt
               and "ERROR:" not in txt)
    (ARTIFACT/"summary.json").write_text(json.dumps({
        "schema":"webeeblocks-a6-native-motor-physics-draft-v1",
        "pass":bool(succeeded),"real_motorized_flight":bool(true_flight),
        "not_pupil_wbb_or_product_scene_qualification":True,
        "not_real_crazyflie_qualification":True,
        "product_window_autolaunch_qualified":False,
        "manual_external_window":manual_external_window,
        "events":events,"missing":missing,"ordered":bool(ordered),
        "native_command_acks":responses,"moves":moves,"browser":bool(browser)
    },indent=2,sort_keys=True)+"\n",encoding="utf-8")
    if not succeeded:
        print("A6_MOTOR_FLIGHT_UNPROVEN "+json.dumps({
            "missing":missing,"ordered":ordered,"native":bool(true_flight),
            "responses":responses,"moves":moves,"browser":browser,
            "lastEvents":observer.EVENTS[-4:]}),file=sys.stderr)
        print(txt[-14000:],file=sys.stderr)
        return 1
    print("WEBEEBLOCKS_A6_MOTOR_PASS native=1 count=1 "
          "corridor=real_PID_and_motors contacts=none screen=passed "
          "pupil_wbb=UNPROVEN",flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(run())

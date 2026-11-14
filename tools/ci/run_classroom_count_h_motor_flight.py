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

import prepare_classroom_count_h_motor_flight as world
import run_classroom_altitude_scene_ack as observer

ARTIFACT=world.ARTIFACT
REQUIRED=("A6_HTML_LOADED","A6_JS_STARTED","A6_RUNTIME_READY",
          "A6_SCENE_ACK","A6_TAKEOFF","A6_CORRIDOR_DONE",
          "A6_LANDED","A6_TEST_COMPLETE")

def run():
    ARTIFACT.mkdir(parents=True,exist_ok=True)
    log=ARTIFACT/"webots.log"
    observer.EVENTS.clear()
    server=None; proc=None; output=None
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
            if (("A6_TEST_COMPLETE" in seen and
                 "WEBEEBLOCKS_A6_MOTOR_RESULT status=achieved" in txt)
                or "A6_ERROR" in seen
                or "WEBEEBLOCKS_A6_MOTOR_FATAL" in txt
                or "WEBEEBLOCKS_RUNTIME_V2 FATAL" in txt
                or proc.poll() is not None):
                break
            time.sleep(.25)
    finally:
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

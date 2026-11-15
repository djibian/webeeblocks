#!/usr/bin/env python3
"""Actual school-only R2025a A5 native A/B/C scene ACK, no pupil flight.

A fresh test-only browser sends genuine nonce-bound WWI SCENE requests.
Original Crazyflie and stage-specific native C evaluators must be present;
the worlds are NOT preloaded, and the physical runtime is not modified.
"""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time

import prepare_classroom_reactive_L_v2_scene_ack as world
import run_classroom_altitude_scene_ack as events

ARTIFACT=world.ROOT/"ci-artifacts/progression-reactive-L-v2-school-selector"
REQUIRED=(
    "A5_SCENE_HTML_LOADED","A5_SCENE_JS_STARTED",
    "A5_SCENE_RUNTIME_READY",
    "A5_SCENE_A_ACK","A5_SCENE_A_RANGE",
    "A5_SCENE_B_ACK","A5_SCENE_B_RANGE",
    "A5_SCENE_C_ACK","A5_SCENE_C_RANGE",
    "A5_SCENE_LEGACY_RESTORED",
    "A5_SCENE_A_REATTACHED","A5_SCENE_FINAL_LEGACY",
    "A5_SCENE_TEST_COMPLETE",
)
MARKERS={
    v:("WEBEEBLOCKS_A5_V2_NATIVE_C_READY scene="+v+
       " oracle=progression-reactive-L-v2")
    for v in "ABC"
}

def run():
    ARTIFACT.mkdir(parents=True,exist_ok=True)
    logpath=ARTIFACT/"webots.log"
    events.EVENTS.clear()
    process=server=output=None
    try:
        for path in (
            world.ROOT/"controllers/crazyflie_classroom_v2/crazyflie_classroom_v2",
            world.ROOT/"controllers/progression_reactive_L_v2/progression_reactive_L_v2",
        ):
            if not path.is_file() or not path.stat().st_size:
                raise FileNotFoundError("native school controller missing "+str(path))
        world.prepare()
        server=events.http.server.ThreadingHTTPServer(
            ("127.0.0.1",8765),events.Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        env=dict(os.environ)
        env["WEBOTS_WEB_BROWSER"]="/workspace/tools/ci/webots_runtime_v2_browser.sh"
        output=logpath.open("w",encoding="utf-8")
        process=subprocess.Popen(
            ["timeout","-k","5s","155s","xvfb-run","-a","webots",
             "--stdout","--stderr","--batch","--mode=realtime",str(world.WORLD)],
            cwd=str(world.ROOT),env=env,stdout=output,stderr=subprocess.STDOUT,
            start_new_session=True)
        until=time.monotonic()+145
        while time.monotonic()<until:
            kinds=[r.get("event") for r in events.EVENTS]
            if ("A5_SCENE_ERROR" in kinds or process.poll() is not None):
                break
            if "A5_SCENE_TEST_COMPLETE" in kinds:
                contents=logpath.read_text(encoding="utf-8",errors="replace")
                if (contents.count(MARKERS["A"])>=2 and
                    contents.count(MARKERS["B"])>=1 and
                    contents.count(MARKERS["C"])>=1):
                    break
            time.sleep(.25)
    finally:
        if process is not None and process.poll() is None:
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                process.wait(timeout=8)
        if output:output.close()
        if server:server.shutdown();server.server_close()
        (ARTIFACT/"events.json").write_text(
            json.dumps(events.EVENTS,indent=2,sort_keys=True)+"\n",
            encoding="utf-8")
        world.cleanup()
    data=logpath.read_text(encoding="utf-8",errors="replace")
    kinds=[r.get("event") for r in events.EVENTS]
    missing=[n for n in REQUIRED if kinds.count(n)!=1]
    ordered=not missing and [kinds.index(n) for n in REQUIRED]==sorted(
        kinds.index(n) for n in REQUIRED)
    native={v:data.count(MARKERS[v]) for v in "ABC"}
    response=re.findall(
        r"WEBEEBLOCKS_RUNTIME_V2 RESPONSE ([0-9]+) (?:OK|SCENE_OK [0-9a-f]{64}|VALUE -?[0-9.]+)",data)
    browserlog=ARTIFACT/"browser-launch.log"
    browser=browserlog.read_text(encoding="utf-8",errors="replace") if browserlog.exists() else ""
    launched="BROWSER_LAUNCHED args=" in browser and "reactive_l_v2_scene_ack_probe.html" in browser
    failures=[s for s in (
        "WEBEEBLOCKS_A5_V2_FATAL",
        "WEBEEBLOCKS_RUNTIME_V2 FATAL",
        "A5_SCENE_ERROR",
    ) if s in data or s in kinds]
    successful=(
        not missing and ordered and not failures and
        native=={"A":2,"B":1,"C":1} and
        response==[str(i) for i in range(1,10)] and launched
    )
    summary=dict(success=successful,native_ready=native,
                 missing=missing,ordered=ordered,errors=failures,
                 responses=response,launched=launched,events=kinds,
                 pupil_flight_tested=False,student_wbb_tested=False)
    (ARTIFACT/"summary.json").write_text(
        json.dumps(summary,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    if not successful:
        print("FAIL staged A5 native school scene selection "+json.dumps(summary),
              file=sys.stderr)
        print(data[-10000:],file=sys.stderr)
        return 1
    print("WEBEEBLOCKS_A5_V2_SCHOOL_SELECTOR_NATIVE_CONFIRMED "
          "A=2 B=1 C=1 legacy_restored=true flight=NOT_TESTED",
          flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(run())

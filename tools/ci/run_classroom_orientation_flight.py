#!/usr/bin/env python3
"""Actual R2025a flight across all Activity 3 3D/orientation checkpoints.

CI-only RAW native action witness, NOT the pupil Blockly/.wbb workflow.
Independent Webots C oracle must certify ordered checkpoints and full landing.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import prepare_classroom_orientation_flight as world
import run_classroom_altitude_scene_ack as ack

ARTIFACT=world.ROOT/'ci-artifacts'/'progression-neutral-start'/'orientation-native-flight'
REQUIRED=(
    'ORIENT_HTML_LOADED','ORIENT_JS_STARTED','ORIENT_RUNTIME_READY',
    'ORIENT_SCENE_ACK','ORIENT_A_TURNED','ORIENT_B_TURNED','ORIENT_C_TURNED',
    'ORIENT_LANDED','ORIENT_NATIVE_ACHIEVED','ORIENT_TEST_COMPLETE'
)

def run()->int:
    ARTIFACT.mkdir(parents=True,exist_ok=True)
    log_path=ARTIFACT/'webots.log'
    ack.EVENTS.clear()
    server=None
    process=None
    output=None
    try:
        for path in (
            world.ROOT/'controllers/crazyflie_classroom_v2/crazyflie_classroom_v2',
            world.ROOT/'controllers/progression_orientation_3d/progression_orientation_3d',
        ):
            if not path.is_file() or not path.stat().st_size:
                raise FileNotFoundError('missing independently compiled native controller '+str(path))
        world.prepare()
        server=ack.http.server.ThreadingHTTPServer(('127.0.0.1',8765),ack.Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        env=dict(os.environ)
        env['WEBOTS_WEB_BROWSER']='/workspace/tools/ci/webots_runtime_v2_browser.sh'
        output=log_path.open('w',encoding='utf-8')
        process=subprocess.Popen(
            ['timeout','-k','5s','320s','xvfb-run','-a','webots','--stdout',
             '--stderr','--batch','--mode=realtime',str(world.WORLD)],
            cwd=str(world.ROOT),stdout=output,stderr=subprocess.STDOUT,
            env=env,start_new_session=True)
        deadline=time.monotonic()+310
        while time.monotonic()<deadline:
            names=[entry.get('event') for entry in ack.EVENTS]
            if 'ORIENT_TEST_COMPLETE' in names or 'ORIENT_ERROR' in names or process.poll() is not None:
                break
            time.sleep(0.25)
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait(timeout=8)
        if output is not None:output.close()
        if server is not None:
            server.shutdown()
            server.server_close()
        (ARTIFACT/'events.json').write_text(
            json.dumps(ack.EVENTS,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        world.cleanup()
    txt=log_path.read_text(encoding='utf-8',errors='replace')
    names=[entry.get('event') for entry in ack.EVENTS]
    missing=[name for name in REQUIRED if names.count(name)!=1]
    ordered=(not missing and [names.index(e) for e in REQUIRED] ==
             sorted(names.index(e) for e in REQUIRED))
    native_result=re.search(
        r'WEBEEBLOCKS_ORIENTATION_3D_RESULT attempt=1 status=achieved checkpoints=3\b',txt)
    responses=re.findall(
        r'WEBEEBLOCKS_RUNTIME_V2 RESPONSE (\d+) (?:OK|SCENE_OK [0-9a-f]{64})',txt)
    turns=re.findall(r'WEBEEBLOCKS_RUNTIME_V2 TRACE TURN angle_deg=(-?[0-9.]+) stop=1',txt)
    vertical=re.findall(
        r'WEBEEBLOCKS_RUNTIME_V2 TRACE VERTICAL (up|down) distance=([0-9.]+) stop=1',txt)
    launch_file=ARTIFACT.parent/'browser-launch.log'
    launch=launch_file.read_text(encoding='utf-8',errors='replace') if launch_file.exists() else ''
    browser='BROWSER_LAUNCHED args=' in launch and 'orientation_flight_probe.html' in launch
    successful=(
        not missing and ordered and names.count('ORIENT_ERROR')==0 and
        native_result is not None and browser and
        'WEBEEBLOCKS_ORIENTATION_3D_READY scene=orientation-v1 oracle=progression-orientation-3d-v1' in txt and
        responses==[str(n) for n in range(1,14)] and
        turns==['-90.000000000','90.000000000','-90.000000000'] and
        vertical==[('up','0.160000000'),('down','0.160000000')] and
        'WEBEEBLOCKS_RUNTIME_V2 FATAL' not in txt and
        'WEBEEBLOCKS_ORIENTATION_3D_FATAL' not in txt and
        'ERROR:' not in txt)
    (ARTIFACT/'summary.json').write_text(json.dumps({
        'pass':successful,'required_events_missing':missing,'ordered':ordered,
        'native_result':bool(native_result),'browser':browser,'responses':responses,
        'turns':turns,'vertical':vertical,'events':names
    },indent=2,sort_keys=True)+'\n',encoding='utf-8')
    if not successful:
        print('FAIL native Activity 3 orientation flight '+json.dumps({
            'missing':missing,'ordered':ordered,'native_result':bool(native_result),
            'browser':browser,'responses':responses,'turns':turns,
            'vertical':vertical,'events':ack.EVENTS[-5:]}),file=sys.stderr)
        print(txt[-12000:],file=sys.stderr)
        return 1
    print('PASS real Webots R2025a Activity 3: relative yaw, relative altitude, three ordered native checkpoints and full landing',flush=True)
    return 0

if __name__=='__main__':
    raise SystemExit(run())

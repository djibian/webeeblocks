#!/usr/bin/env python3
"""Webots R2025a: actual Blockly-generated .wbb executes against school C oracle."""
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
import prepare_classroom_altitude_pupil as world
import run_classroom_altitude_scene_ack as native_ack

ARTIFACT=world.ROOT/'ci-artifacts'/Path(os.environ.get(
    'WEBEEBLOCKS_CI_ARTIFACT_DIR','/workspace/ci-artifacts/progression-neutral-start'
)).name/'altitude-pupil-blockly'
REQUIRED=(
    'PUPIL_HTML_LOADED','PUPIL_JS_STARTED','PUPIL_BLOCKLY_PROJECT_ROUNDTRIP',
    'PUPIL_RUNTIME_READY','PUPIL_INTERPRETER_LANDED',
    'PUPIL_NATIVE_ACHIEVED','PUPIL_TEST_COMPLETE'
)
def run()->int:
    ARTIFACT.mkdir(parents=True,exist_ok=True)
    log=ARTIFACT/'webots.log'
    native_ack.EVENTS.clear()
    server=None
    process=None
    output=None
    try:
        world.prepare()
        server=native_ack.http.server.ThreadingHTTPServer(('127.0.0.1',8765),native_ack.Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        env=dict(os.environ)
        env['WEBOTS_WEB_BROWSER']='/workspace/tools/ci/webots_runtime_v2_browser.sh'
        output=log.open('w',encoding='utf-8')
        process=subprocess.Popen([
            'timeout','-k','5s','280s','xvfb-run','-a','webots','--stdout','--stderr',
            '--batch','--mode=realtime',str(world.WORLD)
        ],cwd=str(world.ROOT),stdout=output,stderr=subprocess.STDOUT,
           env=env,start_new_session=True)
        deadline=time.monotonic()+270
        while time.monotonic()<deadline:
            names=[x.get('event') for x in native_ack.EVENTS]
            if 'PUPIL_TEST_COMPLETE' in names or 'PUPIL_ERROR' in names or process.poll() is not None:
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
            json.dumps(native_ack.EVENTS,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        world.cleanup()

    txt=log.read_text(encoding='utf-8',errors='replace')
    ev=list(native_ack.EVENTS)
    names=[x.get('event') for x in ev]
    missing=[x for x in REQUIRED if names.count(x)!=1]
    event_order=not missing and [names.index(x) for x in REQUIRED]==sorted(names.index(x) for x in REQUIRED)
    success=re.search(
        r'WEBEEBLOCKS_ALTITUDE_RESULT attempt=1 status=achieved\b[^\n]*\bairborne=1\b[^\n]*\bcrossed=1\b[^\n]*\bcontact=0\b[^\n]*\bcompletion=1\b',txt)
    messages=re.findall(r'WEBEEBLOCKS_RUNTIME_V2 RESPONSE (\d+) (?:OK|SCENE_OK [0-9a-f]{64})',txt)
    request_count=len(messages)
    browser_dir=ARTIFACT.parent
    launch_file=browser_dir/'browser-launch.log'
    launch=launch_file.read_text(encoding='utf-8',errors='replace') if launch_file.exists() else ''
    valid_launch='BROWSER_LAUNCHED args=' in launch and 'altitude_pupil_probe.html' in launch
    valid=('WEBEEBLOCKS_ALTITUDE_READY scene=altitude-v1 oracle=progression-altitude-3d-v1' in txt and
        ' SCENE_OK ' in txt and
        success is not None and request_count>=8 and valid_launch and event_order and
        'PUPIL_ERROR' not in names and
        'WEBEEBLOCKS_ALTITUDE_FATAL' not in txt and
        'WEBEEBLOCKS_RUNTIME_V2 FATAL' not in txt and
        'ERROR:' not in txt)
    summary={'pass':valid,'missing':missing,'ordered':event_order,
        'native_result':bool(success),'request_responses':request_count,
        'real_browser':valid_launch,'events':names}
    (ARTIFACT/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    if not valid:
        print('FAIL native A2 pupil Blockly path '+json.dumps(summary),file=sys.stderr)
        print(txt[-13000:],file=sys.stderr)
        return 1
    print('PASS R2025a native Activity 2: real Blockly .wbb → AST/preflight/interpreter/SCENE/WWI → physical no-contact crossing + LAND + C achieved',flush=True)
    return 0

if __name__=='__main__':
    raise SystemExit(run())

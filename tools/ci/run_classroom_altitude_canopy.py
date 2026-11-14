#!/usr/bin/env python3
"""Falsify canopy high-takeoff bypass in actual Webots R2025a.

No mocked flight, no simulator bypass, no AST inspection. Outputs are evidence,
not an owner pedagogical PASS; the first low-flight trajectory is experimental.
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

import prepare_classroom_altitude_canopy as world
import run_classroom_altitude_scene_ack as ack

ARTIFACT = world.ROOT / 'ci-artifacts' / Path(
    os.environ.get('WEBEEBLOCKS_CI_ARTIFACT_DIR',
                   '/workspace/ci-artifacts/progression-neutral-start')
).name / 'altitude-canopy-flight'
REQUIRED = (
    'CANOPY_HTML_LOADED','CANOPY_JS_STARTED','CANOPY_RUNTIME_READY',
    'CANOPY_SCENE_ACK','CANOPY_HIGH_REJECTED','CANOPY_RESET_FRESH',
    'CANOPY_SCENE_REATTACHED','CANOPY_CLEARED_LOW',
    'CANOPY_ASCENDED_AFTER_CLEARANCE','CANOPY_LOW_CLIMB_ACHIEVED',
    'CANOPY_TEST_COMPLETE',
)


def run() -> int:
    ARTIFACT.mkdir(parents=True,exist_ok=True)
    log_path = ARTIFACT / 'webots.log'
    events_path = ARTIFACT / 'events.json'
    ack.EVENTS.clear()
    server = None
    process = None
    output = None
    try:
        world.prepare()
        server = ack.http.server.ThreadingHTTPServer(('127.0.0.1',8765),ack.Handler)
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        env = dict(os.environ)
        env['WEBOTS_WEB_BROWSER'] = '/workspace/tools/ci/webots_runtime_v2_browser.sh'
        output = log_path.open('w',encoding='utf-8')
        process = subprocess.Popen(
            ['timeout','-k','5s','295s','xvfb-run','-a','webots',
             '--stdout','--stderr','--batch','--mode=realtime',str(world.WORLD)],
            cwd=str(world.ROOT),stdout=output,stderr=subprocess.STDOUT,
            env=env,start_new_session=True
        )
        deadline = time.monotonic()+285
        while time.monotonic()<deadline:
            observed = [e.get('event') for e in ack.EVENTS]
            if 'CANOPY_TEST_COMPLETE' in observed or 'CANOPY_ERROR' in observed:
                break
            if process.poll() is not None:
                break
            time.sleep(0.25)
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try: process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait(timeout=8)
        if output is not None: output.close()
        if server is not None:
            server.shutdown()
            server.server_close()
        events_path.write_text(json.dumps(ack.EVENTS,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        world.cleanup()

    transcript = log_path.read_text(encoding='utf-8',errors='replace')
    observed = [e.get('event') for e in ack.EVENTS]
    missing = [name for name in REQUIRED if observed.count(name)!=1]
    native_ready = 'WEBEEBLOCKS_ALTITUDE_READY scene=altitude-v1 oracle=progression-altitude-3d-v1' in transcript
    actual_contact = re.search(
        r'WEBEEBLOCKS_ALTITUDE_RESULT attempt=1 status=not-achieved\b[^\n]*\bcontact=1\b',transcript)
    low_success = re.search(
        r'WEBEEBLOCKS_ALTITUDE_RESULT attempt=2 status=achieved\b[^\n]*\bcrossed=1\b',transcript)
    browser_dir = world.ROOT / 'ci-artifacts' / Path(
        os.environ.get('WEBEEBLOCKS_CI_ARTIFACT_DIR',
                       '/workspace/ci-artifacts/progression-neutral-start')
    ).name
    launch_file = browser_dir / 'browser-launch.log'
    launch = launch_file.read_text(encoding='utf-8',errors='replace') if launch_file.exists() else ''
    launched = 'BROWSER_LAUNCHED args=' in launch and 'altitude_canopy_probe.html' in launch
    fatal = ('CANOPY_ERROR' in observed or
             'WEBEEBLOCKS_ALTITUDE_FATAL' in transcript or
             'WEBEEBLOCKS_RUNTIME_V2 FATAL' in transcript or
             'ERROR:' in transcript)
    (ARTIFACT/'summary.json').write_text(json.dumps({
        'required_events_missing':missing,
        'native_ready':native_ready,'physical_roof_contact':bool(actual_contact),
        'low_climb_landing':bool(low_success),'browser_launched':launched,
        'fatal':fatal,'observed':observed
    },indent=2,sort_keys=True)+'\n',encoding='utf-8')
    if missing or not native_ready or not actual_contact or not low_success or not launched or fatal:
        print('FAIL native R2025a canopy flight '+json.dumps({
            'missing':missing,'native_ready':native_ready,'roof_contact':bool(actual_contact),
            'low_success':bool(low_success),'browser_launched':launched,
            'fatal':fatal,'events':ack.EVENTS[-5:]
        }),file=sys.stderr)
        print(transcript[-12000:],file=sys.stderr)
        return 1
    print('PASS real Webots R2025a canopy: high TAKEOFF native collision, reset freshness, low departure then ascent and full-pad LAND')
    return 0


if __name__=='__main__':
    raise SystemExit(run())

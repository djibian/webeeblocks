#!/usr/bin/env python3
"""Native R2025a witness of real Blockly Activity 3 AST and 3-beacon flight.

Uses the *actual student catalog profile* and school world, under test-only
browser orchestration. Real File System Access picker and pupil competence
remain unproven by this experiment.
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

import prepare_classroom_orientation_pupil as world
import run_classroom_altitude_scene_ack as ack

ARTIFACT=world.ROOT/'ci-artifacts'/'progression-neutral-start'/'orientation-pupil-blockly'
REQUIRED=(
    'A3_PUPIL_HTML_LOADED','A3_PUPIL_JS_STARTED',
    'A3_PUPIL_BLOCKLY_ROUNDTRIP','A3_PUPIL_RUNTIME_READY',
    'A3_PUPIL_INTERPRETER_LANDED','A3_PUPIL_NATIVE_ACHIEVED',
    'A3_PUPIL_TEST_COMPLETE'
)

def run()->int:
    ARTIFACT.mkdir(parents=True,exist_ok=True)
    logpath=ARTIFACT/'webots.log'
    ack.EVENTS.clear()
    server=None
    process=None
    output=None
    try:
        for rel in (
            'controllers/crazyflie_classroom_v2/crazyflie_classroom_v2',
            'controllers/progression_orientation_3d/progression_orientation_3d',
        ):
            exe=world.ROOT/rel
            if not exe.is_file() or not exe.stat().st_size:
                raise FileNotFoundError('missing exact native school controller '+rel)
        world.prepare()
        server=ack.http.server.ThreadingHTTPServer(('127.0.0.1',8765),ack.Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        env=dict(os.environ)
        env['WEBOTS_WEB_BROWSER']='/workspace/tools/ci/webots_runtime_v2_browser.sh'
        output=logpath.open('w',encoding='utf-8')
        process=subprocess.Popen(
            ['timeout','-k','5s','340s','xvfb-run','-a','webots','--stdout',
             '--stderr','--batch','--mode=realtime',str(world.WORLD)],
            cwd=str(world.ROOT),stdout=output,stderr=subprocess.STDOUT,
            env=env,start_new_session=True
        )
        deadline=time.monotonic()+330
        while time.monotonic()<deadline:
            names=[e.get('event') for e in ack.EVENTS]
            if ('A3_PUPIL_TEST_COMPLETE' in names or 'A3_PUPIL_ERROR' in names
                    or process.poll() is not None):
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

    txt=logpath.read_text(encoding='utf-8',errors='replace')
    names=[e.get('event') for e in ack.EVENTS]
    missing=[name for name in REQUIRED if names.count(name)!=1]
    ordered=not missing and [names.index(n) for n in REQUIRED]==sorted(names.index(n) for n in REQUIRED)
    native=re.search(
        r'WEBEEBLOCKS_ORIENTATION_3D_RESULT attempt=1 status=achieved checkpoints=3\b',txt)
    responses=re.findall(r'WEBEEBLOCKS_RUNTIME_V2 RESPONSE (\d+) (?:OK|SCENE_OK [0-9a-f]{64})',txt)
    turns=re.findall(r'WEBEEBLOCKS_RUNTIME_V2 TRACE TURN angle_deg=(-?[0-9.]+) stop=1',txt)
    vertical=re.findall(
        r'WEBEEBLOCKS_RUNTIME_V2 TRACE VERTICAL (up|down) distance=([0-9.]+) stop=1',txt)
    moves=re.findall(
        r'WEBEEBLOCKS_RUNTIME_V2 TRACE MOVE forward distance=([0-9.]+) stop=1',txt)
    browser_log=ARTIFACT.parent/'browser-launch.log'
    browser_text=(browser_log.read_text(encoding='utf-8',errors='replace')
                  if browser_log.exists() else '')
    browser='BROWSER_LAUNCHED args=' in browser_text and 'orientation_pupil_probe.html' in browser_text
    roundtrip=next((e.get('detail') for e in ack.EVENTS
                    if e.get('event')=='A3_PUPIL_BLOCKLY_ROUNDTRIP'),None)
    completed=next((e.get('detail') for e in ack.EVENTS
                    if e.get('event')=='A3_PUPIL_TEST_COMPLETE'),None)
    valid=(
        not missing and ordered and names.count('A3_PUPIL_ERROR')==0 and
        native is not None and browser and
        isinstance(roundtrip,dict) and
        roundtrip.get('id')=='progression-orientation-3d-v1' and
        roundtrip.get('statements')==4 and
        isinstance(roundtrip.get('repeat'),dict) and
        roundtrip['repeat'].get('kind')=='repeat' and roundtrip['repeat'].get('count')==2 and
        [step.get('kind') for step in roundtrip['repeat'].get('body',[])] ==
        ['move','turn','vertical','move','turn','vertical'] and
        isinstance(completed,dict) and completed.get('same_wbb') is True and
        completed.get('status')=='achieved' and
        'WEBEEBLOCKS_ORIENTATION_3D_READY scene=orientation-v1 oracle=progression-orientation-3d-v1' in txt and
        responses==[str(n) for n in range(1,17)] and
        moves==['0.450000000'] * 4 and
        turns==['-90.000000000','90.000000000','-90.000000000','90.000000000'] and
        vertical==[('up','0.160000000'),('down','0.160000000'),
                   ('up','0.160000000'),('down','0.160000000')] and
        'WEBEEBLOCKS_RUNTIME_V2 FATAL' not in txt and
        'WEBEEBLOCKS_ORIENTATION_3D_FATAL' not in txt and
        'ERROR:' not in txt
    )
    summary={
        'pass':valid,'missing_events':missing,'ordered':ordered,'browser':browser,
        'native_result':bool(native),'responses':responses,
        'moves':moves,'turns':turns,'vertical':vertical,'events':names,
        'profile_kind':'public pupil catalog profile (CI-only native witness)',
        'profile_id':roundtrip.get('id') if isinstance(roundtrip,dict) else None
    }
    (ARTIFACT/'summary.json').write_text(
        json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    if not valid:
        print('FAIL native Blockly Activity 3 pupil path '+json.dumps(summary),file=sys.stderr)
        print(txt[-12000:],file=sys.stderr)
        return 1
    print('PASS native R2025a Activity 3: six-action motif repeated twice, .wbb roundtrip, AST/preflight/interpreter, three ordered 3D checkpoints, full LAND and independent C achieved',flush=True)
    return 0

if __name__=='__main__':
    raise SystemExit(run())

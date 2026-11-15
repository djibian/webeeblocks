#!/usr/bin/env python3
"""Single exact .wbb across A/B real Webots R2025a via school Blockly runtime.

The experimental profile is kept out of the student catalogue. Only the
independent C evaluator's achieved terminal verdict proves mission behavior.
An actual browser builds the Blockly workspace, serializes its only project
once, loads those exact same bytes twice, and executes the real interpreter.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time

import prepare_classroom_mini_gp_pupil as world
import run_classroom_altitude_scene_ack as ack

ARTIFACT=world.ROOT/'ci-artifacts/progression-mini-gp-blockly'
REQUIRED=(
    'A7_PUPIL_HTML_LOADED',
    'A7_PUPIL_JS_STARTED',
    'A7_PUPIL_WBB_COMPLETE',
    'A7_PUPIL_BLOCKLY_COMPILED',
    'A7_PUPIL_RUNTIME_READY',
    'A7_PUPIL_TEST_COMPLETE',
)

def run()->int:
    ARTIFACT.mkdir(parents=True,exist_ok=True)
    log_path=ARTIFACT/'webots.log'
    ack.EVENTS.clear()
    server=None
    process=None
    output=None
    try:
        for rel in ('controllers/crazyflie_classroom_v2/crazyflie_classroom_v2',
                    'controllers/progression_mini_grand_prix_v1/progression_mini_grand_prix_v1'):
            exe=world.ROOT/rel
            if not exe.is_file() or not exe.stat().st_size:
                raise FileNotFoundError('missing native product controller '+rel)
        world.prepare()
        server=ack.http.server.ThreadingHTTPServer(('127.0.0.1',8765),ack.Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        env=dict(os.environ)
        env['WEBOTS_WEB_BROWSER']='/workspace/tools/ci/webots_runtime_v2_browser.sh'
        output=log_path.open('w',encoding='utf-8')
        process=subprocess.Popen(
            ['timeout','-k','5s','540s','xvfb-run','-a','webots',
             '--stdout','--stderr','--batch','--mode=realtime',str(world.WORLD)],
            cwd=str(world.ROOT),stdout=output,stderr=subprocess.STDOUT,
            env=env,start_new_session=True)
        started=time.monotonic()
        deadline=started+525
        while time.monotonic()<deadline:
            events=[e.get('event') for e in ack.EVENTS]
            if ('A7_PUPIL_TEST_COMPLETE' in events or
                'A7_PUPIL_ERROR' in events or process.poll() is not None):
                break
            # The browser is mandatory, and native readiness alone is not it.
            if time.monotonic()-started>45 and 'A7_PUPIL_HTML_LOADED' not in events:
                print('A7_PUPIL_FATAL browser bootstrap missing after 45s',
                      file=sys.stderr,flush=True)
                break
            time.sleep(.25)
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait(timeout=8)
        if output is not None: output.close()
        if server is not None:
            server.shutdown()
            server.server_close()
        (ARTIFACT/'events.json').write_text(
            json.dumps(ack.EVENTS,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        world.cleanup()

    text=log_path.read_text(encoding='utf-8',errors='replace')
    events=[e.get('event') for e in ack.EVENTS]
    missing=[event for event in REQUIRED if events.count(event)!=1]
    ordered=not missing and [events.index(e) for e in REQUIRED]==sorted(
        events.index(e) for e in REQUIRED)
    chunks=[e.get('detail') for e in ack.EVENTS
            if e.get('event')=='A7_PUPIL_WBB_CHUNK']
    project=None
    if chunks and all(isinstance(c,dict) and
                      isinstance(c.get('index'),int) and
                      isinstance(c.get('text'),str) for c in chunks):
        indices=[x['index'] for x in chunks]
        if indices==list(range(len(indices))):
            project=''.join(chunk['text'] for chunk in chunks)
            (ARTIFACT/'pupil-project.wbb').write_text(project,encoding='utf-8')
    completed=next((e.get('detail') for e in ack.EVENTS
                    if e.get('event')=='A7_PUPIL_WBB_COMPLETE'),None)
    project_ok=(project is not None and isinstance(completed,dict) and
                completed.get('chars')==len(project))
    if project_ok:
        try:
            parsed=json.loads(project)
            project_ok=(parsed.get('format')=='webeeblocks-project' and
                        parsed.get('activity',{}).get('id')=='ci-mini-grand-prix-conditional-v1')
        except (ValueError,TypeError,AttributeError):
            project_ok=False
    steps=[
        ('A7_PUPIL_PROJECT_REOPENED','l'),
        ('A7_PUPIL_INTERPRETER_LANDED','l'),
        ('A7_PUPIL_NATIVE_ACHIEVED','l'),
        ('A7_PUPIL_NATIVE_RESET',None),
        ('A7_PUPIL_PROJECT_REOPENED','r'),
        ('A7_PUPIL_INTERPRETER_LANDED','r'),
        ('A7_PUPIL_NATIVE_ACHIEVED','r'),
    ]
    observed=[]
    for event,variant in steps:
        candidates=[(i,e) for i,e in enumerate(ack.EVENTS)
                    if e.get('event')==event and
                    (variant is None or
                     isinstance(e.get('detail'),dict) and
                     e['detail'].get('variant')==variant)]
        observed.append(candidates[0][0] if len(candidates)==1 else -1)
    in_order=(all(i>=0 for i in observed) and observed==sorted(observed))
    # Only the independent C observer can award a mission. Browser events
    # and successful PID commands are necessary but never sufficient evidence.
    outcomes=re.findall(
        r'WB_MINI_NATIVE_RESULT variant=([LR]) attempt=([0-9]+) '
        r'status=([a-z-]+) crossed=([01]) turned=([01])',text)
    rays=[float(v) for v in re.findall(
        r'WEBEEBLOCKS_RUNTIME_V2 TRACE RANGE front value=([0-9.]+)',text)]
    moves=re.findall(
        r'WEBEEBLOCKS_RUNTIME_V2 TRACE MOVE forward distance=([0-9.]+) stop=1',text)
    vertical=re.findall(
        r'WEBEEBLOCKS_RUNTIME_V2 TRACE VERTICAL (up|down) distance=([0-9.]+) stop=1',text)
    turns=re.findall(
        r'WEBEEBLOCKS_RUNTIME_V2 TRACE TURN angle=([-0-9.]+) stop=1',text)
    # Only the pinned native browser launch is relevant; never reuse A7 logs.
    browser_log=ARTIFACT/'browser-launch.log'
    browser_text=browser_log.read_text(encoding='utf-8',errors='replace') if browser_log.exists() else ''
    browser_ok=('BROWSER_LAUNCHED args=' in browser_text and
                'mini_gp_pupil_probe.html' in browser_text)
    valid=(not missing and ordered and in_order and
           events.count('A7_PUPIL_ERROR')==0 and
           project_ok and browser_ok and
           outcomes==[('L','1','achieved','1','1'),('R','2','achieved','1','1')] and
           len(rays)==2 and 0.4<=rays[0]<=0.80 and 0.78<=rays[1]<=1.20 and
           rays[1]-rays[0]>=0.20 and
           moves==['0.800000000','0.800000000','0.800000000','0.150000000',
                   '0.800000000','0.800000000','0.300000000',
                   '0.800000000','0.150000000'] and
           vertical==[('up','0.250000000'),('down','0.350000000')]*2 and
           turns==['90.000000000','-90.000000000'] and
           text.count('WEBEEBLOCKS_RUNTIME_V2 TRACE TAKEOFF height=0.500000000 stop=1')==2 and
           text.count('WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1')==2 and
           text.count('WB_MINI_NATIVE_READY variant=L oracle=progression-mini-grand-prix-v1')>=1 and
           text.count('WB_MINI_NATIVE_READY variant=R oracle=progression-mini-grand-prix-v1')>=1 and
           'WB_MINI_NATIVE_FATAL' not in text and
           'WEBEEBLOCKS_RUNTIME_V2 FATAL' not in text)
    summary={'pass':valid,'required_missing':missing,'ordered':ordered,
             'events_ordered':in_order,'native_outcomes':outcomes,
             'rays_m':rays,'moves':moves,'vertical':vertical,'turns':turns,
             'motorized_flight':valid,'same_pupil_wbb':project_ok and in_order,
             'browser':browser_ok,'one_project':project_ok,
             'project_sha256':hashlib.sha256(project.encode('utf-8')).hexdigest() if project else None,
             'project_bytes':len(project.encode('utf-8')) if project else None,
             'profile':'CI-only not registered in student activities.js'}
    (ARTIFACT/'summary.json').write_text(
        json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    if not valid:
        print('FAIL A7 same native .wbb on L/R: '+json.dumps(summary),file=sys.stderr)
        print(text[-13500:],file=sys.stderr)
        return 1
    print('PASS A7 same .wbb on L/R; genuine native sensors, actual PID motors, 90-degree turn, LAND and C oracle achieved in both worlds',flush=True)
    return 0

if __name__=='__main__':
    raise SystemExit(run())

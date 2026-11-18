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

import prepare_classroom_decision_h_pupil as world
import run_classroom_altitude_scene_ack as ack

ARTIFACT=world.ROOT/'ci-artifacts/progression-decision-h-blockly'
REQUIRED=(
    'A4_PUPIL_HTML_LOADED',
    'A4_PUPIL_JS_STARTED',
    'A4_PUPIL_WBB_COMPLETE',
    'A4_PUPIL_BLOCKLY_COMPILED',
    'A4_PUPIL_RUNTIME_READY',
    'A4_PUPIL_TEST_COMPLETE',
)

def classify_live_watchdog(events, exit_code, elapsed_wall_s):
    """Observe runner termination only; never infer a native mission verdict."""
    if 'A4_PUPIL_ERROR' in events:
        return 'browser_error'
    if 'A4_PUPIL_TEST_COMPLETE' in events:
        return 'complete'
    if exit_code is not None:
        return 'webots_terminated'
    if elapsed_wall_s>45 and 'A4_PUPIL_HTML_LOADED' not in events:
        return 'browser_bootstrap_missing'
    if elapsed_wall_s>=525:
        return 'wall_deadline'
    return None

def run()->int:
    ARTIFACT.mkdir(parents=True,exist_ok=True)
    log_path=ARTIFACT/'webots.log'
    ack.EVENTS.clear()
    server=None
    process=None
    output=None
    started=None
    termination={'reason':'not_started',
                 'pre_cleanup_exit_code':None,'elapsed_wall_s':None}
    try:
        for rel in ('controllers/crazyflie_classroom_v2/crazyflie_classroom_v2',
                    'controllers/progression_decision_h_v1/progression_decision_h_v1'):
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
            # Capture the process return code BEFORE deliberately killing
            # Webots during cleanup. Missing COMPLETE is never a native PASS.
            current_return_code=process.poll()
            reason=classify_live_watchdog(
                events,current_return_code,time.monotonic()-started)
            if reason is not None:
                termination['reason']=reason
                termination['pre_cleanup_exit_code']=current_return_code
                if reason=='browser_bootstrap_missing':
                    print('A4_PUPIL_FATAL browser bootstrap missing after 45s',
                          file=sys.stderr,flush=True)
                break
            time.sleep(.25)
        else:
            termination['reason']='wall_deadline'
    finally:
        if started is not None:
            termination['elapsed_wall_s']=round(time.monotonic()-started,3)
        if process is not None and termination['pre_cleanup_exit_code'] is None:
            termination['pre_cleanup_exit_code']=process.poll()
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
            if e.get('event')=='A4_PUPIL_WBB_CHUNK']
    project=None
    if chunks and all(isinstance(c,dict) and
                      isinstance(c.get('index'),int) and
                      isinstance(c.get('text'),str) for c in chunks):
        indices=[x['index'] for x in chunks]
        if indices==list(range(len(indices))):
            project=''.join(chunk['text'] for chunk in chunks)
            (ARTIFACT/'pupil-project.wbb').write_text(project,encoding='utf-8')
    completed=next((e.get('detail') for e in ack.EVENTS
                    if e.get('event')=='A4_PUPIL_WBB_COMPLETE'),None)
    project_ok=(project is not None and isinstance(completed,dict) and
                completed.get('chars')==len(project))
    if project_ok:
        try:
            parsed=json.loads(project)
            project_ok=(parsed.get('format')=='webeeblocks-project' and
                        parsed.get('activity',{}).get('id')=='progression-decision-h-v1')
        except (ValueError,TypeError,AttributeError):
            project_ok=False
    steps=[
        ('A4_PUPIL_PROJECT_REOPENED','a'),
        ('A4_PUPIL_INTERPRETER_LANDED','a'),
        ('A4_PUPIL_NATIVE_ACHIEVED','a'),
        ('A4_PUPIL_NATIVE_RESET',None),
        ('A4_PUPIL_PROJECT_REOPENED','b'),
        ('A4_PUPIL_INTERPRETER_LANDED','b'),
        ('A4_PUPIL_NATIVE_ACHIEVED','b'),
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
    outcomes=re.findall(
        r'WEBEEBLOCKS_DECISION_H_RESULT scene=([AB]) attempt=([0-9]+) '
        r'status=([a-z-]+) stage=([0-9]+)',text)
    rays=[float(v) for v in re.findall(
        r'WEBEEBLOCKS_RUNTIME_V2 TRACE RANGE front value=([0-9.]+)',text)]
    moves=re.findall(
        r'WEBEEBLOCKS_RUNTIME_V2 TRACE MOVE forward distance=([0-9.]+) stop=1',text)
    vertical=re.findall(
        r'WEBEEBLOCKS_RUNTIME_V2 TRACE VERTICAL (up|down) distance=([0-9.]+) stop=1',text)
    # The pinned native launcher writes here, never read A3's stale log.
    browser_log=ARTIFACT/'browser-launch.log'
    browser_text=browser_log.read_text(encoding='utf-8',errors='replace') if browser_log.exists() else ''
    browser_ok=('BROWSER_LAUNCHED args=' in browser_text and
                'decision_h_pupil_probe.html' in browser_text)
    valid=(not missing and ordered and in_order and
           events.count('A4_PUPIL_ERROR')==0 and
           project_ok and browser_ok and
           outcomes==[('A','1','achieved','4'),('B','2','achieved','4')] and
           len(rays)==2 and 0.3<=rays[0]<=0.85 and 0.9<=rays[1]<=1.35 and
           moves==['0.200000000','0.750000000','0.800000000']*2 and
           vertical==[('up','0.250000000'),('down','0.350000000'),
                      ('up','0.250000000'),('up','0.200000000'),
                      ('up','0.250000000'),('up','0.100000000'),
                      ('down','0.250000000'),('down','0.200000000')] and
           text.count('WEBEEBLOCKS_RUNTIME_V2 TRACE TAKEOFF height=0.500000000 stop=1')==2 and
           text.count('WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1')==2 and
           text.count('WEBEEBLOCKS_DECISION_H_READY scene=decision-h-a-v1')>=1 and
           text.count('WEBEEBLOCKS_DECISION_H_READY scene=decision-h-b-v1')>=1 and
           'WEBEEBLOCKS_DECISION_H_FATAL' not in text and
           'WEBEEBLOCKS_RUNTIME_V2 FATAL' not in text)
    # Diagnostic-only: request metadata captured at the actual Chrome bridge.
    # An attempted browser send does NOT prove native receipt; missing native
    # response is not interpreted as a flight failure cause by this probe.
    trace_events=[e.get('detail') for e in ack.EVENTS
                  if e.get('event')=='A4_PUPIL_WWI_TRACE']
    wwi_frames=(trace_events[0].get('frames') if len(trace_events)==1 and
                isinstance(trace_events[0],dict) else None)
    # Positive native evidence must be observable at BOTH browser bridge ends.
    # On failure, still archive incomplete frames; they are diagnostic, never
    # a substitute for a real physical mission result.
    trace_ok=(isinstance(wwi_frames,list) and 1<=len(wwi_frames)<=96 and
              all(isinstance(f,dict) and
                  set(f)=={'direction','id','kind','monotonic_ms'} and
                  f.get('direction') in ('attempted_send','received') and
                  type(f.get('id')) is int and f['id']>=1 and
                  type(f.get('monotonic_ms')) is int and
                  f['monotonic_ms']>=0 and
                  isinstance(f.get('kind'),str) and bool(f['kind'])
                  for f in wwi_frames))
    if trace_ok:
        sent=next((i for i,f in enumerate(wwi_frames)
                   if f['direction']=='attempted_send' and
                   f['id']==7 and f['kind']=='VERTICAL'),None)
        received=next((i for i,f in enumerate(wwi_frames)
                       if f['direction']=='received' and
                       f['id']==7 and f['kind']=='OK'),None)
        trace_ok=(sent is not None and received is not None and sent<received)
    valid=valid and trace_ok
    summary={'pass':valid,'required_missing':missing,'ordered':ordered,
             'wwi_frames':wwi_frames,'wwi_trace_attested':trace_ok,
             'events_ordered':in_order,'native_outcomes':outcomes,
             'rays_m':rays,'moves':moves,'vertical':vertical,
             'browser':browser_ok,'one_project':project_ok,
             'project_sha256':hashlib.sha256(project.encode('utf-8')).hexdigest() if project else None,
             'project_bytes':len(project.encode('utf-8')) if project else None,
             'profile':'CI-only not registered in student activities.js',
             'runner_termination':termination}
    (ARTIFACT/'summary.json').write_text(
        json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    if not valid:
        print('A4_PUPIL_RUNNER_TERMINATION '+json.dumps(termination,sort_keys=True),
              file=sys.stderr,flush=True)
        print('FAIL A4 same native .wbb on A/B: '+json.dumps(summary),file=sys.stderr)
        print(text[-13500:],file=sys.stderr)
        return 1
    print('PASS A4 same .wbb on A/B; native sensor conditional, full physics, H+threshold, LAND and C oracle achieved for both variants',flush=True)
    return 0

if __name__=='__main__':
    raise SystemExit(run())

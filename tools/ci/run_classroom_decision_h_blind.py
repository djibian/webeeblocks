#!/usr/bin/env python3
"""Real native A4 adversarial blind routes (not a claim against all algorithms).

Wrong fixed high path against scene A's H, and wrong fixed low path against
scene B's curb. No sensor read, no Blockly AST rule and no simulated oracle:
the independent C Webots observer must reject both live trajectories.
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

import prepare_classroom_decision_h_pupil as pupil
import run_classroom_altitude_scene_ack as ack

ROOT=pupil.ROOT
WORLD=ROOT/'worlds/ci_classroom_decision_h_blind.wbt'
PROJECT=ROOT/'worlds/.ci_classroom_decision_h_blind.wbproj'
ARTIFACT=ROOT/'ci-artifacts/progression-decision-h-blind'
MARKER='# WEBEEBLOCKS_A4_BLIND_NATIVE_NEGATIVE_CI_ONLY'

def world_text()->str:
    base=pupil.compose(pupil.ack.SOURCE.read_text(encoding='utf-8'))
    if base.count('window "decision_h_pupil_probe"')!=1 or base.count(pupil.MARKER)!=1:
        raise ValueError('invalid original school classroom identity')
    text=base.replace('window "decision_h_pupil_probe"',
                      'window "decision_h_blind_probe"').replace(pupil.MARKER,MARKER)
    if text.count(MARKER)!=1 or text.count('window "decision_h_blind_probe"')!=1:
        raise ValueError('invalid blind witness world')
    return text

def main()->int:
    ARTIFACT.mkdir(parents=True,exist_ok=True)
    logfile=ARTIFACT/'webots.log'
    if WORLD.exists() or PROJECT.exists():
        raise FileExistsError('refusing to overwrite existing blind-native world')
    body=world_text()
    ack.EVENTS.clear()
    server=None
    output=None
    process=None
    try:
        for rel in ('controllers/crazyflie_classroom_v2/crazyflie_classroom_v2',
                    'controllers/progression_decision_h_v1/progression_decision_h_v1'):
            f=ROOT/rel
            if not f.is_file() or f.stat().st_size==0:
                raise FileNotFoundError('missing native school/observer binary: '+rel)
        WORLD.write_text(body,encoding='utf-8')
        PROJECT.write_text(pupil.PROJECT_TEXT,encoding='utf-8')
        print('A4_BLIND_WORLD_SHA256 '+hashlib.sha256(body.encode()).hexdigest(),
              flush=True)
        server=ack.http.server.ThreadingHTTPServer(('127.0.0.1',8765),ack.Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        output=logfile.open('w',encoding='utf-8')
        process=subprocess.Popen(
            ['timeout','-k','5s','360s','xvfb-run','-a','webots',
             '--stdout','--stderr','--batch','--mode=realtime',str(WORLD)],
            cwd=ROOT,env={**os.environ,'WEBOTS_WEB_BROWSER':
                          '/workspace/tools/ci/webots_runtime_v2_browser.sh'},
            stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
        start=time.monotonic()
        while time.monotonic()-start<345:
            names=[e.get('event') for e in ack.EVENTS]
            if ('A4_BLIND_TEST_COMPLETE' in names or
                'A4_BLIND_ERROR' in names or process.poll() is not None):break
            if time.monotonic()-start>45 and 'A4_BLIND_HTML_LOADED' not in names:
                print('A4_BLIND_FATAL no native browser after 45s',file=sys.stderr)
                break
            time.sleep(.2)
    finally:
        if process and process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait(timeout=8)
        if output:output.close()
        if server:
            server.shutdown()
            server.server_close()
        (ARTIFACT/'events.json').write_text(
            json.dumps(ack.EVENTS,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        if WORLD.exists():
            if WORLD.read_text(encoding='utf-8')!=body:
                raise ValueError('refusing to delete changed blind-native world')
            WORLD.unlink()
        if PROJECT.exists():
            if PROJECT.read_text(encoding='utf-8')!=pupil.PROJECT_TEXT:
                raise ValueError('refusing to delete changed blind-native Webots project')
            PROJECT.unlink()
    log=logfile.read_text(encoding='utf-8',errors='replace')
    events=ack.EVENTS
    names=[e.get('event') for e in events]
    sequence=['A4_BLIND_HTML_LOADED','A4_BLIND_JS_STARTED',
      'A4_BLIND_RUNTIME_READY','A4_BLIND_SCENE_READY',
      'A4_BLIND_WRONG_BRANCH_STARTED','A4_BLIND_NATIVE_REFUSED',
      'A4_BLIND_NATIVE_RESET','A4_BLIND_SCENE_READY',
      'A4_BLIND_WRONG_BRANCH_STARTED','A4_BLIND_NATIVE_REFUSED',
      'A4_BLIND_NATIVE_RESET','A4_BLIND_SCENE_READY',
      'A4_BLIND_WRONG_PAD_STARTED','A4_BLIND_WRONG_PAD_REFUSED',
      'A4_BLIND_NATIVE_RESET','A4_BLIND_SCENE_READY',
      'A4_BLIND_CONTACT_STARTED','A4_BLIND_CONTACT_REFUSED',
      'A4_BLIND_TEST_COMPLETE']
    valid_sequence=names==sequence
    refused=[e.get('detail') for e in events
             if e.get('event')=='A4_BLIND_NATIVE_REFUSED']
    refused_ok=(len(refused)==2 and
      [r.get('variant') for r in refused]==['a','b'] and
      [r.get('status') for r in refused]==['not-achieved','not-achieved'] and
      [r.get('wrong') for r in refused]==['high-on-H','low-on-threshold'] and
      [r.get('reason') for r in refused]==['unsafe-clearance','unsafe-clearance'] and
      [r.get('renderedDetail') for r in refused]==[
        'MISSION NON RÉUSSIE — Mission non accomplie — Zone ou hauteur de franchissement non respectée'
      ]*2)
    wrong_pad=[e.get('detail') for e in events
               if e.get('event')=='A4_BLIND_WRONG_PAD_REFUSED']
    wrong_pad_ok=(len(wrong_pad)==1 and
      wrong_pad[0].get('variant')=='a' and
      wrong_pad[0].get('status')=='not-achieved' and
      wrong_pad[0].get('reason')=='wrong-pad' and
      wrong_pad[0].get('renderedDetail')==
        'MISSION NON RÉUSSIE — Mission non accomplie — Atterrissage hors de la zone prévue')
    contact=[e.get('detail') for e in events if e.get('event')=='A4_BLIND_CONTACT_REFUSED']
    contact_ok=(len(contact)==1 and
      contact[0].get('variant')=='a' and
      contact[0].get('target')=='H_LEFT' and
      contact[0].get('status')=='not-achieved' and
      contact[0].get('reason')=='obstacle-contact' and
      contact[0].get('renderedDetail')==
        'MISSION NON RÉUSSIE — Mission non accomplie — Contact avec un obstacle')
    resets=[e.get('detail') for e in events if e.get('event')=='A4_BLIND_NATIVE_RESET']
    resets_ok=(len(resets)==3 and
      [x.get('between') for x in resets]==['a,b','b,wrong-pad','wrong-pad,contact'])
    results=re.findall(
      r'WEBEEBLOCKS_DECISION_H_RESULT scene=([AB]) attempt=([0-9]+) '
      r'status=([a-z-]+) stage=([0-9]+)',log)
    first_fail=re.findall(
      r'WEBEEBLOCKS_DECISION_H_VERDICT_SAMPLE attempt=([0-9]+) '
      r'time=[0-9.]+ xyz=([-0-9.]+),([-0-9.]+),([-0-9.]+) '
      r'velocity=[-0-9.]+,[-0-9.]+,[-0-9.]+ contact=([-0-9]+) '
      r'completed=([01]) stage=([0-9]+) airborne=([01]) verdict=2',log)
    # Check the exact live physical x-domain where the wrong H/curb fails,
    # before the 0.75m station and without a collision contact substitution.
    invalid_samples=(len(first_fail)==4 and
      [s[0] for s in first_fail]==['1','2','3','4'] and
      all(0.55<float(s[1])<0.9 and s[4]=='0' and s[5]=='0'
          and s[6]=='0' and s[7]=='1' for s in first_fail[:2]) and
      float(first_fail[0][3])>0.530 and float(first_fail[1][3])<0.790 and
      1.60<float(first_fail[2][1])<1.90 and
      0.20<float(first_fail[2][2])<0.50 and
      0.0<float(first_fail[2][3])<=0.020 and
      first_fail[2][4:] == ('0','1','4','1') and
      0.65<float(first_fail[3][1])<0.85 and
      0.08<float(first_fail[3][2])<0.280 and
      0.25<float(first_fail[3][3])<=0.530 and
      first_fail[3][4]=='1' and first_fail[3][5]=='0' and
      first_fail[3][6] in ('0','1') and first_fail[3][7]=='1')
    # The last real landing has crossed both obstacles (stage 4);
    # the two deliberately wrong in-flight crossings fail at stage 0.
    # Capture the native stage and refuse any different chronology rather
    # than deleting a legitimate wrong-pad verdict from the evidence.
    native_reasons=re.findall(
      r'WEBEEBLOCKS_DECISION_H_RESULT scene=([AB]) attempt=([0-9]+) '
      r'status=not-achieved stage=([0-9]+) reason=([a-z-]+)',log)
    native_reason_ok=(len(native_reasons)==4 and native_reasons[:3]==[
      ('A','1','0','unsafe-clearance'),
      ('B','2','0','unsafe-clearance'),
      ('A','3','4','wrong-pad')] and
      native_reasons[3][:2]==('A','4') and
      native_reasons[3][2] in ('0','1') and
      native_reasons[3][3]=='obstacle-contact')
    # This is a real collider-side Webots contact, not a guessed pose or
    # a browser-supplied collision flag. It must precede the C terminal
    # verdict in exactly the fourth native attempt.
    fourth=log.find('WEBEEBLOCKS_DECISION_H_ATTEMPT attempt=4')
    contact_index=log.find('WEBEEBLOCKS_DECISION_H_COLLIDER_CONTACT type=H_LEFT',fourth)
    terminal_index=log.find('WEBEEBLOCKS_DECISION_H_RESULT scene=A attempt=4 status=not-achieved',fourth)
    native_contact_ok=(fourth>=0 and contact_index>fourth and
                       terminal_index>contact_index)
    no_sensor='WEBEEBLOCKS_RUNTIME_V2 TRACE RANGE' not in log
    browser_log=ARTIFACT/'browser-launch.log'
    browser=browser_log.read_text(encoding='utf-8',errors='replace') if browser_log.exists() else ''
    browser_ok=('BROWSER_LAUNCHED args=' in browser and
                'decision_h_blind_probe.html' in browser)
    results_ok=(len(results)==4 and results[:3]==[
      ('A','1','not-achieved','0'),
      ('B','2','not-achieved','0'),
      ('A','3','not-achieved','4')] and
      results[3][:3]==('A','4','not-achieved') and
      results[3][3] in ('0','1'))
    valid=(valid_sequence and refused_ok and wrong_pad_ok and contact_ok and
           resets_ok and native_reason_ok and native_contact_ok and
           results_ok and no_sensor and browser_ok and invalid_samples and
           'WEBEEBLOCKS_DECISION_H_FATAL' not in log)
    summary={'pass':valid,'sequence':names,'native_results':results,
             'native_failure_reasons':native_reasons,
             'physical_rejection_samples':first_fail,
             'blind_cases':refused,'wrong_pad':wrong_pad,'contact':contact,
             'native_contact_ok':native_contact_ok,'resets_ok':resets_ok,
             'range_reads':0 if no_sensor else 'unexpected',
             'browser_ok':browser_ok,
             'note':'three native physical failure causes; not universal impossibility'}
    (ARTIFACT/'summary.json').write_text(
      json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    if not valid:
        print('FAIL A4 real native blind-path controls '+json.dumps(summary),
              file=sys.stderr,flush=True)
        print(log[-11000:],file=sys.stderr)
        return 1
    print('A4_BLIND_NATIVE_PASS native clearance, wrong-pad Floor and physical H_LEFT contact displayed',flush=True)
    return 0

if __name__=='__main__':
    raise SystemExit(main())

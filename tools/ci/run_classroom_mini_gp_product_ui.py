#!/usr/bin/env python3
"""CI-only real A7 student status UI: Webots R2025a -> WWI -> production main.js.

No fake outcome, injected terminal status, camera teleport, or test DOM. The
only browser automation constructs a Blockly program, selects the public A7
profile and clicks the ordinary product Run button in blockly_v2.html.
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
import time
import urllib.request

import prepare_classroom_mini_gp_pupil as school
from prepare_classroom_altitude_scene_ack import SOURCE

ROOT=school.ROOT
OUT=ROOT/"ci-artifacts/progression-mini-gp-product-ui"
WORLD=ROOT/"worlds/ci_classroom_mini_gp_product_ui.wbt"
PROJECT=ROOT/"worlds/.ci_classroom_mini_gp_product_ui.wbproj"
MARKER="# WEBEEBLOCKS_A7_PRODUCT_WINDOW_NATIVE_CI_ONLY"
WINDOW='window "mini_gp_pupil_probe"'
PRODUCT='window "blockly_v2"'
EXPECTED="Mission non accomplie — Fin de parcours ou zone de pose non validée"

# Reuse the repository's existing Chrome DevTools client, tested with genuine
# Webots product UI. The package is provided by python3-websocket in the job.
sys.path.insert(0,str(ROOT/"experiments/runtime-v2-student-ui"))
from probe import Cdp, wait_target  # noqa: E402

def compose():
    original=school.compose(SOURCE.read_text(encoding="utf-8"))
    if original.count(WINDOW)!=1 or original.count(school.MARKER)!=1:
        raise ValueError("A7 world has changed: fail closed")
    body=original.replace(WINDOW,PRODUCT,1).replace(school.MARKER,MARKER,1)
    if (body.count(PRODUCT)!=1 or body.count(MARKER)!=1 or
        body.count('translation -1.4 0 0.015')!=1 or
        'controller "crazyflie_runtime_v2"' in body or
        "DEF WEBEEBLOCKS_MINI_GP_" in body):
        raise ValueError("A7 product world is not native, isolated and canonical")
    return body

def prepare():
    if WORLD.exists() or PROJECT.exists():
        raise FileExistsError("refuse concurrent or stale UI native world")
    body=compose()
    WORLD.write_text(body,encoding="utf-8")
    PROJECT.write_text(school.PROJECT_TEXT,encoding="utf-8")
    print("A7_PRODUCT_UI_WORLD_SHA256 "+hashlib.sha256(body.encode()).hexdigest(),flush=True)

def cleanup():
    if WORLD.exists():
        if WORLD.read_text(encoding="utf-8")!=compose():
            raise ValueError("native product world changed during execution; refuse cleanup")
        WORLD.unlink()
    if PROJECT.exists():
        if PROJECT.read_text(encoding="utf-8")!=school.PROJECT_TEXT:
            raise ValueError("native Webots project changed; refuse cleanup")
        PROJECT.unlink()

# This JS executes INSIDE the genuine blockly_v2 page served by Webots.
# Nothing in the test writes a native verdict, a backend response, or the
# production status elements. The product's own runProgram updates both.
SETUP=r'''(() => {
  if (!location.pathname.endsWith('/robot_windows/blockly_v2/blockly_v2.html'))
    throw new Error('not the actual Blockly v2 page');
  const status=document.getElementById('statusPanel');
  const state=document.getElementById('runtimeState');
  const detail=document.getElementById('runtimeDetail');
  if (!status || status.getAttribute('aria-live')!=='polite' ||
      !state || !detail || !status.contains(state) || !status.contains(detail) ||
      !document.querySelector('script[src="main.js"]'))
    throw new Error('genuine product status elements unavailable');
  if (!runtimeBackend || !runtimeBackend.ready || !workspace ||
      state.textContent!=='PRÊT')
    throw new Error('production UI not ready');
  const profile=JSON.parse(JSON.stringify(
    WebeeBlocksActivities.getProfile('progression-mini-grand-prix-v1')));
  profile.runtime.scene='mini-grand-prix-l-v1';
  WebeeBlocksActivityProfiles.validateProfile(profile,WebeeBlocksActivities.BLOCK_CATALOG);
  runtimeProfile=profile;
  profileFieldOptions.setProfile(profile,workspace);
  workspace.updateToolbox(buildToolbox(profile));
  profileFieldOptions.applyWorkspace(workspace);
  const ws=new Blockly.Workspace();
  const create=t=>ws.newBlock(t);
  function number(parent,input,val){
    const n=create('math_number');n.setFieldValue(String(val),'NUM');
    const socket=parent.getInput(input);
    if(!socket || !socket.connection)throw new Error('missing numeric block socket');
    socket.connection.connect(n.outputConnection);n.setShadow(true);
  }
  const takeoff=create('webeeblocks_v2_takeoff');number(takeoff,'HEIGHT',0.50);
  const speed=create('webeeblocks_v2_speed');speed.setFieldValue('0.1','SPEED');
  const move=create('webeeblocks_v2_move');move.setFieldValue('forward','DIRECTION');
  number(move,'DISTANCE',0.20);
  const land=create('webeeblocks_v2_land');
  takeoff.nextConnection.connect(speed.previousConnection);
  speed.nextConnection.connect(move.previousConnection);
  move.nextConnection.connect(land.previousConnection);
  const data=Blockly.serialization.workspaces.save(ws);
  workspace.clear();
  Blockly.serialization.workspaces.load(data,workspace);
  ws.dispose();
  WebeeBlocksActivityContract.applyFieldBounds(profile,workspace);
  WebeeBlocksActivityContract.preflightWorkspace(profile,workspace);
  const ast=WebeeBlocksSemanticAst.compileWorkspace(workspace);
  if(ast.program.length!==4 ||
     ast.program[0].kind!=='takeoff' ||
     ast.program[1].kind!=='set_speed' ||
     ast.program[2].kind!=='move' || ast.program[2].distance_m!==0.20 ||
     ast.program[3].kind!=='land')
    throw new Error('unexpected Blockly AST for native failure experiment');
  window.__a7ProductNative={
    phase:'built',source:'blockly_v2/main.js',
    statusEvents:[],wwiResponses:[],clicked:false,astKinds:ast.program.map(a=>a.kind)
  };
  window.addEventListener('webeeblocks-runtime-v2',event=>{
    const p=window.__a7ProductNative;
    if(p&&p.statusEvents.length<64)
      p.statusEvents.push({state:event.detail.state,detail:event.detail.detail});
  });
  window.addEventListener('webeeblocks-wwi',event=>{
    const p=window.__a7ProductNative,raw=String(event.detail);
    if(p && p.wwiResponses.length<64 &&
       /^WEBEEBLOCKS_RUNTIME_V2 RESPONSE [0-9]+ /.test(raw))
      p.wwiResponses.push(raw);
  });
  return {page:location.pathname,astKinds:window.__a7ProductNative.astKinds};
})()'''

PREPARE=r'''(() => {
  const p=window.__a7ProductNative;
  if(!p||p.phase!=='built')throw new Error('missing Blockly UI setup');
  p.phase='preparing';
  runtimeBackend.prepareActivity(runtimeProfile).then(()=>{
    p.phase='prepared';
  }).catch(e=>{p.phase='prepare-error';p.error=String(e&&e.stack||e);});
  return true;
})()'''

EXECUTE=r'''(() => {
  const p=window.__a7ProductNative;
  if(!p||p.phase!=='prepared'||p.clicked)
    throw new Error('not prepared for a single native product run');
  const button=document.getElementById('submit');
  if(button.disabled || button.textContent!=='Lancer le vol')
    throw new Error('real product Run button disabled after scene preparation');
  p.phase='running';p.clicked=true;
  button.click();
  return {clicked:p.clicked,disabled:button.disabled};
})()'''

SNAPSHOT=r'''(() => {
  const p=window.__a7ProductNative||null;
  const state=document.getElementById('runtimeState');
  const detail=document.getElementById('runtimeDetail');
  return {
    phase:p?p.phase:null,error:p?p.error:null,clicked:p?p.clicked:null,
    source:p?p.source:null,astKinds:p?p.astKinds:null,
    statusEvents:p?p.statusEvents:null,wwiResponses:p?p.wwiResponses:null,
    state:state?state.textContent:null,detail:detail?detail.textContent:null,
    bodyState:document.body.dataset.runtimeState||null,
    ready:!!(runtimeBackend&&runtimeBackend.ready),
    running:!!runtimeRunning,terminal:!!runtimeTerminal,
    outcomePending:!!runtimeOutcomePending,
    page:location.pathname,
    nativeProductMain:!!document.querySelector('script[src="main.js"]'),
    statusLive:document.getElementById('statusPanel')?.getAttribute('aria-live')
  };
})()'''

def run():
    OUT.mkdir(parents=True,exist_ok=True)
    prepare()
    proc=None
    browser=None
    log=None
    browserlog=None
    c=None
    summary={}
    success=False
    try:
        for rel in ("controllers/crazyflie_classroom_v2/crazyflie_classroom_v2",
                    "controllers/progression_mini_grand_prix_v1/progression_mini_grand_prix_v1"):
            p=ROOT/rel
            if not p.is_file() or p.stat().st_size<1:
                raise FileNotFoundError("real native controller missing "+rel)
        conf=Path("/root/.config/Cyberbotics/Webots-R2025a.conf")
        conf.parent.mkdir(parents=True,exist_ok=True)
        conf.write_text("[RobotWindow]\n"
            "browser=/workspace/experiments/runtime-v2-student-ui/browser.sh\n"
            "newBrowserWindow=false\n",encoding="utf-8")
        browser_script=ROOT/"experiments/runtime-v2-student-ui/browser.sh"
        browser_script.chmod(browser_script.stat().st_mode|0o111)
        env=dict(os.environ)
        env["WEBEEBLOCKS_CI_ARTIFACT_DIR"]=str(OUT)
        log=(OUT/"webots.log").open("w",encoding="utf-8")
        proc=subprocess.Popen(["timeout","-k","5s","280s","xvfb-run","-a","webots",
              "--stdout","--stderr","--batch","--mode=realtime",str(WORLD)],
             cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,
             start_new_session=True)
        first=time.monotonic()
        target=None
        while time.monotonic()-first<90:
            if proc.poll() is not None:
                raise RuntimeError("native Webots exited before product UI started")
            try:target=wait_target(timeout=2)
            except (RuntimeError,OSError,ValueError):pass
            if target:break
            # The automatic Webots browser may be hidden by xvfb/Chrome.
            # Only launch a fallback if Webots HTTP truly serves the real HTML.
            if time.monotonic()-first>22 and browser is None:
                page=("http://localhost:1234/robot_windows/blockly_v2/"
                      "blockly_v2.html?name=Crazyflie%20WebeeBlocks")
                try:
                    with urllib.request.urlopen(page,timeout=2) as response:
                        html=response.read(10000)
                        if response.status!=200 or b'id="runtimeState"' not in html:
                            raise RuntimeError("real product page not served")
                except OSError:
                    continue
                browserlog=(OUT/"browser-explicit.log").open("w",encoding="utf-8")
                browser=subprocess.Popen(["/bin/bash",str(browser_script),page],
                    cwd=ROOT,env=env,stdout=browserlog,
                    stderr=subprocess.STDOUT,start_new_session=True)
        if not target:raise RuntimeError("real blockly_v2 Chrome CDP page unavailable")
        c=Cdp(target["webSocketDebuggerUrl"])
        c.ws.settimeout(65)
        c.call("Runtime.enable")
        c.call("Page.enable")
        c.call("Page.bringToFront")
        snap=None
        deadline=time.monotonic()+65
        while time.monotonic()<deadline:
            try:snap=c.eval(SNAPSHOT)
            except Exception:
                time.sleep(.2);continue
            if snap and snap["ready"] and snap["state"]=="PRÊT":
                break
            if snap and snap["state"]=="ERREUR":
                raise RuntimeError("production startup error "+json.dumps(snap,ensure_ascii=False))
            time.sleep(.2)
        else:
            raise RuntimeError("real student UI not ready "+json.dumps(snap,ensure_ascii=False))
        summary["setup"]=c.eval(SETUP)
        c.eval(PREPARE)
        deadline=time.monotonic()+55
        while time.monotonic()<deadline:
            snap=c.eval(SNAPSHOT)
            if snap["phase"]=="prepared":break
            if snap["phase"]=="prepare-error":
                raise RuntimeError("native scene preparation failed: "+str(snap["error"]))
            time.sleep(.25)
        else:raise RuntimeError("native A7 scene not prepared")
        time.sleep(1.6)
        summary["click"]=c.eval(EXECUTE)
        deadline=time.monotonic()+105
        while time.monotonic()<deadline:
            snap=c.eval(SNAPSHOT)
            if snap["state"] in ("MISSION NON RÉUSSIE","MISSION RÉUSSIE","ERREUR","MISSION INTERROMPUE"):
                break
            time.sleep(.25)
        else:raise RuntimeError("product UI never reached a terminal outcome")
        summary["product_dom"]=snap
        # The page that rendered this was served unchanged by the product;
        # the test did not create runtimeState/runtimeDetail or call status setters.
        expected=(
            snap["state"]=="MISSION NON RÉUSSIE" and
            snap["bodyState"]=="MISSION NON RÉUSSIE" and
            snap["detail"]==EXPECTED and
            snap["terminal"] is True and snap["outcomePending"] is False and
            snap["clicked"] is True and snap["nativeProductMain"] is True and
            snap["statusLive"]=="polite" and
            any(e.get("state")=="MISSION NON RÉUSSIE" and e.get("detail")==EXPECTED
                for e in (snap["statusEvents"] or [])) and
            any(re.search(r"RESPONSE [0-9]+ STATE not-achieved reason=early-finish$",q)
                for q in (snap["wwiResponses"] or []))
        )
        if not expected:
            raise AssertionError("real product status or WWI token mismatch")
        success=True
    except Exception as exc:
        summary["error"]=str(exc)
        print("A7_PRODUCT_UI_NATIVE_UNPROVEN "+str(exc),file=sys.stderr,flush=True)
    finally:
        if c:
            try:c.ws.close()
            except Exception:pass
        if browser:
            try:os.killpg(browser.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:browser.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(browser.pid,signal.SIGKILL);browser.wait()
        if proc and proc.poll() is None:
            try:os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        if log:log.close()
        if browserlog:browserlog.close()
        cleanup()
    raw=(OUT/"webots.log").read_text(encoding="utf-8",errors="replace") if (OUT/"webots.log").exists() else ""
    verdict=re.findall(
        r"WB_MINI_NATIVE_RESULT variant=L attempt=1 status=not-achieved crossed=0 turned=0 reason=([a-z-]+)",raw)
    physical=(
        bool(verdict) and set(verdict)=={"early-finish"} and
        "WEBEEBLOCKS_RUNTIME_V2 TRACE TAKEOFF height=0.500000000 stop=1" in raw and
        "WEBEEBLOCKS_RUNTIME_V2 TRACE MOVE forward distance=0.200000000 stop=1" in raw and
        "WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1" in raw and
        "WB_MINI_NATIVE_FATAL" not in raw and
        "WEBEEBLOCKS_RUNTIME_V2 FATAL" not in raw)
    summary["native_verdicts"]=verdict
    summary["native_motor_and_oracle_attested"]=physical
    summary["pass"]=bool(success and physical)
    (OUT/"summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False,sort_keys=True)+"\n",
        encoding="utf-8")
    if not summary["pass"]:
        print("FAIL A7 real student main.js status with native Webots: "+
            json.dumps(summary,ensure_ascii=False),file=sys.stderr,flush=True)
        print(raw[-9000:],file=sys.stderr)
        return 1
    print("PASS A7 real blockly_v2/main.js runtimeState/runtimeDetail: native early-finish WWI reason from actual motor flight",flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(run())

#!/usr/bin/env python3
"""A6 Draft ONLY: independently judge the same private generic Blockly program
inside the genuine Webots R2025a classroom Robot Window.

Three separate real-world CI jobs load identical CI-only project WBB bytes.
They choose 1/2/3 H with real Chrome clicks, run the student's button,
and require BOTH native C success and UI MISSION RÉUSSIE.
No solver is shipped in student starters; no Windows/hardware PASS is implied.
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

from count_h_cdp_evidence import attest_visit
from run_classroom_count_h_variant_cdp import (
    Chrome, FATAL, ROOT, SCENES, WORLD, browser_url, content,
)
from a6_pupil_negative_cdp import _browser_state, _click_real_button

OUT_BASE=ROOT/"ci-artifacts/progression-count-h-private-product-ui"
PRIVATE_WBB=(ROOT/"ci-artifacts/progression-count-h-private-blockly/"
             "a6-real-profile-ci-only.wbb")
RESULT=re.compile(r"(?m)^WEBEEBLOCKS_A6_MOTOR_RESULT status=achieved n=([123]) ")
FLOOR=re.compile(r"(?m)^WEBEEBLOCKS_A6_MOTOR_NATIVE_FLOOR_CONTACT n=([123]) ")
REJECT=re.compile(r"(?m)^WEBEEBLOCKS_A6_MOTOR_REJECT attempt=\d+ ")
ACK=re.compile(r"(?m)^WEBEEBLOCKS_RUNTIME_V2 RESPONSE \d+ SCENE_OK [0-9a-f]{64}$")


def check_candidate():
    if not PRIVATE_WBB.is_file() or PRIVATE_WBB.is_symlink():
        raise FileNotFoundError("no genuine-profile, CI-only A6 WBB")
    candidate=PRIVATE_WBB.read_text(encoding="utf-8")
    if not 1000<len(candidate)<200000:
        raise ValueError("private generic WBB size outside bound")
    parsed=json.loads(candidate)
    if (parsed.get("format")!="webeeblocks-project" or
        parsed.get("version")!=1 or
        parsed.get("activity",{}).get("id")!="progression-count-h-v1"):
        raise ValueError("private generic WBB profile identity invalid")
    if any(scene in candidate for scene in SCENES):
        raise ValueError("private candidate leaks session scene identity")
    return candidate


def run_one(variant):
    if variant not in (1,2,3):
        raise ValueError("A6 private UI CI variant must be 1/2/3")
    out=OUT_BASE/("n"+str(variant))
    out.mkdir(parents=True,exist_ok=True)
    log=out/"webots.log"
    browser=out/"browser-launch.log"
    if browser.exists() or log.exists():
        raise AssertionError("stale A6 native/browser trace in private UI job")
    result={"pass":False,"variant":variant,
            "scope":"CI-only genuine hidden A6 product profile, Webots R2025a, Chrome Blockly, actual motor and C oracle; Windows/teacher/hardware UNPROVEN"}
    candidate=check_candidate()
    result["candidate_sha256"]=hashlib.sha256(candidate.encode()).hexdigest()
    process=None
    dev=None
    observers={1:0,2:0,3:0}
    nonces=set()
    try:
        env=dict(os.environ)
        env["WEBOTS_WEB_BROWSER"]="/workspace/tools/ci/webots_count_h_variant_cdp.sh"
        env["WEBEEBLOCKS_CI_ARTIFACT_DIR"]=str(out)
        env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"]="true"
        with log.open("w",encoding="utf-8") as handle:
            process=subprocess.Popen(
                ["timeout","-k","5s","495s","xvfb-run","-a","webots",
                 "--stdout","--stderr","--batch","--mode=realtime",str(WORLD)],
                cwd=ROOT,env=env,stdout=handle,stderr=subprocess.STDOUT,
                start_new_session=True)
            end=time.monotonic()+460
            # First enter A, then reopen the saved program BEFORE selecting B/C.
            # A .wbb intentionally contains the activity, never its session scene.
            for index in range(1):
                n=index+1
                while time.monotonic()<end:
                    trace=content(log)
                    if any(f in trace for f in FATAL) or process.poll() is not None:
                        raise AssertionError("native A6 failed during private scene selection")
                    if dev is None:
                        url=browser_url()
                        if url:
                            dev=Chrome(url)
                    if dev is not None:
                        state=dev.state()
                        witness=attest_visit(trace,index,n,observers,nonces)
                        if (state and witness and
                            state["id"]=="progression-count-h-v1" and
                            state["scene"]==SCENES[n-1] and
                            state["ack"]==SCENES[n-1] and
                            state["status"]=="PRÊT" and state["enabled"]):
                            observers[n]=witness["ready_count"]
                            nonces.add(witness["nonce"])
                            break
                    time.sleep(0.25)
                else:
                    raise AssertionError("private generic A6 product scene not natively admitted")

            # Load through the actual browser manager, which validates the
            # genuine hidden school profile and enforces the Webots world.
            before=content(log)
            baseline=ACK.findall(before)
            payload=json.dumps(candidate,ensure_ascii=False)
            opened=dev.eval("""(async () => {
              const text="""+payload+""";
              const manager=window.WebeeBlocksProjectManager;
              if(!manager || !runtimeBackend || !runtimeBackend.ready)
                throw Error('genuine product browser/WWI not ready');
              await manager.openTemplateText('a6-private-generic-ci-only.wbb',text);
              const ast=WebeeBlocksSemanticAst.compileWorkspace(workspace);
              WebeeBlocksActivityContract.preflightWorkspace(runtimeProfile,workspace);
              WebeeBlocksActivityContract.preflightAst(runtimeProfile,ast);
              if(!ast || !ast.program || !ast.program.some(s=>s.kind==='while') ||
                 workspace.getAllBlocks(false).length<20)
                throw Error('private generic program absent/invalid in real Blockly');
              return {profile:runtimeProfile.id,
                scene:runtimeProfile.runtime.scene,
                nativeScene:runtimeBackend.sceneIdentity,
                blocks:workspace.getAllBlocks(false).length,
                project:manager.encodeCurrent()};
            })()""")
            if (not opened or
                opened.get("profile")!="progression-count-h-v1" or
                opened.get("scene")!=SCENES[0] or
                opened.get("nativeScene")!=SCENES[0] or
                opened.get("blocks",0)<20 or
                not isinstance(opened.get("project"),str)):
                raise AssertionError("private generic .wbb not loaded by genuine Blockly")
            if ACK.findall(content(log))!=baseline:
                raise AssertionError("idempotent generic project open imported new scene")
            encoded=opened["project"]
            # The newly opened project defaults safely to A. Now select
            # the target B/C from the visible pupil variant button. A fresh
            # scene token/observer is mandatory for each actual transition.
            for index in range(1,variant):
                n=index+1
                _click_real_button(dev,"activityVariant")
                while time.monotonic()<end:
                    trace=content(log)
                    if any(f in trace for f in FATAL) or process.poll() is not None:
                        raise AssertionError("native A6 failed during private scene selection")
                    if dev is None:
                        url=browser_url()
                        if url:
                            dev=Chrome(url)
                    if dev is not None:
                        state=dev.state()
                        witness=attest_visit(trace,index,n,observers,nonces)
                        if (state and witness and
                            state["id"]=="progression-count-h-v1" and
                            state["scene"]==SCENES[n-1] and
                            state["ack"]==SCENES[n-1] and
                            state["status"]=="PRÊT" and state["enabled"]):
                            observers[n]=witness["ready_count"]
                            nonces.add(witness["nonce"])
                            break
                    time.sleep(0.25)
                else:
                    raise AssertionError("private generic A6 product scene not natively admitted")

            if any(scene in encoded for scene in SCENES):
                raise AssertionError("private generic student project leaked scene ID")
            state=_browser_state(dev)
            if (state["status"]!="PRÊT" or not state["run_available"] or
                state["scene"]!=SCENES[variant-1] or
                state["native_scene"]!=SCENES[variant-1] or
                state["project"]!=encoded):
                raise AssertionError("private generic project changed during post-open scene selection: "+
                                     json.dumps({"status":state["status"],
                                                 "scene":state["scene"],
                                                 "native_scene":state["native_scene"],
                                                 "same_wbb":state["project"]==encoded}))
            result["block_count"]=opened["blocks"]
            result["product_wbb_sha256"]=hashlib.sha256(encoded.encode()).hexdigest()
            print("A6_PRIVATE_GENERIC_REAL_BROWSER_LOADED n="+str(variant)+
                  " Blockly_nonempty=true candidate_scene_leak=false",flush=True)
            _click_real_button(dev,"submit")
            terminal=None
            while time.monotonic()<end:
                trace=content(log)
                if any(f in trace for f in FATAL) or process.poll() is not None:
                    raise AssertionError("native fatal/exit during private generic flight")
                state=_browser_state(dev)
                if state["status"] in ("ERREUR","ARRÊTÉ","À CORRIGER"):
                    raise AssertionError("real generic Blockly runtime error: "+str(state["status"]))
                if state["terminal"] and not state["running"] and not state["pending"]:
                    terminal=state
                    break
                time.sleep(.4)
            if terminal is None:
                raise AssertionError("private generic Blockly flight did not terminate")
            result["ui_terminal_state"]=terminal["status"]
            matched=RESULT.findall(content(log))
            floor=FLOOR.findall(content(log))
            rejects=REJECT.findall(content(log))
            if (terminal["status"]!="MISSION RÉUSSIE" or matched!=[str(variant)] or
                floor!=[str(variant)] or rejects or
                terminal["project"]!=encoded):
                raise AssertionError(
                    "private generic real school UI mission NOT proven: "+
                    json.dumps({"status":terminal["status"],"native_results":matched,
                                "native_contacts":floor,"native_rejects":len(rejects),
                                "same_wbb":terminal["project"]==encoded}))
            result["pass"]=True
            result["native_result"]=matched
            result["same_wbb_after_flight"]=True
            print("WEBEEBLOCKS_A6_PRIVATE_GENERIC_PRODUCT_UI_PASS n="+str(variant)+
                  " native_C_oracle=achieved real_Chrome_student_Run=true "+
                  "exact_private_wbb_preserved=true",flush=True)
    except Exception as error:
        result["error"]=type(error).__name__+": "+str(error)
        print("WEBEEBLOCKS_A6_PRIVATE_GENERIC_PRODUCT_UI_REFUTATION n="+
              str(variant)+" "+result["error"],file=sys.stderr,flush=True)
    finally:
        if dev is not None:
            dev.ws.close()
        if process is not None and process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait(timeout=8)
        result["browser_launched"]="blockly_count_h.html" in content(browser)
        result["native_fatal"]=any(f in content(log) for f in FATAL)
        (out/"summary.json").write_text(
            json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    if result["pass"] and result["browser_launched"] and not result["native_fatal"]:
        return 0
    print(content(log)[-3500:],file=sys.stderr,flush=True)
    return 1


if __name__=="__main__":
    raise SystemExit(run_one(int(os.environ.get("A6_VARIANT","0"))))

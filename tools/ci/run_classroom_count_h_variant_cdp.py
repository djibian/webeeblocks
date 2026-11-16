#!/usr/bin/env python3
"""Non-decision A6 real UI test: Chrome CDP clicks, Webots-native scene ACKs."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.request import urlopen
import websocket
from count_h_cdp_evidence import attest_visit

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / "worlds/crazyflie_classroom_count_h_start.wbt"
OUT = ROOT / "ci-artifacts/progression-count-h-real-variant"
SCENES = ("count-h-1-v1", "count-h-2-v1", "count-h-3-v1")
FATAL = ("WEBEEBLOCKS_RUNTIME_V2 FATAL", "WEBEEBLOCKS_A6_MOTOR_FATAL")

def content(path):
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""

def browser_url():
    try:
        with urlopen("http://127.0.0.1:9222/json/list", timeout=1) as stream:
            pages = json.load(stream)
        for page in pages:
            if page.get("type") == "page" and "blockly_count_h.html" in page.get("url", ""):
                return page["webSocketDebuggerUrl"]
    except (OSError, ValueError, KeyError):
        pass
    return None

class Chrome:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=7, origin="http://localhost:1234")
        self.sequence = 0
    def call(self, method, params=None):
        self.sequence += 1
        seq = self.sequence
        self.ws.send(json.dumps({"id": seq, "method": method, "params": params or {}}))
        while True:
            response = json.loads(self.ws.recv())
            if response.get("id") != seq:
                continue
            if "error" in response:
                raise AssertionError("CDP rejected " + method + ": " + str(response["error"]))
            return response.get("result", {})
    def eval(self, expression):
        response = self.call("Runtime.evaluate", {
            "expression": expression, "returnByValue": True, "awaitPromise": True})
        if response.get("exceptionDetails"):
            raise AssertionError("JavaScript error " + str(response["exceptionDetails"]))
        return response.get("result", {}).get("value")
    def state(self):
        return self.eval("""(() => {
          let button = document.getElementById('activityVariant');
          let state = document.getElementById('runtimeState');
          let profile = typeof runtimeProfile !== 'undefined' ? runtimeProfile : null;
          let backend = typeof runtimeBackend !== 'undefined' ? runtimeBackend : null;
          let manager = window.WebeeBlocksProjectManager;
          // Real browser ProjectFiles manager, not a fabricated file serializer.
          let project = manager && typeof manager.encodeCurrent === 'function' ?
            manager.encodeCurrent() : null;
          return {
            id: profile ? profile.id : null,
            scene: profile ? profile.runtime.scene : null,
            ack: backend ? backend.sceneIdentity : null,
            status: state ? state.textContent.trim() : null,
            enabled: !!button && !button.hidden && !button.disabled,
            label: button ? button.textContent.trim() : null,
            project: project,
            projectMode: document.body && document.body.dataset ?
              (document.body.dataset.projectFileMode || null) : null,
            program: typeof workspace !== 'undefined' && workspace ?
              JSON.stringify(Blockly.serialization.workspaces.save(workspace)) : null
          };
        })()""")
    def verify_project_reopen(self):
        # Execute real in-browser ProjectFiles manager. No fake .wbb parser or
        # OS file picker: this is strictly a browser encode/openTemplateText
        # round trip, NOT a disk Save As/Open or Windows distribution test.
        return self.eval("""(async () => {
          const manager=window.WebeeBlocksProjectManager;
          if (!manager || typeof manager.encodeCurrent!=='function' ||
              typeof manager.openTemplateText!=='function')
            throw Error('real browser project manager unavailable');
          const before=manager.encodeCurrent();
          const foreign=WebeeBlocksProjectFiles.createStarterText('progression-sequence-v1');
          let refusal=null;
          try {
            await manager.openTemplateText('wrong-world.wbb',foreign);
          } catch(error) {
            refusal=String(error && error.message || error);
          }
          const afterRefusal=manager.encodeCurrent();
          if (!refusal || !refusal.includes('incompatible with the current Webots world') ||
              afterRefusal!==before)
            throw Error('foreign .wbb was accepted or mutated the student project');
          const result=await manager.openTemplateText('a6-browser-roundtrip.wbb',before);
          return {
            rejectedForeignWorld:true,
            before:before,
            after:manager.encodeCurrent(),
            name:manager.currentName(),
            id:runtimeProfile.id,
            scene:runtimeProfile.runtime.scene,
            nativeSceneIdentity:runtimeBackend.sceneIdentity,
            actualManager:true,
            openResultName:result && result.name || null
          };
        })()""")
    def click(self):
        point = self.eval("""(() => {
          let b = document.getElementById('activityVariant');
          if (!b || b.disabled || b.hidden) return null;
          let r=b.getBoundingClientRect();
          return r.width>5 && r.height>5 ? {x:r.left+r.width/2,y:r.top+r.height/2}:null;
        })()""")
        if not point:
            raise AssertionError("actual variant button disabled, hidden or unrendered")
        params = {"x":point["x"],"y":point["y"],"button":"left","clickCount":1}
        self.call("Input.dispatchMouseEvent",{"type":"mousePressed",**params})
        self.call("Input.dispatchMouseEvent",{"type":"mouseReleased",**params})

def run():
    OUT.mkdir(parents=True, exist_ok=True)
    log=OUT/"webots.log"
    browser=OUT/"browser-launch.log"
    if browser.exists():
        raise AssertionError("stale browser/CDP evidence")
    if 'window "blockly_count_h"' not in content(WORLD):
        raise AssertionError("wrong school WBT")
    process=None
    dev=None
    result={"pass":False,"scope":"Actual Chrome UI plus native scenes and in-browser .wbb serializer/reopen; no OS Save/Open or Windows release"}
    visits=[]
    project_bytes=None
    # Each native READY belongs to one scene incarnation, not to a previously
    # loaded variant. Returning to n=1 must yield a *second* native witness.
    observed_ready={1:0,2:0,3:0}
    seen_scene_nonces=set()
    try:
        env=dict(os.environ)
        env["WEBOTS_WEB_BROWSER"]="/workspace/tools/ci/webots_count_h_variant_cdp.sh"
        env["WEBEEBLOCKS_CI_ARTIFACT_DIR"]=str(OUT)
        env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"]="true"
        with log.open("w",encoding="utf-8") as output:
            process=subprocess.Popen(
                ["timeout","-k","5s","200s","xvfb-run","-a","webots",
                 "--stdout","--stderr","--batch","--mode=realtime",str(WORLD)],
                cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
            deadline=time.monotonic()+180
            original=None
            for index,count in enumerate((1,2,3,1)):
                if index:
                    dev.click()
                target=SCENES[count-1]
                while time.monotonic()<deadline:
                    trace=content(log)
                    if any(x in trace for x in FATAL):
                        raise AssertionError("Webots native FATAL")
                    if process.poll() is not None:
                        raise AssertionError("Webots exited before scene admission")
                    if dev is None:
                        uri=browser_url()
                        if uri:
                            dev=Chrome(uri)
                    if dev is not None:
                        state=dev.state()
                        # Require fresh nonce-bound SCENE_OK and subsequent native
                        # observer incarnation, never a stale earlier n=1 log.
                        native_witness=attest_visit(
                            trace,index,count,observed_ready,seen_scene_nonces)
                        ready=native_witness is not None
                        if (state and state["id"]=="progression-count-h-v1" and
                            state["scene"]==target and state["ack"]==target and
                            state["status"]=="PRÊT" and ready):
                            if not state["enabled"]:
                                raise AssertionError("variant UI unavailable: "+str(state))
                            if original is None:
                                original=state["program"]
                            if not original or original!=state["program"]:
                                raise AssertionError("Blockly workspace changed during variant selection")
                            project=state.get("project")
                            if not isinstance(project,str) or not project:
                                raise AssertionError("real browser ProjectFiles manager unavailable")
                            parsed=json.loads(project)
                            if parsed.get("activity",{}).get("id")!="progression-count-h-v1":
                                raise AssertionError("A6 .wbb activity identity changed")
                            if any(scene in project for scene in SCENES):
                                raise AssertionError("session-only H count leaked into saved .wbb")
                            if project_bytes is None:
                                project_bytes=project
                            elif project_bytes!=project:
                                raise AssertionError("real browser .wbb bytes changed during variants")
                            nonce=native_witness["nonce"]
                            seen_scene_nonces.add(nonce)
                            observed_ready[count]=native_witness["ready_count"]
                            visits.append({"scene":target,"label":state["label"],
                                           "scene_request_id":index+1,
                                           "native_ready_occurrences":native_witness["ready_count"],
                                           "native_nonce_sha256":hashlib.sha256(
                                               nonce.encode()).hexdigest(),
                                           "workspace_sha256":hashlib.sha256(
                                               original.encode()).hexdigest(),
                                           "wbb_sha256":hashlib.sha256(
                                               project_bytes.encode()).hexdigest(),
                                           "file_mode":state.get("projectMode")})
                            print("A6_REAL_VARIANT_NATIVE_ADMITTED "+target,flush=True)
                            break
                    time.sleep(0.3)
                else:
                    raise AssertionError("native UI transition timed out: "+target)
            # A real ProjectFiles parser/serializer/browser workspace round
            # trip after four native scene admissions; no OS picker is faked.
            # Opening the same already-trusted scene MUST be idempotent:
            # neither a fifth SCENE request nor a new observer incarnation.
            import re
            native_before=content(log)
            ack_pattern=r"(?m)^WEBEEBLOCKS_RUNTIME_V2 RESPONSE (\d+) SCENE_OK ([0-9a-f]{64})$"
            observer_pattern=r"(?m)^WEBEEBLOCKS_A6_MOTOR_READY n=([123]) "
            ack_before=re.findall(ack_pattern,native_before)
            observer_before=re.findall(observer_pattern,native_before)
            response_pattern=r"(?m)^WEBEEBLOCKS_RUNTIME_V2 RESPONSE [0-9]+ .*$"
            responses_before=re.findall(response_pattern,native_before)
            if ([request_id for request_id,_ in ack_before]!=["1","2","3","4"] or
                observer_before!=["1","2","3","1"]):
                raise AssertionError("baseline four fresh native scene epochs missing")
            reopened=dev.verify_project_reopen()
            if (not reopened or not reopened.get("rejectedForeignWorld") or
                not reopened.get("actualManager") or
                reopened.get("before")!=project_bytes or
                reopened.get("after")!=project_bytes or
                reopened.get("id")!="progression-count-h-v1" or
                reopened.get("scene")!=SCENES[0] or
                reopened.get("nativeSceneIdentity")!=SCENES[0]):
                raise AssertionError("real browser .wbb round-trip or world gate failed")
            # Both the foreign-world rejection and same-scene re-open must
            # preserve the native epoch; the WWI backend caches sceneIdentity.
            # No new ACK/observer is authoritative or required for an
            # idempotent in-browser project re-open.
            trace=content(log)
            ack_after=re.findall(ack_pattern,trace)
            observer_after=re.findall(observer_pattern,trace)
            responses_after=re.findall(response_pattern,trace)
            if (ack_after!=ack_before or observer_after!=observer_before or
                responses_after!=responses_before):
                raise AssertionError("idempotent .wbb reopen mutated the native scene epoch")
            result["project_reopen"]={
                "actual_manager":True,
                "foreign_world_rejected":True,
                "same_world_reopened":True,
                "same_native_epoch_preserved":True,
                "no_os_picker_proven":True,
                "wbb_sha256":hashlib.sha256(project_bytes.encode()).hexdigest(),
                "name":reopened.get("name"),
                "native_request_ids":[1,2,3,4]
            }
            print("A6_REAL_BROWSER_WBB_ROUNDTRIP_PASS foreign_rejected=true "
                  "same_world_bytes_unchanged=true native_epoch_preserved=true "
                  "os_save_open=UNPROVEN",flush=True)
        if len(visits)!=4 or [v["scene"] for v in visits]!=[
                SCENES[0],SCENES[1],SCENES[2],SCENES[0]]:
            raise AssertionError("incomplete real A6 native scene cycle")
        if observed_ready!={1:2,2:1,3:1} or len(seen_scene_nonces)!=4:
            raise AssertionError("A6 did not attest four fresh native scene epochs")
        result["pass"]=True
        result["visited"]=visits
    except Exception as error:
        result["error"]=type(error).__name__+": "+str(error)
        print("A6_REAL_VARIANT_CDP_REFUTATION "+result["error"],file=sys.stderr,flush=True)
    finally:
        if dev is not None:
            dev.ws.close()
        if process is not None and process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try:
                process.wait(timeout=7)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait(timeout=7)
        trace=content(log)
        result["browser_launched"]="blockly_count_h.html" in content(browser)
        result["native_fatal"]=any(x in trace for x in FATAL)
        result["scene_ready"]={str(n):"WEBEEBLOCKS_A6_MOTOR_READY n="+str(n) in trace for n in (1,2,3)}
        (OUT/"summary.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    if result["pass"] and all(result["scene_ready"].values()) and not result["native_fatal"]:
        print("A6_REAL_VARIANT_CDP_PASS scene_cycle=1-2-3-1 program_unchanged=true",flush=True)
        return 0
    print(content(log)[-4000:],file=sys.stderr,flush=True)
    return 1

if __name__=="__main__":
    raise SystemExit(run())

#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, socket, subprocess, tempfile, threading, time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from run_historical_blockly_oracle import EXPECTED_PYTHON_SHA256, chrome_executable

ROOT=Path(__file__).resolve().parents[2]
WINDOW_DIR=ROOT/"plugins"/"robot_windows"/"blockly"
HTML_PATH=WINDOW_DIR/"blockly.html"
PROGRAM_DIR=ROOT/"controllers"/"Blockly_Programs"
SUPERVISOR_DIR=ROOT/"controllers"/"supervisor"
SIDECAR=SUPERVISOR_DIR/"blocklyServer"/"blocklyServer"
CONTROLLER=ROOT/"controllers"/"my_controller"/"my_controller.py"
TMP_LAST=PROGRAM_DIR/".tmp.txt"
FIXTURE="BoxWithDistSensor.xml"
FIXTURE_NAME=Path(FIXTURE).stem
PROJECT_NAME="CIUiRoundTrip"
SAVED_XML=PROGRAM_DIR/(PROJECT_NAME+".xml")

def read_log(handle):
    if handle is None:
        return ""
    try:
        handle.flush()
        handle.seek(0)
        return handle.read().strip()
    except Exception as exc:
        return f"<unable to read log: {exc}>"

class ResultHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args): pass

    def do_POST(self):
        if self.path not in ("/__ci_result", "/__ci_progress"):
            self.send_error(404)
            return
        try:
            length=int(self.headers.get("Content-Length","0"))
            payload=json.loads(self.rfile.read(length).decode("utf-8"))
            if self.path == "/__ci_progress":
                self.server.ui_progress=payload
                print("CI_UI_PROGRESS="+json.dumps(payload, sort_keys=True), flush=True)
            else:
                self.server.ui_result=payload
                self.server.ui_event.set()
            self.send_response(204)
            self.end_headers()
        except Exception as exc:
            self.server.ui_result={"ok":False,"stage":"result-callback","error":f"result callback failed: {exc}"}
            self.server.ui_event.set()
            self.send_error(400)

def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0)); return sock.getsockname()[1]

def wait_for_port(port, timeout=5):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        with socket.socket() as sock:
            sock.settimeout(.2)
            if sock.connect_ex(("127.0.0.1",port))==0: return
        time.sleep(.05)
    raise RuntimeError(f"port {port} did not open")

def injected_harness():
    source=HTML_PATH.read_text(encoding="utf-8")
    return source+f"""
<script>
(async function() {{
 const result={{ok:false,stage:"start",initialRestore:false,saveClicked:false,submitClicked:false,restoreClicked:false,restoredTopBlocks:0,error:null,browserErrors:[],websocketEvents:[]}};
 const post=async(path,payload)=>{{
   try {{ await fetch(path,{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify(payload)}}); }}
   catch(e) {{ console.error("CI callback failed",path,e); }}
 }};
 const progress=async(stage,extra={{}})=>{{
   result.stage=stage;
   await post("/__ci_progress",Object.assign({{stage:stage}},extra));
 }};
 const finish=async()=>post("/__ci_result",result);
 window.addEventListener("error",e=>{{
   result.browserErrors.push("error: "+String(e.message||e.error||e));
   void post("/__ci_progress",{{stage:result.stage,browserError:result.browserErrors[result.browserErrors.length-1]}});
 }});
 window.addEventListener("unhandledrejection",e=>{{
   result.browserErrors.push("unhandledrejection: "+String(e.reason&&e.reason.stack?e.reason.stack:e.reason));
   void post("/__ci_progress",{{stage:result.stage,browserError:result.browserErrors[result.browserErrors.length-1]}});
 }});
 const waitFor=async (p,label,limit=15000)=>{{const start=Date.now();while(Date.now()-start<limit){{if(p())return;await new Promise(r=>setTimeout(r,50));}}throw new Error("timeout waiting for "+label);}};
 const waitForSavedProject=(name,limit=15000)=>new Promise((resolve,reject)=>{{
   const list=document.getElementById("saveList");
   const find=()=>Array.from(list.querySelectorAll("a")).find(a=>a.textContent===name);
   const existing=find(); if(existing){{resolve(existing);return;}}
   const timer=setTimeout(()=>{{observer.disconnect();reject(new Error("timeout waiting for saved project "+name));}},limit);
   const observer=new MutationObserver(()=>{{const link=find();if(link){{clearTimeout(timer);observer.disconnect();resolve(link);}}}});
   observer.observe(list,{{childList:true,subtree:true,characterData:true}});
 }});
 const waitForRestoredWorkspace=(limit=15000)=>new Promise((resolve,reject)=>{{
   const done=()=>Blockly.mainWorkspace.getTopBlocks(false).length>0;
   if(done()){{resolve();return;}}
   const timer=setTimeout(()=>{{Blockly.mainWorkspace.removeChangeListener(listener);reject(new Error("timeout waiting for restored workspace"));}},limit);
   const listener=()=>{{if(done()){{clearTimeout(timer);Blockly.mainWorkspace.removeChangeListener(listener);resolve();}}}};
   Blockly.mainWorkspace.addChangeListener(listener);
 }});
 try {{
  const saveButton=document.getElementById("save");
  const submitButton=document.getElementById("submit");
  const restoreButton=document.getElementById("restore");
  const titleElement=document.getElementById("projectTitle");

  await progress("wait-websocket");
  let socketInstrumented=false;
  await waitFor(()=>{{
    if(window.ws && !socketInstrumented){{
      socketInstrumented=true;
      ws.addEventListener("open",()=>{{result.websocketEvents.push("open");void post("/__ci_progress",{{stage:result.stage,websocket:"open"}});}});
      ws.addEventListener("error",()=>{{result.websocketEvents.push("error");void post("/__ci_progress",{{stage:result.stage,websocket:"error"}});}});
      ws.addEventListener("close",e=>{{result.websocketEvents.push("close:"+e.code);void post("/__ci_progress",{{stage:result.stage,websocket:"close",code:e.code,reason:e.reason}});}});
    }}
    return window.ws && ws.readyState===WebSocket.OPEN && !saveButton.disabled && !submitButton.disabled && !restoreButton.disabled;
  }},"WebSocket/buttons");

  await progress("wait-initial-restore",{{websocketState:ws.readyState}});
  await waitFor(()=>titleElement.textContent==="{FIXTURE_NAME}" && Blockly.mainWorkspace.getTopBlocks(false).length>0,"initial RESTORE_LAST");
  result.initialRestore=true;
  await progress("initial-restore-complete",{{topBlocks:Blockly.mainWorkspace.getTopBlocks(false).length}});

  titleElement.textContent="{PROJECT_NAME}";
  await progress("save");
  saveButton.click(); result.saveClicked=true;

  // Listing saved projects is our browser-visible acknowledgement that the
  // preceding SAVE/SAVE_LAST frames have been processed by the real sidecar.
  await progress("list-after-save");
  restoreButton.click(); result.restoreClicked=true;
  const savedLink=await waitForSavedProject("{PROJECT_NAME}");
  await progress("saved-project-visible");

  // Submit only after SAVE has been observed, avoiding races in the historical
  // single `currCommand` state machine. WebSocket frame ordering then ensures
  // SEND_CODE/SAVE_LAST are processed before the following RESTORE_SAVE.
  await progress("submit");
  submitButton.click(); result.submitClicked=true;

  Blockly.mainWorkspace.clear();
  if(Blockly.mainWorkspace.getTopBlocks(false).length!==0)throw new Error("workspace clear failed");
  await progress("restore");
  const restored=waitForRestoredWorkspace();
  savedLink.click();
  await restored;
  result.restoredTopBlocks=Blockly.mainWorkspace.getTopBlocks(false).length;
  await progress("complete",{{restoredTopBlocks:result.restoredTopBlocks}});
  result.ok=true;
 }} catch(e) {{
   result.error=String(e&&e.stack?e.stack:e);
   await post("/__ci_progress",{{stage:result.stage,error:result.error,browserErrors:result.browserErrors,websocketEvents:result.websocketEvents}});
 }}
 await finish();
}})();
</script>
"""

def run_chrome(url, server, timeout=35):
    # Keep a real headless browser alive while actual WebSocket/network events
    # occur. Persist Chrome stderr to a file so a timeout cannot hide browser
    # diagnostics or deadlock on a full stderr pipe.
    cmd=[chrome_executable(),"--headless=new","--no-sandbox","--disable-gpu","--disable-dev-shm-usage","--disable-background-networking","--remote-debugging-port=0",url]
    chrome_out=tempfile.TemporaryFile(mode="w+",encoding="utf-8")
    chrome_err=tempfile.TemporaryFile(mode="w+",encoding="utf-8")
    p=subprocess.Popen(cmd,text=True,stdout=chrome_out,stderr=chrome_err)
    deadline=time.monotonic()+timeout
    try:
        while time.monotonic()<deadline:
            if server.ui_event.wait(timeout=.1):
                return server.ui_result
            if p.poll() is not None:
                raise RuntimeError(
                    f"headless browser exited before UI result callback ({p.returncode}); "
                    f"last progress={server.ui_progress}; stderr={read_log(chrome_err)}"
                )
        raise RuntimeError(
            "timeout waiting for browser UI result callback; "
            f"last progress={server.ui_progress}; chrome stderr={read_log(chrome_err)}"
        )
    finally:
        if p.poll() is None:
            p.terminate()
            try: p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill(); p.wait(timeout=3)
        chrome_out.close()
        chrome_err.close()

def main():
    if not SIDECAR.is_file(): raise RuntimeError(f"rebuilt sidecar missing: {SIDECAR}")
    controller_backup=CONTROLLER.read_bytes()
    tmp_backup=TMP_LAST.read_bytes() if TMP_LAST.exists() else None
    saved_backup=SAVED_XML.read_bytes() if SAVED_XML.exists() else None
    sidecar=server=thread=harness_path=None
    sidecar_out=sidecar_err=None
    try:
        SAVED_XML.unlink(missing_ok=True)
        # Seed a real existing last project so main.js completes its historical
        # RESTORE_LAST_NAME -> RESTORE_LAST startup exchange before the test
        # starts issuing new commands on the single currCommand state machine.
        TMP_LAST.write_text(FIXTURE_NAME,encoding="utf-8")
        sidecar_out=tempfile.TemporaryFile(mode="w+",encoding="utf-8")
        sidecar_err=tempfile.TemporaryFile(mode="w+",encoding="utf-8")
        sidecar=subprocess.Popen([str(SIDECAR)],cwd=SUPERVISOR_DIR,text=True,stdout=sidecar_out,stderr=sidecar_err)
        wait_for_port(8001)
        with tempfile.NamedTemporaryFile(mode="w",suffix=".html",prefix="ci-ui-",dir=WINDOW_DIR,encoding="utf-8",delete=False) as h:
            h.write(injected_harness()); harness_path=Path(h.name)
        port=free_port()
        server=ThreadingHTTPServer(("127.0.0.1",port),partial(ResultHandler,directory=str(WINDOW_DIR)))
        server.ui_event=threading.Event(); server.ui_result=None; server.ui_progress={"stage":"server-started"}
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            result=run_chrome(f"http://127.0.0.1:{port}/{harness_path.name}",server)
        except Exception as exc:
            raise RuntimeError(
                f"{exc}; blocklyServer stdout={read_log(sidecar_out)}; "
                f"blocklyServer stderr={read_log(sidecar_err)}"
            ) from exc
        if not result or not result.get("ok"):
            raise RuntimeError(
                "browser UI flow failed at "+str(result.get("stage") if result else "unknown")+": "
                +str(result.get("error") if result else "no result")
                +"; browserErrors="+str(result.get("browserErrors") if result else None)
                +"; websocketEvents="+str(result.get("websocketEvents") if result else None)
                +"; blocklyServer stdout="+read_log(sidecar_out)
                +"; blocklyServer stderr="+read_log(sidecar_err)
            )
        if not result.get("initialRestore"): raise RuntimeError("historical initial restore did not complete")
        if not all(result.get(k) for k in ("saveClicked","submitClicked","restoreClicked")): raise RuntimeError("not all real UI buttons were exercised")
        if int(result.get("restoredTopBlocks",0))<=0: raise RuntimeError("Restore did not repopulate workspace")
        if not SAVED_XML.is_file(): raise RuntimeError("Save did not create XML")
        saved=SAVED_XML.read_text(encoding="utf-8")
        if "<xml" not in saved or "motors_" not in saved: raise RuntimeError("saved XML lacks historical fixture blocks")
        digest=hashlib.sha256(CONTROLLER.read_bytes()).hexdigest(); expected=EXPECTED_PYTHON_SHA256[FIXTURE]
        if digest!=expected: raise RuntimeError(f"Submit Python sha256={digest}, expected={expected}")
        if not TMP_LAST.is_file() or TMP_LAST.read_text(encoding="utf-8").strip()!=PROJECT_NAME: raise RuntimeError("last-project state not updated")
        print(f"PASS: real blockly.html/main.js initial restore plus Save, Submit and Restore buttons worked against real blocklyServer; submitted {FIXTURE} Python sha256 matched.")
        return 0
    finally:
        if server is not None: server.shutdown(); server.server_close()
        if thread is not None: thread.join(timeout=2)
        if sidecar is not None:
            sidecar.terminate()
            try: sidecar.wait(timeout=2)
            except subprocess.TimeoutExpired: sidecar.kill(); sidecar.wait(timeout=2)
        if sidecar_out is not None: sidecar_out.close()
        if sidecar_err is not None: sidecar_err.close()
        if harness_path is not None: harness_path.unlink(missing_ok=True)
        CONTROLLER.write_bytes(controller_backup)
        (TMP_LAST.unlink(missing_ok=True) if tmp_backup is None else TMP_LAST.write_bytes(tmp_backup))
        (SAVED_XML.unlink(missing_ok=True) if saved_backup is None else SAVED_XML.write_bytes(saved_backup))
if __name__=="__main__": raise SystemExit(main())

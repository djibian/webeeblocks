#!/usr/bin/env python3
from __future__ import annotations
import hashlib, html, json, re, socket, subprocess, sys, tempfile, threading, time
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
RESULT_RE=re.compile(r'<pre id="ui-result">(.*?)</pre>', re.DOTALL)

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args): pass

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
<pre id="ui-result">NOT_RUN</pre>
<script>
(async function() {{
 const result={{ok:false,initialRestore:false,saveClicked:false,submitClicked:false,restoreClicked:false,restoredTopBlocks:0,error:null}};
 const waitFor=async (p,label,limit=10000)=>{{const start=Date.now();while(Date.now()-start<limit){{if(p())return;await new Promise(r=>setTimeout(r,50));}}throw new Error("timeout waiting for "+label);}};
 const waitForSavedProject=(name)=>new Promise(resolve=>{{
   const list=document.getElementById("saveList");
   const find=()=>Array.from(list.querySelectorAll("a")).find(a=>a.textContent===name);
   const existing=find(); if(existing){{resolve(existing);return;}}
   const observer=new MutationObserver(()=>{{const link=find();if(link){{observer.disconnect();resolve(link);}}}});
   observer.observe(list,{{childList:true,subtree:true,characterData:true}});
 }});
 const waitForRestoredWorkspace=()=>new Promise(resolve=>{{
   const done=()=>Blockly.mainWorkspace.getTopBlocks(false).length>0;
   if(done()){{resolve();return;}}
   const listener=()=>{{if(done()){{Blockly.mainWorkspace.removeChangeListener(listener);resolve();}}}};
   Blockly.mainWorkspace.addChangeListener(listener);
 }});
 try {{
  const saveButton=document.getElementById("save");
  const submitButton=document.getElementById("submit");
  const restoreButton=document.getElementById("restore");
  const titleElement=document.getElementById("projectTitle");
  await waitFor(()=>window.ws && ws.readyState===WebSocket.OPEN && !saveButton.disabled && !submitButton.disabled && !restoreButton.disabled,"WebSocket/buttons");
  await waitFor(()=>titleElement.textContent==="{FIXTURE_NAME}" && Blockly.mainWorkspace.getTopBlocks(false).length>0,"initial RESTORE_LAST");
  result.initialRestore=true;
  titleElement.textContent="{PROJECT_NAME}";
  saveButton.click(); result.saveClicked=true;
  submitButton.click(); result.submitClicked=true;
  Blockly.mainWorkspace.clear();
  if(Blockly.mainWorkspace.getTopBlocks(false).length!==0)throw new Error("workspace clear failed");
  restoreButton.click(); result.restoreClicked=true;
  const savedLink=await waitForSavedProject("{PROJECT_NAME}");
  const restored=waitForRestoredWorkspace();
  savedLink.click();
  await restored;
  result.restoredTopBlocks=Blockly.mainWorkspace.getTopBlocks(false).length; result.ok=true;
 }} catch(e) {{ result.error=String(e&&e.stack?e.stack:e); }}
 document.getElementById("ui-result").textContent=JSON.stringify(result);
}})();
</script>
"""

def parse_output(stdout):
    m=RESULT_RE.search(stdout)
    if not m: raise RuntimeError("headless browser did not emit ui-result")
    raw=html.unescape(m.group(1))
    if raw=="NOT_RUN": raise RuntimeError("UI harness did not run")
    return json.loads(raw)

def run_chrome(url):
    cmd=[chrome_executable(),"--headless=new","--no-sandbox","--disable-gpu","--disable-dev-shm-usage","--disable-background-networking","--virtual-time-budget=15000","--dump-dom",url]
    p=subprocess.Popen(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    timed=False
    try: out,err=p.communicate(timeout=35)
    except subprocess.TimeoutExpired:
        timed=True; p.kill(); out,err=p.communicate()
    try: result=parse_output(out)
    except Exception as exc: raise RuntimeError(f"browser UI test produced no valid result{' after timeout' if timed else ''}: {err.strip()}") from exc
    if not timed and p.returncode: raise RuntimeError(f"headless browser exited with {p.returncode}: {err.strip()}")
    return result

def main():
    if not SIDECAR.is_file(): raise RuntimeError(f"rebuilt sidecar missing: {SIDECAR}")
    controller_backup=CONTROLLER.read_bytes()
    tmp_backup=TMP_LAST.read_bytes() if TMP_LAST.exists() else None
    saved_backup=SAVED_XML.read_bytes() if SAVED_XML.exists() else None
    sidecar=server=thread=harness_path=None
    try:
        SAVED_XML.unlink(missing_ok=True)
        # Seed a real existing last project so main.js completes its historical
        # RESTORE_LAST_NAME -> RESTORE_LAST startup exchange before the test
        # starts issuing new commands on the single currCommand state machine.
        TMP_LAST.write_text(FIXTURE_NAME,encoding="utf-8")
        sidecar=subprocess.Popen([str(SIDECAR)],cwd=SUPERVISOR_DIR,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        wait_for_port(8001)
        with tempfile.NamedTemporaryFile(mode="w",suffix=".html",prefix="ci-ui-",dir=WINDOW_DIR,encoding="utf-8",delete=False) as h:
            h.write(injected_harness()); harness_path=Path(h.name)
        port=free_port(); server=ThreadingHTTPServer(("127.0.0.1",port),partial(QuietHandler,directory=str(WINDOW_DIR)))
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        result=run_chrome(f"http://127.0.0.1:{port}/{harness_path.name}")
        if not result.get("ok"): raise RuntimeError("browser UI flow failed: "+str(result.get("error")))
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
        if harness_path is not None: harness_path.unlink(missing_ok=True)
        CONTROLLER.write_bytes(controller_backup)
        (TMP_LAST.unlink(missing_ok=True) if tmp_backup is None else TMP_LAST.write_bytes(tmp_backup))
        (SAVED_XML.unlink(missing_ok=True) if saved_backup is None else SAVED_XML.write_bytes(saved_backup))
if __name__=="__main__": raise SystemExit(main())

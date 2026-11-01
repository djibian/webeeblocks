#!/usr/bin/env python3
"""EXPERIMENT ONLY: real Windows Webots --batch + real Chrome headless reload.

Uses the existing Linux native recovery instrumentation unchanged except the
HTML target, in a disposable copy of the exact #778 Windows package. No C, JS
product source, native oracle, physics or browser protocol mocks are modified.
"""
import argparse
import contextlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.ci.experiment_r3_windows_batch_wwi import captured_native_batch,probe_http
from tools.ci.run_grand_prix_windows_native import engine_environment

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1",0))
        return s.getsockname()[1]

def logs(path):
    try:return path.read_text(encoding="utf-8",errors="replace")
    except OSError:return ""

def records(path):
    out=[]
    for line in logs(path).splitlines():
        if not line.strip():continue
        try:out.append(json.loads(line))
        except ValueError:raise RuntimeError("Invalid browser telemetry JSON")
    return out

def stop(pid):
    if pid.poll() is None:
        # Only the newly-created test process tree, not an existing user browser.
        subprocess.run(["taskkill","/PID",str(pid.pid),"/T","/F"],capture_output=True,
                       timeout=20,check=False)
    try:pid.wait(timeout=15)
    except subprocess.TimeoutExpired:
        pid.kill()
        pid.wait(timeout=15)

def inject_existing_linux_test_into_disposable_windows_package(html):
    assert html.is_file(), "Real content-addressed packaged Robot Window required"
    before=html.read_text(encoding="utf-8")
    assert "<!-- WEBEEBLOCKS_RESET_REPLAY_CI -->" not in before
    source=(ROOT/"tools/ci/prepare_runtime_v2_reset.py").read_text(encoding="utf-8")
    assert "HTML = ROOT / 'plugins/robot_windows/blockly_v2/blockly_v2.html'" in source
    source=source.replace(
       "HTML = ROOT / 'plugins/robot_windows/blockly_v2/blockly_v2.html'",
       "HTML = Path("+repr(str(html))+")",1)
    # Fixture only; this exec does not read/alter product C, JS or physical oracles.
    fixture={"__file__":str(ROOT/"tools/ci/prepare_runtime_v2_reset.py"),
             "__name__":"windows_native_fixture"}
    exec(compile(source,"prepare_runtime_v2_reset.py","exec"),fixture)
    after=html.read_text(encoding="utf-8")
    assert after.count("<!-- WEBEEBLOCKS_RESET_REPLAY_CI -->")==1
    assert before in after, "Test injector unexpectedly rewrote packaged HTML bytes"
    return True

def result_assertions(events,webots):
    names=[e.get("event") for e in events]
    critical=("READY","WORLD_RELOAD_REQUEST","WORLD_RECOVERY_READY","WORLD_RECOVERY_RERUN")
    for key in critical:
        if names.count(key)!=1:raise RuntimeError(f"Missing/duplicate real browser phase: {key}={names.count(key)}")
    if any(e.get("event") in ("ERROR","WINDOW_ERROR","UNHANDLED_REJECTION","NEGATIVE_ERROR") for e in events):
        raise RuntimeError("Browser recorded real JS/transport error")
    pre=next(e["detail"] for e in events if e["event"]=="WORLD_RELOAD_REQUEST")
    post=next(e["detail"] for e in events if e["event"]=="WORLD_RECOVERY_READY")
    after=next(e["detail"] for e in events if e["event"]=="WORLD_RECOVERY_RERUN")
    assert pre["workspace"]==post["workspace"]==after["workspace"],"Exact serialized Blockly diverged"
    assert pre["ast"]==post["ast"],"Original and restored semantic AST diverged"
    assert pre["workspace"]!="","No non-trivial program"
    assert names.count("RESET_OK")>=3, "Native strict RESET preconditions missing"
    reset_events=[e.get("detail",{}) for e in events if e.get("event")=="RESET_EVENT"]
    assert sum(v.get("worldRebuilt") is True for v in reset_events)==1,"One rebuild attestation required"
    assert sum(v.get("workspacePreserved") is True for v in reset_events)>=1
    assert webots.count("WORLD_RELOAD_REQUESTED (not a recovery ACK)")==1
    assert webots.count("RECOVERY_CLEARED")==1, "Exactly one native C witness clear required"
    assert webots.count("TRACE RESET ")>=5, "Expected old 3 + new 2 strict C RESET traces"
    assert "WEBEEBLOCKS_RUNTIME_V2 READY" in webots
    return {
        "blockly_ast_identical":True,
        "reset_traces_at_least":webots.count("TRACE RESET "),
        "world_reload_native_count":webots.count("WORLD_RELOAD_REQUESTED (not a recovery ACK)"),
        "clear_native_count":webots.count("RECOVERY_CLEARED"),
        "scene_confirmation_browser_count":sum(1 for e in events if e.get("event")=="SCENE_OK"),
        "recovered_ready":True,
        "explicit_rerun":True,
        "browser_event_count":len(events)
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--package",type=Path,required=True)
    ap.add_argument("--webots-home",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    if sys.platform!="win32":raise RuntimeError("Windows-only native browser experiment")
    out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=True)
    package=args.package.resolve()
    home=args.webots_home.resolve()
    world=package/"worlds/crazyflie_runtime_v2.wbt"
    assert world.is_file()
    world_text=world.read_text(encoding="utf-8")
    names=re.findall(r'window "([^"]+)"',world_text)
    assert len(names)==1
    name=names[0]
    html=package/"plugins/robot_windows"/name/(name+".html")
    assert inject_existing_linux_test_into_disposable_windows_package(html)
    chrome=next((p for p in (
        Path(os.environ.get("PROGRAMFILES",r"C:\Program Files"))/"Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)",r"C:\Program Files (x86)"))/"Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA",r"C:\Users\runneradmin\AppData\Local"))/"Google/Chrome/Application/chrome.exe")
       if p.is_file()),None)
    if not chrome:raise RuntimeError("Official Windows runner has no Chrome; no GUI claim")
    browser_events=out/"browser-events.jsonl"
    event_port=8765
    with socket.socket() as sock:
        try:sock.bind(("127.0.0.1",event_port))
        except OSError:raise RuntimeError("Existing process occupies protected fixture event port 8765")
    summary={"scope":"WINDOWS_NATIVE_WEBOTS_BATCH_CHROME_HEADLESS_REAL_BROWSER",
             "product_head":"f243b2b597a2a6bd6af38e895787d9dd4bdfef5e",
             "status":"UNPROVEN",
             "chromium":"HEADLESS_REAL_CHROME_NOT_INTERACTIVE_GUI",
             "controller_unchanged":True,
             "html_only_disposable_test_injection":True,
             "urls":[]}
    chrome_proc=None
    event_proc=None
    outlog=open(out/"event-server.log","wb")
    chromelog=open(out/"chrome.log","wb")
    try:
        event_proc=subprocess.Popen([sys.executable,"-u",str(ROOT/"tools/ci/runtime_wwi_event_server.py"),
                                      "--output",str(browser_events)],
                                    cwd=ROOT,stdout=outlog,stderr=subprocess.STDOUT)
        for i in range(40):
            try:
                with urllib.request.urlopen("http://127.0.0.1:8765/health",timeout=0.5) as h:
                    if h.status==200:break
            except OSError:time.sleep(.2)
        else:raise RuntimeError("Native browser event server never reachable")
        env=engine_environment(home,os.environ.copy())
        env["WEBOTS_HOME"]=str(home)
        env["WEBEEBLOCKS_RECOVERY_STATE_DIR"]=str(out/"isolated-state")
        (out/"isolated-state").mkdir(exist_ok=True)
        port=free_port()
        url=f"http://127.0.0.1:{port}/robot_windows/{name}/{name}.html?name=Crazyflie%20WebeeBlocks"
        # Only static URL metadata, never a bearer or workspace.
        summary["url"]={"host":"127.0.0.1","port":port,"robotWindowName":name}
        command=[str(home/"msys64/mingw64/bin/webots.exe"),"--stdout","--stderr",
                 "--batch","--mode=realtime",f"--port={port}",str(world)]
        with captured_native_batch(command,package,env,out/"webots.stdout.log",out/"webots.stderr.log") as webots:
            deadline=time.monotonic()+65
            while time.monotonic()<deadline:
                if webots.poll() is not None:raise RuntimeError("Webots exited before browser boot")
                if "WEBEEBLOCKS_RUNTIME_V2 READY" in logs(out/"webots.stdout.log"):
                    h=probe_http(port,f"/robot_windows/{name}/{name}.html?name=Crazyflie%20WebeeBlocks")
                    if h.get("served"):break
                time.sleep(.5)
            else:raise RuntimeError("Native Webots C READY and HTTP not available")
            profile=out/"chrome-private-profile"
            profile.mkdir(exist_ok=True)
            chrome_cmd=[str(chrome),"--headless=new","--disable-gpu",
                        "--disable-background-networking","--no-first-run",
                        "--no-default-browser-check",
                        "--user-data-dir="+str(profile),url]
            chrome_proc=subprocess.Popen(chrome_cmd,cwd=package,stdout=chromelog,
                                         stderr=subprocess.STDOUT)
            deadline=time.monotonic()+370
            while time.monotonic()<deadline:
                if webots.poll() is not None:raise RuntimeError("Webots exited before recovery evidence")
                if chrome_proc.poll() is not None:raise RuntimeError("Chrome exited during genuine Webots recovery")
                ev=records(browser_events)
                if any(e.get("event") in ("ERROR","WINDOW_ERROR","UNHANDLED_REJECTION") for e in ev):
                    raise RuntimeError("Real Blockly browser test reported failure")
                if any(e.get("event")=="WORLD_RECOVERY_RERUN" for e in ev):
                    break
                time.sleep(.5)
            else:raise RuntimeError("No completed browser full reload/Blockly replay before deadline")
            time.sleep(1)
            ws=logs(out/"webots.stdout.log")+"\n"+logs(out/"webots.stderr.log")
            summary["proof"]=result_assertions(records(browser_events),ws)
            summary["status"]="PASS_NATIVE_WINDOWS_BROWSER_RELOAD_ONLY"
    except Exception as exc:
        summary["error_type"]=type(exc).__name__
        summary["error_summary"]=str(exc)[:190]
        raise
    finally:
        if chrome_proc:stop(chrome_proc)
        if event_proc:stop(event_proc)
        chromelog.close();outlog.close()
        (out/"browser-native-report.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
        print("WINDOWS_BATCH_BROWSER_VERDICT="+summary["status"],flush=True)
    return 0

if __name__=="__main__":raise SystemExit(main())

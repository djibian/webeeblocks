"""Real Windows R2025a extracted-product probe, never a GUI claim.

Checks three original canonical worlds through the *installed* native
flight and static-attestation evaluator plus real WWI protocol. This test
does not build or edit the distributed package.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.ci.test_grand_prix_route_windows_package import verify
from tools.ci.run_grand_prix_windows_native import captured_engine, engine_environment, read

def run_one(package, home, root, index):
    folder = root / f"route-{index:02d}"
    folder.mkdir()
    file = package / f"worlds/grand_prix_route_v2_{index:02d}_fps60.wbt"
    engine = home / "msys64/mingw64/bin/webots-bin.exe"
    node = shutil.which("node")
    if not engine.is_file() or not node:
        raise RuntimeError("Native Windows R2025a engine and Node >=22 required")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = engine_environment(home, os.environ)
    env.update(
        WEBOTS_HOME=str(home),
        WEBEEBLOCKS_GP_PYTHON_DIR=str(package / "runtime/python"),
        WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE="true",
        PYTHONHOME=str(folder / "nonexistent"),
        PYTHONPATH=str(folder / "nonexistent"),
    )
    cmd = [str(engine), "--stdout", "--stderr", "--batch", "--mode=fast",
           "--no-rendering", f"--port={port}", str(file)]
    metadata = {"course":index,"world_sha256":hashlib.sha256(file.read_bytes()).hexdigest(),
                "source_sha": (package/"SOURCE_SHA").read_text().strip(),
                "command":cmd,"native":True,"gui":False}
    (folder/"launch.json").write_text(json.dumps(metadata,indent=2)+"\n")
    with captured_engine(cmd, package, env, folder/"webots.stdout.log",
                         folder/"webots.stderr.log") as process:
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            logs = read(folder/"webots.stdout.log")+"\n"+read(folder/"webots.stderr.log")
            if "WEBEEBLOCKS_RUNTIME_V2 READY" in logs:
                break
            if process.poll() is not None:
                raise RuntimeError(f"Webots terminated before Runtime READY: {process.returncode}")
            time.sleep(.1)
        else:
            raise RuntimeError("Real native runtime READY missing")
        script=ROOT/"tools/ci/grand_prix_route_windows_node_probe.js"
        with (folder/"node.log").open("w",encoding="utf-8") as log:
            result=subprocess.run([node,str(script),str(port),
                                   str(folder/"events.jsonl"),str(package)],
                                  cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,
                                  timeout=510)
        if result.returncode:
            raise RuntimeError(f"Real native Grand Prix route trial failed: {index} / {result.returncode}")
        evidence=[json.loads(line) for line in read(folder/"events.jsonl").splitlines()]
        classes=[item["event"] for item in evidence]
        expected=("runtime-ready","first-takeoff","first-land",
                  "reset-complete","second-ready","second-takeoff",
                  "native-sequence-completed")
        if any(classes.count(label)!=1 for label in expected):
            raise RuntimeError(f"Missing exactly-once native route events: {index}, {classes!r}")
        if not ("dynamic-rejected" in classes or
                any(x["event"]=="dynamic-outcome" and
                    x["data"].get("status")=="not-achieved" for x in evidence)):
            raise RuntimeError("No native dynamic mission refusal")
        logs=read(folder/"webots.stdout.log")+"\n"+read(folder/"webots.stderr.log")
        if "Traceback (most recent call last)" in logs or any(
                line.startswith("ERROR:") for line in logs.splitlines()):
            raise RuntimeError("Webots reported a native engine/controller error")
    result={"route":index,"checks":list(expected),"dynamic_rejection":True,
            "webots":"R2025a", "gui_pass":False}
    (folder/"result.json").write_text(json.dumps(result,indent=2)+"\n")
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--package",type=Path,required=True)
    p.add_argument("--webots-home",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    if sys.platform!="win32":
        raise RuntimeError("Windows native validation only")
    package,home,output=[x.resolve() for x in (a.package,a.webots_home,a.output)]
    if (home/"resources/version.txt").read_text().strip()!="R2025a":
        raise ValueError("Native engine is not Webots R2025a")
    verified=verify(package)
    output.mkdir(parents=True,exist_ok=False)
    results=[]
    try:
        for index in (5,0,11):
            results.append(run_one(package,home,output,index))
            (output/"campaign.json").write_text(json.dumps({
               "package":verified,"results":results,"gui_status":"UNPROVEN"
            },indent=2)+"\n")
        print("GP_ROUTE_WINDOWS_NATIVE_EXTRACTED_PASS routes=5,0,11; GUI=UNPROVEN")
    finally:
        hashes={p.relative_to(output).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                for p in output.rglob("*") if p.is_file() and p.name!="sha256.json"}
        (output/"sha256.json").write_text(json.dumps(hashes,sort_keys=True,indent=2)+"\n")

if __name__=="__main__":
    main()

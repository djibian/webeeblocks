#!/usr/bin/env python3
"""One bounded genuine Webots R2025a Windows --batch HTTP/WWI discrimination.

Never infer WS from HTTP or C READY. Uses raw RFC6455 transport and C's
unmodified authenticated WWI protocol; no browser, GUI, mocks or product edits.
Sensitive bearer and challenge values are never logged or persisted.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import sys
import time
import urllib.error
import urllib.request
import subprocess
import threading
from contextlib import contextmanager

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.ci.run_grand_prix_windows_native import engine_environment

@contextmanager
def captured_native_batch(command,cwd,env,stdout_path,stderr_path):
    errors=[]
    with stdout_path.open("wb") as out,stderr_path.open("wb") as err:
        process=subprocess.Popen(command,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        def drain(src,dest):
            try:
                with src:
                    while chunk:=src.read1(65536):
                        dest.write(chunk);dest.flush()
            except Exception as exc:
                errors.append(type(exc).__name__)
        threads=[threading.Thread(target=drain,args=(src,dst),daemon=True)
                 for src,dst in ((process.stdout,out),(process.stderr,err))]
        for thread in threads: thread.start()
        try:
            yield process
        finally:
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill();process.wait(timeout=15)
            else: process.wait(timeout=15)
            for thread in threads:thread.join(timeout=15)
            if errors or any(t.is_alive() for t in threads):
                raise RuntimeError("native output pipe capture incomplete: "+str(errors))

PREFIX = "WEBEEBLOCKS_RUNTIME_V2"
TIME_BUDGET_S = 60

def probe_http(port, path):
    url = "http://127.0.0.1:%d%s" % (port, path)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Connection":"close"}),
                                    timeout=0.8) as response:
            body = response.read(256)
            return {"served": response.status == 200, "status":response.status,
                    "mime":response.headers.get("Content-Type",""), "bytes_prefix_length":len(body)}
    except (OSError, urllib.error.URLError, ValueError) as error:
        return {"served":False, "error_type":type(error).__name__}

def recv_exact(sock, size):
    buf = bytearray()
    while len(buf) < size:
        piece = sock.recv(size-len(buf))
        if not piece:
            raise EOFError("WebSocket closed")
        buf.extend(piece)
    return bytes(buf)

class Ws:
    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1",port), timeout=2)
        self.sock.settimeout(2)
        key = base64.b64encode(secrets.token_bytes(16)).decode()
        request = ("GET / HTTP/1.1\r\nHost: 127.0.0.1:%d\r\n"
                   "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                   "Sec-WebSocket-Version: 13\r\nSec-WebSocket-Key: %s\r\n"
                   "Origin: http://127.0.0.1:%d\r\n\r\n" % (port,key,port))
        self.sock.sendall(request.encode("ascii"))
        header = b""
        while b"\r\n\r\n" not in header and len(header)<8192:
            header += self.sock.recv(1024)
        if not header.startswith(b"HTTP/1.1 101 ") and not header.startswith(b"HTTP/1.0 101 "):
            raise RuntimeError("No actual RFC6455 101 WebSocket upgrade")
        want=base64.b64encode(hashlib.sha1((key+"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
        if b"sec-websocket-accept: "+want.lower() not in header.lower():
            raise RuntimeError("WebSocket accept hash incorrect")
    def send(self, text):
        data=text.encode()
        mask=secrets.token_bytes(4)
        hdr=bytearray([0x81])
        n=len(data)
        if n<126: hdr.append(0x80|n)
        elif n<65536: hdr.extend([0x80|126,(n>>8)&255,n&255])
        else: raise ValueError("probe message too large")
        self.sock.sendall(bytes(hdr)+mask+bytes(c ^ mask[i%4] for i,c in enumerate(data)))
    def recv(self):
        b=recv_exact(self.sock,2)
        length=b[1]&0x7f
        if length==126: length=int.from_bytes(recv_exact(self.sock,2),"big")
        elif length==127: length=int.from_bytes(recv_exact(self.sock,8),"big")
        if length>65536: raise ValueError("unbounded WebSocket reply")
        mask=recv_exact(self.sock,4) if b[1]&0x80 else None
        data=recv_exact(self.sock,length)
        if mask: data=bytes(c ^ mask[i%4] for i,c in enumerate(data))
        return data.decode("utf-8",errors="replace")
    def close(self):
        self.sock.close()

def read_reply(ws, request_id, kind, deadline):
    # Do NOT store whole incoming frames: they may include confidential fields.
    # Only compare locally against allowed exact public response forms.
    while time.monotonic()<deadline:
        try: data=ws.recv()
        except socket.timeout: continue
        for line in data.splitlines():
            if not line.startswith("robot:"):
                continue
            if kind=="epoch":
                m=re.search(rf"{PREFIX} RESPONSE {request_id} AUTH_EPOCH ([0-9a-f]{{64}}) ([0-9a-f]{{32}})",line)
                if m:return (m.group(1),m.group(2))
            if kind=="claim":
                m=re.search(rf"{PREFIX} RESPONSE {request_id} AUTH_OK ([0-9a-f]{{64}})",line)
                if m:return (m.group(1),)
            if kind=="light":
                m=re.search(rf"{PREFIX} RESPONSE {request_id} (OK|ERR [A-Z_]+)",line)
                if m:return (m.group(1),)
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--package",type=Path,required=True)
    ap.add_argument("--webots-home",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    if sys.platform!="win32": raise RuntimeError("Windows-only witness")
    out=a.output.resolve()
    out.mkdir(parents=True,exist_ok=True)
    package=a.package.resolve()
    home=a.webots_home.resolve()
    exe=home/"msys64/mingw64/bin/webots.exe"
    world=package/"worlds/crazyflie_runtime_v2.wbt"
    assert exe.is_file() and world.is_file()
    text=world.read_text(encoding="utf-8")
    matches=re.findall(r'window "([^"]+)"',text)
    assert len(matches)==1, "Expected a single actual robotWindow world name"
    window=matches[0]
    with socket.socket() as s:
        s.bind(("127.0.0.1",0))
        port=s.getsockname()[1]
    env=engine_environment(home,os.environ.copy())
    env["WEBOTS_HOME"]=str(home)
    env["WEBEEBLOCKS_RECOVERY_STATE_DIR"]=str(out/"isolated-state")
    (out/"isolated-state").mkdir(exist_ok=True)
    command=[str(exe),"--stdout","--stderr","--batch","--mode=fast",f"--port={port}",str(world)]
    result={"product_head":"f243b2b597a2a6bd6af38e895787d9dd4bdfef5e",
            "scope":"WINDOWS_BATCH_HTTP_WWI_DISCRIMINATION","port":port,
            "world_window_name":window,"webots_batch":False,"http_robot_window":False,
            "websocket_101":False,"auth_epoch":False,"auth_claim":False,"light_c_native":False,
            "world_reload": "NOT_TESTED","verdict":"UNPROVEN"}
    try:
        with captured_native_batch(command, package, env, out/"webots.stdout.log",
                                   out/"webots.stderr.log") as proc:
            result["webots_pid"]=proc.pid
            deadline=time.monotonic()+TIME_BUDGET_S
            url=f"/robot_windows/{window}/{window}.html?name=Crazyflie%20WebeeBlocks"
            while time.monotonic()<deadline:
                log=(out/"webots.stdout.log").read_text(encoding="utf-8",errors="replace")
                result["webots_batch"]=PREFIX+" READY" in log
                if result["webots_batch"]:
                    result["http_probe"]=probe_http(port,url)
                    if result["http_probe"]["served"]:
                        result["http_robot_window"]=True
                        break
                if proc.poll() is not None:
                    result["exit_before_http"]=proc.returncode
                    break
                time.sleep(0.5)
            if not result["http_robot_window"]:
                result["boundary"]="Native C READY does not imply batch HTTP Robot Window; not attempting synthetic WebSocket."
            else:
                ws=None
                try:
                    ws=Ws(port)
                    result["websocket_101"]=True
                    ws.send("robot:Crazyflie WebeeBlocks:init robot window")
                    challenge=secrets.token_hex(32)
                    ws.send(f"robot:Crazyflie WebeeBlocks:{PREFIX} REQUEST 101 AUTH_EPOCH {challenge}")
                    e=read_reply(ws,101,"epoch",time.monotonic()+8)
                    if e and e[0]==challenge:
                        result["auth_epoch"]=True
                        bearer=e[1]+secrets.token_hex(16)
                        nonce=secrets.token_hex(32)
                        ws.send(f"robot:Crazyflie WebeeBlocks:{PREFIX} REQUEST 102 AUTH_CLAIM {bearer} {nonce}")
                        claim=read_reply(ws,102,"claim",time.monotonic()+8)
                        if claim and claim[0]==nonce:
                            result["auth_claim"]=True
                            ws.send(f"robot:Crazyflie WebeeBlocks:{PREFIX} REQUEST 103 AUTH {bearer} LIGHT red")
                            response=read_reply(ws,103,"light",time.monotonic()+8)
                            # Native C emits a correlated trace only when it
                            # really reached wb_led_set, not an HTTP response.
                            result["light_native_ack"]=bool(response and response[0]=="OK")
                            # Webots C fflush(stdout) can precede the separate
                            # Python pipe-drain thread writing its disk log.
                            # Bound the independent trace barrier; ACK alone
                            # never substitutes for an actual C LED trace.
                            trace=""
                            trace_deadline=time.monotonic()+3
                            while time.monotonic()<trace_deadline:
                                trace=(out/"webots.stdout.log").read_text(
                                    encoding="utf-8",errors="replace")
                                if "TRACE LIGHT color=red rgb=ff0000" in trace:break
                                time.sleep(.05)
                            result["light_c_native"]=bool(result["light_native_ack"] and
                                             "TRACE LIGHT color=red rgb=ff0000" in trace)
                    result["boundary"]="Batch WWI connection protocol observed; world reload requires separate full browser checkpoint/handoff."
                except Exception as exc:
                    result["ws_error_type"]=type(exc).__name__
                    result["boundary"]="HTTP success does not establish WWI/CLAIM: transport evidence incomplete"
                finally:
                    if ws: ws.close()
            if not result["webots_batch"]:
                result["verdict"]="UNPROVEN_NATIVE_ENGINE_STARTUP"
                result["boundary"]="Cannot decide batch WWI: official Webots Windows engine failed before C READY."
            elif result["light_c_native"]:
                result["verdict"]="PASS_BATCH_WWI_LIGHT_ONLY"
            elif not result["http_robot_window"]:
                result["verdict"]="BATCH_HTTP_ROBOT_WINDOW_UNAVAILABLE"
            else:
                result["verdict"]="UNPROVEN_WWI"
    finally:
        (out/"batch-wwi-report.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
        print("BATCH_WWI_VERDICT="+result["verdict"],flush=True)
    # Unavailability is a conclusive discriminator, not a failed safety test.
    return 0 if result["verdict"] in ("PASS_BATCH_WWI_LIGHT_ONLY","BATCH_HTTP_ROBOT_WINDOW_UNAVAILABLE") else 1

if __name__=="__main__":
    raise SystemExit(main())

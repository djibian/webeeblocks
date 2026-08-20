#!/usr/bin/env python3
from __future__ import annotations
import http.server, os, pathlib, shutil, socketserver, subprocess, sys, threading, time
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[1]
HARNESS=pathlib.Path('experiments/reactive-blockly-pipeline/ui_pipeline_harness.html')
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

def browser():
    for c in (os.environ.get('CHROME_BIN'),'google-chrome','google-chrome-stable','chromium','chromium-browser'):
        if c and shutil.which(c): return shutil.which(c)
    raise RuntimeError('no Chrome/Chromium binary found')

def main():
    os.chdir(ROOT)
    with socketserver.TCPServer(('127.0.0.1',0),Quiet) as server:
        port=server.server_address[1]
        threading.Thread(target=server.serve_forever,daemon=True).start(); time.sleep(0.05)
        cp=subprocess.run([browser(),'--headless','--disable-gpu','--no-sandbox','--disable-dev-shm-usage','--virtual-time-budget=5000','--dump-dom',f'http://127.0.0.1:{port}/{HARNESS.as_posix()}'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=30,check=False)
        server.shutdown()
    marker='PASS real Blockly 2020 -> compiler #44 -> interpreter #45 -> scripted backend'
    if marker not in cp.stdout:
        print('FAIL composed reactive pipeline',file=sys.stderr); print(cp.stderr[-4000:],file=sys.stderr); print(cp.stdout[-8000:],file=sys.stderr); return 1
    print(marker); return 0
if __name__=='__main__': raise SystemExit(main())

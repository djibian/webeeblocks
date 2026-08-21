#!/usr/bin/env python3
from __future__ import annotations
import http.server, os, pathlib, re, shutil, socketserver, subprocess, sys, threading, time
HERE=pathlib.Path(__file__).resolve().parent; REPO_ROOT=HERE.parents[1]; HARNESS=pathlib.Path('tools/ci/runtime_v2_core_harness.html')
def browser_binary():
    for candidate in (os.environ.get('CHROME_BIN'),'google-chrome','google-chrome-stable','chromium','chromium-browser'):
        if candidate and shutil.which(candidate): return shutil.which(candidate) or candidate
    raise RuntimeError('no Chrome/Chromium binary found; set CHROME_BIN')
class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self,fmt,*args): pass
def main():
    browser=browser_binary(); os.chdir(REPO_ROOT)
    with socketserver.TCPServer(('127.0.0.1',0),QuietHandler) as server:
        port=server.server_address[1]; threading.Thread(target=server.serve_forever,daemon=True).start(); time.sleep(.05); url=f'http://127.0.0.1:{port}/{HARNESS.as_posix()}'
        completed=subprocess.run([browser,'--headless','--disable-gpu','--no-sandbox','--disable-dev-shm-usage','--virtual-time-budget=5000','--dump-dom',url],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=30,check=False); server.shutdown()
    marker='PASS Runtime v2 resolved profile -> real Blockly -> AST -> preflight -> interpreter'
    rendered=re.search(r'<pre id="result" data-status="PASS">([^<]+)</pre>', completed.stdout)
    if not rendered or rendered.group(1).strip()!=marker:
        print('FAIL Runtime v2 product core',file=sys.stderr); print('browser exit:',completed.returncode,file=sys.stderr); print(completed.stderr[-4000:],file=sys.stderr); print(completed.stdout[-8000:],file=sys.stderr); return 1
    print(marker); return 0
if __name__=='__main__': raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations
import html, http.server, os, pathlib, re, shutil, socketserver, subprocess, sys, threading, time
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
        process=subprocess.Popen([browser,'--headless=new','--disable-gpu','--no-sandbox','--disable-dev-shm-usage','--disable-background-networking','--virtual-time-budget=5000','--dump-dom',url],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        timed_out=False
        try: stdout,stderr=process.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            timed_out=True; process.kill(); stdout,stderr=process.communicate()
        server.shutdown()
    marker='PASS Runtime v2 modern Blockly reactive semantics -> AST -> fail-closed preflight -> shared interpreter'
    rendered=re.search(r'<pre id="result" data-status="PASS">([^<]+)</pre>',stdout)
    rendered_text=html.unescape(rendered.group(1)).strip() if rendered else None
    if rendered_text!=marker:
        print('FAIL Runtime v2 product core',file=sys.stderr); print('browser exit:',process.returncode,file=sys.stderr); print(stderr[-4000:],file=sys.stderr); print(stdout[-8000:],file=sys.stderr); return 1
    if not timed_out and process.returncode:
        print(f'FAIL Runtime v2 product core: browser exited {process.returncode}',file=sys.stderr); print(stderr[-4000:],file=sys.stderr); return 1
    if timed_out: print('WARN: headless browser required forced shutdown after emitting the exact Runtime v2 PASS DOM marker.',file=sys.stderr)
    print(marker); return 0
if __name__=='__main__': raise SystemExit(main())

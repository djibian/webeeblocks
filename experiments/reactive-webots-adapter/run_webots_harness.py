#!/usr/bin/env python3
from __future__ import annotations
import http.server
import json
import os
import pathlib
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
HARNESS = pathlib.Path('experiments/reactive-webots-adapter/ui_webots_harness.html')

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

def browser():
    for candidate in (os.environ.get('CHROME_BIN'), 'google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'):
        if candidate and shutil.which(candidate):
            return shutil.which(candidate)
    raise RuntimeError('no Chrome/Chromium binary found')

def wait_webots(timeout=60.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=1) as response:
                payload = json.load(response)
            if payload.get('fatal'):
                raise RuntimeError('Webots adapter fatal: ' + str(payload['fatal']))
            if payload.get('ready') is True:
                return
            last = payload
        except Exception as exc:
            last = str(exc)
        time.sleep(0.25)
    raise RuntimeError('Webots adapter did not become ready: ' + repr(last))

def main():
    wait_webots()
    os.chdir(ROOT)
    with socketserver.TCPServer(('127.0.0.1', 0), Quiet) as server:
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        time.sleep(0.05)
        command = [
            browser(), '--headless', '--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage',
            '--disable-background-networking', '--dump-dom',
            f'http://127.0.0.1:{port}/{HARNESS.as_posix()}'
        ]
        try:
            completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=75, check=False)
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ''
            stderr = exc.stderr or ''
            marker = 'PASS real Blockly 2020 -> #44 compiler -> #45 interpreter -> real Webots range/action adapter'
            if marker in stdout:
                print(marker)
                return 0
            print('FAIL browser timeout', file=sys.stderr)
            print(stderr[-4000:], file=sys.stderr)
            print(stdout[-10000:], file=sys.stderr)
            return 1
        finally:
            server.shutdown()
    marker = 'PASS real Blockly 2020 -> #44 compiler -> #45 interpreter -> real Webots range/action adapter'
    if completed.returncode != 0 or marker not in completed.stdout:
        print('FAIL reactive Webots adapter harness', file=sys.stderr)
        print(completed.stderr[-4000:], file=sys.stderr)
        print(completed.stdout[-12000:], file=sys.stderr)
        return 1
    print(marker)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

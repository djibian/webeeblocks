#!/usr/bin/env python3
"""Disposable R3 T1/T3 loopback witness. Never logs or persists old bearer keys."""
import argparse
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--events", required=True)
parser.add_argument("--phase-file", required=True)
args = parser.parse_args()
events = Path(args.events)
phase_path = Path(args.phase_file)
events.parent.mkdir(parents=True, exist_ok=True)
guard = threading.Lock()
old_key = None

class Handler(BaseHTTPRequestHandler):
    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def reply(self, status, data=None):
        payload = b"" if data is None else json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if payload:
            self.wfile.write(payload)

    def do_OPTIONS(self):
        self.reply(204)

    def do_GET(self):
        global old_key
        if self.path == "/phase":
            self.reply(200, {"phase": int(phase_path.read_text().strip())})
        elif self.path == "/old-capability":
            with guard:
                cap = old_key if phase_path.read_text().strip() == "2" else None
            self.reply(200 if cap else 409, {"key": cap} if cap else {"error":"not ready"})
        else:
            self.reply(404)

    def do_POST(self):
        global old_key
        if self.path not in ("/event", "/old-capability") or int(self.headers.get("Content-Length","0")) > 262144:
            self.reply(400)
            return
        try:
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if not isinstance(payload, dict):
                raise ValueError("not an object")
            if self.path == "/old-capability":
                cap = payload.get("key")
                if (phase_path.read_text().strip() != "1" or
                    not isinstance(cap,str) or not re.fullmatch(r"[0-9a-f]{64}",cap)):
                    self.reply(403); return
                with guard:
                    if old_key is not None:
                        self.reply(409); return
                    old_key = cap  # Volatile RAM only, never printed or written.
                self.reply(204); return
            if ("key" in json.dumps(payload).lower() or
                re.search(r"[0-9a-f]{64}", json.dumps(payload))):
                self.reply(400); return
            row = json.dumps(payload, allow_nan=False, ensure_ascii=True)
            with guard, events.open("a", encoding="utf-8") as f:
                f.write(row + "\n")
                f.flush()
            self.reply(204)
        except (ValueError, KeyError, TypeError):
            self.reply(400)

    def log_message(self, *_):
        pass

ThreadingHTTPServer(("127.0.0.1",8765), Handler).serve_forever()

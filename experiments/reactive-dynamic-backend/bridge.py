#!/usr/bin/env python3
import json, os, pathlib, tempfile, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(os.environ.get("WEBEEBLOCKS_ROOT", ".")).resolve()
ART = ROOT / "ci-artifacts"
ART.mkdir(parents=True, exist_ok=True)
COMMAND = ART / "b4-command.txt"
TRACE = ART / "b4-controller-trace.jsonl"
counter = 0

def atomic_write(path, text):
    fd, tmp = tempfile.mkstemp(prefix=path.name+".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass

class H(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def cors(self):
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
        self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS")
    def reply(self, code, obj):
        raw=json.dumps(obj,separators=(",",":")).encode()
        self.send_response(code); self.cors()
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw))); self.end_headers()
        self.wfile.write(raw)
    def do_OPTIONS(self):
        self.send_response(204); self.cors(); self.end_headers()
    def do_GET(self):
        if self.path == "/health":
            self.reply(200, {"ok": True})
        elif self.path == "/trace":
            rows=[]
            if TRACE.exists():
                for line in TRACE.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        try: rows.append(json.loads(line))
                        except Exception: rows.append({"op":"trace-parse-error","raw":line})
            self.reply(200, {"trace": rows})
        else: self.reply(404, {"ok":False,"error":"not found"})
    def do_POST(self):
        global counter
        if self.path != "/rpc":
            self.reply(404, {"ok":False,"error":"not found"}); return
        try:
            n=int(self.headers.get("Content-Length","0"))
            req=json.loads(self.rfile.read(n).decode())
            counter += 1; ident=counter
            op=req.get("op","")
            # The line protocol consumed by the C controller uses whitespace
            # tokenisation. Keep commands without a direction (TAKEOFF/LAND)
            # representable with an explicit sentinel instead of `direction=`.
            direction=req.get("direction") or "-"
            value=req.get("height_m", req.get("distance_m", 0))
            atomic_write(COMMAND, f"id={ident} op={op} direction={direction} value={float(value):.9f}\n")
            response=ART/f"b4-response-{ident}.json"
            deadline=time.time()+40
            while time.time()<deadline:
                if response.exists():
                    obj=json.loads(response.read_text(encoding="utf-8"))
                    self.reply(200 if obj.get("ok") else 409,obj); return
                time.sleep(.02)
            self.reply(504, {"ok":False,"error":"dynamic backend timeout","id":ident})
        except Exception as exc:
            self.reply(400, {"ok":False,"error":str(exc)})

if __name__ == "__main__":
    for p in ART.glob("b4-response-*.json"): p.unlink()
    for p in (COMMAND, TRACE):
        try: p.unlink()
        except FileNotFoundError: pass
    ThreadingHTTPServer(("127.0.0.1",8766),H).serve_forever()

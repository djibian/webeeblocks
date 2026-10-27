#!/usr/bin/env python3
import argparse
import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--output', required=True)
    parser.add_argument('--completion-sentinel')
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    completion_sentinel = Path(args.completion_sentinel) if args.completion_sentinel else None
    if completion_sentinel:
        completion_sentinel.parent.mkdir(parents=True, exist_ok=True)

    write_lock = threading.Lock()
    max_event_bytes = 4 * 1024 * 1024

    class Handler(BaseHTTPRequestHandler):
        def _cors(self) -> None:
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            if self.path != '/health':
                self.send_error(404)
                return
            self.send_response(200)
            self._cors()
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK\n')

        def do_POST(self):
            if self.path != '/event':
                self.send_error(404)
                return
            # Reject malformed/unbounded HTTP bodies before they enter the
            # durable native-evidence stream. Browser probes send small JSON
            # objects with a regular Content-Length.
            try:
                length = int(self.headers.get('Content-Length', ''))
            except ValueError:
                self.send_error(400, 'invalid Content-Length')
                return
            if length <= 0:
                self.send_error(400, 'empty or invalid event length')
                return
            if length > max_event_bytes:
                self.send_error(413, 'event exceeds size limit')
                return
            self.connection.settimeout(5)
            try:
                raw = self.rfile.read(length)
            except (OSError, socket.timeout):
                self.send_error(400, 'incomplete event body')
                return
            if len(raw) != length:
                self.send_error(400, 'incomplete event body')
                return
            try:
                payload = json.loads(raw.decode('utf-8'))
            except (ValueError, UnicodeError, RecursionError):
                self.send_error(400, 'invalid event JSON')
                return
            if not isinstance(payload, dict):
                self.send_error(400, 'event must be a JSON object')
                return
            # Python json.loads accepts NaN/Infinity (including overflowing
            # exponents) by default. Validate the *serialized* row before any
            # durable effect, so JSONL stays standard JSON at every depth.
            try:
                row = json.dumps(payload, separators=(',', ':'), allow_nan=False)
            except (ValueError, RecursionError):
                self.send_error(400, 'invalid or non-finite event JSON value')
                return
            # These requests run on separate HTTP threads. Serialize the
            # append and completion marker so rows cannot interleave or race.
            with write_lock:
                with output.open('a', encoding='utf-8') as handle:
                    handle.write(row + '\n')
                    handle.flush()
                    os.fsync(handle.fileno())
                if completion_sentinel and payload.get('event') == 'CHALLENGE_TEST_COMPLETE':
                    pending = completion_sentinel.with_suffix(completion_sentinel.suffix + '.tmp')
                    pending.write_text('CHALLENGE_TEST_COMPLETE\n', encoding='utf-8')
                    pending.replace(completion_sentinel)
            self.send_response(204)
            self._cors()
            self.end_headers()

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

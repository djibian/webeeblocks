#!/usr/bin/env python3
"""Loopback-only, non-authority bridge to one live Crazyflie capability session.

The service intentionally exposes only the two reads required by
physical_capability_contract.js: the current connection epoch and a fresh
capability descriptor. It owns no arming, setpoint, movement, light or other
physical effect API.
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets

from probe_reference_hardware import ProbeError, ReadOnlyCapabilitySession


class CapabilityBridgeError(RuntimeError):
    """Fail-closed request/bridge error."""


class ReadOnlyCapabilityHttpBridge:
    def __init__(
        self,
        session: ReadOnlyCapabilitySession,
        *,
        token: str | None = None,
        host: str = "127.0.0.1",
        port: int = 0,
    ) -> None:
        if host not in {"127.0.0.1", "localhost"}:
            raise CapabilityBridgeError("capability bridge must bind to IPv4 loopback")
        self.session = session
        self.token = token or secrets.token_urlsafe(32)
        if not isinstance(self.token, str) or not self.token.strip():
            raise CapabilityBridgeError("capability bridge token must be non-empty")
        self._server = ThreadingHTTPServer((host, port), self._handler_type())

    def _handler_type(self):
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format: str, *_args) -> None:
                return

            def _cors(self) -> None:
                # The service is loopback-only and every data read still requires
                # the unguessable bearer capability. No cookies/credentials are used.
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Authorization, Cache-Control")

            def _json(self, status: int, payload: object) -> None:
                data = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self._cors()
                self.end_headers()
                self.wfile.write(data)

            def _authorized(self) -> bool:
                return self.headers.get("Authorization") == f"Bearer {bridge.token}"

            def do_OPTIONS(self) -> None:  # noqa: N802 - browser CORS preflight only
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.send_header("Cache-Control", "no-store")
                self._cors()
                self.end_headers()

            def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
                if not self._authorized():
                    self._json(401, {"error": "unauthorized"})
                    return
                try:
                    if self.path == "/v1/connection-epoch":
                        self._json(200, {"connectionEpoch": bridge.session.read_connection_epoch()})
                    elif self.path == "/v1/capabilities":
                        self._json(200, bridge.session.read_capabilities())
                    else:
                        self._json(404, {"error": "not-found"})
                except ProbeError as exc:
                    self._json(409, {"error": str(exc)})

            def do_POST(self) -> None:  # noqa: N802 - fail closed on effects
                self._json(405, {"error": "read-only bridge"})

            def do_PUT(self) -> None:  # noqa: N802
                self._json(405, {"error": "read-only bridge"})

            def do_DELETE(self) -> None:  # noqa: N802
                self._json(405, {"error": "read-only bridge"})

        return Handler

    @property
    def address(self) -> tuple[str, int]:
        host, port = self._server.server_address[:2]
        return str(host), int(port)

    def serve_forever(self) -> None:
        self._server.serve_forever()

    def shutdown(self) -> None:
        self._server.shutdown()
        self._server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", required=True, help="explicit radio:// Crazyradio URI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()

    with ReadOnlyCapabilitySession(args.uri) as session:
        bridge = ReadOnlyCapabilityHttpBridge(session, host=args.host, port=args.port)
        host, port = bridge.address
        print(json.dumps({
            "baseUrl": f"http://{host}:{port}",
            "token": bridge.token,
            "executionAuthority": False,
        }, separators=(",", ":")), flush=True)
        try:
            bridge.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            bridge.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

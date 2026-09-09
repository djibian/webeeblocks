#!/usr/bin/env python3
"""Loopback-only, non-authority bridge to one live Crazyflie capability session.

The service exposes fresh capability/epoch reads plus a bounded current-program
challenge/response handoff for the already-integrated #249 browser preflight.
Only the trusted host can create a challenge. The browser-held bearer can answer
that pending challenge, but cannot create one and gains no arming, setpoint,
movement, light or other physical-effect API.
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import secrets
from threading import Condition
from time import monotonic

from probe_reference_hardware import ProbeError, ReadOnlyCapabilitySession


class CapabilityBridgeError(RuntimeError):
    """Fail-closed request/bridge error."""


_EVIDENCE_MINT_KEY = object()


class CurrentProgramPreflightEvidence:
    """One fresh exact-current-program assertion minted only by the host bridge."""

    def __init__(
        self,
        *,
        profile_id: str,
        ast_binding: str,
        connection_epoch: str,
        challenge_id: str,
        _mint_key: object,
    ) -> None:
        if _mint_key is not _EVIDENCE_MINT_KEY:
            raise CapabilityBridgeError(
                "current-program evidence may only be minted by the trusted host bridge"
            )
        self.profile_id = _require_text(profile_id, "profileId")
        self.ast_binding = _require_text(ast_binding, "astBinding")
        self.connection_epoch = _require_text(connection_epoch, "connectionEpoch")
        self.challenge_id = _require_text(challenge_id, "challengeId")
        self.execution_authority = False


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise CapabilityBridgeError(f"{name} must be a non-empty trimmed string")
    return value


def _require_timeout(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CapabilityBridgeError("current-program assertion timeout must be positive")
    timeout = float(value)
    if not math.isfinite(timeout) or timeout <= 0.0:
        raise CapabilityBridgeError("current-program assertion timeout must be positive")
    return timeout


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
        self._preflight_condition = Condition()
        self._preflight_pending: dict[str, object] | None = None
        self._preflight_closed = False
        self._server = ThreadingHTTPServer((host, port), self._handler_type())
        self._server.daemon_threads = True

    def assert_current_program(
        self,
        *,
        profile_id: str,
        ast_binding: str,
        connection_epoch: str,
        timeout_seconds: float = 1.0,
    ) -> CurrentProgramPreflightEvidence:
        """Require one fresh #249 browser assertion for this exact host binding."""
        expected_profile = _require_text(profile_id, "profileId")
        expected_ast = _require_text(ast_binding, "astBinding")
        expected_epoch = _require_text(connection_epoch, "connectionEpoch")
        timeout = _require_timeout(timeout_seconds)

        try:
            before_epoch = self.session.read_connection_epoch()
        except Exception as exc:
            raise CapabilityBridgeError(
                "live connection epoch unavailable before current-program challenge"
            ) from exc
        if before_epoch != expected_epoch:
            raise CapabilityBridgeError(
                "live connection changed before current-program challenge"
            )

        pending = {
            "challenge_id": secrets.token_urlsafe(24),
            "profile_id": expected_profile,
            "ast_binding": expected_ast,
            "connection_epoch": expected_epoch,
            "claimed": False,
            "settled": False,
            "error": None,
        }
        deadline = monotonic() + timeout
        with self._preflight_condition:
            if self._preflight_closed:
                raise CapabilityBridgeError("capability bridge is shut down")
            if self._preflight_pending is not None:
                raise CapabilityBridgeError(
                    "another current-program challenge is already pending"
                )
            self._preflight_pending = pending
            self._preflight_condition.notify_all()
            while not pending["settled"] and not self._preflight_closed:
                remaining = deadline - monotonic()
                if remaining <= 0.0:
                    if self._preflight_pending is pending:
                        self._preflight_pending = None
                        self._preflight_condition.notify_all()
                    raise CapabilityBridgeError(
                        "current-program assertion timed out"
                    )
                self._preflight_condition.wait(remaining)

            if self._preflight_closed:
                if self._preflight_pending is pending:
                    self._preflight_pending = None
                raise CapabilityBridgeError("capability bridge shut down during assertion")

            if self._preflight_pending is pending:
                self._preflight_pending = None
                self._preflight_condition.notify_all()
            error = pending["error"]

        if error is not None:
            raise CapabilityBridgeError(str(error))

        try:
            after_epoch = self.session.read_connection_epoch()
        except Exception as exc:
            raise CapabilityBridgeError(
                "live connection epoch unavailable after current-program assertion"
            ) from exc
        if after_epoch != expected_epoch:
            raise CapabilityBridgeError(
                "live connection changed during current-program assertion"
            )

        return CurrentProgramPreflightEvidence(
            profile_id=expected_profile,
            ast_binding=expected_ast,
            connection_epoch=expected_epoch,
            challenge_id=str(pending["challenge_id"]),
            _mint_key=_EVIDENCE_MINT_KEY,
        )

    def _claim_current_program_challenge(
        self,
        *,
        timeout_seconds: float = 1.0,
    ) -> str | None:
        deadline = monotonic() + _require_timeout(timeout_seconds)
        with self._preflight_condition:
            while True:
                if self._preflight_closed:
                    raise CapabilityBridgeError("capability bridge is shut down")
                pending = self._preflight_pending
                if (
                    pending is not None
                    and pending["settled"] is False
                    and pending["claimed"] is False
                ):
                    pending["claimed"] = True
                    return str(pending["challenge_id"])
                remaining = deadline - monotonic()
                if remaining <= 0.0:
                    return None
                self._preflight_condition.wait(remaining)

    def _submit_current_program_assertion(self, payload: object) -> None:
        if not isinstance(payload, dict):
            raise CapabilityBridgeError("current-program assertion must be a JSON object")
        challenge_id = _require_text(payload.get("challengeId"), "challengeId")

        with self._preflight_condition:
            pending = self._preflight_pending
            if (
                pending is None
                or pending["settled"] is True
                or pending["challenge_id"] != challenge_id
            ):
                raise CapabilityBridgeError(
                    "current-program assertion is stale, replayed or unknown"
                )
            if pending["claimed"] is not True:
                raise CapabilityBridgeError(
                    "current-program challenge was not claimed by the browser"
                )

            error: str | None = None
            try:
                if payload.get("executionAuthority") is not False:
                    raise CapabilityBridgeError(
                        "current-program assertion must remain non-authority"
                    )
                if payload.get("ok") is not True:
                    raise CapabilityBridgeError(
                        "browser current-program re-assertion failed"
                    )
                profile_id = _require_text(payload.get("profileId"), "profileId")
                ast_binding = _require_text(payload.get("astBinding"), "astBinding")
                connection_epoch = _require_text(
                    payload.get("connectionEpoch"), "connectionEpoch"
                )
                if (
                    profile_id != pending["profile_id"]
                    or ast_binding != pending["ast_binding"]
                    or connection_epoch != pending["connection_epoch"]
                ):
                    raise CapabilityBridgeError(
                        "browser current-program assertion does not match host binding"
                    )
            except CapabilityBridgeError as exc:
                error = str(exc)

            pending["error"] = error
            pending["settled"] = True
            self._preflight_condition.notify_all()

        if error is not None:
            raise CapabilityBridgeError(error)

    def _handler_type(self):
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format: str, *_args) -> None:
                return

            def _cors(self) -> None:
                # The service is loopback-only and every request still requires
                # the unguessable bearer capability. No cookies/credentials are used.
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header(
                    "Access-Control-Allow-Headers",
                    "Authorization, Cache-Control, Content-Type",
                )

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

            def _read_json(self) -> object:
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError as exc:
                    raise CapabilityBridgeError("invalid request length") from exc
                if length <= 0 or length > 4096:
                    raise CapabilityBridgeError("invalid current-program assertion size")
                try:
                    return json.loads(self.rfile.read(length).decode("utf-8"))
                except Exception as exc:
                    raise CapabilityBridgeError(
                        "malformed current-program assertion JSON"
                    ) from exc

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
                    elif self.path == "/v1/preflight-challenge":
                        challenge_id = bridge._claim_current_program_challenge()
                        self._json(
                            200,
                            {
                                "challengeId": challenge_id,
                                "executionAuthority": False,
                            },
                        )
                    else:
                        self._json(404, {"error": "not-found"})
                except (ProbeError, CapabilityBridgeError) as exc:
                    self._json(409, {"error": str(exc)})

            def do_POST(self) -> None:  # noqa: N802 - non-effect assertion response only
                if not self._authorized():
                    self._json(401, {"error": "unauthorized"})
                    return
                if self.path != "/v1/preflight-assertion":
                    self._json(405, {"error": "read-only bridge"})
                    return
                try:
                    bridge._submit_current_program_assertion(self._read_json())
                    self._json(
                        200,
                        {
                            "accepted": True,
                            "executionAuthority": False,
                        },
                    )
                except CapabilityBridgeError as exc:
                    self._json(409, {"error": str(exc)})

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
        with self._preflight_condition:
            self._preflight_closed = True
            self._preflight_condition.notify_all()
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

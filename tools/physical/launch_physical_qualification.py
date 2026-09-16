#!/usr/bin/env python3
"""Trusted product launcher for one exact WebeeBlocks physical qualification run.

The launcher composes the already-integrated physical host with three distinct
channels: ordinary parameter-free caller IPC, a one-way non-authority Robot
Window bootstrap, and the host-first teacher decision socket.  The browser never
receives the teacher socket.  Importing this module starts no process and creates
no physical authority.

This launcher does not replace the physical-host trust boundary.  It only makes
that boundary human-executable with the real Webots Robot Window.  The exact
current Blockly program is preflighted in the browser, re-asserted by the host,
shown to the teacher as a host-owned post-reset binding, and executed only after
one explicit approval.  After approval, the launcher sends only repeated
parameter-free ``execute-next-inflight`` requests; their count is derived from
the exact already-bound AST using the same static/dynamic dispatch boundary as
the host, never from caller-selected motion semantics.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import secrets
import shutil
import socket
import subprocess
import sys
from threading import Event, Lock, Thread
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
HOST = PHYSICAL / "serve_physical_host.py"
BASE_WINDOW = ROOT / "plugins" / "robot_windows" / "blockly_v2"
BASE_WORLD = ROOT / "worlds" / "crazyflie_runtime_v2.wbt"
BROWSER_HELPER = PHYSICAL / "physical_qualification_runtime.js"
MAX_JSON_BYTES = 65536
ROBOT_WINDOW_PERSPECTIVE = (
    "Webots Project File version R2025a\n"
    "robotWindow: Crazyflie WebeeBlocks\n"
)


class PhysicalQualificationLauncherError(RuntimeError):
    """Fail-closed launcher/composition error."""


def _require_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise PhysicalQualificationLauncherError(name + " must be a non-empty trimmed string")
    return value


def _read_socket_line(sock: socket.socket, *, timeout_seconds: float) -> dict[str, object]:
    if timeout_seconds <= 0:
        raise PhysicalQualificationLauncherError("socket timeout must be positive")
    old_timeout = sock.gettimeout()
    sock.settimeout(timeout_seconds)
    data = bytearray()
    try:
        while len(data) <= MAX_JSON_BYTES:
            chunk = sock.recv(1)
            if not chunk:
                raise PhysicalQualificationLauncherError("trusted channel closed before JSON line")
            if chunk == b"\n":
                break
            data.extend(chunk)
        else:
            raise PhysicalQualificationLauncherError("trusted channel message is too large")
    except (OSError, TimeoutError) as exc:
        raise PhysicalQualificationLauncherError("trusted channel read failed") from exc
    finally:
        sock.settimeout(old_timeout)
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PhysicalQualificationLauncherError("trusted channel returned malformed JSON") from exc
    if not isinstance(value, dict):
        raise PhysicalQualificationLauncherError("trusted channel JSON must be an object")
    return value


def _write_socket_line(sock: socket.socket, value: dict[str, object]) -> None:
    try:
        encoded = (json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PhysicalQualificationLauncherError("trusted channel response is not JSON-safe") from exc
    if len(encoded) > MAX_JSON_BYTES:
        raise PhysicalQualificationLauncherError("trusted channel response is too large")
    try:
        sock.sendall(encoded)
    except OSError as exc:
        raise PhysicalQualificationLauncherError("trusted channel write failed") from exc


def _read_fd_line(fd: int, *, timeout_seconds: float) -> dict[str, object]:
    result: queue.Queue[object] = queue.Queue(maxsize=1)

    def reader() -> None:
        try:
            with os.fdopen(fd, "r", encoding="utf-8", closefd=True) as stream:
                line = stream.readline(MAX_JSON_BYTES + 1)
                if not line or len(line.encode("utf-8")) > MAX_JSON_BYTES:
                    raise PhysicalQualificationLauncherError("browser bootstrap is missing or too large")
                result.put(json.loads(line))
        except Exception as exc:
            result.put(exc)

    thread = Thread(target=reader, daemon=True)
    thread.start()
    try:
        value = result.get(timeout=timeout_seconds)
    except queue.Empty as exc:
        raise PhysicalQualificationLauncherError("timed out waiting for host browser bootstrap") from exc
    if isinstance(value, Exception):
        if isinstance(value, PhysicalQualificationLauncherError):
            raise value
        raise PhysicalQualificationLauncherError("host browser bootstrap could not be read") from value
    if not isinstance(value, dict):
        raise PhysicalQualificationLauncherError("host browser bootstrap must be a JSON object")
    return value


def validate_host_bootstrap(value: dict[str, object]) -> dict[str, object]:
    if set(value) != {"baseUrl", "executionAuthority", "preflightResponderToken", "token"}:
        raise PhysicalQualificationLauncherError("host browser bootstrap has unsupported fields")
    if value.get("executionAuthority") is not False:
        raise PhysicalQualificationLauncherError("host browser bootstrap crossed authority boundary")
    base_url = _require_text(value.get("baseUrl"), "host bootstrap baseUrl")
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise PhysicalQualificationLauncherError("host browser bootstrap must stay on loopback HTTP")
    if parsed.port is None:
        raise PhysicalQualificationLauncherError("host browser bootstrap loopback port is missing")
    _require_text(value.get("token"), "host bootstrap token")
    _require_text(value.get("preflightResponderToken"), "host bootstrap responder token")
    return dict(value)


@dataclass(frozen=True, slots=True)
class PreparedProgram:
    profile_id: str
    ast_binding: str
    connection_epoch: str


class _PreparationState:
    def __init__(self, token: str) -> None:
        self.token = token
        self.lock = Lock()
        self.request_id: str | None = None
        self.result: dict[str, object] | None = None
        self.result_ready = Event()

    def begin(self) -> str:
        with self.lock:
            if self.request_id is not None:
                raise PhysicalQualificationLauncherError("physical preparation is one-shot")
            self.request_id = secrets.token_urlsafe(24)
            return self.request_id

    def snapshot_request(self) -> str | None:
        with self.lock:
            return self.request_id

    def publish(self, payload: dict[str, object]) -> None:
        with self.lock:
            if self.request_id is None:
                raise PhysicalQualificationLauncherError("browser prepared a program before request")
            if self.result is not None:
                raise PhysicalQualificationLauncherError("browser preparation result is already settled")
            if payload.get("requestId") != self.request_id:
                raise PhysicalQualificationLauncherError("browser preparation has wrong correlation")
            if payload.get("executionAuthority") is not False:
                raise PhysicalQualificationLauncherError("browser preparation crossed authority boundary")
            ok = payload.get("ok")
            if not isinstance(ok, bool):
                raise PhysicalQualificationLauncherError("browser preparation result lacks boolean ok")
            if ok:
                if set(payload) != {
                    "requestId", "ok", "profileId", "astBinding",
                    "connectionEpoch", "executionAuthority",
                }:
                    raise PhysicalQualificationLauncherError("browser success contains unsupported fields")
                _require_text(payload.get("profileId"), "prepared profileId")
                _require_text(payload.get("astBinding"), "prepared astBinding")
                _require_text(payload.get("connectionEpoch"), "prepared connectionEpoch")
            else:
                if set(payload) != {"requestId", "ok", "error", "executionAuthority"}:
                    raise PhysicalQualificationLauncherError("browser failure contains unsupported fields")
                _require_text(payload.get("error"), "prepared error")
            self.result = dict(payload)
            self.result_ready.set()

    def wait(self, timeout_seconds: float) -> PreparedProgram:
        if not self.result_ready.wait(timeout_seconds):
            raise PhysicalQualificationLauncherError("timed out waiting for Robot Window preflight")
        with self.lock:
            payload = dict(self.result or {})
        if payload.get("ok") is not True:
            raise PhysicalQualificationLauncherError(
                "Robot Window physical preflight failed: " + str(payload.get("error", "unknown error"))
            )
        return PreparedProgram(
            profile_id=_require_text(payload.get("profileId"), "prepared profileId"),
            ast_binding=_require_text(payload.get("astBinding"), "prepared astBinding"),
            connection_epoch=_require_text(payload.get("connectionEpoch"), "prepared connectionEpoch"),
        )


class QualificationPreparationBridge:
    """Authenticated loopback bridge carrying preparation data but no execution authority."""

    def __init__(self) -> None:
        self._state = _PreparationState(secrets.token_urlsafe(32))
        state = self._state

        class Handler(BaseHTTPRequestHandler):
            server_version = "WebeeBlocksPhysicalQualification/1"

            def log_message(self, _format: str, *_args: object) -> None:
                return

            def _cors(self) -> None:
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, Cache-Control")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Cache-Control", "no-store")

            def _json(self, status: int, value: dict[str, object]) -> None:
                encoded = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
                self.send_response(status)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def _authorized(self) -> bool:
                return self.headers.get("Authorization") == "Bearer " + state.token

            def do_OPTIONS(self) -> None:
                self.send_response(204)
                self._cors()
                self.end_headers()

            def do_GET(self) -> None:
                if not self._authorized():
                    self._json(401, {"error": "unauthorized", "executionAuthority": False})
                    return
                if self.path != "/v1/prepare-request":
                    self._json(404, {"error": "not found", "executionAuthority": False})
                    return
                self._json(200, {
                    "requestId": state.snapshot_request(),
                    "executionAuthority": False,
                })

            def do_POST(self) -> None:
                if not self._authorized():
                    self._json(401, {"error": "unauthorized", "executionAuthority": False})
                    return
                if self.path != "/v1/prepared":
                    self._json(404, {"error": "not found", "executionAuthority": False})
                    return
                try:
                    length_text = self.headers.get("Content-Length")
                    if length_text is None:
                        raise PhysicalQualificationLauncherError("missing Content-Length")
                    length = int(length_text)
                    if length < 0 or length > MAX_JSON_BYTES:
                        raise PhysicalQualificationLauncherError("preparation payload is too large")
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                    if not isinstance(payload, dict):
                        raise PhysicalQualificationLauncherError("preparation payload must be an object")
                    state.publish(payload)
                except (ValueError, UnicodeError, json.JSONDecodeError, PhysicalQualificationLauncherError) as exc:
                    self._json(400, {"error": str(exc), "executionAuthority": False})
                    return
                self._json(200, {"ok": True, "executionAuthority": False})

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        try:
            self._thread.start()
        except BaseException:
            self._server.server_close()
            raise

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    @property
    def token(self) -> str:
        return self._state.token

    def request_preparation(self, *, timeout_seconds: float) -> PreparedProgram:
        self._state.begin()
        return self._state.wait(timeout_seconds)

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=1.0)


def _html_safe_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).replace("<", "\\u003c")


@dataclass(slots=True)
class EphemeralRobotWindow:
    plugin_dir: Path
    world_path: Path
    perspective_path: Path

    def close(self) -> None:
        try:
            self.perspective_path.unlink(missing_ok=True)
            self.world_path.unlink(missing_ok=True)
        finally:
            shutil.rmtree(self.plugin_dir, ignore_errors=True)


def prepare_ephemeral_robot_window(
    *,
    source_plugin: Path,
    source_world: Path,
    helper_script: Path,
    launcher_base_url: str,
    launcher_token: str,
    host_bootstrap: dict[str, object],
) -> EphemeralRobotWindow:
    source_plugin = source_plugin.resolve()
    source_world = source_world.resolve()
    helper_script = helper_script.resolve()
    if not source_plugin.is_dir() or not source_world.is_file() or not helper_script.is_file():
        raise PhysicalQualificationLauncherError("qualification Robot Window sources are incomplete")
    for required in ("blockly_v2.html", "main.js", "physical_preflight_runtime.js"):
        if not (source_plugin / required).is_file():
            raise PhysicalQualificationLauncherError("qualification Robot Window missing " + required)
    if source_plugin == BASE_WINDOW.resolve() and not (source_plugin / "vendor" / "blockly_compressed.js").is_file():
        raise PhysicalQualificationLauncherError(
            "Runtime v2 assets are not prepared; run tools/prepare_runtime_v2.sh or tools/prepare_runtime_v2.ps1 first"
        )

    robot_windows = source_plugin.parent
    worlds = source_world.parent
    suffix = secrets.token_hex(8)
    plugin_name = "blockly_v2_physical_" + suffix
    plugin_dir = robot_windows / plugin_name
    world_path = worlds / ("webeeblocks-physical-" + suffix + ".wbt")
    perspective_path = worlds / ("." + world_path.stem + ".wbproj")
    if plugin_dir.exists() or world_path.exists() or perspective_path.exists():
        raise PhysicalQualificationLauncherError("ephemeral qualification path collision")

    try:
        shutil.copytree(source_plugin, plugin_dir)
        shutil.copy2(helper_script, plugin_dir / "physical_qualification_runtime.js")
        source_html_path = plugin_dir / "blockly_v2.html"
        html = source_html_path.read_text(encoding="utf-8")
        marker = '<script src="physical_preflight_runtime.js"></script>'
        if html.count(marker) != 1:
            raise PhysicalQualificationLauncherError("Robot Window preflight insertion point is ambiguous")
        config = {
            "launcherBaseUrl": _require_text(launcher_base_url, "launcherBaseUrl"),
            "launcherToken": _require_text(launcher_token, "launcherToken"),
            "hostBootstrap": validate_host_bootstrap(host_bootstrap),
            "executionAuthority": False,
        }
        injection = (
            marker
            + "\n  <script>window.WebeeBlocksPhysicalQualificationConfig = Object.freeze("
            + _html_safe_json(config)
            + ");</script>\n  <script src=\"physical_qualification_runtime.js\"></script>"
        )
        html_path = plugin_dir / (plugin_name + ".html")
        html_path.write_text(html.replace(marker, injection, 1), encoding="utf-8")
        source_html_path.unlink()

        world = source_world.read_text(encoding="utf-8")
        window_marker = 'window "blockly_v2"'
        if world.count(window_marker) != 1:
            raise PhysicalQualificationLauncherError("source world Robot Window binding is ambiguous")
        world_path.write_text(
            world.replace(window_marker, f'window "{plugin_name}"', 1),
            encoding="utf-8",
        )
        perspective_path.write_text(ROBOT_WINDOW_PERSPECTIVE, encoding="utf-8")
        return EphemeralRobotWindow(
            plugin_dir=plugin_dir,
            world_path=world_path,
            perspective_path=perspective_path,
        )
    except Exception:
        try:
            perspective_path.unlink(missing_ok=True)
            world_path.unlink(missing_ok=True)
        finally:
            shutil.rmtree(plugin_dir, ignore_errors=True)
        raise


def execution_request_count(ast_binding: str) -> int:
    """Return only how many parameter-free host execution requests are required."""
    _require_text(ast_binding, "astBinding")
    try:
        parsed = json.loads(ast_binding)
    except json.JSONDecodeError as exc:
        raise PhysicalQualificationLauncherError("prepared AST binding is malformed") from exc
    if not isinstance(parsed, dict) or not isinstance(parsed.get("program"), list):
        raise PhysicalQualificationLauncherError("prepared AST program is unavailable")

    if str(PHYSICAL) not in sys.path:
        sys.path.insert(0, str(PHYSICAL))
    from physical_program_sequence import PhysicalProgramSequence, PhysicalProgramSequenceError

    try:
        PhysicalProgramSequence(ast_binding)
    except PhysicalProgramSequenceError:
        return 1
    count = len(parsed["program"]) - 1
    if count < 1:
        raise PhysicalQualificationLauncherError("static physical program has no terminal execution step")
    return count


def _teacher_proposal(value: dict[str, object], prepared: PreparedProgram) -> dict[str, object]:
    required = {
        "op", "requestId", "challengeId", "profileId", "astBinding",
        "connectionEpoch", "executionAuthority",
    }
    if set(value) != required or value.get("op") != "teacher-run-binding-proposal":
        raise PhysicalQualificationLauncherError("teacher proposal has unsupported shape")
    if value.get("executionAuthority") is not False:
        raise PhysicalQualificationLauncherError("teacher proposal crossed authority boundary")
    for name in ("requestId", "challengeId", "profileId", "astBinding", "connectionEpoch"):
        _require_text(value.get(name), "teacher proposal " + name)
    if (
        value.get("profileId") != prepared.profile_id
        or value.get("astBinding") != prepared.ast_binding
    ):
        raise PhysicalQualificationLauncherError("teacher proposal changed the exact prepared program")
    if value.get("connectionEpoch") == prepared.connection_epoch:
        raise PhysicalQualificationLauncherError("teacher proposal did not rotate the connection epoch")
    return dict(value)


def teacher_decision_reply(proposal: dict[str, object], approved: bool) -> dict[str, object]:
    if not isinstance(approved, bool):
        raise PhysicalQualificationLauncherError("teacher approval must be explicit boolean")
    return {
        "op": "teacher-run-decision-result",
        "requestId": proposal["requestId"],
        "challengeId": proposal["challengeId"],
        "profileId": proposal["profileId"],
        "astBinding": proposal["astBinding"],
        "connectionEpoch": proposal["connectionEpoch"],
        "approved": approved,
        "executionAuthority": False,
    }


class PhysicalQualificationSession:
    """One trusted launcher session; no physical effect happens before explicit approval."""

    def __init__(
        self,
        *,
        uri: str,
        webots_executable: str,
        world_path: Path = BASE_WORLD,
        host_path: Path = HOST,
        source_plugin: Path = BASE_WINDOW,
        helper_script: Path = BROWSER_HELPER,
        webots_args: tuple[str, ...] = (),
    ) -> None:
        if not isinstance(uri, str) or not uri.startswith("radio://"):
            raise PhysicalQualificationLauncherError("explicit radio:// URI is required")
        self.uri = uri
        self.webots_executable = _require_text(webots_executable, "webots executable")
        self.world_path = world_path
        self.host_path = host_path
        self.source_plugin = source_plugin
        self.helper_script = helper_script
        self.webots_args = tuple(webots_args)
        self._bridge: QualificationPreparationBridge | None = None
        self._ephemeral: EphemeralRobotWindow | None = None
        self._host: subprocess.Popen[Any] | None = None
        self._webots: subprocess.Popen[Any] | None = None
        self._caller: socket.socket | None = None
        self._teacher: socket.socket | None = None
        self._prepared: PreparedProgram | None = None
        self._teacher_sealed = False

    def _spawn_host(self) -> dict[str, object]:
        caller_host, caller_peer = socket.socketpair()
        teacher_host, teacher_peer = socket.socketpair()
        browser_read, browser_write = os.pipe()
        child_sockets = (caller_host, teacher_host)
        try:
            for item in child_sockets:
                item.set_inheritable(True)
            os.set_inheritable(browser_write, True)
            argv = [
                sys.executable, str(self.host_path),
                "--uri", self.uri,
                "--caller-fd", str(caller_host.fileno()),
                "--browser-config-fd", str(browser_write),
                "--teacher-fd", str(teacher_host.fileno()),
            ]
            popen_kwargs: dict[str, object] = {"cwd": str(ROOT)}
            if os.name == "posix":
                popen_kwargs["close_fds"] = True
                popen_kwargs["pass_fds"] = (
                    caller_host.fileno(), browser_write, teacher_host.fileno()
                )
            else:
                popen_kwargs["close_fds"] = False
            self._host = subprocess.Popen(argv, **popen_kwargs)
        except Exception:
            caller_peer.close()
            teacher_peer.close()
            os.close(browser_read)
            raise
        finally:
            caller_host.close()
            teacher_host.close()
            os.close(browser_write)
        self._caller = caller_peer
        self._teacher = teacher_peer
        return validate_host_bootstrap(_read_fd_line(browser_read, timeout_seconds=10.0))

    def start(self) -> None:
        if self._host is not None or self._bridge is not None:
            raise PhysicalQualificationLauncherError("qualification session is already started")
        try:
            bootstrap = self._spawn_host()
            self._bridge = QualificationPreparationBridge()
            self._ephemeral = prepare_ephemeral_robot_window(
                source_plugin=self.source_plugin,
                source_world=self.world_path,
                helper_script=self.helper_script,
                launcher_base_url=self._bridge.base_url,
                launcher_token=self._bridge.token,
                host_bootstrap=bootstrap,
            )
            self._webots = subprocess.Popen(
                [self.webots_executable, *self.webots_args, str(self._ephemeral.world_path)],
                cwd=str(ROOT),
            )
        except BaseException:
            self.close()
            raise

    def prepare(self, *, timeout_seconds: float = 30.0) -> tuple[PreparedProgram, dict[str, object]]:
        if self._bridge is None or self._caller is None or self._teacher is None:
            raise PhysicalQualificationLauncherError("qualification session is not started")
        if self._prepared is not None:
            raise PhysicalQualificationLauncherError("qualification program is already prepared")
        prepared = self._bridge.request_preparation(timeout_seconds=timeout_seconds)
        request_id = secrets.token_urlsafe(18)
        _write_socket_line(self._caller, {
            "op": "validate-run-context",
            "requestId": request_id,
            "profileId": prepared.profile_id,
            "astBinding": prepared.ast_binding,
            "connectionEpoch": prepared.connection_epoch,
        })
        response = _read_socket_line(self._caller, timeout_seconds=timeout_seconds)
        if set(response) != {"requestId", "ok", "executionAuthority"}:
            raise PhysicalQualificationLauncherError("host validation reply has unsupported shape")
        if response.get("requestId") != request_id or response.get("executionAuthority") is not False:
            raise PhysicalQualificationLauncherError("host validation reply lost exact correlation/non-authority")
        if response.get("ok") is not True:
            raise PhysicalQualificationLauncherError("host rejected exact current-program validation")
        proposal = _teacher_proposal(
            _read_socket_line(self._teacher, timeout_seconds=timeout_seconds),
            prepared,
        )
        self._prepared = prepared
        return prepared, proposal

    def decide(self, proposal: dict[str, object], *, approved: bool) -> None:
        if self._teacher is None or self._prepared is None or self._teacher_sealed:
            raise PhysicalQualificationLauncherError("teacher decision is not available")
        checked = _teacher_proposal(proposal, self._prepared)
        _write_socket_line(self._teacher, teacher_decision_reply(checked, approved))
        # sendall returning makes the one-shot decision an irrevocable outcome:
        # never allow a retry even if the following local half-close is uncertain.
        self._teacher_sealed = True
        try:
            self._teacher.shutdown(socket.SHUT_WR)
        except OSError as exc:
            raise PhysicalQualificationLauncherError(
                "teacher decision was sent; local channel half-close is uncertain"
            ) from exc

    def execute_approved_program(self, *, timeout_seconds: float = 30.0) -> None:
        if self._caller is None or self._prepared is None or not self._teacher_sealed:
            raise PhysicalQualificationLauncherError("approved exact program is not ready for execution")
        count = execution_request_count(self._prepared.ast_binding)
        for index in range(count):
            request_id = "execute-" + str(index + 1) + "-" + secrets.token_urlsafe(12)
            _write_socket_line(self._caller, {
                "op": "execute-next-inflight",
                "requestId": request_id,
            })
            response = _read_socket_line(self._caller, timeout_seconds=timeout_seconds)
            if response.get("requestId") != request_id or response.get("executionAuthority") is not False:
                raise PhysicalQualificationLauncherError("in-flight reply lost exact correlation/non-authority")
            if response.get("ok") is not True:
                raise PhysicalQualificationLauncherError(
                    "trusted parameter-free program execution failed closed at step " + str(index + 1)
                )

    def close(self) -> None:
        if self._caller is not None:
            try:
                self._caller.shutdown(socket.SHUT_WR)
            except OSError:
                pass
            try:
                self._caller.close()
            except OSError:
                pass
            self._caller = None
        if self._teacher is not None:
            try:
                self._teacher.close()
            except OSError:
                pass
            self._teacher = None
        if self._webots is not None:
            if self._webots.poll() is None:
                self._webots.terminate()
                try:
                    self._webots.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    self._webots.kill()
                    self._webots.wait(timeout=5.0)
            self._webots = None
        if self._host is not None:
            try:
                self._host.wait(timeout=10.0)
            except subprocess.TimeoutExpired:
                self._host.terminate()
                try:
                    self._host.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    self._host.kill()
                    self._host.wait(timeout=5.0)
            self._host = None
        if self._bridge is not None:
            self._bridge.close()
            self._bridge = None
        if self._ephemeral is not None:
            self._ephemeral.close()
            self._ephemeral = None

    def __enter__(self) -> "PhysicalQualificationSession":
        self.start()
        return self

    def __exit__(self, _kind, _value, _traceback) -> None:
        self.close()


def _binding_summary(prepared: PreparedProgram, proposal: dict[str, object]) -> str:
    digest = hashlib.sha256(prepared.ast_binding.encode("utf-8")).hexdigest()
    return (
        "Profile: " + prepared.profile_id + "\n"
        + "AST SHA-256: " + digest + "\n"
        + "Post-reset connection epoch: " + str(proposal["connectionEpoch"])
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Launch one trusted WebeeBlocks physical qualification run"
    )
    parser.add_argument("--uri", required=True, help="explicit radio:// Crazyradio URI")
    parser.add_argument("--webots", default="webots", help="Webots executable")
    parser.add_argument("--world", type=Path, default=BASE_WORLD, help="source Webots world")
    parser.add_argument("--webots-arg", action="append", default=[], help="additional Webots argument")
    args = parser.parse_args(argv)

    try:
        with PhysicalQualificationSession(
            uri=args.uri,
            webots_executable=args.webots,
            world_path=args.world,
            webots_args=tuple(args.webots_arg),
        ) as session:
            print("Robot Window physique lancée. Préparez le programme final dans WebeeBlocks.")
            command = input("Tapez PREPARE pour figer le programme exact, ou QUIT pour annuler : ").strip().upper()
            if command != "PREPARE":
                print("Qualification annulée avant toute autorisation physique.")
                return 2
            prepared, proposal = session.prepare()
            print("\nLe host propose exactement ce programme après reset :")
            print(_binding_summary(prepared, proposal))
            decision = input("Tapez APPROVE pour autoriser cette exécution unique, sinon DENY : ").strip().upper()
            approved = decision == "APPROVE"
            session.decide(proposal, approved=approved)
            if not approved:
                print("Exécution physique refusée ; aucun programme n'est lancé.")
                return 2
            session.execute_approved_program()
            print("Programme physique exact terminé sous l'autorité du host.")
            return 0
    except (PhysicalQualificationLauncherError, OSError, subprocess.SubprocessError) as exc:
        print("ERREUR qualification physique : " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Trusted one-shot launcher for representative physical qualification.

This is preparation/composition for #157, not a motorized CI test and not a new
student authority surface. The launcher keeps the three production channels
separate, starts the existing trusted physical host, delivers only non-authority
bootstrap/caller data to an actual Webots Robot Window, and keeps the teacher
post-reset decision on a distinct host-side socket.

The browser may submit one exact current profile/AST/epoch and then ask this
launcher to run it. It never supplies motion, branch, sensor, cursor or step
parameters. The launcher validates/stages that binding through the existing host,
waits for the exact host-first teacher decision, and advances only the already
teacher-bound program with parameter-free ``execute-next-inflight`` requests.

Importing this module performs no I/O and creates no physical effect.
"""

from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import os
from pathlib import Path
import secrets
import select
import shutil
import socket
import subprocess
import sys
import tempfile
from threading import Lock, Thread
import time
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = Path(__file__).resolve().parent
HOST = PHYSICAL / "serve_physical_host.py"
SOURCE_WINDOW = ROOT / "plugins" / "robot_windows" / "blockly_v2"
SOURCE_HTML = SOURCE_WINDOW / "blockly_v2.html"
SOURCE_WORLD = ROOT / "worlds" / "crazyflie_runtime_v2.wbt"
MAX_HTTP_BODY = 1024 * 1024
HOST_BOOTSTRAP_KEYS = {
    "baseUrl",
    "token",
    "preflightResponderToken",
    "executionAuthority",
}
TEACHER_PROPOSAL_KEYS = {
    "op",
    "requestId",
    "challengeId",
    "profileId",
    "astBinding",
    "connectionEpoch",
    "executionAuthority",
}


class QualificationLaunchError(RuntimeError):
    """Fail-closed physical qualification launcher error."""


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise QualificationLaunchError(f"{name} must be a non-empty trimmed string")
    return value


def validate_host_bootstrap(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != HOST_BOOTSTRAP_KEYS:
        raise QualificationLaunchError("physical-host browser bootstrap has unsupported fields")
    if value.get("executionAuthority") is not False:
        raise QualificationLaunchError("physical-host browser bootstrap must remain non-authority")
    base_url = _text(value.get("baseUrl"), "baseUrl")
    if not (base_url.startswith("http://127.0.0.1:") or base_url.startswith("http://localhost:")):
        raise QualificationLaunchError("physical-host browser bootstrap must remain loopback-only")
    _text(value.get("token"), "token")
    _text(value.get("preflightResponderToken"), "preflightResponderToken")
    return dict(value)


def _json_line(sock: socket.socket, payload: dict[str, object]) -> None:
    encoded = (json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
    sock.sendall(encoded)


def _read_json_line(reader) -> dict[str, object]:
    line = reader.readline()
    if not line:
        raise QualificationLaunchError("trusted physical host closed its caller channel")
    try:
        value = json.loads(line)
    except json.JSONDecodeError as exc:
        raise QualificationLaunchError("trusted physical host returned malformed JSON") from exc
    if not isinstance(value, dict):
        raise QualificationLaunchError("trusted physical host reply must be an object")
    return value


class TrustedCaller:
    """Serialized ordinary caller IPC; it owns no teacher/effect semantics."""

    def __init__(self, sock: socket.socket) -> None:
        if not isinstance(sock, socket.socket):
            raise QualificationLaunchError("caller channel must be a socket")
        self._socket = sock
        self._reader = sock.makefile("r", encoding="utf-8", newline="\n")
        self._lock = Lock()
        self._counter = 0

    def _request(self, operation: str, extra: dict[str, object] | None = None) -> dict[str, object]:
        with self._lock:
            self._counter += 1
            request_id = f"qualification-{self._counter}"
            payload: dict[str, object] = {"op": operation, "requestId": request_id}
            if extra:
                payload.update(extra)
            _json_line(self._socket, payload)
            reply = _read_json_line(self._reader)
        if reply.get("requestId") != request_id or reply.get("executionAuthority") is not False:
            raise QualificationLaunchError("trusted physical host caller reply lost correlation/non-authority")
        return reply

    def validate_run(self, *, profile_id: str, ast_binding: str, connection_epoch: str) -> None:
        reply = self._request(
            "validate-run-context",
            {
                "profileId": _text(profile_id, "profileId"),
                "astBinding": _text(ast_binding, "astBinding"),
                "connectionEpoch": _text(connection_epoch, "connectionEpoch"),
            },
        )
        if reply.get("ok") is not True:
            raise QualificationLaunchError("trusted physical host rejected current-program validation")

    def execute_next(self) -> None:
        # Deliberately no caller-selected direction/distance/height/index/branch.
        reply = self._request("execute-next-inflight")
        if reply.get("ok") is not True:
            raise QualificationLaunchError("trusted physical host rejected exact parameter-free execution")

    def close(self) -> None:
        try:
            self._socket.shutdown(socket.SHUT_WR)
        except OSError:
            pass
        try:
            self._reader.close()
        finally:
            self._socket.close()


def execution_request_count(ast_binding: str) -> int:
    """Return caller turns without deriving any physical effect parameter.

    Flat programs use the already-integrated PhysicalProgramSequence validator;
    takeoff is consumed by activation, so every remaining exact top-level
    statement gets one parameter-free caller turn. Programs outside that flat
    representation are owned by the integrated shared interpreter and therefore
    execute in one parameter-free turn.
    """
    if str(PHYSICAL) not in sys.path:
        sys.path.insert(0, str(PHYSICAL))
    from physical_program_sequence import PhysicalProgramSequence, PhysicalProgramSequenceError

    binding = _text(ast_binding, "astBinding")
    try:
        PhysicalProgramSequence(binding)
    except PhysicalProgramSequenceError:
        return 1
    try:
        document = json.loads(binding)
        program = document["program"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise QualificationLaunchError("validated static AST binding is malformed") from exc
    if not isinstance(program, list) or len(program) < 2:
        raise QualificationLaunchError("validated static AST has no post-takeoff program")
    return len(program) - 1


def execute_bound_run(
    caller: TrustedCaller,
    *,
    profile_id: str,
    ast_binding: str,
    connection_epoch: str,
) -> None:
    caller.validate_run(
        profile_id=profile_id,
        ast_binding=ast_binding,
        connection_epoch=connection_epoch,
    )
    for _ in range(execution_request_count(ast_binding)):
        caller.execute_next()


def _teacher_prompt(proposal: dict[str, object]) -> bool:
    digest = hashlib.sha256(str(proposal["astBinding"]).encode("utf-8")).hexdigest()
    short = digest[:12]
    print("\nAutorisation physique WebeeBlocks requise", flush=True)
    print(f"  profil : {proposal['profileId']}", flush=True)
    print(f"  AST SHA-256 : {digest}", flush=True)
    print(f"  epoch : {proposal['connectionEpoch']}", flush=True)
    answer = input(f"Tapez exactement APPROUVER {short} pour autoriser ce run : ").strip()
    return answer == f"APPROUVER {short}"


def serve_teacher_decision(
    sock: socket.socket,
    decide: Callable[[dict[str, object]], bool] = _teacher_prompt,
) -> None:
    reader = sock.makefile("r", encoding="utf-8", newline="\n")
    try:
        proposal = _read_json_line(reader)
        if set(proposal) != TEACHER_PROPOSAL_KEYS:
            raise QualificationLaunchError("teacher proposal has unsupported fields")
        if proposal.get("op") != "teacher-run-binding-proposal":
            raise QualificationLaunchError("teacher proposal has wrong operation")
        if proposal.get("executionAuthority") is not False:
            raise QualificationLaunchError("teacher proposal must remain non-authority data")
        for name in ("requestId", "challengeId", "profileId", "astBinding", "connectionEpoch"):
            _text(proposal.get(name), name)
        approved = bool(decide(proposal))
        reply = {
            "op": "teacher-run-decision-result",
            "requestId": proposal["requestId"],
            "challengeId": proposal["challengeId"],
            "profileId": proposal["profileId"],
            "astBinding": proposal["astBinding"],
            "connectionEpoch": proposal["connectionEpoch"],
            "approved": approved,
            "executionAuthority": False,
        }
        _json_line(sock, reply)
        sock.shutdown(socket.SHUT_WR)
    finally:
        reader.close()
        sock.close()


class _RunService:
    def __init__(self, caller: TrustedCaller) -> None:
        self.caller = caller
        self.token = secrets.token_urlsafe(32)
        self._lock = Lock()
        self._used = False

    def run(self, payload: object) -> None:
        if not isinstance(payload, dict) or set(payload) != {
            "profileId", "astBinding", "connectionEpoch", "executionAuthority"
        }:
            raise QualificationLaunchError("browser run context has unsupported fields")
        if payload.get("executionAuthority") is not False:
            raise QualificationLaunchError("browser run context must remain non-authority")
        with self._lock:
            if self._used:
                raise QualificationLaunchError("physical qualification launcher is one-shot")
            self._used = True
        execute_bound_run(
            self.caller,
            profile_id=_text(payload.get("profileId"), "profileId"),
            ast_binding=_text(payload.get("astBinding"), "astBinding"),
            connection_epoch=_text(payload.get("connectionEpoch"), "connectionEpoch"),
        )


def _handler_type(service: _RunService):
    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "WebeeBlocksPhysicalQualification/1"

        def log_message(self, _format, *_args):
            return

        def _cors(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Cache-Control", "no-store")

        def _json(self, status: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
            self.send_response(status)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:  # noqa: N802
            if self.path != "/v1/run":
                self._json(404, {"error": "not found", "executionAuthority": False})
                return
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/v1/run":
                self._json(404, {"error": "not found", "executionAuthority": False})
                return
            if self.headers.get("Authorization") != "Bearer " + service.token:
                self._json(401, {"error": "unauthorized", "executionAuthority": False})
                return
            try:
                length = int(self.headers.get("Content-Length", "-1"))
            except ValueError:
                length = -1
            if length < 0 or length > MAX_HTTP_BODY:
                self._json(413, {"error": "invalid request size", "executionAuthority": False})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                service.run(payload)
            except (UnicodeError, json.JSONDecodeError, QualificationLaunchError) as exc:
                self._json(409, {"error": str(exc), "executionAuthority": False})
                return
            except Exception:
                self._json(409, {"error": "physical qualification failed closed", "executionAuthority": False})
                return
            self._json(200, {"ok": True, "executionAuthority": False})

    return Handler


def _browser_runtime_script(
    host_bootstrap: dict[str, object],
    caller_base_url: str,
    caller_token: str,
) -> str:
    config = {
        "host": validate_host_bootstrap(host_bootstrap),
        "callerBaseUrl": _text(caller_base_url, "callerBaseUrl"),
        "callerToken": _text(caller_token, "callerToken"),
    }
    encoded = json.dumps(config, separators=(",", ":"), sort_keys=True).replace("</", "<\\/")
    return """
<script>
(function() {
  'use strict';
  var config = %s;
  var running = false;
  function disableSimulationOnlyControls() {
    var debug = document.getElementById('debugPanel');
    if (debug) debug.hidden = true;
    ['stepMode', 'stepNext', 'stepContinue', 'resetSimulation'].forEach(function(id) {
      var node = document.getElementById(id);
      if (node) { node.disabled = true; if (id === 'resetSimulation') node.hidden = true; }
    });
  }
  window.addEventListener('load', function() {
    if (!window.WebeeBlocksPhysicalPreflight ||
        typeof window.WebeeBlocksPhysicalPreflight.configure !== 'function' ||
        typeof window.WebeeBlocksPhysicalPreflight.preflightCurrentProgram !== 'function') {
      setRuntimeFailure(new Error('Prévol physique indisponible'));
      return;
    }
    try {
      window.WebeeBlocksPhysicalPreflight.configure(config.host);
    } catch (error) {
      setRuntimeFailure(error);
      return;
    }
    document.body.dataset.physicalQualificationMode = 'true';
    disableSimulationOnlyControls();
    var submit = document.getElementById('submit');
    submit.textContent = 'Lancer le vol réel';
    submit.setAttribute('aria-label', 'Lancer le vol réel');
    submit.onclick = async function() {
      if (running) return;
      running = true;
      submit.disabled = true;
      disableSimulationOnlyControls();
      try {
        setRuntimeStatus('VÉRIFICATION', 'Prévol physique du programme exact');
        var preflight = await window.WebeeBlocksPhysicalPreflight.preflightCurrentProgram();
        setRuntimeStatus('AUTORISATION', 'Validation enseignant requise');
        var response = await fetch(config.callerBaseUrl + '/v1/run', {
          method: 'POST',
          headers: {
            'Authorization': 'Bearer ' + config.callerToken,
            'Content-Type': 'application/json'
          },
          cache: 'no-store',
          body: JSON.stringify({
            profileId: runtimeProfile.id,
            astBinding: preflight.astBinding,
            connectionEpoch: preflight.connectionEpoch,
            executionAuthority: false
          })
        });
        var payload = await response.json();
        if (!response.ok || !payload || payload.ok !== true || payload.executionAuthority !== false)
          throw new Error(payload && payload.error ? payload.error : 'Exécution physique refusée');
        runtimeTerminal = true;
        setRuntimeStatus('TERMINÉ', 'Programme physique exécuté');
      } catch (error) {
        runtimeTerminal = true;
        setRuntimeFailure(error);
      } finally {
        running = false;
        disableSimulationOnlyControls();
        updateRuntimeActions();
      }
    };
  });
})();
</script>
""" % encoded


def prepare_overlay(
    host_bootstrap: dict[str, object],
    caller_base_url: str,
    caller_token: str,
) -> tuple[Path, Path]:
    """Create one temporary actual Robot Window + world inside the Webots project."""
    if not SOURCE_HTML.is_file() or not SOURCE_WORLD.is_file():
        raise QualificationLaunchError("WebeeBlocks Runtime v2 source project is incomplete")
    suffix = secrets.token_hex(8)
    window_name = "blockly_v2_physical_" + suffix
    destination = SOURCE_WINDOW.parent / window_name
    world = SOURCE_WORLD.parent / ("." + window_name + ".wbt")
    if destination.exists() or world.exists():
        raise QualificationLaunchError("temporary physical qualification overlay already exists")
    shutil.copytree(SOURCE_WINDOW, destination)
    try:
        html = SOURCE_HTML.read_text(encoding="utf-8")
        marker = "</body>"
        if html.count(marker) != 1:
            raise QualificationLaunchError("Runtime v2 Robot Window HTML has unexpected structure")
        html = html.replace(
            marker,
            _browser_runtime_script(host_bootstrap, caller_base_url, caller_token) + marker,
        )
        (destination / (window_name + ".html")).write_text(html, encoding="utf-8")
        world_text = SOURCE_WORLD.read_text(encoding="utf-8")
        needle = 'window "blockly_v2"'
        if world_text.count(needle) != 1:
            raise QualificationLaunchError("Runtime v2 world has unexpected Robot Window binding")
        world.write_text(world_text.replace(needle, f'window "{window_name}"'), encoding="utf-8")
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        try:
            world.unlink()
        except FileNotFoundError:
            pass
        raise
    return destination, world


def cleanup_overlay(window_directory: Path | None, world: Path | None) -> None:
    if window_directory is not None:
        shutil.rmtree(window_directory, ignore_errors=True)
    if world is not None:
        try:
            world.unlink()
        except FileNotFoundError:
            pass


def _find_webots(explicit: str | None) -> str:
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    home = os.environ.get("WEBOTS_HOME")
    if home:
        candidates.extend([str(Path(home) / "webots"), str(Path(home) / "bin" / "webots")])
    discovered = shutil.which("webots")
    if discovered:
        candidates.append(discovered)
    for candidate in candidates:
        path = Path(candidate)
        if not path.is_file():
            continue
        result = subprocess.run([str(path), "--version"], text=True, capture_output=True)
        if result.returncode == 0 and "R2025a" in (result.stdout + result.stderr):
            return str(path)
    raise QualificationLaunchError("Webots R2025a executable is required")


def _read_host_bootstrap(fd: int, process: subprocess.Popen, timeout_seconds: float = 20.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    chunks = bytearray()
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise QualificationLaunchError("physical host exited before browser bootstrap")
        readable, _, _ = select.select([fd], [], [], 0.1)
        if not readable:
            continue
        chunk = os.read(fd, 4096)
        if not chunk:
            raise QualificationLaunchError("physical host closed browser bootstrap channel")
        chunks.extend(chunk)
        if len(chunks) > 65536:
            raise QualificationLaunchError("physical host browser bootstrap is oversized")
        if b"\n" in chunks:
            line, remainder = bytes(chunks).split(b"\n", 1)
            if remainder:
                raise QualificationLaunchError("physical host browser bootstrap emitted extra data")
            try:
                return validate_host_bootstrap(json.loads(line.decode("utf-8")))
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise QualificationLaunchError("physical host browser bootstrap is malformed") from exc
    raise QualificationLaunchError("timed out waiting for physical host browser bootstrap")


def launch(*, uri: str, webots_executable: str | None = None) -> int:
    if os.name != "posix":
        raise QualificationLaunchError("physical qualification launcher currently requires POSIX inherited descriptors")
    _text(uri, "uri")
    if not uri.startswith("radio://"):
        raise QualificationLaunchError("explicit radio:// URI is required")
    webots = _find_webots(webots_executable)

    caller_host, caller_peer = socket.socketpair()
    teacher_host, teacher_peer = socket.socketpair()
    browser_read, browser_write = os.pipe()
    descriptors = {caller_host.fileno(), teacher_host.fileno(), browser_write}
    if len(descriptors) != 3 or min(descriptors) < 3:
        raise QualificationLaunchError("physical host channels must be three distinct non-stdio descriptors")

    host_process: subprocess.Popen | None = None
    webots_process: subprocess.Popen | None = None
    server: http.server.ThreadingHTTPServer | None = None
    caller: TrustedCaller | None = None
    window_directory: Path | None = None
    world: Path | None = None
    teacher_thread: Thread | None = None
    try:
        host_process = subprocess.Popen(
            [
                sys.executable,
                str(HOST),
                "--uri", uri,
                "--caller-fd", str(caller_host.fileno()),
                "--browser-config-fd", str(browser_write),
                "--teacher-fd", str(teacher_host.fileno()),
            ],
            cwd=ROOT,
            pass_fds=tuple(descriptors),
            close_fds=True,
        )
        caller_host.close()
        teacher_host.close()
        os.close(browser_write)
        host_bootstrap = _read_host_bootstrap(browser_read, host_process)
        os.close(browser_read)
        browser_read = -1

        caller = TrustedCaller(caller_peer)
        service = _RunService(caller)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _handler_type(service))
        server_thread = Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        caller_base_url = f"http://127.0.0.1:{server.server_address[1]}"

        teacher_thread = Thread(target=serve_teacher_decision, args=(teacher_peer,), daemon=True)
        teacher_thread.start()

        window_directory, world = prepare_overlay(
            host_bootstrap,
            caller_base_url,
            service.token,
        )
        webots_process = subprocess.Popen(
            [webots, "--mode=realtime", str(world)],
            cwd=ROOT,
            close_fds=True,
        )
        return webots_process.wait()
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if caller is not None:
            caller.close()
        else:
            try:
                caller_peer.close()
            except OSError:
                pass
        try:
            teacher_peer.close()
        except OSError:
            pass
        if browser_read >= 0:
            try:
                os.close(browser_read)
            except OSError:
                pass
        for descriptor in (browser_write,):
            try:
                os.close(descriptor)
            except OSError:
                pass
        if webots_process is not None and webots_process.poll() is None:
            webots_process.terminate()
        if host_process is not None:
            try:
                host_process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                host_process.terminate()
                host_process.wait(timeout=5.0)
        if teacher_thread is not None:
            teacher_thread.join(timeout=1.0)
        cleanup_overlay(window_directory, world)


def main() -> int:
    parser = argparse.ArgumentParser(description="WebeeBlocks trusted physical qualification launcher")
    parser.add_argument("--uri", required=True, help="explicit radio:// Crazyradio URI")
    parser.add_argument("--webots", help="explicit Webots R2025a executable")
    args = parser.parse_args()
    try:
        return launch(uri=args.uri, webots_executable=args.webots)
    except QualificationLaunchError as exc:
        print("WEBEEBLOCKS_PHYSICAL_QUALIFICATION_FAIL " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

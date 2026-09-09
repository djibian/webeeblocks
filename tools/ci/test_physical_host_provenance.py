#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import json
import multiprocessing
from pathlib import Path
import socket
import sys
from threading import Thread
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(PHYSICAL))

import serve_reference_capabilities as bridge_module  # noqa: E402

HOST = PHYSICAL / "serve_physical_host.py"
REMOVED_CLIENT = PHYSICAL / "current_program_provenance.py"
REMOVED_BROKER = PHYSICAL / "serve_current_program_provenance.py"

PROFILE = "activity-1"
AST_BINDING = "ast-1"
EPOCH = "epoch-1"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class FakeEpochSession:
    def __init__(self, epoch: str) -> None:
        self.epoch = epoch

    def read_connection_epoch(self) -> str:
        return self.epoch


def _http_json(
    url: str,
    token: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
) -> tuple[int, dict]:
    body = None
    headers = {
        "Authorization": "Bearer " + token,
        "Cache-Control": "no-store",
    }
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=2.0) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _authority_fixture(
    caller_socket: socket.socket,
    browser_config_send,
    epoch: str,
) -> None:
    bridge = bridge_module.ReadOnlyCapabilityHttpBridge(
        FakeEpochSession(epoch),
        token="authority-capability-token",
        preflight_responder_token="authority-browser-responder-token",
    )
    thread = Thread(target=bridge.serve_forever, daemon=True)
    thread.start()
    host, port = bridge.address
    browser_config_send.send(
        {
            "baseUrl": f"http://{host}:{port}",
            "token": bridge.token,
            "preflightResponderToken": bridge.preflight_responder_token,
            "executionAuthority": False,
        }
    )
    browser_config_send.close()

    reader = caller_socket.makefile("r", encoding="utf-8")
    writer = caller_socket.makefile("w", encoding="utf-8")
    try:
        for line in reader:
            request = json.loads(line)
            request_id = request["requestId"]
            try:
                if request.get("op") != "validate-run-context":
                    raise bridge_module.CapabilityBridgeError("unsupported caller operation")
                evidence = bridge.assert_current_program(
                    profile_id=request["profileId"],
                    ast_binding=request["astBinding"],
                    connection_epoch=request["connectionEpoch"],
                    timeout_seconds=0.35,
                )
            except bridge_module.CapabilityBridgeError as exc:
                response = {
                    "requestId": request_id,
                    "ok": False,
                    "error": str(exc),
                    "executionAuthority": False,
                }
            else:
                require(
                    evidence.execution_authority is False,
                    "fixture #278 evidence remains non-authority",
                )
                response = {
                    "requestId": request_id,
                    "ok": True,
                    "executionAuthority": False,
                }
            writer.write(json.dumps(response, separators=(",", ":")) + "\n")
            writer.flush()
    finally:
        bridge.shutdown()
        thread.join(timeout=1.0)
        reader.close()
        writer.close()
        caller_socket.close()


def _browser_responder(
    config_recv,
    profile_id: str,
    ast_binding: str,
    epoch: str,
    result_send,
) -> None:
    config = config_recv.recv()
    config_recv.close()
    require(config["executionAuthority"] is False, "browser bootstrap is non-authority")
    token = config["preflightResponderToken"]
    base = config["baseUrl"]
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        status, challenge = _http_json(
            base + "/v1/preflight-challenge",
            token,
        )
        if status != 200:
            result_send.send({"ok": False, "error": challenge.get("error")})
            result_send.close()
            return
        challenge_id = challenge.get("challengeId")
        if challenge_id is None:
            continue
        status, response = _http_json(
            base + "/v1/preflight-assertion",
            token,
            method="POST",
            payload={
                "challengeId": challenge_id,
                "ok": True,
                "profileId": profile_id,
                "astBinding": ast_binding,
                "connectionEpoch": epoch,
                "executionAuthority": False,
            },
        )
        result_send.send({"ok": status == 200, "response": response})
        result_send.close()
        return
    result_send.send({"ok": False, "error": "browser responder timed out"})
    result_send.close()


def _self_answer_public_bridge() -> bool:
    bridge = bridge_module.ReadOnlyCapabilityHttpBridge(
        FakeEpochSession(EPOCH),
        token="caller-local-token",
        preflight_responder_token="caller-local-responder",
    )
    failures: list[str] = []

    def answer() -> None:
        try:
            challenge = bridge._claim_current_program_challenge(timeout_seconds=0.3)
            if challenge is None:
                raise AssertionError("caller-local challenge missing")
            bridge._submit_current_program_assertion(
                {
                    "challengeId": challenge,
                    "ok": True,
                    "profileId": PROFILE,
                    "astBinding": AST_BINDING,
                    "connectionEpoch": EPOCH,
                    "executionAuthority": False,
                }
            )
        except BaseException as exc:
            failures.append(repr(exc))

    thread = Thread(target=answer, daemon=True)
    thread.start()
    evidence = bridge.assert_current_program(
        profile_id=PROFILE,
        ast_binding=AST_BINDING,
        connection_epoch=EPOCH,
        timeout_seconds=0.3,
    )
    thread.join(timeout=1.0)
    bridge._server.server_close()
    return (
        not failures
        and type(evidence) is bridge_module.CurrentProgramPreflightEvidence
        and evidence.execution_authority is False
    )


def _caller_worker(
    caller_socket: socket.socket,
    request_ast: str,
    result_send,
) -> None:
    # Strongest historical same-process attack remains possible locally: the
    # ordinary caller can manufacture ordinary #278 evidence.  It is irrelevant
    # to the trusted physical host because no caller-side evidence/client is an
    # input to that host's future effect composition.
    local_forgery = _self_answer_public_bridge()

    # Also manufacture a completely caller-controlled local IPC peer.  This can
    # produce arbitrary JSON, but no production code consumes it as effect
    # authority because #276 will live inside the separate physical host.
    fake_client, fake_server = socket.socketpair()
    fake_server.sendall(
        b'{"requestId":"fake","ok":true,"executionAuthority":false}\n'
    )
    local_fake_reply = fake_client.recv(256)
    fake_client.close()
    fake_server.close()

    request = {
        "op": "validate-run-context",
        "requestId": "installed-channel-request",
        "profileId": PROFILE,
        "astBinding": request_ast,
        "connectionEpoch": EPOCH,
    }
    caller_socket.sendall(
        (json.dumps(request, separators=(",", ":")) + "\n").encode("utf-8")
    )
    reader = caller_socket.makefile("r", encoding="utf-8")
    line = reader.readline()
    reply = json.loads(line) if line else None
    reader.close()
    caller_socket.close()
    result_send.send(
        {
            "localForgery": local_forgery,
            "localFakeReply": local_fake_reply.decode("utf-8").strip(),
            "authorityReply": reply,
        }
    )
    result_send.close()


def _run_separated_case(*, browser: bool, request_ast: str) -> dict:
    ctx = multiprocessing.get_context("spawn")
    caller_parent, caller_child = socket.socketpair()
    browser_recv, browser_send = ctx.Pipe(duplex=False)
    caller_result_recv, caller_result_send = ctx.Pipe(duplex=False)

    authority = ctx.Process(
        target=_authority_fixture,
        args=(caller_parent, browser_send, EPOCH),
    )
    authority.start()
    caller_parent.close()
    browser_send.close()

    browser_process = None
    browser_result_recv = None
    if browser:
        browser_result_recv, browser_result_send = ctx.Pipe(duplex=False)
        browser_process = ctx.Process(
            target=_browser_responder,
            args=(
                browser_recv,
                PROFILE,
                AST_BINDING,
                EPOCH,
                browser_result_send,
            ),
        )
        browser_process.start()
        browser_recv.close()
        browser_result_send.close()
    else:
        # No process receives the bootstrap secret.  Closing the receiver models
        # responder loss; the authority-side #278 challenge must time out.
        browser_recv.close()

    caller = ctx.Process(
        target=_caller_worker,
        args=(caller_child, request_ast, caller_result_send),
    )
    caller.start()
    caller_child.close()
    caller_result_send.close()

    result = caller_result_recv.recv()
    caller_result_recv.close()
    caller.join(timeout=5.0)
    require(caller.exitcode == 0, "ordinary caller process must exit cleanly")

    if browser_process is not None:
        browser_result = browser_result_recv.recv()
        browser_result_recv.close()
        browser_process.join(timeout=5.0)
        require(browser_process.exitcode == 0, "browser responder process exits cleanly")
        require(browser_result["ok"], "production-shaped #249 browser responder succeeds")

    # Closing the installed caller capability terminates the authority fixture.
    authority.join(timeout=5.0)
    if authority.is_alive():
        authority.terminate()
        authority.join(timeout=2.0)
        raise AssertionError("authority process did not terminate after caller EOF")
    require(authority.exitcode == 0, "authority process exits cleanly")
    return result


def test_separate_host_accepts_only_its_browser_responder() -> None:
    result = _run_separated_case(browser=True, request_ast=AST_BINDING)
    require(result["localForgery"], "caller reproduces ordinary #278 self-answer attack")
    require('"ok":true' in result["localFakeReply"], "caller can forge local IPC data")
    reply = result["authorityReply"]
    require(reply["ok"] is True, "trusted host exact current-program request succeeds")
    require(
        reply["executionAuthority"] is False,
        "caller-visible result remains explicitly non-authority",
    )


def test_local_forgery_cannot_replace_missing_browser_responder() -> None:
    result = _run_separated_case(browser=False, request_ast=AST_BINDING)
    require(result["localForgery"], "strong local bridge forgery is reproduced")
    require(
        result["authorityReply"]["ok"] is False,
        "local bridge/socket forgery cannot settle trusted host challenge",
    )


def test_binding_mismatch_fails_closed_across_process_boundary() -> None:
    result = _run_separated_case(browser=True, request_ast="different-ast")
    require(
        result["authorityReply"]["ok"] is False,
        "actual browser AST mismatch must fail closed",
    )


def test_production_host_is_executable_only_and_keeps_provenance_internal() -> None:
    source = HOST.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            raise AssertionError(
                "physical-host authority must export no importable callable/class"
            )

    spec = importlib.util.spec_from_file_location("physical_host_import_probe", HOST)
    require(spec is not None and spec.loader is not None, "physical host import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for forbidden_attr in (
        "ReadOnlyCapabilitySession",
        "ReadOnlyCapabilityHttpBridge",
        "bridge",
        "session",
        "preflight_responder_token",
        "CurrentProgramProvenanceClient",
    ):
        require(
            not hasattr(module, forbidden_attr),
            "imported host leaks authority state/API: " + forbidden_attr,
        )

    for required in (
        "ReadOnlyCapabilitySession",
        "ReadOnlyCapabilityHttpBridge",
        "bridge.assert_current_program(",
        "--caller-fd",
        "--browser-config-fd",
        "preflightResponderToken",
        "Future #276 composition must consume it here immediately",
        "validate-run-context",
    ):
        require(required in source, "missing physical-host composition contract: " + required)

    for forbidden in (
        "CurrentProgramProvenanceClient",
        "CurrentProgramAuthorityEvidence",
        "_bind_effect_current_program_bridge",
        "send_packet(",
        "HighLevelCommander(",
        "takeoff",
        "land(",
    ):
        require(forbidden not in source, "physical-host prerequisite leaks old/effect API: " + forbidden)

    require(
        not REMOVED_CLIENT.exists(),
        "caller-selectable provenance client must be removed",
    )
    require(
        not REMOVED_BROKER.exists(),
        "preflight-only broker must be removed in favor of physical-host root",
    )


def main() -> int:
    test_separate_host_accepts_only_its_browser_responder()
    test_local_forgery_cannot_replace_missing_browser_responder()
    test_binding_mismatch_fails_closed_across_process_boundary()
    test_production_host_is_executable_only_and_keeps_provenance_internal()
    print(
        "PASS physical-host process owns #278 provenance; ordinary caller can "
        "forge local bridge/socket data but cannot replace the host browser responder"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import json
import multiprocessing
from pathlib import Path
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
    request_recv,
    response_send,
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

    try:
        while True:
            try:
                request = request_recv.recv()
            except EOFError:
                break
            request_id = request.get("requestId") if isinstance(request, dict) else None
            try:
                if not isinstance(request, dict):
                    raise bridge_module.CapabilityBridgeError("malformed effect request")
                if request.get("op") != "assert-current-program":
                    raise bridge_module.CapabilityBridgeError("unsupported effect request")
                evidence = bridge.assert_current_program(
                    profile_id=request["profileId"],
                    ast_binding=request["astBinding"],
                    connection_epoch=request["connectionEpoch"],
                    timeout_seconds=0.35,
                )
            except (KeyError, bridge_module.CapabilityBridgeError) as exc:
                response_send.send(
                    {
                        "requestId": request_id,
                        "ok": False,
                        "error": str(exc),
                        "executionAuthority": False,
                    }
                )
            else:
                response_send.send(
                    {
                        "requestId": request_id,
                        "ok": True,
                        "profileId": evidence.profile_id,
                        "astBinding": evidence.ast_binding,
                        "connectionEpoch": evidence.connection_epoch,
                        "challengeId": evidence.challenge_id,
                        "executionAuthority": False,
                    }
                )
    finally:
        bridge.shutdown()
        thread.join(timeout=1.0)
        request_recv.close()
        response_send.close()


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
        status, challenge = _http_json(base + "/v1/preflight-challenge", token)
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


def _effect_request(request_send, response_recv, request_ast: str, timeout: float = 1.0) -> dict:
    request_id = "installed-channel-request"
    request_send.send(
        {
            "op": "assert-current-program",
            "requestId": request_id,
            "profileId": PROFILE,
            "astBinding": request_ast,
            "connectionEpoch": EPOCH,
        }
    )
    if not response_recv.poll(timeout):
        raise RuntimeError("authority response timeout")
    try:
        response = response_recv.recv()
    except EOFError as exc:
        raise RuntimeError("authority response EOF") from exc
    if not isinstance(response, dict):
        raise RuntimeError("malformed authority response")
    if response.get("requestId") != request_id:
        raise RuntimeError("authority response correlation mismatch")
    if response_recv.poll(0):
        raise RuntimeError("duplicate authority response")
    if response.get("executionAuthority") is not False:
        raise RuntimeError("authority response must remain non-authority")
    if response.get("ok") is True:
        expected = {
            "profileId": PROFILE,
            "astBinding": request_ast,
            "connectionEpoch": EPOCH,
        }
        for key, value in expected.items():
            if response.get(key) != value:
                raise RuntimeError("authority response binding mismatch")
        if not isinstance(response.get("challengeId"), str) or not response["challengeId"]:
            raise RuntimeError("authority response missing challenge provenance")
    return response


def _effect_worker(request_send, response_recv, request_ast: str, result_send) -> None:
    # Reproduce the strongest historical attacks inside the actual effect-side
    # process.  It can manufacture public #278 evidence and arbitrary local data,
    # but it owns no send capability for the trusted response pipe.
    local_forgery = _self_answer_public_bridge()
    fake_recv, fake_send = multiprocessing.get_context("spawn").Pipe(duplex=False)
    fake_send.send({"requestId": "fake", "ok": True, "executionAuthority": False})
    local_fake_reply = fake_recv.recv()
    fake_recv.close()
    fake_send.close()
    try:
        authority_reply = _effect_request(request_send, response_recv, request_ast)
        error = None
    except RuntimeError as exc:
        authority_reply = None
        error = str(exc)
    request_send.close()
    response_recv.close()
    result_send.send(
        {
            "localForgery": local_forgery,
            "localFakeReply": local_fake_reply,
            "authorityReply": authority_reply,
            "error": error,
        }
    )
    result_send.close()


def _run_separated_case(*, browser: bool, request_ast: str) -> dict:
    ctx = multiprocessing.get_context("spawn")
    request_recv, request_send = ctx.Pipe(duplex=False)
    response_recv, response_send = ctx.Pipe(duplex=False)
    browser_recv, browser_send = ctx.Pipe(duplex=False)
    result_recv, result_send = ctx.Pipe(duplex=False)

    authority = ctx.Process(
        target=_authority_fixture,
        args=(request_recv, response_send, browser_send, EPOCH),
    )
    authority.start()
    request_recv.close()
    response_send.close()
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
        discarded = browser_recv.recv()
        require(discarded["executionAuthority"] is False, "bootstrap remains non-authority")
        browser_recv.close()

    effect = ctx.Process(
        target=_effect_worker,
        args=(request_send, response_recv, request_ast, result_send),
    )
    effect.start()
    request_send.close()
    response_recv.close()
    result_send.close()

    result = result_recv.recv()
    result_recv.close()
    effect.join(timeout=5.0)
    require(effect.exitcode == 0, "effect worker exits cleanly")

    if browser_process is not None:
        browser_result = browser_result_recv.recv()
        browser_result_recv.close()
        browser_process.join(timeout=5.0)
        require(browser_process.exitcode == 0, "browser responder exits cleanly")
        if request_ast == AST_BINDING:
            require(browser_result["ok"], "production #249 responder succeeds")
        else:
            require(not browser_result["ok"], "browser AST mismatch is rejected")

    authority.join(timeout=5.0)
    if authority.is_alive():
        authority.terminate()
        authority.join(timeout=2.0)
        raise AssertionError("authority did not terminate after request EOF")
    require(authority.exitcode == 0, "authority process exits cleanly")
    return result


def test_effect_worker_cannot_forge_trusted_response() -> None:
    result = _run_separated_case(browser=True, request_ast=AST_BINDING)
    require(result["localForgery"], "effect process reproduces public #278 self-answer")
    require(result["localFakeReply"]["ok"] is True, "effect process can forge local IPC")
    require(result["error"] is None, "trusted authority request succeeds")
    reply = result["authorityReply"]
    require(reply["ok"] is True, "exact current-program request succeeds")
    require(reply["profileId"] == PROFILE, "exact profile is returned")
    require(reply["astBinding"] == AST_BINDING, "exact AST binding is returned")
    require(reply["connectionEpoch"] == EPOCH, "exact epoch is returned")


def test_local_forgery_cannot_replace_missing_browser_responder() -> None:
    result = _run_separated_case(browser=False, request_ast=AST_BINDING)
    require(result["localForgery"], "strong local bridge forgery is reproduced")
    require(result["error"] is None, "authority returned a correlated fail-closed result")
    require(result["authorityReply"]["ok"] is False, "missing browser fails closed")


def test_binding_mismatch_fails_closed_across_process_boundary() -> None:
    result = _run_separated_case(browser=True, request_ast="different-ast")
    require(result["error"] is None, "mismatch is a correlated negative result")
    require(result["authorityReply"]["ok"] is False, "browser AST mismatch fails closed")


def _protocol_worker(response_payloads: list[object], close_without_reply: bool = False) -> str:
    ctx = multiprocessing.get_context("spawn")
    request_recv, request_send = ctx.Pipe(duplex=False)
    response_recv, response_send = ctx.Pipe(duplex=False)

    def responder() -> None:
        try:
            request = request_recv.recv()
            if close_without_reply:
                return
            for payload in response_payloads:
                if payload == "MATCH":
                    payload = {
                        "requestId": request["requestId"],
                        "ok": True,
                        "profileId": request["profileId"],
                        "astBinding": request["astBinding"],
                        "connectionEpoch": request["connectionEpoch"],
                        "challengeId": "challenge",
                        "executionAuthority": False,
                    }
                response_send.send(payload)
        finally:
            request_recv.close()
            response_send.close()

    thread = Thread(target=responder, daemon=True)
    thread.start()
    try:
        _effect_request(request_send, response_recv, AST_BINDING, timeout=0.1)
    except RuntimeError as exc:
        outcome = str(exc)
    else:
        outcome = "accepted"
    request_send.close()
    response_recv.close()
    thread.join(timeout=1.0)
    return outcome


def test_effect_requester_fails_closed_on_channel_ambiguity() -> None:
    require("malformed" in _protocol_worker(["not-a-dict"]), "malformed response rejected")
    require(
        "correlation mismatch" in _protocol_worker([{"requestId": "wrong", "ok": False, "executionAuthority": False}]),
        "wrong correlation rejected",
    )
    require("duplicate" in _protocol_worker(["MATCH", "MATCH"]), "duplicate response rejected")
    require("EOF" in _protocol_worker([], close_without_reply=True), "authority EOF rejected")
    require("timeout" in _protocol_worker([]), "missing/late authority response rejected")


def test_production_host_is_executable_only_and_preserves_one_way_split() -> None:
    source = HOST.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            raise AssertionError("physical authority host must export no callable/class")

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
        require(not hasattr(module, forbidden_attr), "imported host leaks authority: " + forbidden_attr)

    for required in (
        "ReadOnlyCapabilitySession",
        "ReadOnlyCapabilityHttpBridge",
        "bridge.assert_current_program(",
        "--request-fd",
        "--response-fd",
        "--browser-config-fd",
        "preflightResponderToken",
        "assert-current-program",
        "challengeId",
        "separate effect worker",
    ):
        require(required in source, "missing selected #280 boundary: " + required)

    for forbidden in (
        "--caller-fd",
        "CurrentProgramProvenanceClient",
        "CurrentProgramAuthorityEvidence",
        "_bind_effect_current_program_bridge",
        "send_packet(",
        "HighLevelCommander(",
        "takeoff",
        "land(",
    ):
        require(forbidden not in source, "authority prerequisite leaks old/effect API: " + forbidden)

    require(not REMOVED_CLIENT.exists(), "caller-selectable provenance client must stay removed")
    require(not REMOVED_BROKER.exists(), "preflight-only broker must stay removed")


def main() -> int:
    test_effect_worker_cannot_forge_trusted_response()
    test_local_forgery_cannot_replace_missing_browser_responder()
    test_binding_mismatch_fails_closed_across_process_boundary()
    test_effect_requester_fails_closed_on_channel_ambiguity()
    test_production_host_is_executable_only_and_preserves_one_way_split()
    print(
        "PASS #280 authority/effect process split: effect worker owns only request-send "
        "and response-receive capabilities; local forgery and channel ambiguity fail closed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

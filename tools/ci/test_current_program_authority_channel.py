#!/usr/bin/env python3
from __future__ import annotations

from multiprocessing import get_context
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
import inspect
import sys

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(PHYSICAL))

import current_program_authority_channel as channel  # noqa: E402
import serve_reference_capabilities as bridge_module  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class FakeSession:
    def __init__(self, epoch: str) -> None:
        self.epoch = epoch

    def read_connection_epoch(self) -> str:
        return self.epoch

    def read_capabilities(self) -> dict[str, object]:
        return {
            "connected": True,
            "executionAuthority": False,
            "connectionEpoch": self.epoch,
        }


class FakeOpenSyncSession:
    def __init__(self) -> None:
        self.cf = SimpleNamespace()

    def is_link_open(self) -> bool:
        return True


def answer_bridge(
    bridge: bridge_module.ReadOnlyCapabilityHttpBridge,
    *,
    profile_id: str,
    ast_binding: str,
    connection_epoch: str,
    ok: bool = True,
) -> None:
    challenge_id = bridge._claim_current_program_challenge(timeout_seconds=1.0)
    require(isinstance(challenge_id, str) and challenge_id, "browser challenge claimed")
    bridge._submit_current_program_assertion(
        {
            "challengeId": challenge_id,
            "ok": ok,
            "profileId": profile_id,
            "astBinding": ast_binding,
            "connectionEpoch": connection_epoch,
            "executionAuthority": False,
        }
    )


def self_answer_forged_bridge(epoch: str, profile_id: str, ast_binding: str) -> bool:
    """Reproduce the strongest same-process #276 attack in the effect worker."""
    # Exact uninjected production session type, then direct live-looking state
    # mutation exactly as the durable d576 counterexample describes.
    session = bridge_module.ReadOnlyCapabilitySession(
        "radio://0/80/2M/E7E7E7E7E7"
    )
    session._scf = FakeOpenSyncSession()
    session._connection_epoch = epoch
    forged = bridge_module.ReadOnlyCapabilityHttpBridge(
        session,
        token="forged-capability",
        preflight_responder_token="forged-responder",
    )
    responder = Thread(
        target=answer_bridge,
        kwargs={
            "bridge": forged,
            "profile_id": profile_id,
            "ast_binding": ast_binding,
            "connection_epoch": epoch,
        },
        daemon=True,
    )
    responder.start()
    evidence = forged.assert_current_program(
        profile_id=profile_id,
        ast_binding=ast_binding,
        connection_epoch=epoch,
        timeout_seconds=1.0,
    )
    responder.join(timeout=1.0)
    forged._server.server_close()
    return (
        type(evidence) is bridge_module.CurrentProgramPreflightEvidence
        and evidence.execution_authority is False
    )


def effect_worker(
    request_sender,
    response_receiver,
    result_sender,
    *,
    request_id: str,
    profile_id: str,
    ast_binding: str,
    connection_epoch: str,
) -> None:
    """Spawned effect-side probe: arguments contain only one-way capabilities."""
    try:
        # The strongest local bridge/session forgery still succeeds locally.
        local_forgery = self_answer_forged_bridge(
            connection_epoch,
            profile_id,
            ast_binding,
        )

        # It cannot write the inherited trusted response capability or read the
        # request-send capability.
        response_write_blocked = False
        request_read_blocked = False
        try:
            response_receiver.send({"ok": True})
        except (OSError, AttributeError):
            response_write_blocked = True
        try:
            request_sender.recv()
        except (OSError, AttributeError):
            request_read_blocked = True

        request_sender.send(
            channel.request_payload(
                request_id=request_id,
                profile_id=profile_id,
                ast_binding=ast_binding,
                connection_epoch=connection_epoch,
            )
        )
        if not response_receiver.poll(2.0):
            raise RuntimeError("trusted authority response timed out")
        raw = response_receiver.recv()
        evidence = channel.validate_response(
            raw,
            expected_request_id=request_id,
            expected_profile_id=profile_id,
            expected_ast_binding=ast_binding,
            expected_connection_epoch=connection_epoch,
        )
        result_sender.send(
            {
                "ok": True,
                "localForgery": local_forgery,
                "responseWriteBlocked": response_write_blocked,
                "requestReadBlocked": request_read_blocked,
                "challengeId": evidence.challenge_id,
            }
        )
    except Exception as exc:
        result_sender.send(
            {
                "ok": False,
                "error": type(exc).__name__ + ": " + str(exc),
            }
        )


def run_positive_separation() -> None:
    ctx = get_context("spawn")
    request_receiver, request_sender = ctx.Pipe(duplex=False)
    response_receiver, response_sender = ctx.Pipe(duplex=False)
    result_receiver, result_sender = ctx.Pipe(duplex=False)

    epoch = "authority-epoch"
    profile_id = "activity-1"
    ast_binding = "ast-binding-1"
    bridge = bridge_module.ReadOnlyCapabilityHttpBridge(
        FakeSession(epoch),
        token="real-capability",
        preflight_responder_token="real-browser-responder",
    )
    broker = channel.CurrentProgramAuthorityBroker(
        bridge,
        request_receiver,
        response_sender,
    )

    browser = Thread(
        target=answer_bridge,
        kwargs={
            "bridge": bridge,
            "profile_id": profile_id,
            "ast_binding": ast_binding,
            "connection_epoch": epoch,
        },
        daemon=True,
    )
    browser.start()

    child = ctx.Process(
        target=effect_worker,
        kwargs={
            "request_sender": request_sender,
            "response_receiver": response_receiver,
            "result_sender": result_sender,
            "request_id": "request-1",
            "profile_id": profile_id,
            "ast_binding": ast_binding,
            "connection_epoch": epoch,
        },
    )
    child.start()
    # Parent/authority keeps only receive-request + send-response roles.
    request_sender.close()
    response_receiver.close()
    result_sender.close()

    broker.serve_one(timeout_seconds=2.0)
    require(result_receiver.poll(3.0), "effect worker returned deterministic result")
    result = result_receiver.recv()
    child.join(timeout=3.0)
    browser.join(timeout=1.0)
    bridge._server.server_close()
    require(not child.is_alive() and child.exitcode == 0, "spawned worker exited")
    require(result.get("ok") is True, "real authority response accepted: " + str(result))
    require(result.get("localForgery") is True, "strong local bridge forgery reproduced")
    require(result.get("responseWriteBlocked") is True, "worker cannot write trusted response pipe")
    require(result.get("requestReadBlocked") is True, "worker cannot read request-send pipe")
    require(isinstance(result.get("challengeId"), str), "real #278 challenge provenance returned")


def run_negative_authority_response() -> None:
    ctx = get_context("spawn")
    request_receiver, request_sender = ctx.Pipe(duplex=False)
    response_receiver, response_sender = ctx.Pipe(duplex=False)
    result_receiver, result_sender = ctx.Pipe(duplex=False)

    epoch = "authority-denied"
    profile_id = "activity-1"
    ast_binding = "ast-binding-denied"
    bridge = bridge_module.ReadOnlyCapabilityHttpBridge(
        FakeSession(epoch),
        token="deny-capability",
        preflight_responder_token="deny-browser-responder",
    )
    broker = channel.CurrentProgramAuthorityBroker(
        bridge,
        request_receiver,
        response_sender,
    )
    browser = Thread(
        target=answer_bridge,
        kwargs={
            "bridge": bridge,
            "profile_id": profile_id,
            "ast_binding": ast_binding,
            "connection_epoch": epoch,
            "ok": False,
        },
        daemon=True,
    )
    browser.start()
    child = ctx.Process(
        target=effect_worker,
        kwargs={
            "request_sender": request_sender,
            "response_receiver": response_receiver,
            "result_sender": result_sender,
            "request_id": "request-denied",
            "profile_id": profile_id,
            "ast_binding": ast_binding,
            "connection_epoch": epoch,
        },
    )
    child.start()
    request_sender.close()
    response_receiver.close()
    result_sender.close()
    broker.serve_one(timeout_seconds=2.0)
    require(result_receiver.poll(3.0), "denied worker returned result")
    result = result_receiver.recv()
    child.join(timeout=3.0)
    browser.join(timeout=1.0)
    bridge._server.server_close()
    require(not child.is_alive() and child.exitcode == 0, "denied worker exited")
    require(result.get("ok") is False, "real responder denial fails closed")
    require(
        "did not establish fresh evidence" in str(result.get("error")),
        "local self-answer cannot replace real authority denial",
    )


def test_response_validation_fail_closed() -> None:
    expected = dict(
        expected_request_id="r1",
        expected_profile_id="p1",
        expected_ast_binding="a1",
        expected_connection_epoch="e1",
    )
    good = {
        "version": 1,
        "requestId": "r1",
        "ok": True,
        "executionAuthority": False,
        "profileId": "p1",
        "astBinding": "a1",
        "connectionEpoch": "e1",
        "challengeId": "c1",
    }
    for mutated, pattern in (
        ({**good, "requestId": "wrong"}, "correlation"),
        ({**good, "profileId": "wrong"}, "binding"),
        ({**good, "executionAuthority": True}, "authority"),
        ({**good, "ok": False, "error": "denied"}, "did not establish"),
        ({**good, "version": 2}, "version"),
        ({**good, "extra": True}, "shape"),
    ):
        try:
            channel.validate_response(mutated, **expected)
        except channel.CurrentProgramAuthorityChannelError as exc:
            require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        else:
            raise AssertionError("malformed/mismatched response passed validation")


def test_effect_side_has_no_bridge_to_requester_conversion() -> None:
    source = (PHYSICAL / "current_program_authority_channel.py").read_text(
        encoding="utf-8"
    )
    # The only constructor carrying the bridge is authority-side and owns
    # request-receive/response-send. No effect requester/client/binder is minted.
    require("class CurrentProgramAuthorityBroker" in source, "authority broker exists")
    for forbidden in (
        "class CurrentProgramRequester",
        "class CurrentProgramAuthorityClient",
        "def bind_",
        "def mint_",
        "responder_token:",
        "preflight_responder_token:",
        "send_packet",
        "HighLevelCommander",
        "send_arming_request",
        "send_emergency_stop",
    ):
        require(forbidden not in source, "forbidden effect/provenance surface: " + forbidden)

    signature = inspect.signature(effect_worker)
    require(
        list(signature.parameters) == [
            "request_sender",
            "response_receiver",
            "result_sender",
            "request_id",
            "profile_id",
            "ast_binding",
            "connection_epoch",
        ],
        "spawned effect worker receives no bridge/session/responder credential",
    )


def main() -> int:
    run_positive_separation()
    run_negative_authority_response()
    test_response_validation_fail_closed()
    test_effect_side_has_no_bridge_to_requester_conversion()
    print(
        "PASS current-program provenance crosses only trusted one-way process capabilities; "
        "local bridge/session self-answer cannot inject the authority response"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

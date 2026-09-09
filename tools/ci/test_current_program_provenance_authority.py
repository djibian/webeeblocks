#!/usr/bin/env python3
from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import socket
import subprocess
import sys
from threading import Thread

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(PHYSICAL))

import current_program_provenance as provenance  # noqa: E402
import serve_reference_capabilities as bridge_module  # noqa: E402


AUTHORITY = PHYSICAL / "serve_current_program_provenance.py"
CLIENT = PHYSICAL / "current_program_provenance.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except provenance.CurrentProgramProvenanceError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError("expected CurrentProgramProvenanceError")


def run_fixture_server(
    channel: socket.socket,
    *,
    mode: str,
    seen: list[dict],
) -> Thread:
    def serve() -> None:
        reader = channel.makefile("r", encoding="utf-8")
        writer = channel.makefile("w", encoding="utf-8")
        try:
            line = reader.readline()
            if not line:
                return
            request = json.loads(line)
            seen.append(request)
            if mode == "close":
                return
            if mode == "malformed":
                writer.write("{not-json}\n")
                writer.flush()
                return
            response = {
                "requestId": request["requestId"],
                "ok": True,
                "challengeId": "authority-challenge-1",
                "profileId": request["profileId"],
                "astBinding": request["astBinding"],
                "connectionEpoch": request["connectionEpoch"],
                "executionAuthority": False,
            }
            if mode == "mismatch":
                response["astBinding"] = "other-ast"
            elif mode == "negative":
                response = {
                    "requestId": request["requestId"],
                    "ok": False,
                    "error": "browser current-program assertion failed",
                    "executionAuthority": False,
                }
            writer.write(json.dumps(response, separators=(",", ":")) + "\n")
            writer.flush()
        finally:
            try:
                reader.close()
                writer.close()
                channel.close()
            except OSError:
                pass

    thread = Thread(target=serve, daemon=True)
    thread.start()
    return thread


class FakeEpochSession:
    def __init__(self, epoch: str) -> None:
        self.epoch = epoch

    def read_connection_epoch(self) -> str:
        return self.epoch


def self_answer_public_bridge() -> bridge_module.CurrentProgramPreflightEvidence:
    epoch = "epoch-1"
    bridge = bridge_module.ReadOnlyCapabilityHttpBridge(
        FakeEpochSession(epoch),
        token="ordinary-capability-token",
        preflight_responder_token="self-answer-token",
    )
    result = []
    failures = []

    def answer() -> None:
        try:
            challenge = bridge._claim_current_program_challenge(
                timeout_seconds=0.3
            )
            if challenge is None:
                raise AssertionError("challenge was not created")
            bridge._submit_current_program_assertion(
                {
                    "challengeId": challenge,
                    "ok": True,
                    "profileId": "activity-1",
                    "astBinding": "ast-1",
                    "connectionEpoch": epoch,
                    "executionAuthority": False,
                }
            )
        except BaseException as exc:
            failures.append(exc)

    thread = Thread(target=answer, daemon=True)
    thread.start()
    result.append(
        bridge.assert_current_program(
            profile_id="activity-1",
            ast_binding="ast-1",
            connection_epoch=epoch,
            timeout_seconds=0.3,
        )
    )
    thread.join(1.0)
    require(not failures, f"public bridge counterexample failed: {failures!r}")
    bridge._server.server_close()
    return result[0]


def test_exact_positive_channel_result() -> None:
    client_sock, authority_sock = socket.socketpair()
    seen = []
    server = run_fixture_server(authority_sock, mode="ok", seen=seen)
    client = provenance.CurrentProgramProvenanceClient(client_sock)
    evidence = client.assert_current_program(
        profile_id="activity-1",
        ast_binding="ast-1",
        connection_epoch="epoch-1",
        timeout_seconds=0.3,
    )
    server.join(1.0)
    require(len(seen) == 1, "one serialized authority request")
    require(seen[0]["op"] == "assert-current-program", "exact authority operation")
    require(evidence.profile_id == "activity-1", "profile preserved")
    require(evidence.ast_binding == "ast-1", "AST preserved")
    require(evidence.connection_epoch == "epoch-1", "epoch preserved")
    require(evidence.challenge_id == "authority-challenge-1", "challenge provenance preserved")
    require(evidence.execution_authority is False, "authority result remains non-authority")
    require(client.poisoned is False, "clean positive reply keeps channel usable")
    try:
        evidence.profile_id = "changed"
    except (FrozenInstanceError, AttributeError):
        pass
    else:
        raise AssertionError("authority evidence must be immutable")
    client_sock.close()


def test_clean_negative_does_not_fabricate_or_poison() -> None:
    client_sock, authority_sock = socket.socketpair()
    seen = []
    server = run_fixture_server(authority_sock, mode="negative", seen=seen)
    client = provenance.CurrentProgramProvenanceClient(client_sock)
    expect_error(
        lambda: client.assert_current_program(
            profile_id="activity-1",
            ast_binding="ast-1",
            connection_epoch="epoch-1",
            timeout_seconds=0.3,
        ),
        "not established",
    )
    server.join(1.0)
    require(client.poisoned is False, "well-formed negative assertion is not channel ambiguity")
    client_sock.close()


def test_malformed_mismatch_and_eof_poison_channel() -> None:
    for mode, pattern in (
        ("malformed", "failed or is ambiguous"),
        ("mismatch", "binding mismatch"),
        ("close", "closed before reply"),
    ):
        client_sock, authority_sock = socket.socketpair()
        seen = []
        server = run_fixture_server(authority_sock, mode=mode, seen=seen)
        client = provenance.CurrentProgramProvenanceClient(client_sock)
        expect_error(
            lambda: client.assert_current_program(
                profile_id="activity-1",
                ast_binding="ast-1",
                connection_epoch="epoch-1",
                timeout_seconds=0.3,
            ),
            pattern,
        )
        server.join(1.0)
        require(client.poisoned, mode + " must poison ambiguous authority channel")
        expect_error(
            lambda: client.assert_current_program(
                profile_id="activity-1",
                ast_binding="ast-1",
                connection_epoch="epoch-1",
            ),
            "poisoned",
        )


def test_public_self_answering_bridge_cannot_be_converted_by_client_api() -> None:
    forged_evidence = self_answer_public_bridge()
    require(
        type(forged_evidence) is bridge_module.CurrentProgramPreflightEvidence,
        "counterexample must genuinely mint ordinary #278 evidence",
    )
    expect_error(
        lambda: provenance.CurrentProgramProvenanceClient(forged_evidence),
        "OS socket capability",
    )
    forged_bridge = bridge_module.ReadOnlyCapabilityHttpBridge(
        FakeEpochSession("epoch-1")
    )
    expect_error(
        lambda: provenance.CurrentProgramProvenanceClient(forged_bridge),
        "OS socket capability",
    )
    forged_bridge._server.server_close()

    client_source = CLIENT.read_text(encoding="utf-8")
    for forbidden in (
        "serve_reference_capabilities",
        "ReadOnlyCapabilityHttpBridge",
        "ReadOnlyCapabilitySession",
        "preflight_responder_token",
        "_claim_current_program_challenge",
        "_submit_current_program_assertion",
        "_bind_effect_current_program_bridge",
    ):
        require(
            forbidden not in client_source,
            "effect client must not expose/import bridge mint authority: " + forbidden,
        )


def test_production_authority_is_executable_only_and_splits_channels() -> None:
    source = AUTHORITY.read_text(encoding="utf-8")
    tree = ast.parse(source)
    # No module-level callable/class is exported. All authority composition code
    # exists only under the executable __main__ branch.
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            raise AssertionError("authority script must export no importable callable/class")

    for required in (
        "ReadOnlyCapabilitySession",
        "ReadOnlyCapabilityHttpBridge",
        "assert_current_program(",
        "--effect-fd",
        "--browser-config-fd",
        "preflightResponderToken",
    ):
        require(required in source, "missing production authority composition: " + required)
    require(
        'args.effect_fd == args.browser_config_fd' in source,
        "effect and browser channels must be structurally distinct",
    )
    client_source = CLIENT.read_text(encoding="utf-8")
    require(
        "preflightResponderToken" not in client_source,
        "effect-side client must never receive browser responder credential",
    )


def main() -> int:
    test_exact_positive_channel_result()
    test_clean_negative_does_not_fabricate_or_poison()
    test_malformed_mismatch_and_eof_poison_channel()
    test_public_self_answering_bridge_cannot_be_converted_by_client_api()
    test_production_authority_is_executable_only_and_splits_channels()
    print(
        "PASS separate current-program authority channel preserves exact #249 "
        "provenance without exposing bridge/responder mint APIs to effect code"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

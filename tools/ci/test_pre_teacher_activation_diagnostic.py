#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import socket
import sys
from threading import Thread

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(PHYSICAL))

import launch_physical_qualification as launcher  # noqa: E402
import post_reset_teacher_decision as decision  # noqa: E402
import teacher_run_authorization as authorization  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _read_json_line(peer: socket.socket) -> dict[str, object]:
    peer.settimeout(0.5)
    data = bytearray()
    while not data.endswith(b"\n"):
        data.extend(peer.recv(1))
    value = json.loads(data.decode("utf-8"))
    require(isinstance(value, dict), "trusted diagnostic must be a JSON object")
    return value


def _require_no_more_data(peer: socket.socket) -> None:
    peer.settimeout(0.05)
    try:
        data = peer.recv(1)
    except TimeoutError:
        return
    require(not data, "teacher channel unexpectedly received a second host frame")


def test_pre_teacher_failure_is_one_bounded_non_authority_frame() -> None:
    host, peer = socket.socketpair()
    channel = decision.PostResetTeacherDecisionChannel(host, lambda: "epoch-after")
    try:
        long_error = "reset-reopen-" + ("x" * 2048)
        require(
            channel.publish_pre_teacher_failure(RuntimeError(long_error)) is True,
            "first pre-teacher failure must be published",
        )
        message = _read_json_line(peer)
        require(
            message["op"] == "pre-teacher-activation-failure"
            and message["executionAuthority"] is False,
            "pre-teacher failure frame must remain exact non-authority data",
        )
        require(
            isinstance(message["error"], str)
            and message["error"].startswith("reset-reopen-")
            and len(message["error"]) == 1024,
            "pre-teacher failure text must be bounded without losing its causal prefix",
        )
        require(
            channel.publish_pre_teacher_failure(RuntimeError("second failure")) is False,
            "pre-teacher failure publication must be one-shot",
        )
        _require_no_more_data(peer)
    finally:
        channel.close()
        peer.close()


def test_teacher_exchange_start_irrevocably_disables_failure_frame() -> None:
    host, peer = socket.socketpair()
    channel = decision.PostResetTeacherDecisionChannel(host, lambda: "epoch-after")
    authorizer = authorization.TrustedTeacherAuthorizer()
    binding = authorization.PhysicalRunBinding(
        profile_id="activity-1",
        ast_binding='{"program":[]}',
        connection_epoch="epoch-after",
    )
    outcome: dict[str, object] = {}

    def worker() -> None:
        try:
            channel.receive_authorization_for_binding(
                authorizer,
                binding,
                decision_timeout_seconds=0.5,
            )
        except Exception as exc:
            outcome["error"] = exc

    thread = Thread(target=worker, daemon=True)
    thread.start()
    try:
        proposal = _read_json_line(peer)
        require(
            proposal.get("op") == "teacher-run-binding-proposal",
            "real host-first teacher proposal must start the exchange",
        )
        require(
            channel.publish_pre_teacher_failure(RuntimeError("too late")) is False,
            "diagnostic must never be mixed into a started teacher exchange",
        )
        peer.sendall(
            (
                json.dumps(
                    {
                        "op": "teacher-run-decision-result",
                        "requestId": proposal["requestId"],
                        "challengeId": proposal["challengeId"],
                        "profileId": proposal["profileId"],
                        "astBinding": proposal["astBinding"],
                        "connectionEpoch": proposal["connectionEpoch"],
                        "approved": False,
                        "executionAuthority": False,
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8")
        )
        peer.shutdown(socket.SHUT_WR)
        thread.join(timeout=1.0)
        require(not thread.is_alive(), "denied teacher exchange must settle")
        require("error" in outcome, "teacher denial must fail closed")
        _require_no_more_data(peer)
    finally:
        channel.close()
        peer.close()


def test_launcher_surfaces_exact_pre_teacher_failure() -> None:
    prepared = launcher.PreparedProgram(
        profile_id="activity-1",
        ast_binding='{"program":[]}',
        connection_epoch="epoch-before",
    )
    failure = {
        "op": "pre-teacher-activation-failure",
        "error": "post-reset bridge reopen failed",
        "executionAuthority": False,
    }
    try:
        launcher._teacher_proposal(failure, prepared)
    except launcher.PhysicalQualificationLauncherError as exc:
        require(
            str(exc)
            == "trusted activation failed before teacher decision: post-reset bridge reopen failed",
            "launcher must retain the causal pre-teacher failure instead of a generic socket timeout",
        )
    else:
        raise AssertionError("pre-teacher activation failure was mistaken for a teacher proposal")

    malformed = dict(failure)
    malformed["executionAuthority"] = True
    try:
        launcher._teacher_proposal(malformed, prepared)
    except launcher.PhysicalQualificationLauncherError as exc:
        require("authority boundary" in str(exc), "diagnostic authority violation must fail closed")
    else:
        raise AssertionError("authority-bearing pre-teacher failure unexpectedly passed")

    oversized = dict(failure)
    oversized["error"] = "x" * 1025
    try:
        launcher._teacher_proposal(oversized, prepared)
    except launcher.PhysicalQualificationLauncherError as exc:
        require("size limit" in str(exc), "oversized diagnostic must fail closed")
    else:
        raise AssertionError("oversized pre-teacher failure unexpectedly passed")


def test_common_takeoff_controller_owns_diagnostic_boundary() -> None:
    source = (PHYSICAL / "production_takeoff_run.py").read_text(encoding="utf-8")
    start = source.index("teacher_exchange_started = False")
    enter = source.index("teacher_exchange_started = True", start)
    exchange = source.index("receive_authorization_for_binding", enter)
    fallback = source.index("if not teacher_exchange_started:", exchange)
    publish = source.index("publish_pre_teacher_failure(exc)", fallback)
    require(
        start < enter < exchange < fallback < publish,
        "common takeoff controller must publish diagnostics only before teacher exchange starts",
    )
    require(
        "_PreTeacherDiagnosticSocket" not in source,
        "diagnostic repair must not weaken the exact socket type boundary",
    )


def main() -> int:
    test_pre_teacher_failure_is_one_bounded_non_authority_frame()
    test_teacher_exchange_start_irrevocably_disables_failure_frame()
    test_launcher_surfaces_exact_pre_teacher_failure()
    test_common_takeoff_controller_owns_diagnostic_boundary()
    print(
        "PASS pre-teacher activation diagnostic: one bounded failure frame before teacher exchange, "
        "no protocol mixing after exchange start, exact socket boundary preserved, and causal launcher surfacing"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

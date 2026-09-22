#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(PHYSICAL))

import launch_physical_qualification as launcher  # noqa: E402
import serve_physical_host as physical_host  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _tracked_pair():
    raw, peer = socket.socketpair()
    tracked = physical_host._PreTeacherDiagnosticSocket(fileno=raw.detach())
    return tracked, peer


def _read_json_line(peer: socket.socket) -> dict[str, object]:
    peer.settimeout(0.5)
    stream = peer.makefile("r", encoding="utf-8", newline="\n")
    try:
        value = json.loads(stream.readline())
    finally:
        stream.close()
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
    tracked, peer = _tracked_pair()
    try:
        require(
            tracked.publish_pre_teacher_failure(RuntimeError("synthetic reset reopen failure")) is True,
            "first pre-teacher failure must be published",
        )
        message = _read_json_line(peer)
        require(
            message
            == {
                "op": "pre-teacher-activation-failure",
                "error": "synthetic reset reopen failure",
                "executionAuthority": False,
            },
            "pre-teacher failure frame must be exact bounded non-authority data",
        )
        require(
            tracked.publish_pre_teacher_failure(RuntimeError("second failure")) is False,
            "pre-teacher failure publication must be one-shot",
        )
        _require_no_more_data(peer)
    finally:
        tracked.close()
        peer.close()


def test_teacher_output_irrevocably_disables_failure_frame() -> None:
    tracked, peer = _tracked_pair()
    try:
        proposal = b'{"op":"teacher-run-binding-proposal"}\n'
        tracked.sendall(proposal)
        require(
            tracked.publish_pre_teacher_failure(RuntimeError("too late")) is False,
            "diagnostic must never be mixed into an exchange after teacher output starts",
        )
        peer.settimeout(0.5)
        received = bytearray()
        while not received.endswith(b"\n"):
            received.extend(peer.recv(1))
        require(bytes(received) == proposal, "teacher proposal bytes must stay unchanged")
        _require_no_more_data(peer)
    finally:
        tracked.close()
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


def test_host_worker_is_wired_to_bounded_diagnostic_socket() -> None:
    source = (PHYSICAL / "serve_physical_host.py").read_text(encoding="utf-8")
    require(
        "_PreTeacherDiagnosticSocket(fileno=args.teacher_fd)" in source,
        "trusted teacher fd must enter the tracked diagnostic socket",
    )
    require(
        "teacher_socket.publish_pre_teacher_failure(exc)" in source,
        "activation worker must publish its pre-teacher failure through the tracked socket",
    )


def main() -> int:
    test_pre_teacher_failure_is_one_bounded_non_authority_frame()
    test_teacher_output_irrevocably_disables_failure_frame()
    test_launcher_surfaces_exact_pre_teacher_failure()
    test_host_worker_is_wired_to_bounded_diagnostic_socket()
    print(
        "PASS pre-teacher activation diagnostic: one bounded failure frame before teacher exchange, "
        "no protocol mixing after teacher output, and causal launcher surfacing"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

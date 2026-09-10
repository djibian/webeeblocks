#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import socket
import sys
from threading import Thread

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
CI = ROOT / "tools" / "ci"
sys.path.insert(0, str(PHYSICAL))
sys.path.insert(0, str(CI))
HOST = PHYSICAL / "serve_physical_host.py"

import physical_execution_domain  # noqa: E402
import physical_run_activation as activation  # noqa: E402
import post_reset_teacher_decision  # noqa: E402
import takeoff_transport  # noqa: E402
import teacher_run_authorization  # noqa: E402
import test_physical_host_activation as fixture  # noqa: E402


REAL_EXECUTION_DOMAIN = physical_execution_domain.PhysicalExecutionDomain
REAL_TEACHER_CHANNEL = post_reset_teacher_decision.PostResetTeacherDecisionChannel
REAL_TEACHER_AUTHORIZATION = teacher_run_authorization.TeacherRunAuthorization
REAL_TEACHER_AUTHORIZER = teacher_run_authorization.TrustedTeacherAuthorizer


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def send_line(sock: socket.socket, payload: object) -> None:
    sock.sendall(
        (json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n").encode(
            "utf-8"
        )
    )


def read_line(sock: socket.socket) -> dict[str, object]:
    data = bytearray()
    while True:
        part = sock.recv(1)
        require(part != b"", "teacher peer received unexpected EOF")
        data.extend(part)
        if part == b"\n":
            payload = json.loads(bytes(data[:-1]).decode("utf-8"))
            require(isinstance(payload, dict), "teacher proposal must be an object")
            return payload


def install_boundary_fakes() -> None:
    """Keep hardware/effect seams fake while restoring the real authority boundaries."""
    fixture.install_fakes()

    physical_execution_domain.PhysicalExecutionDomain = REAL_EXECUTION_DOMAIN
    post_reset_teacher_decision.PostResetTeacherDecisionChannel = REAL_TEACHER_CHANNEL
    teacher_run_authorization.TeacherRunAuthorization = REAL_TEACHER_AUTHORIZATION
    teacher_run_authorization.TrustedTeacherAuthorizer = REAL_TEACHER_AUTHORIZER

    activation.PhysicalExecutionDomain = REAL_EXECUTION_DOMAIN
    activation.PostResetTeacherDecisionChannel = REAL_TEACHER_CHANNEL
    activation.TrustedTeacherAuthorizer = REAL_TEACHER_AUTHORIZER

    class RealDomainTransport(fixture.FakeTransportBase):
        """Fake packet substrate that advances only through the real #273 transaction."""

        def send_from_authorized_ast(self) -> fixture.FakeAckResult:
            binding = self._read_current_binding()
            require(
                binding == self.teacher_binding,
                "fresh provenance must match the real teacher receipt",
            )
            with self.execution_domain.effect_transaction(lambda: None) as transaction:
                transaction.mark_emitted()
                permit = transaction.mark_accepted()
            self.execution_domain.complete_accepted_effect(
                permit,
                physical_execution_domain.FLYING,
                lambda: True,
            )
            fixture.EVENTS.append(("transport-send", binding.connection_epoch))
            return fixture.FakeAckResult()

    takeoff_transport.TrustedTakeoffTransport = RealDomainTransport
    activation.TrustedTakeoffTransport = RealDomainTransport


def teacher_peer(sock: socket.socket, *, mode: str) -> None:
    proposal = read_line(sock)
    require(
        set(proposal)
        == {
            "op",
            "requestId",
            "challengeId",
            "profileId",
            "astBinding",
            "connectionEpoch",
            "executionAuthority",
        },
        "post-reset teacher proposal fields changed",
    )
    require(
        proposal["op"] == "teacher-run-binding-proposal",
        "real post-reset teacher channel must send the host-first proposal",
    )
    require(proposal["profileId"] == "activity-1", "proposal profile binding")
    require(proposal["astBinding"] == fixture.canonical_ast(), "proposal AST binding")
    require(proposal["connectionEpoch"] == "epoch-after", "proposal rotated epoch")
    require(proposal["executionAuthority"] is False, "proposal remains non-authority data")
    fixture.EVENTS.append(("teacher-proposal", proposal["connectionEpoch"]))

    reply = {
        "op": "teacher-run-decision-result",
        "requestId": proposal["requestId"],
        "challengeId": proposal["challengeId"],
        "profileId": proposal["profileId"],
        "astBinding": proposal["astBinding"],
        "connectionEpoch": proposal["connectionEpoch"],
        "approved": True,
        "executionAuthority": False,
    }
    if mode == "mismatch":
        reply["connectionEpoch"] = "wrong-epoch"
    elif mode != "approve":
        raise AssertionError("unsupported teacher peer mode")
    send_line(sock, reply)
    sock.shutdown(socket.SHUT_WR)
    fixture.EVENTS.append(("teacher-reply", reply["connectionEpoch"]))


def run_host(*, teacher_mode: str) -> None:
    caller_host, caller_peer = socket.socketpair()
    browser_read, browser_write = os.pipe()
    teacher_host, teacher_side = socket.socketpair()

    argv = [
        str(HOST),
        "--uri",
        "radio://0/80/2M/E7E7E7E7E7",
        "--caller-fd",
        str(caller_host.detach()),
        "--browser-config-fd",
        str(browser_write),
        "--teacher-fd",
        str(teacher_host.detach()),
    ]

    outcome: dict[str, object] = {}
    teacher_outcome: dict[str, object] = {}
    old_argv = sys.argv[:]

    def host_target() -> None:
        sys.argv = argv
        try:
            runpy.run_path(str(HOST), run_name="__main__")
        except Exception as exc:
            outcome["error"] = exc
        finally:
            sys.argv = old_argv

    def teacher_target() -> None:
        try:
            teacher_peer(teacher_side, mode=teacher_mode)
        except Exception as exc:
            teacher_outcome["error"] = exc

    host_worker = Thread(target=host_target, daemon=True)
    decision_worker = Thread(target=teacher_target, daemon=True)
    host_worker.start()
    decision_worker.start()

    with os.fdopen(browser_read, "r", encoding="utf-8") as stream:
        bootstrap = json.loads(stream.readline())
    require(bootstrap["executionAuthority"] is False, "browser bootstrap non-authority")
    require(bootstrap["token"] == "capability-token", "stable read-only token")
    require(
        bootstrap["preflightResponderToken"] == "responder-token",
        "stable responder token",
    )

    request = {
        "op": "validate-run-context",
        "requestId": "request-1",
        "profileId": "activity-1",
        "astBinding": fixture.canonical_ast(),
        "connectionEpoch": "epoch-before",
    }
    caller_peer.sendall(
        (json.dumps(request, separators=(",", ":")) + "\n").encode("utf-8")
    )
    response = json.loads(caller_peer.makefile("r", encoding="utf-8").readline())
    require(
        response == {
            "executionAuthority": False,
            "ok": True,
            "requestId": "request-1",
        },
        "ordinary caller reply must remain diagnostic",
    )
    caller_peer.shutdown(socket.SHUT_WR)

    host_worker.join(timeout=3.0)
    decision_worker.join(timeout=2.0)
    require(not host_worker.is_alive(), "production host must terminate after caller EOF")
    require(not decision_worker.is_alive(), "teacher exchange must terminate")
    require("error" not in outcome, "production host failed: " + repr(outcome.get("error")))
    require(
        "error" not in teacher_outcome,
        "real teacher peer failed: " + repr(teacher_outcome.get("error")),
    )

    caller_peer.close()
    teacher_side.close()


def test_mismatched_real_teacher_binding_cannot_reach_effect() -> None:
    fixture.EVENTS.clear()
    run_host(teacher_mode="mismatch")
    require(
        ("teacher-proposal", "epoch-after") in fixture.EVENTS,
        "real post-reset teacher proposal was not observed",
    )
    require(
        not any(
            isinstance(event, tuple) and event[0] == "transport-send"
            for event in fixture.EVENTS
        ),
        "mismatched real teacher reply reached the effect boundary",
    )
    require(
        REAL_EXECUTION_DOMAIN().phase == physical_execution_domain.INACTIVE,
        "teacher mismatch must leave the reset-established domain inactive",
    )


def test_exact_real_teacher_binding_reaches_effect_through_real_domain() -> None:
    fixture.EVENTS.clear()
    run_host(teacher_mode="approve")

    required = [
        ("session-open", "epoch-before"),
        ("current-program", "epoch-before"),
        ("bridge-begin", "epoch-before"),
        ("session-close", "epoch-before"),
        "power-cycle",
        ("session-open", "epoch-after"),
        ("bridge-install", "epoch-after"),
        ("current-program", "epoch-after"),
        ("teacher-proposal", "epoch-after"),
        ("teacher-reply", "epoch-after"),
        "watchdog-activate",
        ("transport-send", "epoch-after"),
    ]
    positions = []
    for event in required:
        require(event in fixture.EVENTS, "missing real-boundary event: " + repr(event))
        positions.append(fixture.EVENTS.index(event))
    require(positions == sorted(positions), "real teacher/execution-domain ordering changed")
    require(
        REAL_EXECUTION_DOMAIN().phase == physical_execution_domain.FLYING,
        "real shared #273 domain must reach flying only after accepted effect completion",
    )


def main() -> int:
    install_boundary_fakes()
    test_mismatched_real_teacher_binding_cannot_reach_effect()
    test_exact_real_teacher_binding_reaches_effect_through_real_domain()
    print(
        "PASS actual physical host: real post-reset teacher socket + real #267 receipt + "
        "real #273 reset/effect domain gate the fake hardware effect boundary"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

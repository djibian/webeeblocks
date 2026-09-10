#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import socket
from threading import Thread

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
HOST = PHYSICAL / "serve_physical_host.py"

import sys
sys.path.insert(0, str(PHYSICAL))

import teacher_decision_channel as channel  # noqa: E402
import teacher_run_authorization as auth  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except channel.TeacherDecisionChannelError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError("expected TeacherDecisionChannelError containing " + repr(pattern))


class Epoch:
    def __init__(self, value: str = "epoch-1") -> None:
        self.value = value

    def __call__(self) -> str:
        return self.value


def binding(epoch: str = "epoch-1") -> auth.PhysicalRunBinding:
    return auth.PhysicalRunBinding(
        profile_id="activity-1",
        ast_binding="ast-1",
        connection_epoch=epoch,
    )


def read_line(sock: socket.socket) -> dict:
    data = bytearray()
    while True:
        part = sock.recv(1)
        require(part != b"", "teacher peer received unexpected EOF")
        data.extend(part)
        if part == b"\n":
            return json.loads(bytes(data[:-1]).decode("utf-8"))


def reply_for(request: dict, *, approved: bool = True, **changes) -> dict:
    reply = {
        "op": "teacher-run-decision-result",
        "requestId": request["requestId"],
        "profileId": request["profileId"],
        "astBinding": request["astBinding"],
        "connectionEpoch": request["connectionEpoch"],
        "approved": approved,
        "executionAuthority": False,
    }
    reply.update(changes)
    return reply


def send_line(sock: socket.socket, payload: object) -> None:
    sock.sendall(
        (json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
    )


def test_exact_positive_decision_mints_one_local_receipt() -> None:
    host_sock, teacher_sock = socket.socketpair()
    epoch = Epoch()
    decision = channel.TrustedTeacherDecisionChannel(
        host_sock,
        epoch,
        request_id_factory=lambda: "decision-1",
    )
    authorizer = auth.TrustedTeacherAuthorizer()
    observed: list[dict] = []

    def teacher() -> None:
        request = read_line(teacher_sock)
        observed.append(request)
        send_line(teacher_sock, reply_for(request, approved=True))
        teacher_sock.close()

    worker = Thread(target=teacher, daemon=True)
    worker.start()
    receipt = decision.authorize_run(
        binding(),
        authorizer,
        timeout_seconds=0.5,
    )
    worker.join(timeout=1.0)

    require(type(receipt) is auth.TeacherRunAuthorization, "exact #267 receipt")
    require(receipt.binding == binding(), "receipt keeps exact approved binding")
    require(receipt.active is True and authorizer.has_active_run, "approved run is active")
    require(decision.terminal, "one teacher decision consumes the channel")
    require(len(observed) == 1, "teacher receives one decision challenge")
    request = observed[0]
    require(request["op"] == "teacher-run-decision", "bounded teacher operation")
    require(request["requestId"] == "decision-1", "host correlation id")
    require(request["executionAuthority"] is False, "teacher transport is non-authority data")
    expect_error(
        lambda: decision.authorize_run(binding(), authorizer, timeout_seconds=0.1),
        "terminal",
    )
    decision.close()


def test_denial_does_not_mint_authority() -> None:
    host_sock, teacher_sock = socket.socketpair()
    decision = channel.TrustedTeacherDecisionChannel(host_sock, Epoch())

    def teacher() -> None:
        request = read_line(teacher_sock)
        send_line(teacher_sock, reply_for(request, approved=False))
        teacher_sock.close()

    worker = Thread(target=teacher, daemon=True)
    worker.start()
    authorizer = auth.TrustedTeacherAuthorizer()
    expect_error(
        lambda: decision.authorize_run(binding(), authorizer, timeout_seconds=0.5),
        "explicitly denied",
    )
    worker.join(timeout=1.0)
    require(not authorizer.has_active_run, "denial must not mint #267 authority")
    require(decision.terminal, "denial consumes the one-shot channel")
    decision.close()


def test_wrong_correlation_or_binding_fails_closed_and_stays_terminal() -> None:
    cases = (
        ("correlation", {"requestId": "wrong"}, "correlation"),
        ("binding", {"astBinding": "different-ast"}, "exact run binding"),
    )
    for _label, changes, pattern in cases:
        host_sock, teacher_sock = socket.socketpair()
        decision = channel.TrustedTeacherDecisionChannel(host_sock, Epoch())
        authorizer = auth.TrustedTeacherAuthorizer()

        def teacher(changes=changes) -> None:
            request = read_line(teacher_sock)
            send_line(teacher_sock, reply_for(request, **changes))
            teacher_sock.close()

        worker = Thread(target=teacher, daemon=True)
        worker.start()
        expect_error(
            lambda: decision.authorize_run(binding(), authorizer, timeout_seconds=0.5),
            pattern,
        )
        worker.join(timeout=1.0)
        require(not authorizer.has_active_run, "mismatched decision cannot mint authority")
        require(decision.terminal, "mismatched reply poisons one-shot channel")
        expect_error(
            lambda: decision.authorize_run(binding(), authorizer, timeout_seconds=0.1),
            "terminal",
        )
        decision.close()


def test_eof_and_malformed_reply_fail_closed() -> None:
    for mode, pattern in (("eof", "closed"), ("json", "malformed JSON")):
        host_sock, teacher_sock = socket.socketpair()
        decision = channel.TrustedTeacherDecisionChannel(host_sock, Epoch())
        authorizer = auth.TrustedTeacherAuthorizer()

        def teacher(mode=mode) -> None:
            read_line(teacher_sock)
            if mode == "json":
                teacher_sock.sendall(b"{not-json}\n")
            teacher_sock.close()

        worker = Thread(target=teacher, daemon=True)
        worker.start()
        expect_error(
            lambda: decision.authorize_run(binding(), authorizer, timeout_seconds=0.5),
            pattern,
        )
        worker.join(timeout=1.0)
        require(not authorizer.has_active_run, "ambiguous/malformed transport mints no authority")
        require(decision.terminal, "ambiguous/malformed transport is terminal")
        decision.close()


def test_reconnect_during_decision_fails_closed() -> None:
    host_sock, teacher_sock = socket.socketpair()
    epoch = Epoch()
    decision = channel.TrustedTeacherDecisionChannel(host_sock, epoch)
    authorizer = auth.TrustedTeacherAuthorizer()

    def teacher() -> None:
        request = read_line(teacher_sock)
        epoch.value = "epoch-2"
        send_line(teacher_sock, reply_for(request))
        teacher_sock.close()

    worker = Thread(target=teacher, daemon=True)
    worker.start()
    expect_error(
        lambda: decision.authorize_run(binding(), authorizer, timeout_seconds=0.5),
        "epoch changed",
    )
    worker.join(timeout=1.0)
    require(not authorizer.has_active_run, "reconnect cannot inherit teacher authority")
    require(decision.terminal, "reconnect ambiguity consumes channel")
    decision.close()


def test_untrusted_substitute_socket_cannot_replace_installed_teacher_channel() -> None:
    installed_host, installed_teacher = socket.socketpair()
    fake_host, fake_peer = socket.socketpair()
    decision = channel.TrustedTeacherDecisionChannel(installed_host, Epoch())
    authorizer = auth.TrustedTeacherAuthorizer()

    # An ordinary caller may manufacture arbitrary positive JSON on another
    # socket; it has no route into the launcher-installed channel.
    send_line(
        fake_peer,
        {
            "op": "teacher-run-decision-result",
            "requestId": "forged",
            "profileId": "activity-1",
            "astBinding": "ast-1",
            "connectionEpoch": "epoch-1",
            "approved": True,
            "executionAuthority": False,
        },
    )

    def teacher() -> None:
        request = read_line(installed_teacher)
        send_line(installed_teacher, reply_for(request, approved=False))
        installed_teacher.close()

    worker = Thread(target=teacher, daemon=True)
    worker.start()
    expect_error(
        lambda: decision.authorize_run(binding(), authorizer, timeout_seconds=0.5),
        "explicitly denied",
    )
    worker.join(timeout=1.0)
    require(not authorizer.has_active_run, "forged side socket cannot authorize installed host")
    forged = read_line(fake_host)
    require(forged["approved"] is True, "forged data remained isolated on substitute socket")
    fake_host.close()
    fake_peer.close()
    decision.close()


def test_module_and_host_composition_expose_no_effect_or_receipt_channel() -> None:
    module_source = (PHYSICAL / "teacher_decision_channel.py").read_text(encoding="utf-8")
    for forbidden in (
        "send_packet(",
        "HighLevelCommander(",
        "PowerSwitch(",
        "send_setpoint(",
        "send_emergency_stop(",
    ):
        require(forbidden not in module_source, "teacher channel leaked effect primitive: " + forbidden)

    host_source = HOST.read_text(encoding="utf-8")
    for required in (
        "--teacher-fd",
        "TrustedTeacherDecisionChannel",
        "TrustedTeacherAuthorizer",
        "PhysicalRunBinding",
        "authorize-run-context",
        "teacher_channel.authorize_run(",
        "active_teacher_authorization =",
        "bridge.assert_current_program(",
    ):
        require(required in host_source, "host lacks trusted teacher composition: " + required)
    require(
        host_source.index("bridge.assert_current_program(")
        < host_source.index("teacher_channel.authorize_run("),
        "fresh #249 assertion must precede the teacher decision for the exact run",
    )
    require('"runId"' not in host_source, "caller response must not serialize #267 receipt identity")

    spec = importlib.util.spec_from_file_location("teacher_host_import_probe", HOST)
    require(spec is not None and spec.loader is not None, "physical-host import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for forbidden_attr in (
        "TrustedTeacherDecisionChannel",
        "TrustedTeacherAuthorizer",
        "teacher_channel",
        "teacher_socket",
        "active_teacher_authorization",
    ):
        require(
            not hasattr(module, forbidden_attr),
            "imported physical host leaked trusted teacher state/API: " + forbidden_attr,
        )


def main() -> int:
    test_exact_positive_decision_mints_one_local_receipt()
    test_denial_does_not_mint_authority()
    test_wrong_correlation_or_binding_fails_closed_and_stays_terminal()
    test_eof_and_malformed_reply_fail_closed()
    test_reconnect_during_decision_fails_closed()
    test_untrusted_substitute_socket_cannot_replace_installed_teacher_channel()
    test_module_and_host_composition_expose_no_effect_or_receipt_channel()
    print(
        "PASS trusted teacher decision channel mints one exact #267 run receipt "
        "inside the physical host and fails closed on substitution/ambiguity"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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


def proposal(*, epoch: str = "epoch-1", **changes) -> dict:
    value = {
        "op": "teacher-run-authorization-request",
        "requestId": "teacher-request-1",
        "profileId": "activity-1",
        "astBinding": "ast-1",
        "connectionEpoch": epoch,
        "executionAuthority": False,
    }
    value.update(changes)
    return value


def decision_for(challenge: dict, *, approved: bool = True, **changes) -> dict:
    value = {
        "op": "teacher-run-decision-result",
        "requestId": challenge["requestId"],
        "challengeId": challenge["challengeId"],
        "profileId": challenge["profileId"],
        "astBinding": challenge["astBinding"],
        "connectionEpoch": challenge["connectionEpoch"],
        "approved": approved,
        "executionAuthority": False,
    }
    value.update(changes)
    return value


def send_line(sock: socket.socket, payload: object) -> None:
    sock.sendall(
        (json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
    )


def read_line(sock: socket.socket) -> dict:
    data = bytearray()
    while True:
        part = sock.recv(1)
        require(part != b"", "teacher peer received unexpected EOF")
        data.extend(part)
        if part == b"\n":
            return json.loads(bytes(data[:-1]).decode("utf-8"))


def run_teacher_exchange(
    teacher_sock: socket.socket,
    *,
    request: dict | None = None,
    approved: bool = True,
    decision_changes: dict | None = None,
    duplicate: bool = False,
    mutate_epoch=None,
) -> None:
    send_line(teacher_sock, request or proposal())
    challenge = read_line(teacher_sock)
    require(challenge["op"] == "teacher-run-decision-challenge", "host challenge op")
    if mutate_epoch is not None:
        mutate_epoch()
    result = decision_for(
        challenge,
        approved=approved,
        **(decision_changes or {}),
    )
    send_line(teacher_sock, result)
    if duplicate:
        send_line(teacher_sock, result)
    teacher_sock.shutdown(socket.SHUT_WR)


def test_exact_positive_decision_mints_one_local_receipt() -> None:
    host_sock, teacher_sock = socket.socketpair()
    epoch = Epoch()
    decision = channel.TrustedTeacherDecisionChannel(
        host_sock,
        epoch,
        challenge_id_factory=lambda: "challenge-1",
    )
    authorizer = auth.TrustedTeacherAuthorizer()

    worker = Thread(target=run_teacher_exchange, args=(teacher_sock,), daemon=True)
    worker.start()
    receipt = decision.receive_authorization(authorizer, decision_timeout_seconds=0.5)
    worker.join(timeout=1.0)

    require(type(receipt) is auth.TeacherRunAuthorization, "exact #267 receipt")
    require(
        receipt.binding
        == auth.PhysicalRunBinding("activity-1", "ast-1", "epoch-1"),
        "receipt keeps exact teacher-approved binding",
    )
    require(receipt.active and authorizer.has_active_run, "approved run is active")
    require(decision.terminal, "one positive decision consumes the channel")
    expect_error(
        lambda: decision.receive_authorization(authorizer, decision_timeout_seconds=0.1),
        "terminal",
    )
    teacher_sock.close()
    decision.close()


def test_denial_eof_and_malformed_messages_fail_closed() -> None:
    host_sock, teacher_sock = socket.socketpair()
    decision = channel.TrustedTeacherDecisionChannel(host_sock, Epoch())
    authorizer = auth.TrustedTeacherAuthorizer()
    worker = Thread(
        target=run_teacher_exchange,
        args=(teacher_sock,),
        kwargs={"approved": False},
        daemon=True,
    )
    worker.start()
    expect_error(
        lambda: decision.receive_authorization(authorizer, decision_timeout_seconds=0.5),
        "explicitly denied",
    )
    worker.join(timeout=1.0)
    require(not authorizer.has_active_run, "denial mints no authority")
    teacher_sock.close()
    decision.close()

    host_sock, teacher_sock = socket.socketpair()
    decision = channel.TrustedTeacherDecisionChannel(host_sock, Epoch())
    authorizer = auth.TrustedTeacherAuthorizer()
    teacher_sock.close()
    expect_error(
        lambda: decision.receive_authorization(authorizer, decision_timeout_seconds=0.1),
        "closed",
    )
    require(not authorizer.has_active_run, "EOF mints no authority")
    decision.close()

    host_sock, teacher_sock = socket.socketpair()
    decision = channel.TrustedTeacherDecisionChannel(host_sock, Epoch())
    authorizer = auth.TrustedTeacherAuthorizer()
    teacher_sock.sendall(b"{bad-json}\n")
    expect_error(
        lambda: decision.receive_authorization(authorizer, decision_timeout_seconds=0.1),
        "malformed JSON",
    )
    require(not authorizer.has_active_run, "malformed request mints no authority")
    teacher_sock.close()
    decision.close()


def test_wrong_correlation_or_binding_fails_closed() -> None:
    cases = (
        ({"requestId": "wrong"}, "request correlation"),
        ({"challengeId": "wrong"}, "challenge correlation"),
        ({"profileId": "activity-2"}, "exact run binding"),
        ({"astBinding": "other-ast"}, "exact run binding"),
        ({"connectionEpoch": "other-epoch"}, "exact run binding"),
    )
    for changes, pattern in cases:
        host_sock, teacher_sock = socket.socketpair()
        decision = channel.TrustedTeacherDecisionChannel(host_sock, Epoch())
        authorizer = auth.TrustedTeacherAuthorizer()
        worker = Thread(
            target=run_teacher_exchange,
            args=(teacher_sock,),
            kwargs={"decision_changes": changes},
            daemon=True,
        )
        worker.start()
        expect_error(
            lambda: decision.receive_authorization(authorizer, decision_timeout_seconds=0.5),
            pattern,
        )
        worker.join(timeout=1.0)
        require(not authorizer.has_active_run, "mismatched decision mints no authority")
        require(decision.terminal, "mismatch consumes one-shot channel")
        teacher_sock.close()
        decision.close()


def test_wrong_request_binding_and_reconnect_fail_closed() -> None:
    host_sock, teacher_sock = socket.socketpair()
    decision = channel.TrustedTeacherDecisionChannel(host_sock, Epoch())
    authorizer = auth.TrustedTeacherAuthorizer()
    send_line(teacher_sock, proposal(epoch="epoch-2"))
    expect_error(
        lambda: decision.receive_authorization(authorizer, decision_timeout_seconds=0.1),
        "live connection epoch",
    )
    require(not authorizer.has_active_run, "wrong-epoch request mints no authority")
    teacher_sock.close()
    decision.close()

    host_sock, teacher_sock = socket.socketpair()
    epoch = Epoch()
    decision = channel.TrustedTeacherDecisionChannel(host_sock, epoch)
    authorizer = auth.TrustedTeacherAuthorizer()
    worker = Thread(
        target=run_teacher_exchange,
        args=(teacher_sock,),
        kwargs={"mutate_epoch": lambda: setattr(epoch, "value", "epoch-2")},
        daemon=True,
    )
    worker.start()
    expect_error(
        lambda: decision.receive_authorization(authorizer, decision_timeout_seconds=0.5),
        "epoch changed",
    )
    worker.join(timeout=1.0)
    require(not authorizer.has_active_run, "reconnect mints no stale authority")
    teacher_sock.close()
    decision.close()


def test_duplicate_or_late_decision_data_fails_before_mint() -> None:
    host_sock, teacher_sock = socket.socketpair()
    decision = channel.TrustedTeacherDecisionChannel(host_sock, Epoch())
    authorizer = auth.TrustedTeacherAuthorizer()
    worker = Thread(
        target=run_teacher_exchange,
        args=(teacher_sock,),
        kwargs={"duplicate": True},
        daemon=True,
    )
    worker.start()
    expect_error(
        lambda: decision.receive_authorization(authorizer, decision_timeout_seconds=0.5),
        "duplicate or late",
    )
    worker.join(timeout=1.0)
    require(not authorizer.has_active_run, "duplicate/late decision mints no authority")
    teacher_sock.close()
    decision.close()


def test_receipt_binding_change_stays_permanently_invalid() -> None:
    host_sock, teacher_sock = socket.socketpair()
    decision = channel.TrustedTeacherDecisionChannel(host_sock, Epoch())
    authorizer = auth.TrustedTeacherAuthorizer()
    worker = Thread(target=run_teacher_exchange, args=(teacher_sock,), daemon=True)
    worker.start()
    receipt = decision.receive_authorization(authorizer, decision_timeout_seconds=0.5)
    worker.join(timeout=1.0)

    try:
        receipt.assert_effect_binding(
            profile_id="activity-2",
            ast_binding="ast-1",
            connection_epoch="epoch-1",
        )
    except auth.TeacherRunAuthorizationError:
        pass
    else:
        raise AssertionError("changed exact run binding must invalidate #267 receipt")
    require(not receipt.active, "binding mismatch permanently invalidates receipt")
    try:
        receipt.assert_effect_binding(
            profile_id="activity-1",
            ast_binding="ast-1",
            connection_epoch="epoch-1",
        )
    except auth.TeacherRunAuthorizationError:
        pass
    else:
        raise AssertionError("correcting binding must not resurrect stale receipt")
    teacher_sock.close()
    decision.close()


def test_untrusted_channels_cannot_trigger_or_substitute_teacher_authority() -> None:
    module_source = (PHYSICAL / "teacher_decision_channel.py").read_text(encoding="utf-8")
    for forbidden in (
        "send_packet(",
        "HighLevelCommander(",
        "PowerSwitch(",
        "send_setpoint(",
        "send_emergency_stop(",
        "TAKEOFF",
        "LAND",
    ):
        require(forbidden not in module_source, "teacher channel leaked effect primitive: " + forbidden)

    host_source = HOST.read_text(encoding="utf-8")
    for required in (
        "--teacher-fd",
        "TrustedTeacherDecisionChannel",
        "TrustedTeacherAuthorizer",
        "run_teacher_decision_channel",
        "teacher_channel.receive_authorization(teacher_authorizer)",
        'if request.get("op") != "validate-run-context":',
        'teacher_state["authorization"] = receipt',
    ):
        require(required in host_source, "host lacks trusted teacher composition: " + required)
    for forbidden in (
        "authorize-run-context",
        '"runId"',
        '"teacherDecision"',
        '"approved"',
    ):
        require(forbidden not in host_source, "ordinary caller path leaked teacher authority: " + forbidden)
    require(
        "args.teacher_fd in {args.caller_fd, args.browser_config_fd}" in host_source,
        "teacher fd must be distinct from caller/browser channels",
    )

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
    test_denial_eof_and_malformed_messages_fail_closed()
    test_wrong_correlation_or_binding_fails_closed()
    test_wrong_request_binding_and_reconnect_fail_closed()
    test_duplicate_or_late_decision_data_fails_before_mint()
    test_receipt_binding_change_stays_permanently_invalid()
    test_untrusted_channels_cannot_trigger_or_substitute_teacher_authority()
    print(
        "PASS trusted teacher decision channel mints one exact #267 run receipt "
        "inside the physical host without an ordinary caller flight-request path"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

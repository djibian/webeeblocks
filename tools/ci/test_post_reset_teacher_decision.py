#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import socket
from threading import Thread

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"

import sys
sys.path.insert(0, str(PHYSICAL))

import post_reset_teacher_decision as post_reset  # noqa: E402
import teacher_decision_channel as base_channel  # noqa: E402
import teacher_run_authorization as auth  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except base_channel.TeacherDecisionChannelError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError("expected TeacherDecisionChannelError containing " + repr(pattern))


class Epoch:
    def __init__(self, value: str = "epoch-post-reset") -> None:
        self.value = value

    def __call__(self) -> str:
        return self.value


def read_line(sock: socket.socket) -> dict:
    data = bytearray()
    while True:
        part = sock.recv(1)
        require(part != b"", "teacher peer received unexpected EOF")
        data.extend(part)
        if part == b"\n":
            return json.loads(bytes(data[:-1]).decode("utf-8"))


def send_line(sock: socket.socket, payload: object) -> None:
    sock.sendall(
        (json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
    )


def decision_for(proposal: dict, *, approved: bool = True, **changes) -> dict:
    result = {
        "op": "teacher-run-decision-result",
        "requestId": proposal["requestId"],
        "challengeId": proposal["challengeId"],
        "profileId": proposal["profileId"],
        "astBinding": proposal["astBinding"],
        "connectionEpoch": proposal["connectionEpoch"],
        "approved": approved,
        "executionAuthority": False,
    }
    result.update(changes)
    return result


def teacher_peer(
    sock: socket.socket,
    *,
    approved: bool = True,
    changes: dict | None = None,
    duplicate: bool = False,
    mutate_epoch=None,
) -> None:
    proposal = read_line(sock)
    require(
        proposal["op"] == "teacher-run-binding-proposal",
        "host must publish the post-reset binding first",
    )
    require(proposal["executionAuthority"] is False, "binding proposal is non-authority")
    if mutate_epoch is not None:
        mutate_epoch()
    result = decision_for(proposal, approved=approved, **(changes or {}))
    send_line(sock, result)
    if duplicate:
        send_line(sock, result)
    sock.shutdown(socket.SHUT_WR)


def binding(epoch: str = "epoch-post-reset") -> auth.PhysicalRunBinding:
    return auth.PhysicalRunBinding(
        profile_id="activity-1",
        ast_binding='{"program":[{"height_m":0.8,"kind":"takeoff"},{"kind":"land"}],"semantics":"webeeblocks-ast-v1","version":1}',
        connection_epoch=epoch,
    )


def test_host_first_exact_post_reset_binding_mints_receipt() -> None:
    host_sock, teacher_sock = socket.socketpair()
    epoch = Epoch()
    decision = post_reset.PostResetTeacherDecisionChannel(
        host_sock,
        epoch,
        challenge_id_factory=lambda: "post-reset-challenge",
    )
    authorizer = auth.TrustedTeacherAuthorizer()
    exact = binding()
    observed = {}

    def peer() -> None:
        proposal = read_line(teacher_sock)
        observed.update(proposal)
        send_line(teacher_sock, decision_for(proposal))
        teacher_sock.shutdown(socket.SHUT_WR)

    worker = Thread(target=peer, daemon=True)
    worker.start()
    receipt = decision.receive_authorization_for_binding(
        authorizer,
        exact,
        decision_timeout_seconds=0.5,
    )
    worker.join(timeout=1.0)

    require(observed["profileId"] == exact.profile_id, "host publishes exact profile")
    require(observed["astBinding"] == exact.ast_binding, "host publishes exact canonical AST")
    require(
        observed["connectionEpoch"] == exact.connection_epoch,
        "host publishes newly live post-reset epoch",
    )
    require(observed["executionAuthority"] is False, "proposal never becomes authority")
    require(type(receipt) is auth.TeacherRunAuthorization, "exact #267 receipt minted")
    require(receipt.binding == exact and receipt.active, "receipt binds exact post-reset run")
    require(decision.terminal, "one teacher decision consumes the channel")
    teacher_sock.close()
    decision.close()


def test_stale_pre_reset_epoch_fails_before_publication() -> None:
    host_sock, teacher_sock = socket.socketpair()
    teacher_sock.settimeout(0.05)
    decision = post_reset.PostResetTeacherDecisionChannel(host_sock, Epoch())
    authorizer = auth.TrustedTeacherAuthorizer()
    expect_error(
        lambda: decision.receive_authorization_for_binding(
            authorizer,
            binding("epoch-pre-reset"),
            decision_timeout_seconds=0.1,
        ),
        "live connection epoch",
    )
    require(not authorizer.has_active_run, "stale pre-reset binding mints no receipt")
    try:
        leaked = teacher_sock.recv(1)
    except socket.timeout:
        leaked = b""
    require(leaked == b"", "stale binding is never published to teacher peer")
    teacher_sock.close()
    decision.close()


def test_teacher_cannot_substitute_host_proposed_binding() -> None:
    for changes, pattern in (
        ({"profileId": "activity-2"}, "host-proposed run binding"),
        ({"astBinding": "different-ast"}, "host-proposed run binding"),
        ({"connectionEpoch": "epoch-forged"}, "host-proposed run binding"),
        ({"challengeId": "wrong"}, "challenge correlation"),
    ):
        host_sock, teacher_sock = socket.socketpair()
        decision = post_reset.PostResetTeacherDecisionChannel(host_sock, Epoch())
        authorizer = auth.TrustedTeacherAuthorizer()
        worker = Thread(
            target=teacher_peer,
            args=(teacher_sock,),
            kwargs={"changes": changes},
            daemon=True,
        )
        worker.start()
        expect_error(
            lambda: decision.receive_authorization_for_binding(
                authorizer,
                binding(),
                decision_timeout_seconds=0.5,
            ),
            pattern,
        )
        worker.join(timeout=1.0)
        require(not authorizer.has_active_run, "substitution mints no authority")
        teacher_sock.close()
        decision.close()


def test_reconnect_denial_and_late_data_fail_closed() -> None:
    host_sock, teacher_sock = socket.socketpair()
    epoch = Epoch()
    decision = post_reset.PostResetTeacherDecisionChannel(host_sock, epoch)
    authorizer = auth.TrustedTeacherAuthorizer()
    worker = Thread(
        target=teacher_peer,
        args=(teacher_sock,),
        kwargs={"mutate_epoch": lambda: setattr(epoch, "value", "epoch-after-reconnect")},
        daemon=True,
    )
    worker.start()
    expect_error(
        lambda: decision.receive_authorization_for_binding(
            authorizer,
            binding(),
            decision_timeout_seconds=0.5,
        ),
        "epoch changed",
    )
    worker.join(timeout=1.0)
    require(not authorizer.has_active_run, "reconnect mints no stale receipt")
    teacher_sock.close()
    decision.close()

    host_sock, teacher_sock = socket.socketpair()
    decision = post_reset.PostResetTeacherDecisionChannel(host_sock, Epoch())
    authorizer = auth.TrustedTeacherAuthorizer()
    worker = Thread(
        target=teacher_peer,
        args=(teacher_sock,),
        kwargs={"approved": False},
        daemon=True,
    )
    worker.start()
    expect_error(
        lambda: decision.receive_authorization_for_binding(
            authorizer,
            binding(),
            decision_timeout_seconds=0.5,
        ),
        "explicitly denied",
    )
    worker.join(timeout=1.0)
    require(not authorizer.has_active_run, "denial mints no receipt")
    teacher_sock.close()
    decision.close()

    host_sock, teacher_sock = socket.socketpair()
    decision = post_reset.PostResetTeacherDecisionChannel(host_sock, Epoch())
    authorizer = auth.TrustedTeacherAuthorizer()
    worker = Thread(
        target=teacher_peer,
        args=(teacher_sock,),
        kwargs={"duplicate": True},
        daemon=True,
    )
    worker.start()
    expect_error(
        lambda: decision.receive_authorization_for_binding(
            authorizer,
            binding(),
            decision_timeout_seconds=0.5,
        ),
        "duplicate or late",
    )
    worker.join(timeout=1.0)
    require(not authorizer.has_active_run, "late/duplicate data mints no receipt")
    teacher_sock.close()
    decision.close()


def test_protocol_extension_has_no_effect_surface() -> None:
    source = (PHYSICAL / "post_reset_teacher_decision.py").read_text(encoding="utf-8")
    for forbidden in (
        "send_packet(",
        "HighLevelCommander(",
        "PowerSwitch(",
        "stm_power_cycle(",
        "send_setpoint(",
        "send_emergency_stop(",
    ):
        require(forbidden not in source, "post-reset teacher protocol leaked effect: " + forbidden)
    require(
        '"teacher-run-binding-proposal"' in source,
        "host-first exact binding proposal must be explicit",
    )
    require(
        "TrustedTeacherAuthorizer" in source and "PhysicalRunBinding" in source,
        "extension must reuse integrated #267 authority primitive",
    )


def main() -> int:
    test_host_first_exact_post_reset_binding_mints_receipt()
    test_stale_pre_reset_epoch_fails_before_publication()
    test_teacher_cannot_substitute_host_proposed_binding()
    test_reconnect_denial_and_late_data_fail_closed()
    test_protocol_extension_has_no_effect_surface()
    print(
        "PASS post-reset teacher binding bootstrap publishes the exact host-owned new epoch "
        "on the existing trusted channel and mints only one correlated #267 receipt"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

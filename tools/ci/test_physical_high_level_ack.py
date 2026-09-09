#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "physical" / "high_level_ack.py"
sys.path.insert(0, str(MODULE_PATH.parent))
import high_level_ack as ack  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except ack.HighLevelAckError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError(f"expected HighLevelAckError containing {pattern!r}")


class Epoch:
    def __init__(self, value: str) -> None:
        self.value = value

    def __call__(self) -> str:
        return self.value


def unique(name: str) -> str:
    return "ack-test-" + name


def request(prefix: bytes = b"\x0c\x00\x00") -> bytes:
    return prefix + b"payload"


def test_success_and_definitive_rejection_are_not_poison() -> None:
    epoch = Epoch(unique("success"))
    domain = ack.HighLevelAckDomain(epoch)

    with domain.transaction(request()) as txn:
        require(not txn.emitted, "preparation alone is not an effect")
        txn.mark_emitted()
        result = txn.resolve_reply(b"\x0c\x00\x00\x00")
        require(result.accepted and result.status == 0, "zero firmware result accepted")
        require(result.connection_epoch == epoch.value, "reply is epoch-bound")
    require(not domain.poisoned, "definitive success preserves reply freshness")

    with domain.transaction(request(b"\x07\x00\x11")) as txn:
        txn.mark_emitted()
        result = txn.resolve_reply(b"\x07\x00\x11\x10")
        require(
            not result.accepted and result.status == 0x10,
            "nonzero result is definitive rejection",
        )
    require(
        not domain.poisoned,
        "exact nonzero firmware result is rejection, not transport ambiguity",
    )


def test_malformed_or_wrong_prefix_poison_across_reconstruction() -> None:
    for label, reply, pattern in (
        ("short", b"\x0c\x00\x00", "malformed"),
        ("long", b"\x0c\x00\x00\x00\x00", "malformed"),
        ("prefix", b"\x0c\x00\x01\x00", "prefix"),
    ):
        epoch = Epoch(unique(label))
        domain = ack.HighLevelAckDomain(epoch)
        with domain.transaction(request()) as txn:
            txn.mark_emitted()
            expect_error(lambda r=reply, t=txn: t.resolve_reply(r), pattern)
        require(domain.poisoned, label + ": malformed reply poisons epoch")
        expect_error(lambda e=epoch: ack.HighLevelAckDomain(e), "poisoned")


def test_timeout_disconnect_and_unresolved_close_poison() -> None:
    for label, reason, pattern in (
        ("timeout", "ack timeout", "timeout"),
        ("disconnect", "Crazyflie disconnected", "disconnected"),
    ):
        epoch = Epoch(unique(label))
        domain = ack.HighLevelAckDomain(epoch)
        with domain.transaction(request()) as txn:
            txn.mark_emitted()
            expect_error(lambda t=txn, r=reason: t.fail_ambiguous(r), pattern)
        require(domain.poisoned, label + ": ambiguous physical outcome poisons epoch")

    epoch = Epoch(unique("implicit-close"))
    domain = ack.HighLevelAckDomain(epoch)
    with domain.transaction(request()) as txn:
        txn.mark_emitted()
    require(domain.poisoned, "leaving an emitted request unresolved poisons epoch")


def test_pre_emission_failure_does_not_poison() -> None:
    epoch = Epoch(unique("pre-effect"))
    domain = ack.HighLevelAckDomain(epoch)
    try:
        with domain.transaction(request()):
            raise RuntimeError("local validation failed before send")
    except RuntimeError:
        pass
    require(not domain.poisoned, "pre-effect failure creates no reply ambiguity")
    with domain.transaction(request()) as txn:
        txn.mark_emitted()
        require(
            txn.resolve_reply(b"\x0c\x00\x00\x00").accepted,
            "later request still works",
        )


def test_epoch_change_after_emission_poison_old_epoch_only() -> None:
    old = unique("epoch-old")
    new = unique("epoch-new")
    epoch = Epoch(old)
    domain = ack.HighLevelAckDomain(epoch)
    with domain.transaction(request()) as txn:
        txn.mark_emitted()
        epoch.value = new
        expect_error(
            lambda: txn.resolve_reply(b"\x0c\x00\x00\x00"),
            "epoch changed",
        )
    require(domain.poisoned, "old reply domain is poisoned on epoch rotation")
    fresh = ack.HighLevelAckDomain(epoch)
    require(
        fresh.bound_connection_epoch == new and not fresh.poisoned,
        "new epoch clears reply matching ambiguity only",
    )


def test_same_epoch_transactions_are_process_wide_serialized() -> None:
    epoch = Epoch(unique("serialization"))
    first = ack.HighLevelAckDomain(epoch)
    second = ack.HighLevelAckDomain(epoch)
    txn = first.transaction(request())
    try:
        expect_error(
            lambda: second.transaction(request(b"\x07\x00\x01")),
            "already active",
        )
        require(
            not first.poisoned,
            "rejected concurrent preparation creates no ambiguity",
        )
    finally:
        txn.close()
    with second.transaction(request()) as retry:
        retry.mark_emitted()
        retry.resolve_reply(b"\x0c\x00\x00\x00")


def test_invalid_inputs_fail_before_effect() -> None:
    epoch = Epoch(unique("validation"))
    domain = ack.HighLevelAckDomain(epoch)
    for bad in (b"", b"12", "not-bytes", bytearray(31)):
        expect_error(lambda value=bad: domain.transaction(value), "request")
    require(not domain.poisoned, "local request validation cannot poison transport")


def test_source_has_no_physical_send_or_cflib_retry_surface() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "import cflib",
        "CRTPPacket",
        "HighLevelCommander(",
        ".send_packet(",
        "add_port_callback(",
        "expected_" + "reply",
    ):
        require(
            forbidden not in source,
            "pure ack domain contains effect surface: " + forbidden,
        )


def main() -> int:
    test_success_and_definitive_rejection_are_not_poison()
    test_malformed_or_wrong_prefix_poison_across_reconstruction()
    test_timeout_disconnect_and_unresolved_close_poison()
    test_pre_emission_failure_does_not_poison()
    test_epoch_change_after_emission_poison_old_epoch_only()
    test_same_epoch_transactions_are_process_wide_serialized()
    test_invalid_inputs_fail_before_effect()
    test_source_has_no_physical_send_or_cflib_retry_surface()
    print(
        "PASS pure SETPOINT_HL acknowledgement freshness serializes one request "
        "and poisons ambiguous same-epoch replies without any physical send"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
MODULE_PATH = PHYSICAL / "setpoint_hl_transport.py"
sys.path.insert(0, str(PHYSICAL))

import high_level_ack as ack  # noqa: E402
import physical_execution_domain as execution  # noqa: E402
import safelink_precondition as safelink  # noqa: E402
import setpoint_hl_transport as transport  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_error(callable_, error_type, pattern: str) -> None:
    try:
        callable_()
    except error_type as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError(f"expected {error_type.__name__} containing {pattern!r}")


class Epoch:
    def __init__(self, value: str) -> None:
        self.value = value

    def __call__(self) -> str:
        return self.value


class Link:
    def __init__(self, needs_resending=False) -> None:
        self.needs_resending = needs_resending


class Packet:
    def __init__(self, data=b"") -> None:
        self.port = 0x08
        self.data = bytearray(data)


class FakeCrazyflie:
    def __init__(
        self,
        *,
        reply: bytes | None = None,
        send_error: BaseException | None = None,
        disconnect_on_send: bool = False,
        needs_resending=False,
    ) -> None:
        self.link_uri = "radio://0/80/2M/E7E7E7E7E7"
        self.link = Link(needs_resending)
        self.connected = True
        self.reply = reply
        self.send_error = send_error
        self.disconnect_on_send = disconnect_on_send
        self.callbacks: dict[int, list] = {}
        self.send_calls: list[tuple[tuple, dict]] = []
        self.callback_removals = 0

    def is_connected(self):
        return self.connected

    def add_port_callback(self, port, callback):
        self.callbacks.setdefault(port, []).append(callback)

    def remove_port_callback(self, port, callback):
        callbacks = self.callbacks.get(port, [])
        if callback in callbacks:
            callbacks.remove(callback)
        self.callback_removals += 1

    def send_packet(self, *args, **kwargs):
        require(len(args) == 1, "transport must send exactly one packet argument")
        require(not kwargs, "transport must not use cflib expected_reply/retry kwargs")
        require(
            bool(self.callbacks.get(0x08)),
            "SETPOINT_HL reply callback must be installed before physical send",
        )
        self.send_calls.append((args, kwargs))
        if self.disconnect_on_send:
            self.connected = False
        if self.send_error is not None:
            raise self.send_error
        if self.reply is not None:
            packet = Packet(self.reply)
            for callback in tuple(self.callbacks.get(0x08, ())):
                callback(packet)


def packet_factory(request: bytes):
    return Packet(request)


_counter = 0


def unique(label: str) -> str:
    global _counter
    _counter += 1
    return f"transport-{label}-{_counter}"


def ready_execution() -> execution.PhysicalExecutionDomain:
    domain = execution.PhysicalExecutionDomain()
    if domain.phase == execution.RECOVERY_REQUIRED:
        domain.run_reset_establishment(lambda: object())
    require(
        domain.phase == execution.INACTIVE,
        "test fixture must enter from stable inactive execution phase",
    )
    return domain


def reset_after_ambiguity(domain: execution.PhysicalExecutionDomain) -> None:
    require(
        domain.phase == execution.RECOVERY_REQUIRED,
        "ambiguous physical effect must force recovery-required",
    )
    domain.run_reset_establishment(lambda: object())
    require(domain.phase == execution.INACTIVE, "fixture reset restores inactive")


def make_transport(
    label: str,
    cf: FakeCrazyflie,
    domain: execution.PhysicalExecutionDomain,
):
    epoch = Epoch(unique(label))
    guard = safelink.LiveSafeLinkPrecondition(cf, epoch)
    acknowledgement = ack.HighLevelAckDomain(epoch)
    return (
        transport.TrustedSetpointHlTransport(
            crazyflie=cf,
            execution_domain=domain,
            acknowledgement_domain=acknowledgement,
            safelink_precondition=guard,
            packet_factory=packet_factory,
        ),
        acknowledgement,
        guard,
        epoch,
    )


def request(command: int = 12) -> bytes:
    if command == 12:
        return struct.pack("<BBBBfffff", 12, 0, 1, 0, 0.2, 0.0, 0.0, 0.0, 1.0)
    if command in (7, 8):
        return struct.pack("<BBff?f", command, 0, 0.5, 0.0, True, 1.0)
    raise AssertionError("test request helper supports only ordinary motion commands")


def required_assertions(log: list[str]):
    def check(name):
        def assertion():
            log.append(name)
        return assertion

    return {
        "exact_preflight_assertion": check("preflight"),
        "teacher_binding_assertion": check("teacher"),
        "powered_session_assertion": check("powered"),
        "watchdog_liveness_assertion": check("watchdog"),
    }


def test_definitive_acceptance_is_one_send_then_completion_required() -> None:
    domain = ready_execution()
    req = request()
    cf = FakeCrazyflie(reply=req[:3] + b"\x00")
    sender, acknowledgement, _, _ = make_transport("accept", cf, domain)
    order: list[str] = []
    checks = required_assertions(order)

    def build():
        order.append("builder")
        require(
            domain.phase == execution.INACTIVE,
            "request builder runs under stable pre-effect exclusion",
        )
        return req

    result = sender.send_once(
        request_builder=build,
        **checks,
        action_preconditions=(lambda: order.append("action"),),
    )
    require(result.accepted and result.status == 0, "zero firmware reply accepted")
    require(
        order == ["preflight", "teacher", "powered", "watchdog", "action", "builder"],
        "all trusted gates run before request construction",
    )
    require(len(cf.send_calls) == 1, "accepted request is emitted exactly once")
    packet = cf.send_calls[0][0][0]
    require(packet.port == 0x08, "request uses SETPOINT_HL port")
    require(bytes(packet.data) == req, "exact request bytes are emitted")
    require(cf.callback_removals == 1, "reply callback is cleaned up")
    require(not acknowledgement.poisoned, "definitive reply preserves ack freshness")
    require(
        domain.phase == execution.AWAITING_COMPLETION,
        "positive acknowledgement is not trajectory completion",
    )
    domain.complete_accepted_effect(execution.INACTIVE, lambda: True)


def test_definitive_rejection_restores_prior_phase_without_retry() -> None:
    domain = ready_execution()
    req = request(7)
    cf = FakeCrazyflie(reply=req[:3] + b"\x10")
    sender, acknowledgement, _, _ = make_transport("reject", cf, domain)
    result = sender.send_once(
        request_builder=lambda: req,
        **required_assertions([]),
    )
    require(not result.accepted and result.status == 0x10, "non-zero status rejects")
    require(len(cf.send_calls) == 1, "rejected command is never retried")
    require(not acknowledgement.poisoned, "definitive rejection is not ambiguity")
    require(
        domain.phase == execution.INACTIVE,
        "definitive rejection restores exact prior inactive phase",
    )


def test_all_mandatory_gates_precede_builder_and_send() -> None:
    domain = ready_execution()
    cf = FakeCrazyflie(reply=request()[:3] + b"\x00")
    sender, acknowledgement, _, _ = make_transport("gate-fail", cf, domain)
    called: list[str] = []

    def fail_teacher():
        called.append("teacher")
        raise RuntimeError("teacher binding mismatch")

    checks = required_assertions(called)
    checks["teacher_binding_assertion"] = fail_teacher
    expect_error(
        lambda: sender.send_once(
            request_builder=lambda: called.append("builder") or request(),
            **checks,
        ),
        RuntimeError,
        "teacher binding mismatch",
    )
    require(called == ["preflight", "teacher"], "gates stop on first failure")
    require(not cf.send_calls, "failed trusted gate emits no packet")
    require(not acknowledgement.poisoned, "pre-effect gate failure is non-poisoning")
    require(domain.phase == execution.INACTIVE, "pre-effect gate failure is neutral")


def test_safelink_is_rechecked_after_builder_before_ack_and_send() -> None:
    domain = ready_execution()
    cf = FakeCrazyflie(
        reply=request()[:3] + b"\x00",
        needs_resending=True,
    )
    sender, acknowledgement, _, _ = make_transport("safelink", cf, domain)
    built: list[bool] = []
    expect_error(
        lambda: sender.send_once(
            request_builder=lambda: built.append(True) or request(),
            **required_assertions([]),
        ),
        safelink.SafeLinkPreconditionError,
        "not positively established",
    )
    require(built == [True], "request is finalized before last live SafeLink proof")
    require(not cf.callbacks.get(0x08), "ack callback is not installed before SafeLink")
    require(not cf.send_calls, "failed SafeLink emits no packet")
    require(not acknowledgement.poisoned, "pre-effect SafeLink failure is non-poisoning")
    require(domain.phase == execution.INACTIVE, "failed SafeLink preserves prior phase")


def test_two_byte_stop_is_rejected_before_physical_effect() -> None:
    domain = ready_execution()
    cf = FakeCrazyflie()
    sender, acknowledgement, _, _ = make_transport("stop", cf, domain)
    expect_error(
        lambda: sender.send_once(
            request_builder=lambda: b"\x03\x00",
            **required_assertions([]),
        ),
        transport.SetpointHlTransportError,
        "three-byte reply prefix",
    )
    require(not cf.send_calls, "two-byte motor-cut STOP is outside ordinary transport")
    require(not acknowledgement.poisoned, "local request rejection is non-poisoning")
    require(domain.phase == execution.INACTIVE, "invalid request is pre-effect neutral")

    expect_error(
        lambda: sender.send_once(
            request_builder=lambda: b"\x03\x00\x00" + bytes(12),
            **required_assertions([]),
        ),
        transport.SetpointHlTransportError,
        "outside the ordinary WebeeBlocks motion surface",
    )
    require(not cf.send_calls, "padded STOP cannot enter ordinary motion transport")


def test_timeout_disconnect_send_failure_and_bad_reply_fail_closed() -> None:
    cases = (
        ("timeout", FakeCrazyflie(), ack.HighLevelAckError, "timeout"),
        (
            "disconnect",
            FakeCrazyflie(disconnect_on_send=True),
            ack.HighLevelAckError,
            "disconnected",
        ),
        (
            "send-error",
            FakeCrazyflie(send_error=RuntimeError("radio send failed")),
            RuntimeError,
            "radio send failed",
        ),
        (
            "bad-reply",
            FakeCrazyflie(reply=b"\x0c\x00\x00\x00"),
            ack.HighLevelAckError,
            "prefix",
        ),
    )
    for label, cf, error_type, pattern in cases:
        domain = ready_execution()
        sender, acknowledgement, _, _ = make_transport(label, cf, domain)
        expect_error(
            lambda s=sender: s.send_once(
                request_builder=request,
                **required_assertions([]),
                reply_timeout_seconds=0.01,
            ),
            error_type,
            pattern,
        )
        require(len(cf.send_calls) == 1, label + ": physical send occurs at most once")
        require(
            acknowledgement.poisoned,
            label + ": ambiguous post-send outcome poisons ack epoch",
        )
        reset_after_ambiguity(domain)


def test_exact_crazyflie_and_epoch_bindings_are_required() -> None:
    domain = ready_execution()
    cf = FakeCrazyflie()
    other = FakeCrazyflie()
    epoch = Epoch(unique("binding"))
    guard = safelink.LiveSafeLinkPrecondition(other, epoch)
    acknowledgement = ack.HighLevelAckDomain(epoch)
    expect_error(
        lambda: transport.TrustedSetpointHlTransport(
            crazyflie=cf,
            execution_domain=domain,
            acknowledgement_domain=acknowledgement,
            safelink_precondition=guard,
            packet_factory=packet_factory,
        ),
        transport.SetpointHlTransportError,
        "exact Crazyflie",
    )

    guard = safelink.LiveSafeLinkPrecondition(cf, Epoch(unique("safe-epoch")))
    acknowledgement = ack.HighLevelAckDomain(Epoch(unique("ack-epoch")))
    expect_error(
        lambda: transport.TrustedSetpointHlTransport(
            crazyflie=cf,
            execution_domain=domain,
            acknowledgement_domain=acknowledgement,
            safelink_precondition=guard,
            packet_factory=packet_factory,
        ),
        transport.SetpointHlTransportError,
        "same epoch",
    )


def test_source_has_only_bounded_trusted_effect_surface() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    require(
        "self._cf.send_packet(packet)" in source,
        "transport must contain one explicit plain physical send boundary",
    )
    require(
        source.count("self._cf.send_packet(packet)") == 1,
        "transport source has exactly one physical send call",
    )
    for forbidden in (
        "expected_reply=",
        "HighLevelCommander(",
        "send_arming_request",
        "send_emergency_stop",
        "send_emergency_stop_watchdog",
        "http.server",
        "requests.",
        "Flask",
    ):
        require(
            forbidden not in source,
            "transport contains forbidden authority/retry surface: " + forbidden,
        )


def main() -> int:
    test_definitive_acceptance_is_one_send_then_completion_required()
    test_definitive_rejection_restores_prior_phase_without_retry()
    test_all_mandatory_gates_precede_builder_and_send()
    test_safelink_is_rechecked_after_builder_before_ack_and_send()
    test_two_byte_stop_is_rejected_before_physical_effect()
    test_timeout_disconnect_send_failure_and_bad_reply_fail_closed()
    test_exact_crazyflie_and_epoch_bindings_are_required()
    test_source_has_only_bounded_trusted_effect_surface()
    print(
        "PASS trusted SETPOINT_HL transport composes mandatory gates, SafeLink, "
        "process-wide exclusion and exact acknowledgement around one no-retry send"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

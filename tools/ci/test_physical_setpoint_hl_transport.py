#!/usr/bin/env python3
from __future__ import annotations

from math import isclose, pi
from pathlib import Path
from types import SimpleNamespace
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
MODULE_PATH = PHYSICAL / "setpoint_hl_transport.py"
sys.path.insert(0, str(PHYSICAL))

import current_program_preflight as current_preflight  # noqa: E402
import high_level_ack as ack  # noqa: E402
import high_level_timing as timing  # noqa: E402
import physical_execution_domain as execution  # noqa: E402
import powered_session_authority as powered  # noqa: E402
import safelink_precondition as safelink  # noqa: E402
import setpoint_hl_transport as transport  # noqa: E402
import supervisor_state  # noqa: E402
import teacher_run_authorization as teacher  # noqa: E402
import watchdog_liveness as watchdog  # noqa: E402
import yaw_observer as yaw  # noqa: E402


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
    def __init__(self, data=b"", *, port=0x08) -> None:
        self.port = port
        self.data = bytearray(data)


class Platform:
    def get_protocol_version(self):
        return 12


class Supervisor:
    def __init__(self) -> None:
        self.watchdog_sends = 0

    def send_emergency_stop_watchdog(self) -> None:
        self.watchdog_sends += 1


class FakeCrazyflie:
    def __init__(
        self,
        *,
        reply_status: int | None = 0,
        explicit_reply: bytes | None = None,
        send_error: BaseException | None = None,
        disconnect_on_send: bool = False,
        needs_resending=False,
    ) -> None:
        self.link_uri = "radio://0/80/2M/E7E7E7E7E7"
        self.link = Link(needs_resending)
        self.connected = True
        self.reply_status = reply_status
        self.explicit_reply = explicit_reply
        self.send_error = send_error
        self.disconnect_on_send = disconnect_on_send
        self.callbacks: dict[int, list] = {}
        self.send_calls: list[tuple[tuple, dict]] = []
        self.callback_removals = 0
        self.platform = Platform()
        self.supervisor = Supervisor()

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
        packet = args[0]
        if self.disconnect_on_send:
            self.connected = False
        if self.send_error is not None:
            raise self.send_error
        reply = self.explicit_reply
        if reply is None and self.reply_status is not None:
            request = bytes(packet.data)
            reply = request[:3] + bytes((self.reply_status,))
        if reply is not None:
            response = Packet(reply)
            for callback in tuple(self.callbacks.get(0x08, ())):
                callback(response)


_counter = 0


def unique(label: str) -> str:
    global _counter
    _counter += 1
    return f"transport-{label}-{_counter}"


def ensure_flying() -> execution.PhysicalExecutionDomain:
    domain = execution.PhysicalExecutionDomain()
    if domain.phase == execution.AWAITING_COMPLETION:
        domain.complete_accepted_effect(execution.FLYING, lambda: True)
    if domain.phase == execution.RECOVERY_REQUIRED:
        domain.run_reset_establishment(lambda: object())
    if domain.phase == execution.INACTIVE:
        with domain.effect_transaction(lambda: None) as effect:
            effect.mark_emitted()
            effect.mark_accepted()
        domain.complete_accepted_effect(execution.FLYING, lambda: True)
    require(domain.phase == execution.FLYING, "fixture must establish flying phase")
    return domain


def recover_after_ambiguity(domain: execution.PhysicalExecutionDomain) -> None:
    require(
        domain.phase == execution.RECOVERY_REQUIRED,
        "ambiguous effect must force recovery-required",
    )
    domain.run_reset_establishment(lambda: object())
    with domain.effect_transaction(lambda: None) as effect:
        effect.mark_emitted()
        effect.mark_accepted()
    domain.complete_accepted_effect(execution.FLYING, lambda: True)


def complete_motion(domain: execution.PhysicalExecutionDomain) -> None:
    require(
        domain.phase == execution.AWAITING_COMPLETION,
        "positive acknowledgement must await fresh completion",
    )
    domain.complete_accepted_effect(execution.FLYING, lambda: True)


def make_supervisor_reader(cf: FakeCrazyflie, epoch: Epoch):
    reader = supervisor_state.FreshSupervisorStateReader(
        cf,
        epoch,
        crtp_types=(Packet, SimpleNamespace(SUPERVISOR=0x0E)),
    )
    state = SimpleNamespace(blocking_fault=False, is_flying=True)
    reader.read = lambda *, timeout_seconds=0.2: state
    return reader, state


def mint_powered_session(cf: FakeCrazyflie, epoch: Epoch):
    factory = powered.TrustedPoweredSessionFactory(
        require_flight_known_inactive=lambda: True,
        invalidate_prior_evidence=lambda: None,
        stm_deck_power_cycle=lambda: None,
        open_post_reset_session=lambda: cf,
        close_post_reset_session=lambda _session: None,
        read_connection_epoch=lambda session: epoch(),
        read_capabilities=lambda session: {
            "connected": True,
            "executionAuthority": False,
            "identity": {
                "model": "crazyflie-2.1",
                "modelEvidence": "verified",
            },
            "evidence": {
                "systemSelfTestPassed": True,
                "protocolVersion": 12,
            },
        },
        assert_bound_preflight=lambda session, current_epoch: True,
        read_fresh_supervisor=lambda session, current_epoch: SimpleNamespace(
            blocking_fault=False
        ),
        identity_factory=lambda: unique("powered"),
    )
    return factory.establish()


class Fixture:
    def __init__(
        self,
        label: str,
        cf: FakeCrazyflie,
        *,
        packet_factory=None,
    ) -> None:
        self.cf = cf
        self.epoch = Epoch(unique(label))
        self.domain = ensure_flying()
        self.powered = mint_powered_session(cf, self.epoch)
        self.supervisor_reader, self.supervisor_state = make_supervisor_reader(
            cf,
            self.epoch,
        )
        self.watchdog = watchdog.EmergencyWatchdogLivenessGuard(
            cf,
            self.epoch,
            self.supervisor_reader,
            self.powered.watchdog_authority,
            keepalive_interval_seconds=0.2,
            max_host_gap_seconds=0.7,
        )
        self.watchdog.activate(supervisor_timeout_seconds=0.05)
        self.binding = teacher.PhysicalRunBinding(
            profile_id="activity-1",
            ast_binding=unique("ast"),
            connection_epoch=self.epoch(),
        )
        self.authorizer = teacher.TrustedTeacherAuthorizer()
        self.authorization = self.authorizer.authorize_run(
            self.binding,
            lambda _binding: True,
        )
        self.current_binding = self.binding
        self.current_preflight_factory = current_preflight.TrustedCurrentProgramPreflightFactory(
            lambda: self.current_binding
        )
        self.current_preflight_guard = self.current_preflight_factory.bind(self.binding)
        self.safelink = safelink.LiveSafeLinkPrecondition(cf, self.epoch)
        self.ack = ack.HighLevelAckDomain(self.epoch)
        factory = packet_factory or (lambda request: Packet(request))
        self.transport = transport.TrustedSetpointHlTransport(
            crazyflie=cf,
            execution_domain=self.domain,
            acknowledgement_domain=self.ack,
            safelink_guard=self.safelink,
            teacher_authorization=self.authorization,
            powered_session=self.powered,
            watchdog_guard=self.watchdog,
            supervisor_reader=self.supervisor_reader,
            current_preflight_guard=self.current_preflight_guard,
            packet_factory=factory,
        )

    def close(self) -> None:
        try:
            self.watchdog.stop_for_terminal_reboot(join_timeout_seconds=0.2)
        except watchdog.WatchdogLivenessError:
            pass


def unpack_go_to(cf: FakeCrazyflie):
    require(len(cf.send_calls) == 1, "exactly one physical packet must be emitted")
    packet = cf.send_calls[0][0][0]
    return struct.unpack("<BBBBfffff", bytes(packet.data))


def test_turn_acceptance_uses_semantics_timing_and_requires_completion() -> None:
    cf = FakeCrazyflie(reply_status=0)
    fixture = Fixture("turn-ok", cf)
    try:
        policy = timing.HighLevelTimingPolicy()
        result = fixture.transport.send_turn(angle_deg=90, timing_policy=policy)
        require(result.accepted, "zero firmware result must be accepted")
        command, group, relative, linear, x, y, z, angle, duration = unpack_go_to(cf)
        require((command, group, relative, linear) == (12, 0, 1, 0), "exact GO_TO_2 header")
        require(isclose(x, 0.0) and isclose(y, 0.0) and isclose(z, 0.0), "turn has no translation")
        require(isclose(angle, pi / 2, rel_tol=1e-6), "turn uses #256 relative yaw")
        require(
            isclose(duration, policy.turn_duration(90), rel_tol=1e-6),
            "turn duration uses #268 policy",
        )
        require(
            fixture.domain.phase == execution.AWAITING_COMPLETION,
            "acknowledgement is not trajectory completion",
        )
        complete_motion(fixture.domain)
    finally:
        fixture.close()


def test_horizontal_move_uses_fresh_yaw_and_horizontal_speed_policy() -> None:
    cf = FakeCrazyflie(reply_status=0)
    fixture = Fixture("move-ok", cf)
    try:
        observer = yaw.FreshYawObserver(cf, fixture.epoch)
        observer._bound_connection_epoch = fixture.epoch()
        observer._opened = True
        observer._config = object()
        observer.read = lambda *, timeout_seconds=0.5: yaw.YawObservation(
            fixture.epoch(),
            10,
            90.0,
            pi / 2,
        )
        policy = timing.HighLevelTimingPolicy(0.2)
        result = fixture.transport.send_horizontal_move(
            direction="forward",
            distance_m=0.2,
            yaw_reader=observer,
            timing_policy=policy,
        )
        require(result.accepted, "horizontal command accepted")
        _, _, _, _, x, y, z, angle, duration = unpack_go_to(cf)
        require(abs(x) < 1e-6 and isclose(y, 0.2, rel_tol=1e-6), "#256 rotates body move with fresh yaw")
        require(isclose(z, 0.0) and isclose(angle, 0.0), "horizontal move preserves relative z/yaw")
        require(
            isclose(duration, policy.horizontal_move_duration(0.2), rel_tol=1e-6),
            "horizontal duration uses current #268 speed state",
        )
        complete_motion(fixture.domain)
    finally:
        fixture.close()


def test_definitive_rejection_restores_flying_without_retry() -> None:
    cf = FakeCrazyflie(reply_status=22)
    fixture = Fixture("reject", cf)
    try:
        result = fixture.transport.send_turn(
            angle_deg=30,
            timing_policy=timing.HighLevelTimingPolicy(),
        )
        require(not result.accepted and result.status == 22, "non-zero firmware status is definitive rejection")
        require(fixture.domain.phase == execution.FLYING, "definitive rejection restores prior flying phase")
        require(len(cf.send_calls) == 1, "definitive rejection must never resend")
    finally:
        fixture.close()


def test_last_moment_safelink_failure_is_pre_effect() -> None:
    cf = FakeCrazyflie(reply_status=0)
    fixture = Fixture("safelink", cf)
    try:
        cf.link.needs_resending = True
        expect_error(
            lambda: fixture.transport.send_turn(
                angle_deg=20,
                timing_policy=timing.HighLevelTimingPolicy(),
            ),
            safelink.SafeLinkPreconditionError,
            "duplicate suppression",
        )
        require(not cf.send_calls, "missing SafeLink must prevent emission")
        require(fixture.domain.phase == execution.FLYING, "pre-effect SafeLink failure is neutral")
    finally:
        fixture.close()


def test_fresh_supervisor_fault_or_not_flying_blocks_send() -> None:
    for label, state, pattern in (
        ("fault", SimpleNamespace(blocking_fault=True, is_flying=True), "blocking"),
        ("not-flying", SimpleNamespace(blocking_fault=False, is_flying=False), "flight"),
    ):
        cf = FakeCrazyflie(reply_status=0)
        fixture = Fixture(label, cf)
        try:
            fixture.supervisor_reader.read = lambda *, timeout_seconds=0.2, state=state: state
            expect_error(
                lambda: fixture.transport.send_turn(
                    angle_deg=20,
                    timing_policy=timing.HighLevelTimingPolicy(),
                ),
                transport.SetpointHlTransportError,
                pattern,
            )
            require(not cf.send_calls, "fresh #257 failure must prevent emission")
            require(fixture.domain.phase == execution.FLYING, "fresh supervisor failure is pre-effect")
        finally:
            fixture.close()


def test_teacher_invalidation_during_request_construction_blocks_send() -> None:
    cf = FakeCrazyflie(reply_status=0)
    fixture = Fixture("teacher-race", cf)
    try:
        policy = timing.HighLevelTimingPolicy()
        original = policy.turn_duration

        def invalidate_then_duration(angle):
            fixture.authorization.invalidate("teacher withdrew run")
            return original(angle)

        policy.turn_duration = invalidate_then_duration
        expect_error(
            lambda: fixture.transport.send_turn(angle_deg=20, timing_policy=policy),
            teacher.TeacherRunAuthorizationError,
            "teacher withdrew run",
        )
        require(not cf.send_calls, "teacher invalidation during builder must prevent send")
        require(fixture.domain.phase == execution.FLYING, "late authority failure remains pre-effect")
    finally:
        fixture.close()


def test_watchdog_terminal_during_request_construction_blocks_send() -> None:
    cf = FakeCrazyflie(reply_status=0)
    fixture = Fixture("watchdog-race", cf)
    try:
        policy = timing.HighLevelTimingPolicy()
        original = policy.turn_duration

        def terminate_then_duration(angle):
            fixture.watchdog.stop_for_terminal_reboot(join_timeout_seconds=0.2)
            return original(angle)

        policy.turn_duration = terminate_then_duration
        expect_error(
            lambda: fixture.transport.send_turn(angle_deg=20, timing_policy=policy),
            watchdog.WatchdogLivenessError,
            "terminal",
        )
        require(not cf.send_calls, "watchdog terminal transition during builder must prevent send")
        require(fixture.domain.phase == execution.FLYING, "late watchdog failure remains pre-effect")
    finally:
        fixture.close()


def test_packet_factory_cannot_substitute_port_or_data() -> None:
    cases = (
        ("port", lambda request: Packet(request, port=0x07), "non-SETPOINT_HL"),
        ("data", lambda request: Packet(request[:-1] + b"\x00"), "substituted"),
    )
    for label, factory, pattern in cases:
        cf = FakeCrazyflie(reply_status=0)
        fixture = Fixture("packet-" + label, cf, packet_factory=factory)
        try:
            expect_error(
                lambda: fixture.transport.send_turn(
                    angle_deg=20,
                    timing_policy=timing.HighLevelTimingPolicy(),
                ),
                transport.SetpointHlTransportError,
                pattern,
            )
            require(not cf.send_calls, "packet-factory substitution must never reach send_packet")
            require(fixture.domain.phase == execution.FLYING, "invalid packet is pre-effect")
        finally:
            fixture.close()


def test_concrete_authority_and_exact_cf_bindings_are_required() -> None:
    cf = FakeCrazyflie(reply_status=0)
    fixture = Fixture("authority-types", cf)
    try:
        kwargs = dict(
            crazyflie=cf,
            execution_domain=fixture.domain,
            acknowledgement_domain=fixture.ack,
            safelink_guard=fixture.safelink,
            teacher_authorization=fixture.authorization,
            powered_session=fixture.powered,
            watchdog_guard=fixture.watchdog,
            supervisor_reader=fixture.supervisor_reader,
            current_preflight_guard=fixture.current_preflight_guard,
            packet_factory=lambda request: Packet(request),
        )
        for key, value, pattern in (
            ("teacher_authorization", object(), "TeacherRunAuthorization"),
            ("watchdog_guard", object(), "watchdog guard"),
            ("supervisor_reader", object(), "FreshSupervisorStateReader"),
            ("current_preflight_guard", object(), "current-program preflight guard"),
        ):
            candidate = dict(kwargs)
            candidate[key] = value
            expect_error(
                lambda candidate=candidate: transport.TrustedSetpointHlTransport(**candidate),
                transport.SetpointHlTransportError,
                pattern,
            )

        forged = powered.EstablishedPoweredSession(
            session=object(),
            connection_epoch=fixture.epoch(),
            watchdog_authority=fixture.powered.watchdog_authority,
        )
        candidate = dict(kwargs)
        candidate["powered_session"] = forged
        expect_error(
            lambda: transport.TrustedSetpointHlTransport(**candidate),
            transport.SetpointHlTransportError,
            "exact Crazyflie",
        )
        require(not cf.send_calls, "constructor authority counterexamples emit no command")
    finally:
        fixture.close()


def test_out_of_policy_commands_have_no_raw_effect_surface() -> None:
    cf = FakeCrazyflie(reply_status=0)
    fixture = Fixture("policy", cf)
    try:
        require(not hasattr(fixture.transport, "send_once"), "raw public send_once must not exist")
        for action in ("send_takeoff", "send_land", "send_vertical", "send_stop"):
            require(not hasattr(fixture.transport, action), "unsupported command surface leaked: " + action)
        expect_error(
            lambda: fixture.transport.send_turn(
                angle_deg=180,
                timing_policy=timing.HighLevelTimingPolicy(),
            ),
            ValueError,
            "bounds",
        )
        require(not cf.send_calls, "out-of-policy but structurally possible command must not emit")
    finally:
        fixture.close()


def test_timeout_send_failure_and_wrong_reply_are_ambiguous_without_retry() -> None:
    cases = (
        ("timeout", FakeCrazyflie(reply_status=None), ack.HighLevelAckError, "timeout"),
        ("send", FakeCrazyflie(send_error=RuntimeError("radio enqueue failed")), RuntimeError, "radio enqueue failed"),
        (
            "reply",
            FakeCrazyflie(explicit_reply=b"\x7f\x00\x00\x00"),
            ack.HighLevelAckError,
            "prefix",
        ),
    )
    for label, cf, error_type, pattern in cases:
        fixture = Fixture("ambiguous-" + label, cf)
        try:
            expect_error(
                lambda: fixture.transport.send_turn(
                    angle_deg=20,
                    timing_policy=timing.HighLevelTimingPolicy(),
                    reply_timeout_seconds=0.03,
                ),
                error_type,
                pattern,
            )
            require(len(cf.send_calls) == 1, "ambiguous command is emitted exactly once")
            require(fixture.domain.phase == execution.RECOVERY_REQUIRED, "ambiguous command poisons execution state")
            require(fixture.ack.poisoned, "ambiguous command poisons #271 epoch freshness")
            recover_after_ambiguity(fixture.domain)
        finally:
            fixture.close()


def test_source_has_one_effect_primitive_and_no_retry_or_raw_command_api() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    require(
        source.count("\n                    send_packet(packet)\n") == 1,
        "one ordinary physical send site",
    )
    for forbidden in (
        "def send_once(",
        "_COMMAND_TAKEOFF",
        "_COMMAND_LAND",
        "_COMMAND_STOP",
        "def send_takeoff(",
        "def send_land(",
        "def send_vertical(",
        "expected_reply=",
        "HighLevelCommander(",
        "send_emergency_stop(",
    ):
        require(forbidden not in source, "forbidden raw/retry/effect surface: " + forbidden)
    for required in (
        "LiveCurrentProgramPreflightGuard",
        "TeacherRunAuthorization",
        "EstablishedPoweredSession",
        "EmergencyWatchdogLivenessGuard",
        "FreshSupervisorStateReader",
        "LiveSafeLinkPrecondition",
        "HighLevelAckDomain",
        "body_relative_move",
        "relative_turn",
        "horizontal_move_duration",
        "turn_duration",
        "packet factory substituted",
        "fresh supervisor",
    ):
        require(required in source, "missing concrete transport contract: " + required)


def main() -> int:
    test_turn_acceptance_uses_semantics_timing_and_requires_completion()
    test_horizontal_move_uses_fresh_yaw_and_horizontal_speed_policy()
    test_definitive_rejection_restores_flying_without_retry()
    test_last_moment_safelink_failure_is_pre_effect()
    test_fresh_supervisor_fault_or_not_flying_blocks_send()
    test_teacher_invalidation_during_request_construction_blocks_send()
    test_watchdog_terminal_during_request_construction_blocks_send()
    test_packet_factory_cannot_substitute_port_or_data()
    test_concrete_authority_and_exact_cf_bindings_are_required()
    test_out_of_policy_commands_have_no_raw_effect_surface()
    test_timeout_send_failure_and_wrong_reply_are_ambiguous_without_retry()
    test_source_has_one_effect_primitive_and_no_retry_or_raw_command_api()
    print(
        "PASS trusted SETPOINT_HL transport binds concrete authority, fresh safety, "
        "validated semantics and exactly one no-retry in-flight effect"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

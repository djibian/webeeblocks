#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from math import isclose, pi
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(PHYSICAL))

import high_level_ack as ack  # noqa: E402
import high_level_timing as timing  # noqa: E402
import physical_execution_domain as execution  # noqa: E402
import powered_session_authority as powered  # noqa: E402
import safelink_precondition as safelink  # noqa: E402
import serve_reference_capabilities as capability_bridge  # noqa: E402
import setpoint_hl_transport as transport  # noqa: E402
import supervisor_state  # noqa: E402
import teacher_run_authorization as teacher  # noqa: E402
import watchdog_liveness as watchdog  # noqa: E402
import yaw_observer as yaw  # noqa: E402

HOST = PHYSICAL / "serve_physical_host.py"
BRIDGE = PHYSICAL / "serve_reference_capabilities.py"
TRANSPORT = PHYSICAL / "setpoint_hl_transport.py"


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
    def __init__(self, *, reply_status: int | None = 0, send_error=None, needs_resending=False) -> None:
        self.link_uri = "radio://0/80/2M/E7E7E7E7E7"
        self.link = Link(needs_resending)
        self.connected = True
        self.reply_status = reply_status
        self.send_error = send_error
        self.callbacks: dict[int, list] = {}
        self.send_calls: list[tuple[tuple, dict]] = []
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

    def send_packet(self, *args, **kwargs):
        require(len(args) == 1, "transport must send exactly one packet argument")
        require(not kwargs, "transport must not use expected_reply/retry kwargs")
        require(bool(self.callbacks.get(0x08)), "reply callback must precede send")
        self.send_calls.append((args, kwargs))
        if self.send_error is not None:
            raise self.send_error
        if self.reply_status is None:
            return
        request = bytes(args[0].data)
        reply = Packet(request[:3] + bytes((self.reply_status,)))
        for callback in tuple(self.callbacks.get(0x08, ())):
            callback(reply)


class FakeCapabilitySession:
    def __init__(self, epoch: Epoch) -> None:
        self.epoch = epoch

    def read_connection_epoch(self) -> str:
        return self.epoch()


_counter = 0


def unique(label: str) -> str:
    global _counter
    _counter += 1
    return f"transport-{label}-{_counter}"


def state(*, blocking_fault=False, is_flying=True, hl_control_active=True, hl_traj_finished=True):
    return SimpleNamespace(
        bitfield=0,
        blocking_fault=blocking_fault,
        is_flying=is_flying,
        hl_control_active=hl_control_active,
        hl_traj_finished=hl_traj_finished,
    )


def ensure_flying() -> execution.PhysicalExecutionDomain:
    domain = execution.PhysicalExecutionDomain()
    if domain.phase == execution.AWAITING_COMPLETION:
        raise AssertionError("fixture inherited unowned accepted effect")
    if domain.phase == execution.RECOVERY_REQUIRED:
        domain.run_reset_establishment(lambda: object())
    if domain.phase == execution.INACTIVE:
        with domain.effect_transaction(lambda: None) as effect:
            effect.mark_emitted()
            permit = effect.mark_accepted()
        domain.complete_accepted_effect(permit, execution.FLYING, lambda: True)
    require(domain.phase == execution.FLYING, "fixture must establish flying phase")
    return domain


def make_supervisor_reader(cf: FakeCrazyflie, epoch: Epoch):
    reader = supervisor_state.FreshSupervisorStateReader(
        cf,
        epoch,
        crtp_types=(Packet, SimpleNamespace(SUPERVISOR=0x0E)),
    )
    queued: list[object] = []
    observed: list[object] = []

    def read(*, timeout_seconds=0.2):
        current = queued.pop(0) if queued else state()
        observed.append(current)
        return current

    reader.read = read
    return reader, queued, observed


def mint_powered_session(cf: FakeCrazyflie, epoch: Epoch):
    factory = powered.TrustedPoweredSessionFactory(
        require_flight_known_inactive=lambda: True,
        invalidate_prior_evidence=lambda: None,
        stm_deck_power_cycle=lambda: None,
        open_post_reset_session=lambda: cf,
        close_post_reset_session=lambda _session: None,
        read_connection_epoch=lambda _session: epoch(),
        read_capabilities=lambda _session: {
            "connected": True,
            "executionAuthority": False,
            "identity": {"model": "crazyflie-2.1", "modelEvidence": "verified"},
            "evidence": {"systemSelfTestPassed": True, "protocolVersion": 12},
        },
        assert_bound_preflight=lambda _session, _epoch: True,
        read_fresh_supervisor=lambda _session, _epoch: SimpleNamespace(blocking_fault=False),
        identity_factory=lambda: unique("powered"),
    )
    return factory.establish()


class TestHostBoundTransport(transport.TrustedSetpointHlTransport):
    """Test-only analogue of the lexical subclass in serve_physical_host.py."""

    def __init__(self, *, bridge, current_binding, **kwargs) -> None:
        self._test_bridge = bridge
        self._test_current_binding = current_binding
        super().__init__(**kwargs)

    def _read_current_binding(self):
        binding = self.teacher_binding
        try:
            evidence = self._test_bridge.assert_current_program(
                profile_id=binding.profile_id,
                ast_binding=binding.ast_binding,
                connection_epoch=binding.connection_epoch,
                timeout_seconds=0.25,
            )
        except Exception as exc:
            raise transport.SetpointHlTransportError(
                "integrated #278/#249 current-program re-assertion failed"
            ) from exc
        if type(evidence) is not capability_bridge.CurrentProgramPreflightEvidence:
            raise transport.SetpointHlTransportError("invalid current-program evidence")
        if evidence.execution_authority is not False:
            raise transport.SetpointHlTransportError("current-program evidence became authority")
        if (
            evidence.profile_id != binding.profile_id
            or evidence.ast_binding != binding.ast_binding
            or evidence.connection_epoch != binding.connection_epoch
        ):
            raise transport.SetpointHlTransportError("current-program binding mismatch")
        return binding


class Fixture:
    def __init__(self, label: str, cf: FakeCrazyflie) -> None:
        self.cf = cf
        self.epoch = Epoch(unique(label))
        self.domain = ensure_flying()
        self.powered = mint_powered_session(cf, self.epoch)
        self.supervisor_reader, self.supervisor_reads, self.supervisor_observed = make_supervisor_reader(cf, self.epoch)
        self.watchdog = watchdog.EmergencyWatchdogLivenessGuard(
            cf,
            self.epoch,
            self.supervisor_reader,
            self.powered.watchdog_authority,
            keepalive_interval_seconds=0.2,
            max_host_gap_seconds=0.7,
        )
        self.watchdog.activate(supervisor_timeout_seconds=0.05)
        self.supervisor_reads.extend(
            [
                state(hl_traj_finished=True),
                state(hl_traj_finished=True),
                state(hl_traj_finished=False),
                state(hl_traj_finished=True),
            ]
        )
        self.binding = teacher.PhysicalRunBinding(
            profile_id="activity-1",
            ast_binding=unique("ast"),
            connection_epoch=self.epoch(),
        )
        self.authorizer = teacher.TrustedTeacherAuthorizer()
        self.authorization = self.authorizer.authorize_run(self.binding, lambda _binding: True)
        self.current_binding = self.binding
        self.bridge = capability_bridge.ReadOnlyCapabilityHttpBridge(
            FakeCapabilitySession(self.epoch),
            token=unique("capability"),
            preflight_responder_token=unique("responder"),
        )
        self.bridge_thread = Thread(target=self.bridge.serve_forever, daemon=True)
        self.bridge_thread.start()
        self.stop = Event()

        def answer() -> None:
            while not self.stop.is_set():
                try:
                    challenge = self.bridge._claim_current_program_challenge(timeout_seconds=0.05)
                except capability_bridge.CapabilityBridgeError:
                    return
                if challenge is None:
                    continue
                current = self.current_binding
                try:
                    self.bridge._submit_current_program_assertion(
                        {
                            "challengeId": challenge,
                            "ok": True,
                            "profileId": current.profile_id,
                            "astBinding": current.ast_binding,
                            "connectionEpoch": current.connection_epoch,
                            "executionAuthority": False,
                        }
                    )
                except capability_bridge.CapabilityBridgeError:
                    pass

        self.responder_thread = Thread(target=answer, daemon=True)
        self.responder_thread.start()
        self.safelink = safelink.LiveSafeLinkPrecondition(cf, self.epoch)
        self.ack = ack.HighLevelAckDomain(self.epoch)
        self.kwargs = dict(
            crazyflie=cf,
            execution_domain=self.domain,
            acknowledgement_domain=self.ack,
            safelink_guard=self.safelink,
            teacher_authorization=self.authorization,
            powered_session=self.powered,
            watchdog_guard=self.watchdog,
            supervisor_reader=self.supervisor_reader,
        )
        self.transport = TestHostBoundTransport(
            bridge=self.bridge,
            current_binding=self.current_binding,
            **self.kwargs,
        )

    def close(self) -> None:
        try:
            self.watchdog.stop_for_terminal_reboot(join_timeout_seconds=0.2)
        except watchdog.WatchdogLivenessError:
            pass
        self.stop.set()
        self.bridge.shutdown()
        self.responder_thread.join(timeout=1.0)
        self.bridge_thread.join(timeout=1.0)


def unpack_go_to(cf: FakeCrazyflie):
    require(len(cf.send_calls) == 1, "exactly one physical packet must be emitted")
    return struct.unpack("<BBBBfffff", bytes(cf.send_calls[0][0][0].data))


transport._default_packet_factory = lambda request: Packet(request)
transport._COMPLETION_POLL_SECONDS = 0.001


def test_direct_core_has_no_positive_provenance_path() -> None:
    cf = FakeCrazyflie(reply_status=0)
    fixture = Fixture("unbound", cf)
    try:
        core = transport.TrustedSetpointHlTransport(**fixture.kwargs)
        expect_error(
            lambda: core.send_turn(angle_deg=20, timing_policy=timing.HighLevelTimingPolicy()),
            transport.SetpointHlTransportError,
            "trusted #283 physical host",
        )
        require(not cf.send_calls, "unbound importable core must not emit")

        try:
            transport.TrustedSetpointHlTransport(
                **fixture.kwargs,
                current_program_preflight=fixture.bridge,
            )
        except TypeError:
            pass
        else:
            raise AssertionError("caller-selected bridge/provenance input must not exist")
    finally:
        fixture.close()


def test_turn_uses_exact_go_to_and_causal_completion() -> None:
    cf = FakeCrazyflie(reply_status=0)
    fixture = Fixture("turn", cf)
    try:
        policy = timing.HighLevelTimingPolicy()
        result = fixture.transport.send_turn(angle_deg=90, timing_policy=policy)
        require(result.accepted, "zero firmware result accepted")
        command, group, relative, linear, x, y, z, angle, duration = unpack_go_to(cf)
        require((command, group, relative, linear) == (12, 0, 1, 0), "exact GO_TO_2 header")
        require(isclose(x, 0.0) and isclose(y, 0.0) and isclose(z, 0.0), "turn has no translation")
        require(isclose(angle, pi / 2, rel_tol=1e-6), "#256 signed relative yaw")
        require(isclose(duration, policy.turn_duration(90), rel_tol=1e-6), "#268 duration")
        require(
            any(getattr(item, "hl_traj_finished", None) is False for item in fixture.supervisor_observed),
            "accepted trajectory must be observed in progress before completion",
        )
        require(fixture.domain.phase == execution.FLYING, "completion restores flying")
    finally:
        fixture.close()


def test_horizontal_move_consumes_fresh_yaw() -> None:
    cf = FakeCrazyflie(reply_status=0)
    fixture = Fixture("move", cf)
    try:
        observer = yaw.FreshYawObserver(cf, fixture.epoch)
        observer._bound_connection_epoch = fixture.epoch()
        observer._opened = True
        observer._config = object()
        observer.read = lambda *, timeout_seconds=0.5: yaw.YawObservation(
            fixture.epoch(), 10, 90.0, pi / 2
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
        require(abs(x) < 1e-6 and isclose(y, 0.2, rel_tol=1e-6), "body move uses fresh yaw")
        require(isclose(z, 0.0) and isclose(angle, 0.0), "horizontal move preserves z/yaw")
        require(isclose(duration, policy.horizontal_move_duration(0.2), rel_tol=1e-6), "speed policy preserved")
    finally:
        fixture.close()


def test_browser_binding_change_blocks_before_effect() -> None:
    cf = FakeCrazyflie(reply_status=0)
    fixture = Fixture("binding", cf)
    try:
        fixture.current_binding = teacher.PhysicalRunBinding(
            profile_id=fixture.binding.profile_id,
            ast_binding=unique("changed-ast"),
            connection_epoch=fixture.binding.connection_epoch,
        )
        expect_error(
            lambda: fixture.transport.send_turn(angle_deg=20, timing_policy=timing.HighLevelTimingPolicy()),
            transport.SetpointHlTransportError,
            "current-program re-assertion",
        )
        require(not cf.send_calls, "changed browser program must prevent effect")
    finally:
        fixture.close()


def test_definitive_rejection_is_one_shot() -> None:
    cf = FakeCrazyflie(reply_status=22)
    fixture = Fixture("reject", cf)
    try:
        result = fixture.transport.send_turn(angle_deg=30, timing_policy=timing.HighLevelTimingPolicy())
        require(not result.accepted and result.status == 22, "non-zero status is definitive rejection")
        require(len(cf.send_calls) == 1, "definitive rejection is never resent")
        require(fixture.domain.phase == execution.FLYING, "definitive rejection restores prior phase")
    finally:
        fixture.close()


def test_timeout_is_ambiguous_and_never_retried() -> None:
    cf = FakeCrazyflie(reply_status=None)
    fixture = Fixture("timeout", cf)
    try:
        expect_error(
            lambda: fixture.transport.send_turn(
                angle_deg=20,
                timing_policy=timing.HighLevelTimingPolicy(),
                reply_timeout_seconds=0.02,
            ),
            ack.HighLevelAckError,
            "timeout",
        )
        require(len(cf.send_calls) == 1, "ambiguous effect is emitted exactly once")
        require(fixture.ack.poisoned, "ambiguous acknowledgement poisons epoch")
        require(fixture.domain.phase == execution.RECOVERY_REQUIRED, "ambiguous effect requires recovery")
    finally:
        fixture.close()


def test_safelink_and_policy_fail_before_effect() -> None:
    cf = FakeCrazyflie(reply_status=0, needs_resending=True)
    fixture = Fixture("safelink", cf)
    try:
        expect_error(
            lambda: fixture.transport.send_turn(angle_deg=20, timing_policy=timing.HighLevelTimingPolicy()),
            safelink.SafeLinkPreconditionError,
            "duplicate suppression",
        )
        require(not cf.send_calls, "missing SafeLink blocks emission")
    finally:
        fixture.close()

    cf = FakeCrazyflie(reply_status=0)
    fixture = Fixture("policy", cf)
    try:
        expect_error(
            lambda: fixture.transport.send_turn(angle_deg=180, timing_policy=timing.HighLevelTimingPolicy()),
            ValueError,
            "bounds",
        )
        require(not cf.send_calls, "out-of-policy command blocks emission")
    finally:
        fixture.close()


def test_production_source_roots_provenance_only_in_host_tcb() -> None:
    host_source = HOST.read_text(encoding="utf-8")
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    transport_source = TRANSPORT.read_text(encoding="utf-8")

    for forbidden in (
        "CurrentProgramEffectPreflightHandle",
        "_bind_effect_current_program_bridge",
        "CurrentProgramProvenanceClient",
    ):
        require(forbidden not in bridge_source, "read-only bridge exposes obsolete provenance surface: " + forbidden)
        require(forbidden not in host_source, "physical host retains obsolete provenance surface: " + forbidden)
        require(forbidden not in transport_source, "effect core retains obsolete provenance surface: " + forbidden)

    require(
        "class _HostBoundSetpointHlTransport(TrustedSetpointHlTransport)" in host_source,
        "production host must define the co-located #276 transport binding",
    )
    require(
        "evidence = bridge.assert_current_program(" in host_source,
        "host-local transport must use the lexical #278 bridge",
    )
    require(
        "def _compose_inflight_setpoint_transport(" in host_source,
        "host must own the #276 composition closure",
    )
    compose_source = host_source.split("def _compose_inflight_setpoint_transport(", 1)[1].split("):", 1)[0]
    require("bridge" not in compose_source, "caller-selectable bridge must not enter composition signature")
    require("current_program" not in compose_source, "caller-selectable provenance must not enter composition signature")
    require(
        "def _read_current_binding(self)" in transport_source
        and "current-program assertion is not bound to the trusted #283 physical host" in transport_source,
        "direct effect core must fail closed without host-local provenance override",
    )
    require(
        "current_program_preflight" not in transport_source,
        "effect core constructor/source must not retain caller-selected preflight handle",
    )
    require(transport_source.count("\n                    send_packet(packet)\n") == 1, "exactly one ordinary send site")
    for forbidden_effect in (
        "def send_once(",
        "def send_takeoff(",
        "def send_land(",
        "def send_vertical(",
        "expected_reply=",
        "HighLevelCommander(",
    ):
        require(forbidden_effect not in transport_source, "forbidden raw/retry/effect surface: " + forbidden_effect)

    spec = importlib.util.spec_from_file_location("physical_host_import_probe_276", HOST)
    require(spec is not None and spec.loader is not None, "host import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for forbidden_attr in (
        "TrustedSetpointHlTransport",
        "_HostBoundSetpointHlTransport",
        "compose_inflight_setpoint_transport",
        "ReadOnlyCapabilityHttpBridge",
        "bridge",
        "session",
    ):
        require(not hasattr(module, forbidden_attr), "imported host leaks TCB composition: " + forbidden_attr)


def main() -> int:
    test_direct_core_has_no_positive_provenance_path()
    test_turn_uses_exact_go_to_and_causal_completion()
    test_horizontal_move_consumes_fresh_yaw()
    test_browser_binding_change_blocks_before_effect()
    test_definitive_rejection_is_one_shot()
    test_timeout_is_ambiguous_and_never_retried()
    test_safelink_and_policy_fail_before_effect()
    test_production_source_roots_provenance_only_in_host_tcb()
    print(
        "PASS trusted SETPOINT_HL transport is co-located under #283 provenance, "
        "concrete safety authority and one-shot causal completion"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import inspect
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(PHYSICAL))

import high_level_ack as ack  # noqa: E402
import physical_execution_domain as execution  # noqa: E402
import powered_session_authority as powered  # noqa: E402
import safelink_precondition as safelink  # noqa: E402
import supervisor_state  # noqa: E402
import teacher_run_authorization as teacher  # noqa: E402
import takeoff_transport as transport  # noqa: E402
import watchdog_liveness as watchdog  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class FakePacket:
    def __init__(self) -> None:
        self.port = None
        self.data = b""


class FakePort:
    SETPOINT_HL = 0x08


class CallbackSet:
    def __init__(self) -> None:
        self.callbacks = []

    def add_callback(self, callback) -> None:
        self.callbacks.append(callback)

    def remove_callback(self, callback) -> None:
        self.callbacks.remove(callback)


class FakeCrazyflie:
    def __init__(self, *, status: int = 0) -> None:
        self.status = status
        self.link_uri = "radio://0/80/2M/E7E7E7E7E7"
        self.link = SimpleNamespace(needs_resending=False)
        self.disconnected = CallbackSet()
        self.platform = SimpleNamespace(get_protocol_version=lambda: 12)
        self.supervisor = SimpleNamespace(send_emergency_stop_watchdog=lambda: None)
        self.callbacks = {}
        self.send_calls = []
        self.connected = True

    def is_connected(self) -> bool:
        return self.connected

    def add_port_callback(self, port, callback) -> None:
        self.callbacks.setdefault(port, []).append(callback)

    def remove_port_callback(self, port, callback) -> None:
        self.callbacks[port].remove(callback)

    def send_packet(self, packet) -> None:
        self.send_calls.append(bytes(packet.data))
        if packet.port == 0x08:
            reply = SimpleNamespace(data=bytes(packet.data[:3]) + bytes([self.status]))
            for callback in tuple(self.callbacks.get(0x08, ())):
                callback(reply)


def install_fake_cflib() -> None:
    cflib = ModuleType("cflib")
    crtp = ModuleType("cflib.crtp")
    crtpstack = ModuleType("cflib.crtp.crtpstack")
    crtpstack.CRTPPacket = FakePacket
    crtpstack.CRTPPort = FakePort
    cflib.crtp = crtp
    crtp.crtpstack = crtpstack
    sys.modules["cflib"] = cflib
    sys.modules["cflib.crtp"] = crtp
    sys.modules["cflib.crtp.crtpstack"] = crtpstack


def canonical_ast(height: float = 0.8) -> str:
    return json.dumps(
        {
            "version": 1,
            "semantics": "webeeblocks-ast-v1",
            "program": [{"kind": "takeoff", "height_m": height}, {"kind": "land"}],
        },
        separators=(",", ":"),
        sort_keys=True,
    )


class Fixture:
    def __init__(self, name: str, *, status: int = 0) -> None:
        install_fake_cflib()
        self.cf = FakeCrazyflie(status=status)
        self.epoch_value = "epoch-" + name
        self.binding = teacher.PhysicalRunBinding(
            "activity-1", canonical_ast(), self.epoch_value
        )
        self.authorizer = teacher.TrustedTeacherAuthorizer()
        self.authorization = self.authorizer.authorize_run(
            self.binding, lambda _binding: True
        )
        lifecycle = powered.EphemeralPoweredSessionWatchdogAuthority(
            "powered-" + name,
            _factory_token=getattr(powered, "_FACTORY_TOKEN"),
        )
        self.powered = powered.EstablishedPoweredSession(
            session=self.cf,
            connection_epoch=self.epoch_value,
            watchdog_authority=lifecycle,
        )
        self.supervisor = supervisor_state.FreshSupervisorStateReader(
            self.cf,
            self.epoch,
            crtp_types=(FakePacket, FakePort),
        )
        self.supervisor._read_once = lambda _timeout: supervisor_state.decode_supervisor_state(
            12,
            (1 << supervisor_state.BIT_CAN_FLY),
        )
        # The real guard constructor must see the exact freshly reset NEW
        # powered-session lifecycle.  Only after that identity composition has
        # succeeded do deterministic tests advance the lifecycle to ACTIVE and
        # replace the asynchronous keepalive oracle with a local exact one.
        self.watchdog = watchdog.EmergencyWatchdogLivenessGuard(
            self.cf,
            self.epoch,
            self.supervisor,
            lifecycle,
        )
        lifecycle.begin_activation()
        lifecycle.mark_active()
        self.watchdog.assert_live = lambda: None
        self.safelink = safelink.LiveSafeLinkPrecondition(self.cf, self.epoch)
        self.ack = ack.HighLevelAckDomain(self.epoch)
        self.execution = execution.PhysicalExecutionDomain()
        execution._PROCESS_STATE.phase = execution.INACTIVE
        execution._PROCESS_STATE.pending_completion = None
        execution._PROCESS_STATE.active_section = None
        execution._PROCESS_STATE.section_owner = None
        self.current_assertions = 0

    def epoch(self) -> str:
        return self.epoch_value

    def read_current_binding(self):
        self.current_assertions += 1
        return self.binding

    def queue_states(self, *states) -> None:
        values = list(states)

        def read(_timeout):
            require(values, "unexpected supervisor read")
            return values.pop(0)

        self.supervisor._read_once = read

    def state(
        self,
        *,
        can_fly: bool = True,
        flying: bool = False,
        hl_active: bool = False,
        finished: bool = False,
        fault: bool = False,
    ):
        bitfield = 0
        if can_fly:
            bitfield |= 1 << supervisor_state.BIT_CAN_FLY
        if flying:
            bitfield |= 1 << supervisor_state.BIT_IS_FLYING
        if hl_active:
            bitfield |= 1 << supervisor_state.BIT_HL_CONTROL_ACTIVE
        if finished:
            bitfield |= 1 << supervisor_state.BIT_HL_TRAJ_FINISHED
        if fault:
            bitfield |= 1 << supervisor_state.BIT_IS_CRASHED
        return supervisor_state.decode_supervisor_state(12, bitfield)


class HostBoundTakeoffTransport(transport.TrustedTakeoffTransport):
    def __init__(self, fixture: Fixture) -> None:
        self._fixture = fixture
        super().__init__(
            crazyflie=fixture.cf,
            execution_domain=fixture.execution,
            acknowledgement_domain=fixture.ack,
            safelink_guard=fixture.safelink,
            teacher_authorization=fixture.authorization,
            powered_session=fixture.powered,
            watchdog_guard=fixture.watchdog,
            supervisor_reader=fixture.supervisor,
        )

    def _read_current_binding(self):
        return self._fixture.read_current_binding()


def expect_transport_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except Exception as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError("expected transport error containing " + repr(pattern))


def test_importable_core_has_no_positive_provenance_path() -> None:
    fixture = Fixture("base")
    base = transport.TrustedTakeoffTransport(
        crazyflie=fixture.cf,
        execution_domain=fixture.execution,
        acknowledgement_domain=fixture.ack,
        safelink_guard=fixture.safelink,
        teacher_authorization=fixture.authorization,
        powered_session=fixture.powered,
        watchdog_guard=fixture.watchdog,
        supervisor_reader=fixture.supervisor,
    )
    expect_transport_error(base.send_from_authorized_ast, "trusted #283 physical host")
    require(not fixture.cf.send_calls, "direct importable core cannot emit")


def test_positive_ack_requires_causal_flying_completion() -> None:
    fixture = Fixture("positive")
    fixture.queue_states(
        fixture.state(),
        fixture.state(flying=True, hl_active=True, finished=False),
        fixture.state(flying=True, hl_active=True, finished=True),
    )
    result = HostBoundTakeoffTransport(fixture).send_from_authorized_ast()
    require(result.accepted, "takeoff command accepted")
    require(
        fixture.execution.phase == execution.FLYING,
        "causal completion advances to flying",
    )
    require(len(fixture.cf.send_calls) == 1, "exactly one command packet emitted")
    require(fixture.cf.send_calls[0][0] == 9, "exact command-9 packet emitted")
    require(
        fixture.current_assertions >= 2,
        "current program reasserted inside effect transaction",
    )


def test_first_post_ack_flying_finished_is_causal_from_not_flying_baseline() -> None:
    fixture = Fixture("immediate")
    fixture.queue_states(
        fixture.state(),
        fixture.state(flying=True, hl_active=True, finished=True),
    )
    result = HostBoundTakeoffTransport(fixture).send_from_authorized_ast()
    require(result.accepted, "fresh flying+finished sample may complete takeoff")
    require(
        fixture.execution.phase == execution.FLYING,
        "exact #279 permit reaches flying",
    )


def test_definitive_rejection_restores_inactive() -> None:
    fixture = Fixture("reject", status=7)
    fixture.queue_states(fixture.state())
    result = HostBoundTakeoffTransport(fixture).send_from_authorized_ast()
    require(
        not result.accepted and result.status == 7,
        "firmware rejection is definitive",
    )
    require(
        fixture.execution.phase == execution.INACTIVE,
        "definitive rejection restores inactive",
    )
    require(len(fixture.cf.send_calls) == 1, "rejection still has exactly one send")


def test_preconditions_fail_before_effect() -> None:
    cases = (
        ("fault", lambda f: f.queue_states(f.state(fault=True)), "fault"),
        ("nofly", lambda f: f.queue_states(f.state(can_fly=False)), "permit flight"),
        (
            "already",
            lambda f: f.queue_states(f.state(flying=True, hl_active=True)),
            "not-flying",
        ),
        ("hl", lambda f: f.queue_states(f.state(hl_active=True)), "high-level"),
    )
    for name, prepare, pattern in cases:
        fixture = Fixture(name)
        prepare(fixture)
        expect_transport_error(
            HostBoundTakeoffTransport(fixture).send_from_authorized_ast,
            pattern,
        )
        require(not fixture.cf.send_calls, "failed precondition cannot emit: " + name)

    fixture = Fixture("safelink")
    fixture.cf.link.needs_resending = True
    fixture.queue_states(fixture.state())
    expect_transport_error(
        HostBoundTakeoffTransport(fixture).send_from_authorized_ast,
        "duplicate suppression",
    )
    require(not fixture.cf.send_calls, "lost SafeLink cannot emit")

    fixture = Fixture("phase")
    execution._PROCESS_STATE.phase = execution.RECOVERY_REQUIRED
    expect_transport_error(
        HostBoundTakeoffTransport(fixture).send_from_authorized_ast,
        "inactive",
    )
    require(not fixture.cf.send_calls, "recovery-required cannot emit")


def test_teacher_or_epoch_change_fails_before_effect() -> None:
    fixture = Fixture("teacher")
    fixture.authorization.invalidate("teacher cancelled")
    expect_transport_error(
        HostBoundTakeoffTransport(fixture).send_from_authorized_ast,
        "teacher",
    )
    require(not fixture.cf.send_calls, "stale teacher receipt cannot emit")

    fixture = Fixture("epoch")
    fixture.epoch_value = "changed"
    fixture.queue_states(fixture.state())
    expect_transport_error(
        HostBoundTakeoffTransport(fixture).send_from_authorized_ast,
        "epoch",
    )
    require(not fixture.cf.send_calls, "reconnect cannot emit under stale run")


def test_completion_without_causal_flight_fails_closed() -> None:
    fixture = Fixture("uncertain")
    fixture.queue_states(
        fixture.state(),
        fixture.state(),
    )
    clock_values = iter((0.0, 0.0, 10.0))
    transport_ = HostBoundTakeoffTransport(fixture)
    transport_._clock = lambda: next(clock_values, 10.0)
    expect_transport_error(transport_.send_from_authorized_ast, "completion")
    require(
        fixture.execution.phase == execution.RECOVERY_REQUIRED,
        "uncertain accepted effect requires recovery",
    )
    require(
        len(fixture.cf.send_calls) == 1,
        "accepted-but-uncertain takeoff is never retried",
    )


def test_no_raw_or_caller_height_surface() -> None:
    source = (PHYSICAL / "takeoff_transport.py").read_text(encoding="utf-8")
    parameters = inspect.signature(
        transport.TrustedTakeoffTransport.send_from_authorized_ast
    ).parameters
    require("height" not in parameters, "effect API accepts no caller height")
    require(
        "request" not in parameters and "bytes" not in parameters,
        "effect API accepts no raw request",
    )
    require(
        "assert_current_program"
        not in inspect.signature(transport.TrustedTakeoffTransport).parameters,
        "constructor accepts no caller-selected provenance callback",
    )
    require(
        "derive_bound_takeoff_command" in source,
        "transport consumes exact-bound semantic command",
    )


def main() -> int:
    test_importable_core_has_no_positive_provenance_path()
    test_positive_ack_requires_causal_flying_completion()
    test_first_post_ack_flying_finished_is_causal_from_not_flying_baseline()
    test_definitive_rejection_restores_inactive()
    test_preconditions_fail_before_effect()
    test_teacher_or_epoch_change_fails_before_effect()
    test_completion_without_causal_flight_fails_closed()
    test_no_raw_or_caller_height_surface()
    print(
        "PASS causal physical takeoff transport: exact AST command 9, fresh gates, "
        "one send and #279 flying completion"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

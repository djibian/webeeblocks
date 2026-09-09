#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import threading
import time
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "physical" / "watchdog_liveness.py"
spec = importlib.util.spec_from_file_location("webeeblocks_watchdog_liveness", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load watchdog liveness")
watchdog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watchdog)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except watchdog.WatchdogLivenessError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError(f"expected WatchdogLivenessError containing {pattern!r}")


class Epoch:
    def __init__(self, value: str) -> None:
        self.value = value

    def __call__(self) -> str:
        return self.value


class FakePlatform:
    def __init__(self, version: int = 12) -> None:
        self.version = version

    def get_protocol_version(self) -> int:
        return self.version


class FakeSupervisor:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.send_count = 0
        self.fail_after: int | None = None
        self.on_send = None

    def send_emergency_stop_watchdog(self) -> None:
        self.send_count += 1
        self.events.append("watchdog")
        if self.on_send is not None:
            self.on_send(self.send_count)
        if self.fail_after is not None and self.send_count > self.fail_after:
            raise RuntimeError("radio send failed")


class FakeCf:
    def __init__(self, events: list[str], protocol_version: int = 12) -> None:
        self.platform = FakePlatform(protocol_version)
        self.supervisor = FakeSupervisor(events)


class FakeReader:
    def __init__(
        self,
        cf: FakeCf,
        epoch: str,
        events: list[str],
        *,
        blocking_fault: bool = False,
    ) -> None:
        self.bound_crazyflie = cf
        self.bound_connection_epoch = epoch
        self.poisoned = False
        self.events = events
        self.blocking_fault = blocking_fault
        self.error: Exception | None = None
        self.on_read = None

    def read(self, *, timeout_seconds: float):
        require(timeout_seconds > 0, "reader receives positive timeout")
        self.events.append("get_state")
        if self.on_read is not None:
            self.on_read()
        if self.error is not None:
            raise self.error
        return SimpleNamespace(blocking_fault=self.blocking_fault)


class FakeClock:
    def __init__(self) -> None:
        self.value = 100.0
        self.lock = threading.Lock()

    def __call__(self) -> float:
        with self.lock:
            return self.value

    def advance(self, seconds: float) -> None:
        with self.lock:
            self.value += seconds


class FakePoweredSessionLifecycle:
    """Test double for state supplied by the future trusted powered-session/reset layer."""

    def __init__(
        self,
        identity: str,
        *,
        state: str = "new",
        terminal_reason: str | None = None,
        reset_proven: bool = True,
    ) -> None:
        self.identity = identity
        self.state = state
        self.terminal_reason = terminal_reason
        self.reset_proven = reset_proven
        self.lock = threading.Lock()

    def require_fresh_reset_proof(self) -> None:
        with self.lock:
            if not self.reset_proven:
                raise RuntimeError("no externally proven STM+deck reset")

    def begin_activation(self) -> None:
        with self.lock:
            if self.state != "new":
                raise RuntimeError("powered session is not fresh")
            self.state = "activating"

    def mark_active(self) -> None:
        with self.lock:
            if self.state != "activating":
                raise RuntimeError("powered session is not activating")
            self.state = "active"

    def mark_terminal(self, reason: str) -> None:
        with self.lock:
            if self.state == "terminal":
                return
            self.state = "terminal"
            if self.terminal_reason is None:
                self.terminal_reason = reason


def make_guard(
    *,
    epoch_value: str,
    powered_session_id: str,
    protocol_version: int = 12,
    blocking_fault: bool = False,
    interval: float = 0.01,
    max_gap: float = 0.2,
    clock=None,
):
    events: list[str] = []
    epoch = Epoch(epoch_value)
    cf = FakeCf(events, protocol_version)
    reader = FakeReader(cf, epoch_value, events, blocking_fault=blocking_fault)
    powered = FakePoweredSessionLifecycle(powered_session_id)
    kwargs = {}
    if clock is not None:
        kwargs["clock"] = clock
    guard = watchdog.EmergencyWatchdogLivenessGuard(
        cf,
        epoch,
        reader,
        powered,
        keepalive_interval_seconds=interval,
        max_host_gap_seconds=max_gap,
        **kwargs,
    )
    return guard, cf, reader, epoch, powered, events


def wait_until(predicate, timeout: float = 0.5) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.002)
    return predicate()


def test_activation_order_and_periodic_service() -> None:
    guard, cf, _reader, _epoch, powered, events = make_guard(
        epoch_value="epoch-success",
        powered_session_id="powered-success",
    )
    state = guard.activate(supervisor_timeout_seconds=0.05)
    require(not state.blocking_fault, "activation state healthy")
    require(events[:2] == ["watchdog", "get_state"], "watchdog must precede fresh GET_STATE")
    require(powered.state == "active", "powered session becomes active only after fence")
    require(wait_until(lambda: cf.supervisor.send_count >= 2), "periodic keepalive starts")
    guard.assert_live()
    guard.stop_for_terminal_reboot(join_timeout_seconds=0.2)
    require(powered.state == "terminal", "terminal stop poisons powered session")
    expect_error(guard.assert_live, "terminal")


def test_local_preconditions_emit_no_watchdog_and_do_not_poison_powered_session() -> None:
    guard, cf, _reader, _epoch, powered, events = make_guard(
        epoch_value="epoch-legacy",
        powered_session_id="powered-legacy",
        protocol_version=11,
    )
    expect_error(guard.activate, "protocol version 12")
    require(events == [], "legacy path must emit no watchdog command")
    require(cf.supervisor.send_count == 0, "legacy sender untouched")
    require(powered.state == "new", "pre-effect protocol failure must not poison powered session")

    events2: list[str] = []
    epoch2 = Epoch("epoch-missing-sender")
    cf2 = FakeCf(events2)
    cf2.supervisor.send_emergency_stop_watchdog = None
    reader2 = FakeReader(cf2, "epoch-missing-sender", events2)
    powered2 = FakePoweredSessionLifecycle("powered-missing-sender")
    guard2 = watchdog.EmergencyWatchdogLivenessGuard(
        cf2,
        epoch2,
        reader2,
        powered2,
        keepalive_interval_seconds=0.01,
        max_host_gap_seconds=0.2,
    )
    expect_error(guard2.activate, "command is unavailable")
    require(events2 == [], "missing sender emits no command")
    require(powered2.state == "new", "missing sender is a local precondition")


def test_reader_binding_and_poison_preconditions_emit_nothing() -> None:
    events: list[str] = []
    epoch = Epoch("epoch-reader")
    cf = FakeCf(events)
    powered = FakePoweredSessionLifecycle("powered-reader-epoch")

    mismatched_epoch = FakeReader(cf, "epoch-other", events)
    expect_error(
        lambda: watchdog.EmergencyWatchdogLivenessGuard(
            cf,
            epoch,
            mismatched_epoch,
            powered,
            keepalive_interval_seconds=0.01,
            max_host_gap_seconds=0.2,
        ),
        "share one connection epoch",
    )

    other_cf = FakeCf(events)
    wrong_cf = FakeReader(other_cf, "epoch-reader", events)
    powered_cf = FakePoweredSessionLifecycle("powered-reader-cf")
    expect_error(
        lambda: watchdog.EmergencyWatchdogLivenessGuard(
            cf,
            epoch,
            wrong_cf,
            powered_cf,
            keepalive_interval_seconds=0.01,
            max_host_gap_seconds=0.2,
        ),
        "exact Crazyflie object",
    )

    poisoned = FakeReader(cf, "epoch-reader", events)
    poisoned.poisoned = True
    powered_poison = FakePoweredSessionLifecycle("powered-reader-poison")
    expect_error(
        lambda: watchdog.EmergencyWatchdogLivenessGuard(
            cf,
            epoch,
            poisoned,
            powered_poison,
            keepalive_interval_seconds=0.01,
            max_host_gap_seconds=0.2,
        ),
        "poisoned",
    )

    unknown_poison = FakeReader(cf, "epoch-reader", events)
    del unknown_poison.poisoned
    powered_unknown = FakePoweredSessionLifecycle("powered-reader-unknown")
    expect_error(
        lambda: watchdog.EmergencyWatchdogLivenessGuard(
            cf,
            epoch,
            unknown_poison,
            powered_unknown,
            keepalive_interval_seconds=0.01,
            max_host_gap_seconds=0.2,
        ),
        "poison state is unavailable",
    )
    require(events == [], "reader precondition failures emit no watchdog command")


def test_ambiguous_fence_poisons_same_powered_session_across_reconnect() -> None:
    guard, cf, reader, _epoch, powered, events = make_guard(
        epoch_value="epoch-fence-a",
        powered_session_id="powered-fence",
    )
    reader.error = RuntimeError("fresh state failed")
    expect_error(guard.activate, "activation fence failed")
    require(events == ["watchdog", "get_state"], "initial ambiguous fence sequence")
    require(cf.supervisor.send_count == 1, "one initial keepalive attempt")
    require(powered.state == "terminal", "ambiguous fence poisons powered session")

    reconnect_events: list[str] = []
    reconnect_cf = FakeCf(reconnect_events)
    reconnect_epoch = Epoch("epoch-fence-b")
    reconnect_reader = FakeReader(reconnect_cf, "epoch-fence-b", reconnect_events)
    same_powered = powered
    expect_error(
        lambda: watchdog.EmergencyWatchdogLivenessGuard(
            reconnect_cf,
            reconnect_epoch,
            reconnect_reader,
            same_powered,
            keepalive_interval_seconds=0.01,
            max_host_gap_seconds=0.2,
        ),
        "terminal until a separately proven STM+deck reset",
    )
    require(reconnect_events == [], "reconnect on same powered identity emits no watchdog")
    require(reconnect_cf.supervisor.send_count == 0, "same powered session cannot retry")

    # This fixture stands in only for a fresh lifecycle object established by the
    # future trusted reset layer after separate STM+deck reset proof. The watchdog
    # module itself has no API that can create this state.
    reset_guard, reset_cf, _reset_reader, _reset_epoch, reset_powered, _reset_events = make_guard(
        epoch_value="epoch-fence-reset",
        powered_session_id="externally-proven-powered-session-after-reset",
    )
    reset_guard.activate()
    require(reset_powered.state == "active", "externally reset-proven lifecycle may activate")
    reset_guard.stop_for_terminal_reboot(join_timeout_seconds=0.2)
    require(reset_cf.supervisor.send_count >= 1, "external fresh lifecycle may activate")


def test_epoch_rotation_is_terminal_for_powered_session() -> None:
    guard, cf, _reader, epoch, powered, _events = make_guard(
        epoch_value="epoch-rotate-a",
        powered_session_id="powered-rotate",
    )
    guard.activate()
    sends_before = cf.supervisor.send_count
    epoch.value = "epoch-rotate-b"
    require(wait_until(lambda: guard.terminal_reason is not None), "rotation becomes terminal")
    require(powered.state == "terminal", "rotation poisons powered-session certainty")
    sends_after_terminal = cf.supervisor.send_count
    time.sleep(0.03)
    require(cf.supervisor.send_count == sends_after_terminal, "terminal rotation emits no more keepalive")
    require(sends_after_terminal == sends_before, "rotation checked before next send")

    reconnect_events: list[str] = []
    reconnect_cf = FakeCf(reconnect_events)
    reconnect_reader = FakeReader(reconnect_cf, "epoch-rotate-b", reconnect_events)
    same_powered = powered
    expect_error(
        lambda: watchdog.EmergencyWatchdogLivenessGuard(
            reconnect_cf,
            Epoch("epoch-rotate-b"),
            reconnect_reader,
            same_powered,
            keepalive_interval_seconds=0.01,
            max_host_gap_seconds=0.2,
        ),
        "terminal until a separately proven STM+deck reset",
    )
    require(reconnect_events == [], "new connection epoch is not watchdog reset proof")


def test_periodic_send_failure_is_terminal() -> None:
    guard, cf, _reader, _epoch, powered, _events = make_guard(
        epoch_value="epoch-send-fail",
        powered_session_id="powered-send-fail",
    )
    cf.supervisor.fail_after = 1
    guard.activate()
    require(wait_until(lambda: guard.terminal_reason is not None), "periodic enqueue failure becomes terminal")
    require(powered.state == "terminal", "maintenance ambiguity poisons powered session")
    expect_error(guard.assert_live, "terminal")


def test_host_gap_never_silently_recovers() -> None:
    clock = FakeClock()
    guard, cf, _reader, _epoch, powered, _events = make_guard(
        epoch_value="epoch-gap",
        powered_session_id="powered-gap",
        interval=0.05,
        max_gap=0.2,
        clock=clock,
    )
    guard.activate()
    clock.advance(0.25)
    expect_error(guard.assert_live, "deadline was missed")
    require(powered.state == "terminal", "missed host gap is powered-session terminal")
    sends = cf.supervisor.send_count
    time.sleep(0.07)
    require(cf.supervisor.send_count == sends, "missed host deadline cannot restart keepalives")


def test_fence_and_enqueue_duration_are_bounded_by_host_gap() -> None:
    clock0 = FakeClock()
    guard0, cf0, _reader0, _epoch0, powered0, events0 = make_guard(
        epoch_value="epoch-slow-initial-enqueue",
        powered_session_id="powered-slow-initial-enqueue",
        interval=0.05,
        max_gap=0.2,
        clock=clock0,
    )
    cf0.supervisor.on_send = lambda _count: clock0.advance(0.25)
    expect_error(guard0.activate, "initial enqueue")
    require(events0 == ["watchdog"], "slow initial enqueue never reaches supervisor fence")
    require(powered0.state == "terminal", "slow initial enqueue poisons powered session")
    require(cf0.supervisor.send_count == 1, "slow initial enqueue emits no retry")

    clock = FakeClock()
    guard, cf, reader, _epoch, powered, events = make_guard(
        epoch_value="epoch-slow-fence",
        powered_session_id="powered-slow-fence",
        interval=0.05,
        max_gap=0.2,
        clock=clock,
    )
    reader.on_read = lambda: clock.advance(0.25)
    expect_error(guard.activate, "deadline was missed")
    require(events == ["watchdog", "get_state"], "slow fence still has exact causal sequence")
    require(powered.state == "terminal", "slow fence cannot be treated active")
    time.sleep(0.07)
    require(cf.supervisor.send_count == 1, "slow fence starts no periodic service")

    clock2 = FakeClock()
    guard2, cf2, _reader2, _epoch2, powered2, _events2 = make_guard(
        epoch_value="epoch-slow-enqueue",
        powered_session_id="powered-slow-enqueue",
        interval=0.05,
        max_gap=0.2,
        clock=clock2,
    )
    guard2.activate()

    def slow_after_first(send_count: int) -> None:
        if send_count >= 2:
            clock2.advance(0.25)

    cf2.supervisor.on_send = slow_after_first
    require(wait_until(lambda: guard2.terminal_reason is not None), "slow periodic enqueue becomes terminal")
    require(powered2.state == "terminal", "slow enqueue poisons powered session")
    expect_error(guard2.assert_live, "terminal")


def test_terminal_stop_is_explicit_and_idempotent() -> None:
    guard, cf, _reader, _epoch, powered, _events = make_guard(
        epoch_value="epoch-stop",
        powered_session_id="powered-stop",
    )
    guard.activate()
    guard.stop_for_terminal_reboot(join_timeout_seconds=0.2)
    sends = cf.supervisor.send_count
    time.sleep(0.03)
    require(cf.supervisor.send_count == sends, "terminal stop ends keepalives")
    guard.stop_for_terminal_reboot(join_timeout_seconds=0.2)
    require(powered.state == "terminal", "terminal stop persists")
    expect_error(guard.assert_live, "terminal")


def test_local_arguments_have_no_command_effect() -> None:
    events: list[str] = []
    epoch = Epoch("epoch-args")
    cf = FakeCf(events)
    reader = FakeReader(cf, "epoch-args", events)

    for index, (interval, gap) in enumerate(((0, 0.5), (0.5, 0.5), (0.5, 1.0), (True, 0.5))):
        powered = FakePoweredSessionLifecycle(f"powered-args-{index}")
        expect_error(
            lambda i=interval, g=gap, p=powered: watchdog.EmergencyWatchdogLivenessGuard(
                cf,
                epoch,
                reader,
                p,
                keepalive_interval_seconds=i,
                max_host_gap_seconds=g,
            ),
            "watchdog",
        )
    require(events == [], "invalid construction emits no command")

    powered = FakePoweredSessionLifecycle("powered-args-activate")
    guard = watchdog.EmergencyWatchdogLivenessGuard(
        cf,
        epoch,
        reader,
        powered,
        keepalive_interval_seconds=0.01,
        max_host_gap_seconds=0.2,
    )
    for timeout in (0, -1, True, float("inf"), float("nan")):
        expect_error(
            lambda t=timeout: guard.activate(supervisor_timeout_seconds=t),
            "positive finite",
        )
    require(events == [], "invalid activation timeout emits no command")
    require(powered.state == "new", "invalid local arguments do not claim powered session")



def test_external_powered_session_freshness_is_required() -> None:
    events: list[str] = []
    epoch = Epoch("epoch-reconstructed")
    cf = FakeCf(events)
    reader = FakeReader(cf, "epoch-reconstructed", events)

    # Host/process reconstruction or choosing a new identity does not establish
    # the separately proven STM+deck reset. Even state="new" must fail closed.
    unproven_new = FakePoweredSessionLifecycle(
        "arbitrary-new-identity-after-host-restart",
        state="new",
        reset_proven=False,
    )
    expect_error(
        lambda: watchdog.EmergencyWatchdogLivenessGuard(
            cf,
            epoch,
            reader,
            unproven_new,
            keepalive_interval_seconds=0.01,
            max_host_gap_seconds=0.2,
        ),
        "fresh reset proof is unavailable",
    )

    for index, state in enumerate(("activating", "active", "terminal", "unknown")):
        powered = FakePoweredSessionLifecycle(
            f"powered-reconstructed-{index}",
            state=state,
            terminal_reason="prior watchdog certainty lost" if state == "terminal" else None,
        )
        expect_error(
            lambda p=powered: watchdog.EmergencyWatchdogLivenessGuard(
                cf,
                epoch,
                reader,
                p,
                keepalive_interval_seconds=0.01,
                max_host_gap_seconds=0.2,
            ),
            "powered-session",
        )

    class MissingLifecycle:
        identity = "powered-missing-contract"
        state = "new"
        terminal_reason = None

    expect_error(
        lambda: watchdog.EmergencyWatchdogLivenessGuard(
            cf,
            epoch,
            reader,
            MissingLifecycle(),
            keepalive_interval_seconds=0.01,
            max_host_gap_seconds=0.2,
        ),
        "contract is incomplete",
    )
    require(events == [], "reconstructed/unknown lifecycle state emits no watchdog command")


def test_source_keeps_authority_and_reset_out_of_scope() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "send_arming_request",
        "send_emergency_stop(",
        "HighLevelCommander(",
        "send_setpoint",
        "send_hover_setpoint",
        "send_velocity_world_setpoint",
        "stm_power_cycle(",
        "PowerSwitch(",
    ):
        require(forbidden not in source, f"watchdog guard exposes forbidden authority: {forbidden}")
    require("__enter__" not in source and "__exit__" not in source, "no benign context-manager lifecycle")
    require("def reset" not in source, "watchdog lifecycle must not self-authorize reset")
    require(
        "class PoweredSessionWatchdogLifecycle" not in source
        and "_POWERED_SESSION_STATES" not in source,
        "watchdog primitive must not mint fresh powered-session state from an arbitrary token",
    )


def main() -> int:
    test_activation_order_and_periodic_service()
    test_local_preconditions_emit_no_watchdog_and_do_not_poison_powered_session()
    test_reader_binding_and_poison_preconditions_emit_nothing()
    test_ambiguous_fence_poisons_same_powered_session_across_reconnect()
    test_epoch_rotation_is_terminal_for_powered_session()
    test_periodic_send_failure_is_terminal()
    test_host_gap_never_silently_recovers()
    test_fence_and_enqueue_duration_are_bounded_by_host_gap()
    test_terminal_stop_is_explicit_and_idempotent()
    test_local_arguments_have_no_command_effect()
    test_external_powered_session_freshness_is_required()
    test_source_keeps_authority_and_reset_out_of_scope()

    print(
        "PASS powered-session watchdog lifecycle: same-port activation fence, "
        "continuous liveness, reconnect is not reset, fail closed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

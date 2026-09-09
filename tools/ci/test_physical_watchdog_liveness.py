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

    def send_emergency_stop_watchdog(self) -> None:
        self.send_count += 1
        self.events.append("watchdog")
        if self.fail_after is not None and self.send_count > self.fail_after:
            raise RuntimeError("radio send failed")


class FakeCf:
    def __init__(self, events: list[str], protocol_version: int = 12) -> None:
        self.platform = FakePlatform(protocol_version)
        self.supervisor = FakeSupervisor(events)


class FakeReader:
    def __init__(
        self,
        epoch: str,
        events: list[str],
        *,
        blocking_fault: bool = False,
    ) -> None:
        self.bound_connection_epoch = epoch
        self.poisoned = False
        self.events = events
        self.blocking_fault = blocking_fault
        self.error: Exception | None = None

    def read(self, *, timeout_seconds: float):
        require(timeout_seconds > 0, "reader receives positive timeout")
        self.events.append("get_state")
        if self.error is not None:
            raise self.error
        return SimpleNamespace(blocking_fault=self.blocking_fault)


def make_guard(
    *,
    epoch_value: str = "epoch-watchdog",
    protocol_version: int = 12,
    blocking_fault: bool = False,
    interval: float = 0.01,
    max_gap: float = 0.2,
):
    events: list[str] = []
    epoch = Epoch(epoch_value)
    cf = FakeCf(events, protocol_version)
    reader = FakeReader(epoch_value, events, blocking_fault=blocking_fault)
    guard = watchdog.EmergencyWatchdogLivenessGuard(
        cf,
        epoch,
        reader,
        keepalive_interval_seconds=interval,
        max_host_gap_seconds=max_gap,
    )
    return guard, cf, reader, epoch, events


def wait_until(predicate, timeout: float = 0.5) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.002)
    return predicate()


def test_activation_order_and_periodic_service() -> None:
    guard, cf, _reader, _epoch, events = make_guard()
    state = guard.activate(supervisor_timeout_seconds=0.05)
    require(not state.blocking_fault, "activation state healthy")
    require(events[:2] == ["watchdog", "get_state"], "watchdog must precede fresh GET_STATE")
    require(wait_until(lambda: cf.supervisor.send_count >= 2), "periodic keepalive starts")
    guard.assert_live()
    guard.stop_for_terminal_reboot(join_timeout_seconds=0.2)
    expect_error(guard.assert_live, "terminal")


def test_legacy_protocol_sends_nothing() -> None:
    events: list[str] = []
    epoch = Epoch("epoch-legacy")
    cf = FakeCf(events, protocol_version=11)
    reader = FakeReader("epoch-legacy", events)
    guard = watchdog.EmergencyWatchdogLivenessGuard(
        cf,
        epoch,
        reader,
        keepalive_interval_seconds=0.01,
        max_host_gap_seconds=0.2,
    )
    expect_error(guard.activate, "protocol version 12")
    require(events == [], "legacy path must emit no watchdog command")
    require(cf.supervisor.send_count == 0, "legacy sender untouched")


def test_epoch_and_poison_preconditions_send_nothing() -> None:
    events: list[str] = []
    epoch = Epoch("epoch-current")
    cf = FakeCf(events)
    mismatched = FakeReader("epoch-other", events)
    expect_error(
        lambda: watchdog.EmergencyWatchdogLivenessGuard(
            cf,
            epoch,
            mismatched,
            keepalive_interval_seconds=0.01,
            max_host_gap_seconds=0.2,
        ),
        "share one connection epoch",
    )
    require(events == [], "epoch mismatch has no command effect")

    poisoned = FakeReader("epoch-current", events)
    poisoned.poisoned = True
    expect_error(
        lambda: watchdog.EmergencyWatchdogLivenessGuard(
            cf,
            epoch,
            poisoned,
            keepalive_interval_seconds=0.01,
            max_host_gap_seconds=0.2,
        ),
        "poisoned",
    )
    require(events == [], "poisoned supervisor domain has no command effect")


def test_failed_fence_never_starts_periodic_service() -> None:
    guard, cf, reader, _epoch, events = make_guard()
    reader.error = RuntimeError("fresh state failed")
    expect_error(guard.activate, "activation fence failed")
    require(events == ["watchdog", "get_state"], "initial fence sequence")
    time.sleep(0.03)
    require(cf.supervisor.send_count == 1, "failed fence must not start keepalive service")
    expect_error(guard.assert_live, "terminal")

    guard2, cf2, _reader2, _epoch2, events2 = make_guard(
        epoch_value="epoch-fault",
        blocking_fault=True,
    )
    expect_error(guard2.activate, "blocking supervisor fault")
    require(events2 == ["watchdog", "get_state"], "fault still comes from fenced observation")
    time.sleep(0.03)
    require(cf2.supervisor.send_count == 1, "blocking state starts no periodic service")


def test_periodic_send_failure_is_terminal() -> None:
    guard, cf, _reader, _epoch, _events = make_guard(epoch_value="epoch-send-fail")
    cf.supervisor.fail_after = 1
    guard.activate()
    require(
        wait_until(lambda: guard.terminal_reason is not None),
        "periodic enqueue failure becomes terminal",
    )
    expect_error(guard.assert_live, "terminal")


def test_epoch_rotation_stops_new_keepalives() -> None:
    guard, cf, _reader, epoch, _events = make_guard(epoch_value="epoch-rotate")
    guard.activate()
    sends_before = cf.supervisor.send_count
    epoch.value = "epoch-new"
    require(wait_until(lambda: guard.terminal_reason is not None), "rotation becomes terminal")
    sends_after_terminal = cf.supervisor.send_count
    time.sleep(0.03)
    require(
        cf.supervisor.send_count == sends_after_terminal,
        "terminal rotated epoch emits no further keepalive",
    )
    require(sends_after_terminal == sends_before, "rotation is checked before next send")
    expect_error(guard.assert_live, "terminal")


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


def test_host_gap_never_silently_recovers() -> None:
    events: list[str] = []
    epoch = Epoch("epoch-gap")
    cf = FakeCf(events)
    reader = FakeReader("epoch-gap", events)
    clock = FakeClock()
    guard = watchdog.EmergencyWatchdogLivenessGuard(
        cf,
        epoch,
        reader,
        keepalive_interval_seconds=0.05,
        max_host_gap_seconds=0.2,
        clock=clock,
    )
    guard.activate()
    clock.advance(0.25)
    expect_error(guard.assert_live, "deadline was missed")
    sends = cf.supervisor.send_count
    time.sleep(0.07)
    require(cf.supervisor.send_count == sends, "missed host deadline cannot restart keepalives")


def test_terminal_stop_is_explicit_and_idempotent() -> None:
    guard, cf, _reader, _epoch, _events = make_guard(epoch_value="epoch-stop")
    guard.activate()
    guard.stop_for_terminal_reboot(join_timeout_seconds=0.2)
    sends = cf.supervisor.send_count
    time.sleep(0.03)
    require(cf.supervisor.send_count == sends, "terminal stop ends keepalives")
    guard.stop_for_terminal_reboot(join_timeout_seconds=0.2)
    expect_error(guard.assert_live, "terminal")


def test_local_arguments_have_no_command_effect() -> None:
    events: list[str] = []
    epoch = Epoch("epoch-args")
    cf = FakeCf(events)
    reader = FakeReader("epoch-args", events)

    for interval, gap in ((0, 0.5), (0.5, 0.5), (0.5, 1.0), (True, 0.5)):
        expect_error(
            lambda i=interval, g=gap: watchdog.EmergencyWatchdogLivenessGuard(
                cf,
                epoch,
                reader,
                keepalive_interval_seconds=i,
                max_host_gap_seconds=g,
            ),
            "watchdog",
        )
    require(events == [], "invalid construction emits no command")

    guard = watchdog.EmergencyWatchdogLivenessGuard(
        cf,
        epoch,
        reader,
        keepalive_interval_seconds=0.01,
        max_host_gap_seconds=0.2,
    )
    for timeout in (0, -1, True, float("inf"), float("nan")):
        expect_error(
            lambda t=timeout: guard.activate(supervisor_timeout_seconds=t),
            "positive finite",
        )
    require(events == [], "invalid activation timeout emits no command")


def main() -> int:
    test_activation_order_and_periodic_service()
    test_legacy_protocol_sends_nothing()
    test_epoch_and_poison_preconditions_send_nothing()
    test_failed_fence_never_starts_periodic_service()
    test_periodic_send_failure_is_terminal()
    test_epoch_rotation_stops_new_keepalives()
    test_host_gap_never_silently_recovers()
    test_terminal_stop_is_explicit_and_idempotent()
    test_local_arguments_have_no_command_effect()

    source = MODULE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "send_arming_request",
        "send_emergency_stop(",
        "HighLevelCommander(",
        "send_setpoint",
        "send_hover_setpoint",
        "send_velocity_world_setpoint",
    ):
        require(forbidden not in source, f"watchdog guard exposes forbidden authority: {forbidden}")
    require("__enter__" not in source and "__exit__" not in source, "no benign context-manager lifecycle")

    print("PASS same-epoch watchdog activation fence and powered-session liveness fail closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

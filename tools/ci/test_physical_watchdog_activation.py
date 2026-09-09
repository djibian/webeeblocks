#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "physical" / "watchdog_activation.py"

spec = importlib.util.spec_from_file_location(
    "webeeblocks_watchdog_activation", MODULE_PATH
)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load watchdog activation fence")
watchdog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watchdog)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except watchdog.WatchdogFenceError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError(f"expected WatchdogFenceError containing {pattern!r}")


class EpochSource:
    def __init__(self, value: str) -> None:
        self.value = value
        self.error = None

    def __call__(self) -> str:
        if self.error is not None:
            raise self.error
        return self.value


class State:
    def __init__(self, *, blocking_fault: bool = False) -> None:
        self.blocking_fault = blocking_fault


class FakeSupervisor:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.error = None
        self.calls = 0

    def send_emergency_stop_watchdog(self) -> None:
        self.calls += 1
        self.events.append("watchdog")
        if self.error is not None:
            raise self.error


class FakeCf:
    def __init__(self, events: list[str]) -> None:
        self.supervisor = FakeSupervisor(events)


class FakeReader:
    def __init__(
        self,
        epoch: str,
        events: list[str],
        *,
        state: State | None = None,
    ) -> None:
        self.bound_connection_epoch = epoch
        self.poisoned = False
        self.events = events
        self.state = state if state is not None else State()
        self.error = None
        self.on_read = None
        self.calls = 0
        self.timeouts: list[float] = []

    def read(self, *, timeout_seconds: float):
        self.calls += 1
        self.timeouts.append(timeout_seconds)
        self.events.append("fresh-state")
        if self.on_read is not None:
            self.on_read()
        if self.error is not None:
            raise self.error
        return self.state


def make_fence(
    epoch_value: str = "epoch-a",
    *,
    state: State | None = None,
):
    events: list[str] = []
    epoch = EpochSource(epoch_value)
    cf = FakeCf(events)
    reader = FakeReader(epoch_value, events, state=state)
    fence = watchdog.WatchdogActivationFence(cf, epoch, reader)
    return fence, cf, epoch, reader, events


def test_success_orders_keepalive_before_fresh_state() -> None:
    fence, cf, _epoch, reader, events = make_fence()
    result = fence.activate_and_verify(timeout_seconds=0.125)

    require(events == ["watchdog", "fresh-state"], "causal fence ordering")
    require(cf.supervisor.calls == 1, "exactly one first keepalive")
    require(reader.calls == 1, "exactly one fresh supervisor read")
    require(reader.timeouts == [0.125], "timeout forwarded to fresh reader")
    require(result.connection_epoch == "epoch-a", "result epoch")
    require(result.supervisor_state is reader.state, "fresh state returned")
    require(fence.activation_attempted, "send attempt recorded")
    require(fence.verified, "successful fence verified")
    require(
        fence.power_cycle_required_to_disable,
        "stock watchdog remains one-way after activation",
    )
    expect_error(
        lambda: fence.activate_and_verify(timeout_seconds=0.125),
        "single-use",
    )
    require(cf.supervisor.calls == 1, "successful fence must not be repeated")


def test_reader_must_share_epoch_before_any_send() -> None:
    events: list[str] = []
    cf = FakeCf(events)
    epoch = EpochSource("epoch-a")
    reader = FakeReader("epoch-b", events)

    expect_error(
        lambda: watchdog.WatchdogActivationFence(cf, epoch, reader),
        "not bound",
    )
    require(cf.supervisor.calls == 0, "mismatched reader must not arm watchdog")


def test_poisoned_reader_rejects_before_any_send() -> None:
    fence, cf, _epoch, reader, events = make_fence()
    reader.poisoned = True

    expect_error(
        lambda: fence.activate_and_verify(timeout_seconds=0.1),
        "poisoned",
    )
    require(events == [], "poisoned freshness must reject before keepalive")
    require(cf.supervisor.calls == 0, "no keepalive on poisoned reader")
    require(not fence.activation_attempted, "no send was attempted")


def test_epoch_change_before_send_rejects_without_activation() -> None:
    fence, cf, epoch, _reader, events = make_fence()
    epoch.value = "epoch-b"

    expect_error(
        lambda: fence.activate_and_verify(timeout_seconds=0.1),
        "connection epoch changed",
    )
    require(events == [], "changed epoch must reject before keepalive")
    require(cf.supervisor.calls == 0, "no keepalive after reconnect")
    require(not fence.activation_attempted, "no send was attempted")


def test_send_failure_is_ambiguous_and_never_retried() -> None:
    fence, cf, _epoch, reader, events = make_fence()
    cf.supervisor.error = RuntimeError("radio queue failed")

    expect_error(
        lambda: fence.activate_and_verify(timeout_seconds=0.1),
        "ambiguous after keepalive attempt",
    )
    require(events == ["watchdog"], "send attempt is durable fence boundary")
    require(reader.calls == 0, "no state read after failed sender")
    require(fence.activation_attempted, "unknown send outcome must be remembered")
    require(
        fence.power_cycle_required_to_disable,
        "unknown first keepalive may have armed stock watchdog",
    )

    expect_error(
        lambda: fence.activate_and_verify(timeout_seconds=0.1),
        "single-use",
    )
    require(cf.supervisor.calls == 1, "unknown send outcome must not blind-retry")


def test_fresh_read_failure_after_keepalive_never_retries() -> None:
    fence, cf, _epoch, reader, events = make_fence()
    reader.error = RuntimeError("fresh supervisor timeout")

    expect_error(
        lambda: fence.activate_and_verify(timeout_seconds=0.1),
        "ambiguous after keepalive attempt",
    )
    require(events == ["watchdog", "fresh-state"], "fence attempt ordering")
    require(fence.activation_attempted and not fence.verified, "failed fence state")

    expect_error(
        lambda: fence.activate_and_verify(timeout_seconds=0.1),
        "single-use",
    )
    require(cf.supervisor.calls == 1, "failed fence must not send a second keepalive")


def test_epoch_change_during_read_fails_after_send() -> None:
    fence, cf, epoch, reader, events = make_fence()
    reader.on_read = lambda: setattr(epoch, "value", "epoch-b")

    expect_error(
        lambda: fence.activate_and_verify(timeout_seconds=0.1),
        "connection epoch changed",
    )
    require(events == ["watchdog", "fresh-state"], "reconnect observed after send")
    require(fence.activation_attempted and not fence.verified, "reconnect invalidates fence")
    require(cf.supervisor.calls == 1, "reconnect ambiguity must not be retried")


def test_blocking_fault_never_becomes_verified() -> None:
    fence, cf, _epoch, reader, events = make_fence(state=State(blocking_fault=True))

    expect_error(
        lambda: fence.activate_and_verify(timeout_seconds=0.1),
        "not demonstrably fault-free",
    )
    require(events == ["watchdog", "fresh-state"], "fault observed through fresh read")
    require(fence.activation_attempted and not fence.verified, "fault blocks verification")
    require(cf.supervisor.calls == 1 and reader.calls == 1, "single causal attempt")


def test_source_keeps_effect_scope_bounded() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    require(
        "send_emergency_stop_watchdog" in source,
        "activation primitive must name the one allowed watchdog effect",
    )
    for forbidden in (
        "send_arming_request",
        "send_emergency_stop(",
        "HighLevelCommander(",
        "send_setpoint",
        "send_hover_setpoint",
        ".read_bitfield(",
    ):
        require(forbidden not in source, f"forbidden authority surface: {forbidden}")


def main() -> int:
    tests = [
        test_success_orders_keepalive_before_fresh_state,
        test_reader_must_share_epoch_before_any_send,
        test_poisoned_reader_rejects_before_any_send,
        test_epoch_change_before_send_rejects_without_activation,
        test_send_failure_is_ambiguous_and_never_retried,
        test_fresh_read_failure_after_keepalive_never_retries,
        test_epoch_change_during_read_fails_after_send,
        test_blocking_fault_never_becomes_verified,
        test_source_keeps_effect_scope_bounded,
    ]
    for test in tests:
        test()
    print(
        "PASS watchdog activation fence: same-epoch keepalive -> fresh #257 state, "
        "fail-closed ambiguity, no blind retry"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

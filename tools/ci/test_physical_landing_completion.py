#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "physical" / "landing_completion.py"
spec = importlib.util.spec_from_file_location("webeeblocks_landing_completion", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load landing completion observer")
landing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(landing)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except landing.LandingCompletionError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError(f"expected LandingCompletionError containing {pattern!r}")


class Epoch:
    def __init__(self, value: str) -> None:
        self.value = value

    def __call__(self) -> str:
        return self.value


class FakeClock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        require(seconds > 0, "poll delay must be positive")
        self.value += seconds


def state(
    bitfield: int,
    *,
    blocking_fault: bool = False,
    is_flying: bool = False,
    hl_control_active: bool = False,
    hl_traj_finished: bool = False,
    is_armed: bool = False,
    is_auto_armed: bool = False,
    can_fly: bool = False,
):
    return SimpleNamespace(
        bitfield=bitfield,
        blocking_fault=blocking_fault,
        is_flying=is_flying,
        hl_control_active=hl_control_active,
        hl_traj_finished=hl_traj_finished,
        is_armed=is_armed,
        is_auto_armed=is_auto_armed,
        can_fly=can_fly,
    )


class FakeReader:
    def __init__(self, epoch: str, states: list[object]) -> None:
        self.bound_connection_epoch = epoch
        self.poisoned = False
        self.states = list(states)
        self.read_count = 0
        self.timeouts: list[float] = []
        self.error: Exception | None = None

    def read(self, *, timeout_seconds: float):
        require(timeout_seconds > 0, "fresh read timeout positive")
        self.read_count += 1
        self.timeouts.append(timeout_seconds)
        if self.error is not None:
            raise self.error
        if len(self.states) > 1:
            return self.states.pop(0)
        if self.states:
            return self.states[0]
        raise RuntimeError("no fake supervisor state")


def make_observer(states: list[object], *, epoch_value: str = "epoch-land"):
    epoch = Epoch(epoch_value)
    reader = FakeReader(epoch_value, states)
    clock = FakeClock()
    observer = landing.ControlledLandingCompletionObserver(
        reader,
        epoch,
        clock=clock,
        sleeper=clock.sleep,
    )
    return observer, reader, epoch, clock


def test_fresh_flight_then_finished_landed_transition() -> None:
    observer, reader, _epoch, _clock = make_observer(
        [
            state(0x110, is_flying=True, hl_control_active=True),
            state(0x110, is_flying=True, hl_control_active=True),
            state(0x300, is_flying=False, hl_control_active=True, hl_traj_finished=True),
            state(0x208, is_flying=False, hl_control_active=False, hl_traj_finished=True),
        ]
    )
    baseline = observer.capture_pre_land_flight(timeout_seconds=0.1)
    require(baseline.connection_epoch == "epoch-land", "baseline epoch")
    require(baseline.bitfield == 0x110, "baseline bitfield")

    result = observer.await_completion(
        baseline,
        total_timeout_seconds=1.0,
        per_read_timeout_seconds=0.1,
        poll_interval_seconds=0.05,
    )
    require(result.connection_epoch == "epoch-land", "completion epoch")
    require(result.observations == 3, "three post-effect fresh observations")
    require(result.supervisor_state.hl_traj_finished, "trajectory finished")
    require(not result.supervisor_state.is_flying, "physical flight ended")
    require(not result.supervisor_state.hl_control_active, "HL control inactive")
    require(reader.read_count == 4, "baseline plus completion reads")


def test_stock_auto_arm_after_landing_is_not_rejected() -> None:
    observer, _reader, _epoch, _clock = make_observer(
        [
            state(0x110, is_flying=True, hl_control_active=True),
            state(
                0x20E,
                is_flying=False,
                hl_control_active=False,
                hl_traj_finished=True,
                is_armed=True,
                is_auto_armed=True,
                can_fly=True,
            ),
        ],
        epoch_value="epoch-autoarm",
    )
    baseline = observer.capture_pre_land_flight()
    result = observer.await_completion(baseline, total_timeout_seconds=0.5)
    require(result.supervisor_state.is_armed, "auto-armed final state is preserved")
    require(result.supervisor_state.is_auto_armed, "auto-arm bit is preserved")


def test_stale_non_flying_state_cannot_become_a_baseline() -> None:
    observer, reader, _epoch, _clock = make_observer(
        [state(0x200, hl_traj_finished=True)],
        epoch_value="epoch-stale",
    )
    expect_error(
        observer.capture_pre_land_flight,
        "did not observe active physical flight",
    )
    require(reader.read_count == 1, "baseline requires one fresh observation")


def test_blocking_fault_refutes_completion_immediately() -> None:
    observer, reader, _epoch, _clock = make_observer(
        [
            state(0x110, is_flying=True, hl_control_active=True),
            state(
                0x240,
                blocking_fault=True,
                is_flying=False,
                hl_traj_finished=True,
            ),
        ],
        epoch_value="epoch-fault",
    )
    baseline = observer.capture_pre_land_flight()
    expect_error(
        lambda: observer.await_completion(baseline, total_timeout_seconds=1.0),
        "blocking supervisor fault",
    )
    require(reader.read_count == 2, "fault terminates observation immediately")


def test_same_epoch_is_required_for_completion() -> None:
    observer, reader, epoch, _clock = make_observer(
        [
            state(0x110, is_flying=True, hl_control_active=True),
            state(0x208, hl_traj_finished=True),
        ],
        epoch_value="epoch-before",
    )
    baseline = observer.capture_pre_land_flight()
    epoch.value = "epoch-after"
    expect_error(
        lambda: observer.await_completion(baseline, total_timeout_seconds=1.0),
        "connection epoch changed",
    )
    require(reader.read_count == 1, "epoch rotation fails before a post-effect read")


def test_fresh_reader_failure_fails_closed() -> None:
    observer, reader, _epoch, _clock = make_observer(
        [state(0x110, is_flying=True, hl_control_active=True)],
        epoch_value="epoch-reader-error",
    )
    baseline = observer.capture_pre_land_flight()
    reader.error = RuntimeError("supervisor timeout")
    expect_error(
        lambda: observer.await_completion(baseline, total_timeout_seconds=1.0),
        "fresh supervisor landing observation failed",
    )


def test_timeout_never_promotes_incomplete_landing() -> None:
    observer, reader, _epoch, _clock = make_observer(
        [
            state(0x110, is_flying=True, hl_control_active=True),
            state(0x110, is_flying=True, hl_control_active=True),
        ],
        epoch_value="epoch-timeout",
    )
    baseline = observer.capture_pre_land_flight()
    expect_error(
        lambda: observer.await_completion(
            baseline,
            total_timeout_seconds=0.12,
            per_read_timeout_seconds=0.05,
            poll_interval_seconds=0.05,
        ),
        "completion timed out",
    )
    require(reader.read_count >= 2, "timeout follows fresh post-effect evidence")


def test_finished_but_still_active_is_not_completion() -> None:
    observer, _reader, _epoch, _clock = make_observer(
        [
            state(0x110, is_flying=True, hl_control_active=True),
            state(
                0x310,
                is_flying=True,
                hl_control_active=True,
                hl_traj_finished=True,
            ),
            state(
                0x300,
                is_flying=False,
                hl_control_active=True,
                hl_traj_finished=True,
            ),
            state(
                0x200,
                is_flying=False,
                hl_control_active=False,
                hl_traj_finished=True,
            ),
        ],
        epoch_value="epoch-active",
    )
    baseline = observer.capture_pre_land_flight()
    result = observer.await_completion(baseline, total_timeout_seconds=1.0)
    require(result.observations == 3, "active trajectory states are not completion")


def test_malformed_state_and_arguments_have_no_false_pass() -> None:
    observer, reader, _epoch, _clock = make_observer(
        [SimpleNamespace(
            bitfield=1,
            blocking_fault=False,
            is_flying="yes",
            hl_control_active=False,
            hl_traj_finished=False,
        )],
        epoch_value="epoch-malformed",
    )
    expect_error(observer.capture_pre_land_flight, "invalid is_flying")
    require(reader.read_count == 1, "malformed state was fresh but rejected")

    clean, clean_reader, _ep, _cl = make_observer(
        [state(0x110, is_flying=True, hl_control_active=True)],
        epoch_value="epoch-args",
    )
    for value in (0, -1, True, float("inf"), float("nan"), "0.2"):
        expect_error(
            lambda v=value: clean.capture_pre_land_flight(timeout_seconds=v),
            "positive finite",
        )
    require(clean_reader.read_count == 0, "invalid baseline arguments emit no read")


def test_source_is_observation_only() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "send_arming_request",
        "send_emergency_stop",
        "send_emergency_stop_watchdog",
        "HighLevelCommander(",
        "send_setpoint",
        "send_hover_setpoint",
        "send_velocity_world_setpoint",
        ".read_bitfield(",
    ):
        require(forbidden not in source, f"landing observer exposes authority: {forbidden}")


def main() -> int:
    tests = [
        test_fresh_flight_then_finished_landed_transition,
        test_stock_auto_arm_after_landing_is_not_rejected,
        test_stale_non_flying_state_cannot_become_a_baseline,
        test_blocking_fault_refutes_completion_immediately,
        test_same_epoch_is_required_for_completion,
        test_fresh_reader_failure_fails_closed,
        test_timeout_never_promotes_incomplete_landing,
        test_finished_but_still_active_is_not_completion,
        test_malformed_state_and_arguments_have_no_false_pass,
        test_source_is_observation_only,
    ]
    for test in tests:
        test()

    print(
        "PASS controlled landing completion requires fresh flight -> finished/non-flying evidence"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

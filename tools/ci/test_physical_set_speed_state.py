#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / "tools" / "ci"
PHYSICAL = ROOT / "tools" / "physical"
SEMANTIC_AST = ROOT / "plugins" / "robot_windows" / "blockly" / "webeeblocks" / "semantic_ast.js"
sys.path.insert(0, str(CI))
sys.path.insert(0, str(PHYSICAL))

import controlled_landing_transport  # noqa: E402
import high_level_timing as timing  # noqa: E402
import landing_command  # noqa: E402
import physical_program_sequence as sequence  # noqa: E402
import physical_run_activation as activation  # noqa: E402
import setpoint_hl_transport  # noqa: E402
import test_physical_host_inflight_sequence as host  # noqa: E402

REAL_TIMING_POLICY = activation.HighLevelTimingPolicy


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def canonical(program: list[dict[str, object]]) -> str:
    return json.dumps(
        {
            "program": program,
            "semantics": "webeeblocks-ast-v1",
            "version": 1,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def speed_ast(speed: object = 0.10, *, include_turn: bool = True) -> str:
    program: list[dict[str, object]] = [
        {"height_m": 0.6, "kind": "takeoff"},
        {"kind": "set_speed", "speed_m_s": speed},
        {"direction": "forward", "distance_m": 0.3, "kind": "move"},
    ]
    if include_turn:
        program.append({"angle_deg": -25, "kind": "turn"})
    program.append({"kind": "land"})
    return canonical(program)


def expect_sequence_error(ast_binding: str, pattern: str) -> None:
    try:
        sequence.PhysicalProgramSequence(ast_binding)
    except sequence.PhysicalProgramSequenceError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError("expected fail-closed physical set_speed sequence error")


def test_exact_speed_sequence_state() -> None:
    domain = sequence.PhysicalProgramSequence(speed_ast(include_turn=False))
    require(domain.next_step_kind == "set_speed", "exact set_speed must be next AST kind")
    claim = domain.reserve_next_speed()
    speed = domain.speed_for_claim(claim)
    require(speed == sequence.SequencedSpeed(1, 0.10), "speed derives exact AST value/index")
    try:
        domain.release_unemitted(claim)
    except sequence.PhysicalProgramSequenceError as exc:
        require("effect claim" in str(exc), "set_speed must stay outside effect retry API")
    else:
        raise AssertionError("no-effect set_speed entered physical effect release API")
    try:
        domain.reserve_next_speed(0.2)
    except TypeError:
        pass
    else:
        raise AssertionError("caller-selected speed entered exact sequence API")
    domain.complete_speed(claim)
    require(domain.next_step_kind == "move", "completed speed state advances exactly once")
    move = domain.reserve_next_motion()
    require(domain.motion_for_claim(move).distance_m == 0.3, "next exact move remains intact")
    domain.complete_motion(move)
    land = domain.reserve_terminal_landing()
    domain.complete_landing(land)
    require(domain.completed, "speed program completes only through exact terminal land")

    failed = sequence.PhysicalProgramSequence(speed_ast(include_turn=False))
    failed_claim = failed.reserve_next_speed()
    failed.fail_speed(failed_claim, "live run binding lost")
    require(failed.terminal and failed.next_index == 1, "failed speed state is terminal without advance")


def test_physical_speed_bounds_are_stricter_than_generic_ast() -> None:
    require(
        "speed_m_s:{min:0.1,max:0.6}" in SEMANTIC_AST.read_text(encoding="utf-8"),
        "backend-neutral AST speed envelope was silently narrowed",
    )
    require(sequence.high_level_timing.MIN_HORIZONTAL_SPEED_M_S == 0.10, "physical minimum drifted")
    require(sequence.high_level_timing.MAX_HORIZONTAL_SPEED_M_S == 0.35, "physical maximum drifted")

    for value in (0.09, 0.36, 0.60, True, "0.2"):
        expect_sequence_error(speed_ast(value, include_turn=False), "set_speed")
    for value in (float("nan"), float("inf")):
        expect_sequence_error(speed_ast(value, include_turn=False), "non-finite")

    malformed = canonical(
        [
            {"height_m": 0.6, "kind": "takeoff"},
            {"kind": "set_speed", "speed_m_s": 0.2, "extra": True},
            {"kind": "land"},
        ]
    )
    expect_sequence_error(malformed, "unsupported fields")

    # No-effect speed state must remain compatible with the existing exact
    # terminal landing derivation because it changes no altitude.
    landing = landing_command.derive_bound_landing_command(speed_ast(0.2, include_turn=False))
    require(landing.descent_m == 0.6, "set_speed must not change terminal landing height")


def _install_recording_fakes(*, failing_watchdog: bool = False) -> None:
    host.install_fakes()

    class RecordingTimingPolicy(REAL_TIMING_POLICY):
        def set_horizontal_speed(self, speed_m_s: object) -> None:
            super().set_horizontal_speed(speed_m_s)
            host.base.EVENTS.append(("speed-state", self.horizontal_speed_m_s))

    class RecordingTransport(host.FakePhysicalTransportBase):
        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs)
            host.base.EVENTS.append(("inflight-transport-init", self.bound_connection_epoch))

        def send_horizontal_move(self, *, direction, distance_m, yaw_reader, timing_policy):
            host.base.EVENTS.append(
                (
                    "move-timing",
                    timing_policy.horizontal_speed_m_s,
                    timing_policy.horizontal_move_duration(distance_m),
                )
            )
            return super().send_horizontal_move(
                direction=direction,
                distance_m=distance_m,
                yaw_reader=yaw_reader,
                timing_policy=timing_policy,
            )

        def send_turn(self, *, angle_deg, timing_policy):
            host.base.EVENTS.append(
                (
                    "turn-timing",
                    timing_policy.horizontal_speed_m_s,
                    timing_policy.turn_duration(angle_deg),
                )
            )
            return super().send_turn(angle_deg=angle_deg, timing_policy=timing_policy)

    activation.HighLevelTimingPolicy = RecordingTimingPolicy
    activation.TrustedControlledLandingTransport = RecordingTransport
    controlled_landing_transport.TrustedControlledLandingTransport = RecordingTransport
    setpoint_hl_transport.TrustedSetpointHlTransport = RecordingTransport

    if failing_watchdog:
        class FailingWatchdog(host.base.FakeWatchdog):
            def assert_live(self) -> None:
                super().assert_live()
                raise RuntimeError("injected set_speed watchdog liveness loss")

        host.base.watchdog_liveness.EmergencyWatchdogLivenessGuard = FailingWatchdog


def test_production_host_consumes_speed_without_effect_and_reuses_policy() -> None:
    host.base.EVENTS.clear()
    _install_recording_fakes()
    replies = host.run_host_sequence(speed_ast(0.10), steps=4)

    require(replies[1]["ok"] is False, "caller-selected substitute fields remain rejected")
    for offset in range(2, 6):
        require(replies[offset]["ok"] is True, f"exact speed program step {offset - 1} failed")
        require(replies[offset]["executionAuthority"] is False, "caller response remains non-authority")

    events = host.base.EVENTS
    takeoff_index = events.index(("transport-send", "epoch-after"))
    speed_index = events.index(("speed-state", 0.10))
    transport_index = events.index(("inflight-transport-init", "epoch-after"))
    require(
        takeoff_index < speed_index < transport_index,
        "set_speed must complete before any post-takeoff physical effect transport is created",
    )

    move_timing = next(event for event in events if isinstance(event, tuple) and event[0] == "move-timing")
    require(math.isclose(move_timing[1], 0.10), "move did not receive exact run-local selected speed")
    expected_selected = timing.REST_TO_REST_PEAK_FACTOR * 0.3 / 0.10
    expected_default = timing.REST_TO_REST_PEAK_FACTOR * 0.3 / timing.DEFAULT_HORIZONTAL_SPEED_M_S
    require(math.isclose(move_timing[2], expected_selected), "move duration does not use selected speed")
    require(move_timing[2] > expected_default, "selected lower speed must causally lengthen move duration")

    turn_timing = next(event for event in events if isinstance(event, tuple) and event[0] == "turn-timing")
    expected_turn = timing.HighLevelTimingPolicy().turn_duration(-25)
    require(math.isclose(turn_timing[2], expected_turn), "turn duration was coupled to horizontal set_speed")

    speed_event_count = sum(1 for event in events if event == ("speed-state", 0.10))
    require(speed_event_count == 1, "consumed exact speed statement replayed")
    current_program_events = [event for event in events if event == ("current-program", "epoch-after")]
    require(len(current_program_events) >= 5, "speed and later effects must re-establish current-program provenance")


def test_invalid_speed_is_rejected_before_takeoff() -> None:
    host.base.EVENTS.clear()
    _install_recording_fakes()
    replies = host.run_host_sequence(speed_ast(0.60, include_turn=False), steps=1)
    require(replies[2]["ok"] is False, "out-of-envelope physical set_speed must reject activation")
    require(
        ("transport-send", "epoch-after") not in host.base.EVENTS,
        "physical speed envelope violation reached takeoff",
    )


def test_watchdog_failure_while_applying_speed_is_terminal() -> None:
    host.base.EVENTS.clear()
    _install_recording_fakes(failing_watchdog=True)
    replies = host.run_host_sequence(speed_ast(0.10, include_turn=False), steps=2)
    require(replies[2]["ok"] is False, "watchdog loss must fail exact speed application")
    require(replies[3]["ok"] is False, "terminal speed failure must reject the later move")
    require(
        not any(
            isinstance(event, tuple)
            and event[0] in {"inflight-move", "terminal-land", "move-timing"}
            for event in host.base.EVENTS
        ),
        "failed no-effect speed state was skipped into a later physical effect",
    )


def main() -> int:
    try:
        test_exact_speed_sequence_state()
        test_physical_speed_bounds_are_stricter_than_generic_ast()
        test_production_host_consumes_speed_without_effect_and_reuses_policy()
        test_invalid_speed_is_rejected_before_takeoff()
        test_watchdog_failure_while_applying_speed_is_terminal()
    finally:
        activation.HighLevelTimingPolicy = REAL_TIMING_POLICY
    print(
        "PASS exact physical set_speed is bounded pre-takeoff, consumed once as trusted no-effect run state, "
        "changes only subsequent horizontal move timing, and fails terminal on lost live-run certainty"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

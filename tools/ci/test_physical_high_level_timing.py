#!/usr/bin/env python3
from __future__ import annotations

import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "physical" / "high_level_timing.py"
sys.path.insert(0, str(MODULE_PATH.parent))
import high_level_timing as timing  # noqa: E402


def close(actual: float, expected: float, tolerance: float = 1e-12) -> None:
    assert math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance), (
        actual,
        expected,
    )


def expect_error(callable_) -> None:
    try:
        callable_()
    except timing.HighLevelTimingError:
        return
    raise AssertionError("expected fail-closed HighLevelTimingError")


policy = timing.HighLevelTimingPolicy()
close(policy.horizontal_speed_m_s, 0.35)
close(timing.REST_TO_REST_PEAK_FACTOR, 35.0 / 16.0)

for distance in (0.1, 0.35, 2.0):
    duration = policy.horizontal_move_duration(distance)
    peak = timing.REST_TO_REST_PEAK_FACTOR * distance / duration
    close(peak, 0.35)

policy.set_horizontal_speed(0.1)
close(policy.horizontal_speed_m_s, 0.1)
duration = policy.horizontal_move_duration(0.5)
close(duration, (35.0 / 16.0) * 5.0)
close(timing.REST_TO_REST_PEAK_FACTOR * 0.5 / duration, 0.1)

vertical_duration = policy.vertical_move_duration(0.5)
close(
    timing.REST_TO_REST_PEAK_FACTOR * 0.5 / vertical_duration,
    timing.MAX_VERTICAL_SPEED_M_S,
)
policy.set_horizontal_speed(0.35)
close(policy.vertical_move_duration(0.5), vertical_duration)

turn_90 = policy.turn_duration(90.0)
close(
    timing.REST_TO_REST_PEAK_FACTOR * math.radians(90.0) / turn_90,
    timing.MAX_YAW_RATE_RAD_S,
)
policy.set_horizontal_speed(0.1)
close(policy.turn_duration(90.0), turn_90)

for bad_speed in (0.0, 0.09, 0.36, True, float("inf"), float("nan")):
    expect_error(lambda value=bad_speed: timing.HighLevelTimingPolicy(value))
    expect_error(lambda value=bad_speed: policy.set_horizontal_speed(value))
for bad_distance in (0.0, 0.09, 2.01, True, float("nan")):
    expect_error(lambda value=bad_distance: policy.horizontal_move_duration(value))
for bad_vertical in (0.0, 0.09, 0.81, True, float("inf"), float("nan")):
    expect_error(lambda value=bad_vertical: policy.vertical_move_duration(value))
for bad_turn in (0.0, 0.9, 180.0, True, float("inf"), float("nan")):
    expect_error(lambda value=bad_turn: policy.turn_duration(value))

source = MODULE_PATH.read_text(encoding="utf-8")
assert "import cflib" not in source
assert "HighLevelCommander(" not in source
assert "send_packet" not in source
assert "takeoff_duration" not in source
assert "landing_duration" not in source

# Keep the new exact-AST set_speed production-shaped regression on the same
# already-selected physical timing CI path without broadening workflow authority.
import test_physical_set_speed_state as speed_state  # noqa: E402
assert speed_state.main() == 0

print(
    "PASS pure physical timing preserves horizontal, fixed vertical and yaw-rate "
    "ceilings for serialized rest-to-rest HighLevelCommander trajectories"
)

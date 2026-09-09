#!/usr/bin/env python3
"""Deterministic parity checks for the pure physical high-level semantic adapter."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "physical" / "high_level_semantics.py"
SPEC = importlib.util.spec_from_file_location("webeeblocks_high_level_semantics", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
semantics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(semantics)


def close(actual: float, expected: float, tolerance: float = 1e-12) -> None:
    assert math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance), (actual, expected)


def target(direction: str, distance: float, yaw: float, expected: tuple[float, float]) -> None:
    result = semantics.body_relative_move(direction, distance, yaw)
    close(result.x_m, expected[0])
    close(result.y_m, expected[1])
    close(result.z_m, 0.0)
    close(result.yaw_rad, 0.0)


def expect_error(callable_) -> None:
    try:
        callable_()
    except semantics.HighLevelSemanticError:
        return
    raise AssertionError("expected fail-closed HighLevelSemanticError")


# Exact parity with crazyflie_runtime_v2.c body/world rotation.
target("forward", 1.0, 0.0, (1.0, 0.0))
target("back", 1.0, 0.0, (-1.0, 0.0))
target("left", 1.0, 0.0, (0.0, 1.0))
target("right", 1.0, 0.0, (0.0, -1.0))
target("forward", 1.0, math.pi / 2.0, (0.0, 1.0))
target("left", 1.0, math.pi / 2.0, (-1.0, 0.0))
target("right", 0.5, -math.pi / 2.0, (-0.5, 0.0))
root_half = math.sqrt(0.5)
target("forward", 2.0, math.pi / 4.0, (2.0 * root_half, 2.0 * root_half))

up = semantics.vertical_move("up", 0.8)
down = semantics.vertical_move("down", 0.1)
assert up == semantics.RelativeHighLevelTarget(0.0, 0.0, 0.8, 0.0)
assert down == semantics.RelativeHighLevelTarget(0.0, 0.0, -0.1, 0.0)

left_turn = semantics.relative_turn(90.0)
right_turn = semantics.relative_turn(-45.0)
close(left_turn.yaw_rad, math.pi / 2.0)
close(right_turn.yaw_rad, -math.pi / 4.0)
assert left_turn.x_m == left_turn.y_m == left_turn.z_m == 0.0

# Do not silently widen the integrated Runtime v2 generic action envelope.
for invalid_direction in ("", "rear", "Forward"):
    expect_error(lambda d=invalid_direction: semantics.body_relative_move(d, 1.0, 0.0))
for invalid_distance in (0.0, 0.09, 2.01, float("inf"), float("nan")):
    expect_error(lambda d=invalid_distance: semantics.body_relative_move("forward", d, 0.0))
for invalid_vertical in (0.09, 0.81, float("nan")):
    expect_error(lambda d=invalid_vertical: semantics.vertical_move("up", d))
for invalid_turn in (0.0, 0.9, 180.0, float("inf")):
    expect_error(lambda a=invalid_turn: semantics.relative_turn(a))
expect_error(lambda: semantics.body_relative_move("forward", 1.0, float("nan")))
expect_error(lambda: semantics.vertical_move("sideways", 0.2))

source = MODULE_PATH.read_text(encoding="utf-8")
assert "import cflib" not in source
assert "HighLevelCommander(" not in source
assert "send_packet" not in source
assert "executionAuthority" not in source

print("PASS pure physical HighLevelCommander geometry preserves Runtime v2 body/world semantics without execution authority")

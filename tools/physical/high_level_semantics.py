#!/usr/bin/env python3
"""Pure WebeeBlocks -> direct HighLevelCommander relative-target semantics.

This module deliberately emits no Crazyflie command and imports no cflib API.
It only preserves the already-integrated Runtime v2 geometry at the future
physical-effect boundary.  The caller must supply an accepted current yaw and
must separately establish teacher authorization, exact bound preflight,
watchdog/liveness and supervisor completion before any physical effect.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


MOVE_DIRECTIONS = ("forward", "back", "left", "right")
VERTICAL_DIRECTIONS = ("up", "down")


class HighLevelSemanticError(ValueError):
    """Fail-closed error for malformed generic physical action semantics."""


@dataclass(frozen=True)
class RelativeHighLevelTarget:
    """Relative target consumed later by direct HighLevelCommander.go_to()."""

    x_m: float
    y_m: float
    z_m: float
    yaw_rad: float


def _finite(value: object, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise HighLevelSemanticError(f"{name} must be finite") from exc
    if not math.isfinite(number):
        raise HighLevelSemanticError(f"{name} must be finite")
    return number


def _bounded_positive(value: object, name: str, minimum: float, maximum: float) -> float:
    number = _finite(value, name)
    if number < minimum or number > maximum:
        raise HighLevelSemanticError(
            f"{name} out of Runtime v2 bounds: {number}"
        )
    return number


def body_relative_move(
    direction: str,
    distance_m: object,
    accepted_yaw_rad: object,
) -> RelativeHighLevelTarget:
    """Map one Runtime v2 body-relative horizontal move to world-frame delta."""

    if direction not in MOVE_DIRECTIONS:
        raise HighLevelSemanticError(f"unsupported move direction: {direction}")
    distance = _bounded_positive(distance_m, "distance_m", 0.1, 2.0)
    yaw = _finite(accepted_yaw_rad, "accepted_yaw_rad")
    forward_x = math.cos(yaw) * distance
    forward_y = math.sin(yaw) * distance

    if direction == "forward":
        dx, dy = forward_x, forward_y
    elif direction == "back":
        dx, dy = -forward_x, -forward_y
    elif direction == "left":
        dx, dy = -math.sin(yaw) * distance, math.cos(yaw) * distance
    else:
        dx, dy = math.sin(yaw) * distance, -math.cos(yaw) * distance

    return RelativeHighLevelTarget(dx, dy, 0.0, 0.0)


def vertical_move(direction: str, distance_m: object) -> RelativeHighLevelTarget:
    """Map Runtime v2 vertical intent to relative world-Z displacement."""

    if direction not in VERTICAL_DIRECTIONS:
        raise HighLevelSemanticError(f"unsupported vertical direction: {direction}")
    distance = _bounded_positive(distance_m, "distance_m", 0.1, 0.8)
    dz = distance if direction == "up" else -distance
    return RelativeHighLevelTarget(0.0, 0.0, dz, 0.0)


def relative_turn(angle_deg: object) -> RelativeHighLevelTarget:
    """Map signed Runtime v2 yaw intent to relative HighLevelCommander yaw."""

    angle = _finite(angle_deg, "angle_deg")
    if abs(angle) < 1.0 or abs(angle) > 179.0:
        raise HighLevelSemanticError(f"angle_deg out of Runtime v2 bounds: {angle}")
    return RelativeHighLevelTarget(0.0, 0.0, 0.0, math.radians(angle))

#!/usr/bin/env python3
"""Pure HighLevelCommander timing policy for established Runtime v2 rate semantics.

The pinned Crazyflie high-level planner uses a seventh-order rest-to-rest
polynomial for normal go_to commands. With zero endpoint
velocity/acceleration/jerk, normalized position is

    35*s^4 - 84*s^5 + 70*s^6 - 20*s^7

and normalized speed peaks at s=0.5 with factor 35/16 over average speed.

This module therefore converts the already-established Runtime v2 horizontal
move-speed limit and yaw-rate limit into trajectory durations without emitting
any command or granting authority. It assumes the later effect consumer
serializes motion and obtains fresh supervisor trajectory-completion evidence
before planning the next motion, so each planned segment starts from the
rest-to-rest boundary this factor describes.

Vertical motion has no student speed semantic. Its smooth GO_TO duration is a
fixed host safety policy using the firmware/cflib-established 0.5 m/s default as
a conservative peak ceiling; it is deliberately independent of run-local
horizontal set_speed. Takeoff and landing keep their separate command-9/10
semantics and are not routed through this policy.
"""

from __future__ import annotations

from math import isfinite, radians

REST_TO_REST_PEAK_FACTOR = 35.0 / 16.0
DEFAULT_HORIZONTAL_SPEED_M_S = 0.35
MIN_HORIZONTAL_SPEED_M_S = 0.10
MAX_HORIZONTAL_SPEED_M_S = 0.35
MAX_YAW_RATE_RAD_S = 0.70
MAX_VERTICAL_SPEED_M_S = 0.50

MIN_MOVE_DISTANCE_M = 0.10
MAX_MOVE_DISTANCE_M = 2.00
MIN_VERTICAL_DISTANCE_M = 0.10
MAX_VERTICAL_DISTANCE_M = 0.80
MIN_TURN_DEG = 1.0
MAX_TURN_DEG = 179.0


class HighLevelTimingError(ValueError):
    """Fail-closed error for invalid pure physical trajectory timing input."""


def _finite(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise HighLevelTimingError(f"{name} must be finite")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise HighLevelTimingError(f"{name} must be finite") from exc
    if not isfinite(number):
        raise HighLevelTimingError(f"{name} must be finite")
    return number


def _bounded(value: object, name: str, minimum: float, maximum: float) -> float:
    number = _finite(value, name)
    if number < minimum or number > maximum:
        raise HighLevelTimingError(f"{name} outside established bounds: {number}")
    return number


class HighLevelTimingPolicy:
    """Per-run host timing state for rate-constrained smooth high-level motion."""

    def __init__(self, horizontal_speed_m_s: object = DEFAULT_HORIZONTAL_SPEED_M_S) -> None:
        self._horizontal_speed_m_s = _bounded(
            horizontal_speed_m_s,
            "horizontal_speed_m_s",
            MIN_HORIZONTAL_SPEED_M_S,
            MAX_HORIZONTAL_SPEED_M_S,
        )

    @property
    def horizontal_speed_m_s(self) -> float:
        return self._horizontal_speed_m_s

    def set_horizontal_speed(self, speed_m_s: object) -> None:
        """Apply Runtime v2 set_speed semantics to subsequent horizontal moves only."""
        self._horizontal_speed_m_s = _bounded(
            speed_m_s,
            "speed_m_s",
            MIN_HORIZONTAL_SPEED_M_S,
            MAX_HORIZONTAL_SPEED_M_S,
        )

    def horizontal_move_duration(self, distance_m: object) -> float:
        """Duration whose rest-to-rest polynomial peak speed is the selected limit."""
        distance = _bounded(
            distance_m,
            "distance_m",
            MIN_MOVE_DISTANCE_M,
            MAX_MOVE_DISTANCE_M,
        )
        return REST_TO_REST_PEAK_FACTOR * distance / self._horizontal_speed_m_s

    def vertical_move_duration(self, distance_m: object) -> float:
        """Fixed host-policy duration keeping smooth vertical peak at/below 0.5 m/s."""
        distance = _bounded(
            distance_m,
            "distance_m",
            MIN_VERTICAL_DISTANCE_M,
            MAX_VERTICAL_DISTANCE_M,
        )
        return REST_TO_REST_PEAK_FACTOR * distance / MAX_VERTICAL_SPEED_M_S

    def turn_duration(self, angle_deg: object) -> float:
        """Duration preserving Runtime v2's established 0.7 rad/s yaw-rate ceiling."""
        angle = _finite(angle_deg, "angle_deg")
        magnitude = abs(angle)
        if magnitude < MIN_TURN_DEG or magnitude > MAX_TURN_DEG:
            raise HighLevelTimingError(f"angle_deg outside established bounds: {angle}")
        return REST_TO_REST_PEAK_FACTOR * abs(radians(angle)) / MAX_YAW_RATE_RAD_S

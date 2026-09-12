#!/usr/bin/env python3
"""Conservative pre-takeoff safety envelope for dynamic physical programs.

This module is deliberately non-authority and emits no physical effect. It
consumes only the exact canonical AST binding already established by trusted
current-program provenance and proves that every dynamically reachable physical
path remains inside the already integrated action and nominal-altitude bounds.

It does not evaluate expressions or choose branches. `if` is treated as either
branch being reachable and `repeat` is expanded for its exact bounded count.
The shared Runtime interpreter remains the sole language evaluator; this module
only supplies a conservative physical safety proof before reset/takeoff.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import high_level_semantics
import high_level_timing
import physical_program_sequence
import takeoff_command

MAX_CONTROL_DEPTH = 20


class DynamicPhysicalPreflightError(RuntimeError):
    """Fail-closed error for an unsafe or unsupported dynamic physical program."""


@dataclass(frozen=True, slots=True)
class ReachablePhysicalEnvelope:
    """Bounded world-Z envelope proven across every admitted control-flow path."""

    ast_binding: str
    initial_altitude_m: float
    min_altitude_m: float
    max_altitude_m: float
    terminal_min_altitude_m: float
    terminal_max_altitude_m: float


@dataclass(frozen=True, slots=True)
class _Bounds:
    low: float
    high: float
    seen_low: float
    seen_high: float


def _error(message: str) -> DynamicPhysicalPreflightError:
    return DynamicPhysicalPreflightError(message)


def _exact_fields(statement: dict[str, object], fields: set[str], context: str) -> None:
    if set(statement) != fields:
        raise _error(context + " contains unsupported fields")


def _number(value: object, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _error(context + " must be finite")
    parsed = float(value)
    if not isfinite(parsed):
        raise _error(context + " must be finite")
    return parsed


def _require_altitude(low: float, high: float) -> None:
    if (
        not isfinite(low)
        or not isfinite(high)
        or low < physical_program_sequence.MIN_NOMINAL_ALTITUDE_M
        or high > physical_program_sequence.MAX_NOMINAL_ALTITUDE_M
    ):
        raise _error(
            "a reachable physical path violates established 0.2-1.5 m nominal-altitude bounds"
        )


def _validate_action(statement: dict[str, object], bounds: _Bounds) -> _Bounds | None:
    kind = statement.get("kind")
    try:
        if kind == "move":
            _exact_fields(statement, {"kind", "direction", "distance_m"}, "move statement")
            direction = statement["direction"]
            if not isinstance(direction, str):
                raise _error("move direction is malformed")
            high_level_semantics.body_relative_move(
                direction,
                statement["distance_m"],
                0.0,
            )
            return bounds

        if kind == "vertical":
            _exact_fields(
                statement,
                {"kind", "direction", "distance_m"},
                "vertical statement",
            )
            direction = statement["direction"]
            if not isinstance(direction, str):
                raise _error("vertical direction is malformed")
            target = high_level_semantics.vertical_move(
                direction,
                statement["distance_m"],
            )
            low = bounds.low + target.z_m
            high = bounds.high + target.z_m
            _require_altitude(low, high)
            return _Bounds(
                low=low,
                high=high,
                seen_low=min(bounds.seen_low, low),
                seen_high=max(bounds.seen_high, high),
            )

        if kind == "turn":
            _exact_fields(statement, {"kind", "angle_deg"}, "turn statement")
            high_level_semantics.relative_turn(statement["angle_deg"])
            return bounds

        if kind == "wait":
            _exact_fields(statement, {"kind", "seconds"}, "wait statement")
            seconds = _number(statement["seconds"], "wait seconds")
            if (
                seconds < physical_program_sequence.MIN_WAIT_SECONDS
                or seconds > physical_program_sequence.MAX_WAIT_SECONDS
            ):
                raise _error("wait seconds violate established Runtime v2 bounds")
            return bounds

        if kind == "set_speed":
            _exact_fields(statement, {"kind", "speed_m_s"}, "set_speed statement")
            speed = _number(statement["speed_m_s"], "set_speed speed_m_s")
            if (
                speed < high_level_timing.MIN_HORIZONTAL_SPEED_M_S
                or speed > high_level_timing.MAX_HORIZONTAL_SPEED_M_S
            ):
                raise _error(
                    "set_speed violates established physical horizontal-speed bounds"
                )
            return bounds

        if kind == "set_light":
            _exact_fields(statement, {"kind", "color"}, "set_light statement")
            color = statement["color"]
            if (
                not isinstance(color, str)
                or color not in physical_program_sequence.LIGHT_COLORS
            ):
                raise _error("set_light color violates established Runtime v2 palette")
            return bounds
    except DynamicPhysicalPreflightError:
        raise
    except (
        TypeError,
        ValueError,
        high_level_semantics.HighLevelSemanticError,
    ) as exc:
        raise _error("reachable physical action violates integrated semantics") from exc

    return None


def _validate_sequence(
    sequence: object,
    bounds: _Bounds,
    *,
    depth: int,
) -> _Bounds:
    if depth > MAX_CONTROL_DEPTH:
        raise _error("dynamic physical control-flow nesting is too deep")
    if not isinstance(sequence, list):
        raise _error("dynamic physical statement sequence must be an array")

    current = bounds
    for statement in sequence:
        if not isinstance(statement, dict) or not isinstance(statement.get("kind"), str):
            raise _error("dynamic physical statement is malformed")

        action = _validate_action(statement, current)
        if action is not None:
            current = action
            continue

        kind = statement["kind"]
        if kind == "set_variable":
            _exact_fields(
                statement,
                {"kind", "variable", "value"},
                "set_variable statement",
            )
            variable = statement["variable"]
            if (
                not isinstance(variable, dict)
                or set(variable) != {"id", "name"}
                or not isinstance(variable.get("id"), str)
                or not variable["id"]
                or not isinstance(variable.get("name"), str)
                or not variable["name"].strip()
            ):
                raise _error("set_variable reference is malformed")
            if not isinstance(statement["value"], dict):
                raise _error("set_variable expression is malformed")
            continue

        if kind == "if":
            allowed = {"kind", "condition", "then", "else"}
            if set(statement) not in ({"kind", "condition", "then"}, allowed):
                raise _error("if statement contains unsupported fields")
            if not isinstance(statement["condition"], dict):
                raise _error("if condition is malformed")
            then_bounds = _validate_sequence(
                statement["then"],
                current,
                depth=depth + 1,
            )
            else_bounds = _validate_sequence(
                statement.get("else", []),
                current,
                depth=depth + 1,
            )
            current = _Bounds(
                low=min(then_bounds.low, else_bounds.low),
                high=max(then_bounds.high, else_bounds.high),
                seen_low=min(
                    current.seen_low,
                    then_bounds.seen_low,
                    else_bounds.seen_low,
                ),
                seen_high=max(
                    current.seen_high,
                    then_bounds.seen_high,
                    else_bounds.seen_high,
                ),
            )
            _require_altitude(current.low, current.high)
            continue

        if kind == "repeat":
            _exact_fields(statement, {"kind", "count", "body"}, "repeat statement")
            count_value = statement["count"]
            if (
                isinstance(count_value, bool)
                or not isinstance(count_value, (int, float))
                or not float(count_value).is_integer()
            ):
                raise _error("repeat count must be an integer")
            count = int(count_value)
            if count < 1 or count > 20:
                raise _error("repeat count violates established Runtime v2 bounds")
            if not isinstance(statement["body"], list):
                raise _error("repeat body is malformed")
            for _ in range(count):
                current = _validate_sequence(
                    statement["body"],
                    current,
                    depth=depth + 1,
                )
            continue

        if kind in {"takeoff", "land"}:
            raise _error("takeoff and land are only allowed at top-level boundaries")

        raise _error("unsupported dynamic physical statement kind: " + kind)

    return current


def validate_bound_dynamic_program(ast_binding: object) -> ReachablePhysicalEnvelope:
    """Prove every reachable physical path before reset/takeoff.

    Expression evaluation and branch selection remain exclusively owned by the
    shared Runtime interpreter. This proof assumes either branch of every `if`
    can be selected and therefore cannot be weakened by a sensor value.
    """

    try:
        takeoff = takeoff_command.derive_bound_takeoff_command(ast_binding)
        parsed = takeoff_command._parse_ast_binding(ast_binding)
    except takeoff_command.TakeoffCommandError as exc:
        raise _error(str(exc)) from exc

    program = parsed["program"]
    if not isinstance(program, list):
        raise _error("physical AST program is unavailable")
    final = program[-1]
    if (
        not isinstance(final, dict)
        or set(final) != {"kind"}
        or final.get("kind") != "land"
    ):
        raise _error("physical AST must end with the exact landing statement")

    initial = float(takeoff.height_m)
    _require_altitude(initial, initial)
    start = _Bounds(
        low=initial,
        high=initial,
        seen_low=initial,
        seen_high=initial,
    )
    terminal = _validate_sequence(
        program[1:-1],
        start,
        depth=0,
    )
    return ReachablePhysicalEnvelope(
        ast_binding=str(ast_binding),
        initial_altitude_m=initial,
        min_altitude_m=terminal.seen_low,
        max_altitude_m=terminal.seen_high,
        terminal_min_altitude_m=terminal.low,
        terminal_max_altitude_m=terminal.high,
    )

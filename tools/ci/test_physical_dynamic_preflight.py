#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools/physical"
if str(PHYSICAL) not in sys.path:
    sys.path.insert(0, str(PHYSICAL))

import takeoff_command  # noqa: E402
from physical_dynamic_preflight import (  # noqa: E402
    DynamicPhysicalPreflightError,
    validate_bound_dynamic_program,
)
import test_physical_shared_interpreter_session as shared_interpreter_test  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def canonical(program: list[dict[str, object]]) -> str:
    return takeoff_command._canonical_json(
        {
            "version": 1,
            "semantics": "webeeblocks-ast-v1",
            "program": program,
        }
    )


def expect_error(program: list[dict[str, object]], pattern: str) -> None:
    try:
        validate_bound_dynamic_program(canonical(program))
    except DynamicPhysicalPreflightError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {str(exc)!r}")
        return
    raise AssertionError("expected DynamicPhysicalPreflightError containing " + repr(pattern))


def number(value: float) -> dict[str, object]:
    return {"kind": "number", "value": value}


def variable(identifier: str = "distance", name: str = "distance") -> dict[str, str]:
    return {"id": identifier, "name": name}


def representative_dynamic_program() -> list[dict[str, object]]:
    ref = variable()
    return [
        {"kind": "takeoff", "height_m": 0.8},
        {
            "kind": "set_variable",
            "variable": ref,
            "value": {"kind": "range", "direction": "front", "unit": "m"},
        },
        {
            "kind": "if",
            "condition": {
                "kind": "compare",
                "op": "LT",
                "left": {"kind": "variable_get", "variable": ref},
                "right": number(1.0),
            },
            "then": [
                {"kind": "vertical", "direction": "up", "distance_m": 0.2},
                {"kind": "set_light", "color": "green"},
            ],
            "else": [
                {"kind": "vertical", "direction": "down", "distance_m": 0.1},
                {"kind": "set_light", "color": "red"},
            ],
        },
        {
            "kind": "repeat",
            "count": 2,
            "body": [
                {"kind": "move", "direction": "forward", "distance_m": 0.3},
                {"kind": "wait", "seconds": 0.1},
            ],
        },
        {"kind": "set_speed", "speed_m_s": 0.2},
        {"kind": "turn", "angle_deg": -90.0},
        {"kind": "land"},
    ]


def test_representative_dynamic_program_is_proven_conservatively() -> None:
    binding = canonical(representative_dynamic_program())
    envelope = validate_bound_dynamic_program(binding)
    require(envelope.ast_binding == binding, "exact AST binding identity was not preserved")
    require(envelope.initial_altitude_m == 0.8, "takeoff altitude changed")
    require(abs(envelope.min_altitude_m - 0.7) < 1e-12, "reachable lower branch altitude was not retained")
    require(envelope.max_altitude_m == 1.0, "reachable upper branch altitude was not retained")
    require(
        abs(envelope.terminal_min_altitude_m - 0.7) < 1e-12
        and envelope.terminal_max_altitude_m == 1.0,
        "terminal reachable altitude interval is wrong",
    )


def test_any_unsafe_if_branch_rejects_before_effect() -> None:
    expect_error(
        [
            {"kind": "takeoff", "height_m": 1.4},
            {
                "kind": "if",
                "condition": {
                    "kind": "range",
                    "direction": "front",
                    "unit": "m",
                },
                "then": [
                    {"kind": "vertical", "direction": "up", "distance_m": 0.2}
                ],
                "else": [],
            },
            {"kind": "land"},
        ],
        "reachable physical path violates",
    )


def test_repeat_expands_the_full_altitude_path() -> None:
    expect_error(
        [
            {"kind": "takeoff", "height_m": 0.3},
            {
                "kind": "repeat",
                "count": 2,
                "body": [
                    {"kind": "vertical", "direction": "down", "distance_m": 0.1}
                ],
            },
            {"kind": "land"},
        ],
        "reachable physical path violates",
    )


def test_nested_flight_boundaries_and_unknown_statements_fail_closed() -> None:
    for statement, pattern in (
        ({"kind": "takeoff", "height_m": 0.8}, "top-level boundaries"),
        ({"kind": "land"}, "top-level boundaries"),
        ({"kind": "future_action"}, "unsupported dynamic physical statement kind"),
    ):
        expect_error(
            [
                {"kind": "takeoff", "height_m": 0.8},
                {"kind": "repeat", "count": 1, "body": [statement]},
                {"kind": "land"},
            ],
            pattern,
        )


def test_all_existing_action_bounds_apply_inside_dynamic_control_flow() -> None:
    cases = [
        (
            {"kind": "move", "direction": "forward", "distance_m": 2.1},
            "reachable physical action violates",
        ),
        (
            {"kind": "vertical", "direction": "up", "distance_m": 0.9},
            "reachable physical action violates",
        ),
        (
            {"kind": "turn", "angle_deg": 180.0},
            "reachable physical action violates",
        ),
        (
            {"kind": "wait", "seconds": 0.05},
            "wait seconds violate",
        ),
        (
            {"kind": "set_speed", "speed_m_s": 10.0},
            "set_speed violates",
        ),
        (
            {"kind": "set_light", "color": "magenta"},
            "set_light color violates",
        ),
    ]
    for statement, pattern in cases:
        expect_error(
            [
                {"kind": "takeoff", "height_m": 0.8},
                {
                    "kind": "if",
                    "condition": number(1.0),
                    "then": [statement],
                    "else": [],
                },
                {"kind": "land"},
            ],
            pattern,
        )


def test_control_flow_metadata_cannot_hide_unsupported_fields() -> None:
    expect_error(
        [
            {"kind": "takeoff", "height_m": 0.8},
            {
                "kind": "repeat",
                "count": 1,
                "body": [],
                "callerBranch": "left",
            },
            {"kind": "land"},
        ],
        "repeat statement contains unsupported fields",
    )
    expect_error(
        [
            {"kind": "takeoff", "height_m": 0.8},
            {
                "kind": "if",
                "condition": number(1.0),
                "then": [],
                "else": [],
                "selected": "then",
            },
            {"kind": "land"},
        ],
        "if statement contains unsupported fields",
    )


def test_noncanonical_or_malformed_binding_fails_closed() -> None:
    program = representative_dynamic_program()
    noncanonical = json.dumps(
        {
            "program": program,
            "semantics": "webeeblocks-ast-v1",
            "version": 1,
        },
        ensure_ascii=False,
    )
    try:
        validate_bound_dynamic_program(noncanonical)
    except DynamicPhysicalPreflightError as exc:
        require("canonical" in str(exc), "noncanonical binding failed for the wrong reason")
    else:
        raise AssertionError("noncanonical AST binding was accepted")

    malformed = canonical(
        [
            {"kind": "takeoff", "height_m": 0.8},
            {"kind": "set_variable", "variable": {"id": "", "name": "x"}, "value": number(1)},
            {"kind": "land"},
        ]
    )
    try:
        validate_bound_dynamic_program(malformed)
    except DynamicPhysicalPreflightError as exc:
        require("reference is malformed" in str(exc), "malformed variable failed for wrong reason")
    else:
        raise AssertionError("malformed set_variable reference was accepted")


def main() -> int:
    test_representative_dynamic_program_is_proven_conservatively()
    test_any_unsafe_if_branch_rejects_before_effect()
    test_repeat_expands_the_full_altitude_path()
    test_nested_flight_boundaries_and_unknown_statements_fail_closed()
    test_all_existing_action_bounds_apply_inside_dynamic_control_flow()
    test_control_flow_metadata_cannot_hide_unsupported_fields()
    test_noncanonical_or_malformed_binding_fails_closed()
    shared_interpreter_test.main()
    print(
        "PASS dynamic physical preflight: every reachable control-flow path "
        "stays inside integrated action and altitude bounds before effect"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

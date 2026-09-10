#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(PHYSICAL))

import takeoff_command as takeoff  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_error(value: object, pattern: str) -> None:
    try:
        takeoff.derive_bound_takeoff_command(value)
    except takeoff.TakeoffCommandError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError("expected TakeoffCommandError containing " + repr(pattern))


def canonical(height: object = 0.8, first: object | None = None) -> str:
    statement = {"kind": "takeoff", "height_m": height} if first is None else first
    return json.dumps(
        {
            "version": 1,
            "semantics": "webeeblocks-ast-v1",
            "program": [statement, {"kind": "land"}],
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def test_exact_command_9_packet() -> None:
    binding = canonical(0.8)
    command = takeoff.derive_bound_takeoff_command(binding)
    require(command.ast_binding == binding, "command preserves exact AST binding")
    require(command.height_m == 0.8, "command derives exact takeoff height")
    require(len(command.request) == struct.calcsize("<BBf?f?f"), "command 9 packet size")
    fields = struct.unpack("<BBf?f?f", command.request)
    require(fields[0] == 9, "command id is TAKEOFF_WITH_VELOCITY")
    require(fields[1] == 0, "takeoff group mask is zero")
    require(abs(fields[2] - 0.8) < 1e-6, "absolute height is AST-derived")
    require(fields[3] is False, "height is absolute")
    require(fields[4] == 0.0, "ignored yaw payload stays neutral")
    require(fields[5] is True, "current yaw is preserved")
    require(abs(fields[6] - 0.5) < 1e-6, "explicit vertical velocity is 0.5 m/s")


def test_ast_binding_rejections() -> None:
    cases = (
        ("", "non-empty trimmed"),
        (" {} ", "non-empty trimmed"),
        ("{bad", "malformed JSON"),
        ('{"program":[],"semantics":"webeeblocks-ast-v1","version":2}', "version"),
        ('{"program":[],"semantics":"other","version":1}', "semantics"),
        (canonical(first={"kind": "move", "direction": "forward", "distance_m": 0.2}), "begin"),
        (canonical(first={"kind": "takeoff", "height_m": 0.8, "velocity": 9}), "begin"),
        (canonical(True), "numeric"),
        (canonical(0.1), "bounds"),
        (canonical(1.6), "bounds"),
    )
    for value, pattern in cases:
        expect_error(value, pattern)


def test_duplicate_and_nonfinite_json_fail_closed() -> None:
    duplicate = (
        '{"program":[{"height_m":0.8,"height_m":1.0,"kind":"takeoff"},{"kind":"land"}],'
        '"semantics":"webeeblocks-ast-v1","version":1}'
    )
    expect_error(duplicate, "duplicate")
    nonfinite = (
        '{"program":[{"height_m":NaN,"kind":"takeoff"},{"kind":"land"}],'
        '"semantics":"webeeblocks-ast-v1","version":1}'
    )
    expect_error(nonfinite, "non-finite")


def test_noncanonical_json_never_reaches_command_construction() -> None:
    # Current-main physical_capability_contract.bindAst() recursively sorts
    # object keys and emits whitespace-free JSON.stringify-compatible text.
    # Equivalent parsed values with a different wire representation are not the
    # exact #267/#249 astBinding and must fail before command bytes are built.
    noncanonical = (
        '{"version":1,"semantics":"webeeblocks-ast-v1",'
        '"program":[{"height_m":0.8,"kind":"takeoff"},{"kind":"land"}]}'
    )
    expect_error(noncanonical, "canonical JSON")

    whitespace = canonical().replace(',"semantics"', ', "semantics"')
    expect_error(whitespace, "canonical JSON")

    numeric_spelling = canonical().replace('"height_m":0.8', '"height_m":8e-1')
    expect_error(numeric_spelling, "canonical JSON")


def test_exact_browser_number_spelling_is_accepted() -> None:
    # JSON.stringify(Number(1.0)) emits `1`, not Python's `1.0` spelling.
    binding = canonical(1)
    command = takeoff.derive_bound_takeoff_command(binding)
    require(command.height_m == 1.0, "canonical integer-shaped JSON number is accepted")


def test_no_effect_or_caller_height_surface() -> None:
    source = (PHYSICAL / "takeoff_command.py").read_text(encoding="utf-8")
    for forbidden in (
        "send_packet(",
        "HighLevelCommander(",
        "PowerSwitch(",
        "teacher_decision",
        "caller_height",
        "set_speed",
        "hlCommander.vtoff",
    ):
        require(forbidden not in source, "pure takeoff semantics leaked authority: " + forbidden)


def main() -> int:
    test_exact_command_9_packet()
    test_ast_binding_rejections()
    test_duplicate_and_nonfinite_json_fail_closed()
    test_noncanonical_json_never_reaches_command_construction()
    test_exact_browser_number_spelling_is_accepted()
    test_no_effect_or_caller_height_surface()
    print(
        "PASS exact-bound takeoff command semantics derive pinned command 9 solely from canonical AST"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(PHYSICAL))

import physical_program_sequence as sequence  # noqa: E402


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


def expect_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except sequence.PhysicalProgramSequenceError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError(f"expected PhysicalProgramSequenceError containing {pattern!r}")


def sample_ast() -> str:
    return canonical(
        [
            {"kind": "takeoff", "height_m": 0.8},
            {"kind": "move", "direction": "forward", "distance_m": 0.3},
            {"kind": "turn", "angle_deg": 45},
            {"kind": "land"},
        ]
    )


def test_exact_order_and_claim_identity() -> None:
    domain = sequence.PhysicalProgramSequence(sample_ast())
    require(domain.next_index == 1, "sequence must begin immediately after completed takeoff")

    first = domain.reserve_next_motion()
    motion = domain.motion_for_claim(first)
    require(
        motion == sequence.SequencedInflightMotion(1, "move", "forward", 0.3, None),
        "first in-flight motion must come from exact AST index 1",
    )
    expect_error(domain.reserve_next_motion, "pending")
    expect_error(lambda: domain.complete_motion(object()), "exact pending")

    domain.complete_motion(first)
    require(domain.next_index == 2, "causal completion alone advances the cursor")
    second = domain.reserve_next_motion()
    turn = domain.motion_for_claim(second)
    require(
        turn == sequence.SequencedInflightMotion(2, "turn", None, None, 45.0),
        "second in-flight motion must preserve exact AST order",
    )

    domain.release_unemitted(second)
    require(domain.next_index == 2, "definitive no-effect/rejection cannot skip a statement")
    retry = domain.reserve_next_motion()
    require(domain.motion_for_claim(retry) == turn, "released statement must remain next")


def test_caller_cannot_select_motion_or_index() -> None:
    domain = sequence.PhysicalProgramSequence(sample_ast())
    try:
        domain.reserve_next_motion({"kind": "turn", "angle_deg": -90})
    except TypeError:
        pass
    else:
        raise AssertionError("caller-selected motion unexpectedly entered sequencing API")

    claim = domain.reserve_next_motion()
    require(
        domain.motion_for_claim(claim).kind == "move",
        "bounded substitute motion cannot replace exact next AST statement",
    )


def test_ambiguous_effect_is_terminal() -> None:
    domain = sequence.PhysicalProgramSequence(sample_ast())
    claim = domain.reserve_next_motion()
    domain.mark_ambiguous(claim, "accepted effect completion became uncertain")
    require(domain.terminal, "ambiguous emitted effect must make sequencing terminal")
    require(domain.next_index == 1, "ambiguity cannot manufacture completion")
    expect_error(domain.reserve_next_motion, "terminal")


def test_unsupported_or_malformed_next_statement_fails_closed() -> None:
    for statement in (
        {"kind": "land"},
        {"kind": "vertical", "direction": "up", "distance_m": 0.2},
        {"kind": "move", "direction": "forward", "distance_m": 0.3, "extra": True},
        {"kind": "move", "direction": "forward", "distance_m": 20},
        {"kind": "turn", "angle_deg": 0},
        {"kind": "repeat", "count": 2, "body": []},
    ):
        ast = canonical(
            [
                {"kind": "takeoff", "height_m": 0.8},
                statement,
                {"kind": "land"},
            ]
        )
        domain = sequence.PhysicalProgramSequence(ast)
        expect_error(domain.reserve_next_motion, "next")


def test_exact_canonical_ast_and_flight_boundaries_are_required() -> None:
    noncanonical = '{"version":1,"semantics":"webeeblocks-ast-v1","program":[{"kind":"takeoff","height_m":0.8},{"kind":"land"}]}'
    expect_error(lambda: sequence.PhysicalProgramSequence(noncanonical), "canonical")

    wrong_first = canonical(
        [
            {"kind": "move", "direction": "forward", "distance_m": 0.3},
            {"kind": "land"},
        ]
    )
    expect_error(lambda: sequence.PhysicalProgramSequence(wrong_first), "begin")

    wrong_last = canonical(
        [
            {"kind": "takeoff", "height_m": 0.8},
            {"kind": "move", "direction": "forward", "distance_m": 0.3},
            {"kind": "wait", "seconds": 1},
        ]
    )
    expect_error(lambda: sequence.PhysicalProgramSequence(wrong_last), "end")


def main() -> int:
    test_exact_order_and_claim_identity()
    test_caller_cannot_select_motion_or_index()
    test_ambiguous_effect_is_terminal()
    test_unsupported_or_malformed_next_statement_fails_closed()
    test_exact_canonical_ast_and_flight_boundaries_are_required()
    print(
        "PASS exact physical-program sequencing derives the next in-flight motion from the "
        "teacher-bound canonical AST and advances only on causal completion"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

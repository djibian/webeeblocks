#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(PHYSICAL))

from inflight_program_sequence import (  # noqa: E402
    ExactInflightProgramSequence,
    InflightProgramSequenceError,
)
from teacher_run_authorization import PhysicalRunBinding  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def binding(program) -> PhysicalRunBinding:
    ast_binding = json.dumps(
        {"version": 1, "semantics": "webeeblocks-ast-v1", "program": program},
        separators=(",", ":"),
        sort_keys=True,
    )
    return PhysicalRunBinding("activity-1", ast_binding, "epoch-1")


class FakeTransport:
    def __init__(self, run_binding: PhysicalRunBinding, accepted=True) -> None:
        self.teacher_binding = run_binding
        self.accepted = accepted
        self.calls = []

    def send_horizontal_move(self, **kwargs):
        self.calls.append(("move", kwargs))
        return SimpleNamespace(accepted=self.accepted, status=0 if self.accepted else 22)

    def send_turn(self, **kwargs):
        self.calls.append(("turn", kwargs))
        return SimpleNamespace(accepted=self.accepted, status=0 if self.accepted else 22)


def expect_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except InflightProgramSequenceError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError("expected InflightProgramSequenceError containing " + repr(pattern))


def test_next_effect_is_derived_from_exact_bound_ast() -> None:
    run_binding = binding(
        [
            {"kind": "takeoff", "height_m": 0.8},
            {"kind": "move", "direction": "left", "distance_m": 0.4},
            {"kind": "turn", "angle_deg": -35},
            {"kind": "land"},
        ]
    )
    sequence = ExactInflightProgramSequence(run_binding)
    transport = FakeTransport(run_binding)
    yaw_reader = object()
    timing_policy = object()

    result = sequence.execute_next(
        transport,
        yaw_reader=yaw_reader,
        timing_policy=timing_policy,
    )
    require(result.accepted, "bound move result accepted")
    require(sequence.next_program_index == 2, "successful exact move advances one statement")
    require(
        transport.calls
        == [
            (
                "move",
                {
                    "direction": "left",
                    "distance_m": 0.4,
                    "yaw_reader": yaw_reader,
                    "timing_policy": timing_policy,
                },
            )
        ],
        "first effect must come only from the exact next AST statement",
    )

    sequence.execute_next(
        transport,
        yaw_reader=yaw_reader,
        timing_policy=timing_policy,
    )
    require(sequence.next_program_index == 3, "second exact statement advances once")
    require(
        transport.calls[1]
        == ("turn", {"angle_deg": -35, "timing_policy": timing_policy}),
        "second effect must preserve exact authorized turn semantics",
    )


def test_rejection_does_not_advance_or_authorize_substitution() -> None:
    run_binding = binding(
        [
            {"kind": "takeoff", "height_m": 0.8},
            {"kind": "move", "direction": "forward", "distance_m": 0.2},
            {"kind": "land"},
        ]
    )
    sequence = ExactInflightProgramSequence(run_binding)
    rejected = FakeTransport(run_binding, accepted=False)
    sequence.execute_next(rejected, yaw_reader=object(), timing_policy=object())
    require(sequence.next_program_index == 1, "definitive rejection must not advance sequencing")
    require(
        rejected.calls[0][1]["direction"] == "forward"
        and rejected.calls[0][1]["distance_m"] == 0.2,
        "caller has no semantic parameter surface to substitute a bounded motion",
    )

    other_binding = binding(
        [
            {"kind": "takeoff", "height_m": 0.8},
            {"kind": "turn", "angle_deg": 20},
            {"kind": "land"},
        ]
    )
    expect_error(
        lambda: sequence.execute_next(
            FakeTransport(other_binding),
            yaw_reader=object(),
            timing_policy=object(),
        ),
        "exact sequenced run",
    )


def test_unsupported_next_statement_fails_closed_without_effect() -> None:
    for statement in (
        {"kind": "wait", "seconds": 1},
        {"kind": "vertical", "direction": "up", "distance_m": 0.2},
        {"kind": "repeat", "count": 2, "body": [{"kind": "turn", "angle_deg": 20}]},
        {"kind": "if", "condition": {"kind": "number", "value": 1}, "then": []},
    ):
        run_binding = binding(
            [
                {"kind": "takeoff", "height_m": 0.8},
                statement,
                {"kind": "land"},
            ]
        )
        sequence = ExactInflightProgramSequence(run_binding)
        transport = FakeTransport(run_binding)
        expect_error(
            lambda: sequence.execute_next(
                transport,
                yaw_reader=object(),
                timing_policy=object(),
            ),
            "outside the bounded move/turn slice",
        )
        require(not transport.calls, "unsupported next statement must remain effect-free")
        require(sequence.next_program_index == 1, "unsupported statement must not advance")


def test_malformed_or_boundary_only_programs_fail_closed() -> None:
    expect_error(
        lambda: ExactInflightProgramSequence(
            PhysicalRunBinding("activity-1", "not-json", "epoch-1")
        ),
        "not JSON",
    )
    boundary = binding(
        [
            {"kind": "takeoff", "height_m": 0.8},
            {"kind": "land"},
        ]
    )
    sequence = ExactInflightProgramSequence(boundary)
    expect_error(
        lambda: sequence.execute_next(
            FakeTransport(boundary),
            yaw_reader=object(),
            timing_policy=object(),
        ),
        "no supported in-flight statement",
    )


def main() -> int:
    test_next_effect_is_derived_from_exact_bound_ast()
    test_rejection_does_not_advance_or_authorize_substitution()
    test_unsupported_next_statement_fails_closed_without_effect()
    test_malformed_or_boundary_only_programs_fail_closed()
    print(
        "PASS exact physical in-flight sequencing: next move/turn derives only from the "
        "teacher-authorized canonical AST and advances only after completed acceptance"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
SEMANTIC_AST = ROOT / "plugins" / "robot_windows" / "blockly" / "webeeblocks" / "semantic_ast.js"
sys.path.insert(0, str(PHYSICAL))

import landing_command as landing  # noqa: E402
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


def expect_landing_error(value: object, pattern: str) -> None:
    try:
        landing.derive_bound_landing_command(value)
    except landing.LandingCommandError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError(f"expected LandingCommandError containing {pattern!r}")


def sample_ast() -> str:
    return canonical(
        [
            {"kind": "takeoff", "height_m": 0.8},
            {"kind": "move", "direction": "forward", "distance_m": 0.3},
            {"kind": "turn", "angle_deg": 45},
            {"kind": "land"},
        ]
    )


def wait_ast(seconds: object = 0.4) -> str:
    return canonical(
        [
            {"kind": "takeoff", "height_m": 0.8},
            {"kind": "wait", "seconds": seconds},
            {"kind": "land"},
        ]
    )


def advance_to_landing(domain: sequence.PhysicalProgramSequence) -> None:
    first = domain.reserve_next_motion()
    domain.complete_motion(first)
    second = domain.reserve_next_motion()
    domain.complete_motion(second)


def test_exact_order_and_claim_identity() -> None:
    domain = sequence.PhysicalProgramSequence(sample_ast())
    require(domain.next_index == 1, "sequence must begin immediately after completed takeoff")
    require(domain.next_step_kind == "move", "exact next kind must derive from AST")
    require(not domain.completed, "fresh post-takeoff sequence cannot be complete")

    first = domain.reserve_next_motion()
    motion = domain.motion_for_claim(first)
    require(
        motion == sequence.SequencedInflightMotion(1, "move", "forward", 0.3, None),
        "first in-flight motion must come from exact AST index 1",
    )
    expect_error(lambda: getattr(domain, "next_step_kind"), "pending")
    expect_error(domain.reserve_next_motion, "pending")
    expect_error(lambda: domain.complete_motion(object()), "motion claim")

    domain.complete_motion(first)
    require(domain.next_index == 2, "causal completion alone advances the cursor")
    require(domain.next_step_kind == "turn", "turn must remain exact next kind")
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
    domain.complete_motion(retry)

    require(domain.next_index == 3, "completed motions must expose exact terminal landing")
    require(domain.next_step_kind == "land", "landing must be exact next kind")
    landing_claim = domain.reserve_terminal_landing()
    require(
        domain.landing_for_claim(landing_claim) == sequence.SequencedTerminalLanding(3),
        "terminal landing must preserve exact AST index",
    )
    expect_error(domain.reserve_next_motion, "pending")
    expect_error(lambda: domain.complete_landing(object()), "landing claim")

    domain.release_unemitted(landing_claim)
    require(domain.next_index == 3, "rejected/unemitted landing cannot advance the cursor")
    landing_retry = domain.reserve_terminal_landing()
    domain.complete_landing(landing_retry)
    require(domain.next_index == 4, "causal landing completion advances past final statement")
    require(domain.completed, "exact program completes only after terminal landing completion")
    require(domain.next_step_kind is None, "completed program exposes no next step")
    expect_error(domain.reserve_terminal_landing, "not the next")


def test_exact_wait_is_no_effect_sequence_step() -> None:
    domain = sequence.PhysicalProgramSequence(wait_ast())
    require(domain.next_step_kind == "wait", "exact wait must be visible as next step kind")
    claim = domain.reserve_next_wait()
    wait = domain.wait_for_claim(claim)
    require(wait == sequence.SequencedWait(1, 0.4), "wait duration must derive from exact AST")
    expect_error(domain.reserve_next_wait, "pending")
    expect_error(lambda: domain.wait_for_claim(object()), "wait claim")
    try:
        domain.release_unemitted(claim)
    except sequence.PhysicalProgramSequenceError as exc:
        require("effect claim" in str(exc), "wait must not be classified as an unemitted effect")
    else:
        raise AssertionError("no-effect wait entered physical effect release API")
    domain.complete_wait(claim)
    require(domain.next_step_kind == "land", "full wait completion alone advances to land")
    landing_claim = domain.reserve_terminal_landing()
    domain.complete_landing(landing_claim)
    require(domain.completed, "wait program completes only after terminal landing")


def test_failed_wait_is_terminal_without_completion() -> None:
    domain = sequence.PhysicalProgramSequence(wait_ast())
    claim = domain.reserve_next_wait()
    domain.fail_wait(claim, "watchdog/session certainty lost during wait")
    require(domain.terminal, "incomplete trusted wait must fail the sequence closed")
    require(domain.next_index == 1, "failed wait cannot manufacture completion")
    require(not domain.completed, "failed wait cannot complete exact program")
    expect_error(lambda: getattr(domain, "next_step_kind"), "terminal")
    expect_error(domain.reserve_next_wait, "terminal")


def test_caller_cannot_select_motion_wait_index_or_landing() -> None:
    domain = sequence.PhysicalProgramSequence(sample_ast())
    try:
        domain.reserve_next_motion({"kind": "turn", "angle_deg": -90})
    except TypeError:
        pass
    else:
        raise AssertionError("caller-selected motion unexpectedly entered sequencing API")

    wait_domain = sequence.PhysicalProgramSequence(wait_ast())
    try:
        wait_domain.reserve_next_wait(0.1)
    except TypeError:
        pass
    else:
        raise AssertionError("caller-selected wait duration unexpectedly entered sequencing API")

    try:
        domain.reserve_terminal_landing({"height_m": 0.1})
    except TypeError:
        pass
    else:
        raise AssertionError("caller-selected landing unexpectedly entered sequencing API")

    expect_error(domain.reserve_terminal_landing, "not the next")
    claim = domain.reserve_next_motion()
    require(
        domain.motion_for_claim(claim).kind == "move",
        "bounded substitute motion cannot replace exact next AST statement",
    )


def test_ambiguous_motion_or_landing_is_terminal() -> None:
    motion_domain = sequence.PhysicalProgramSequence(sample_ast())
    claim = motion_domain.reserve_next_motion()
    motion_domain.mark_ambiguous(claim, "accepted effect completion became uncertain")
    require(motion_domain.terminal, "ambiguous emitted motion must make sequencing terminal")
    require(motion_domain.next_index == 1, "ambiguity cannot manufacture completion")
    expect_error(motion_domain.reserve_next_motion, "terminal")

    landing_domain = sequence.PhysicalProgramSequence(sample_ast())
    advance_to_landing(landing_domain)
    landing_claim = landing_domain.reserve_terminal_landing()
    landing_domain.mark_ambiguous(landing_claim, "landing completion became uncertain")
    require(landing_domain.terminal, "ambiguous emitted landing must make sequencing terminal")
    require(not landing_domain.completed, "ambiguous landing cannot manufacture program completion")
    require(landing_domain.next_index == 3, "ambiguous landing cannot advance final cursor")
    expect_error(landing_domain.reserve_terminal_landing, "terminal")


def test_complete_envelope_is_validated_before_flight() -> None:
    for statement in (
        {"kind": "land"},
        {"kind": "vertical", "direction": "up", "distance_m": 0.2},
        {"kind": "move", "direction": "forward", "distance_m": 0.3, "extra": True},
        {"kind": "move", "direction": "forward", "distance_m": 20},
        {"kind": "turn", "angle_deg": 0},
        {"kind": "wait", "seconds": 0},
        {"kind": "wait", "seconds": 5.1},
        {"kind": "wait", "seconds": 0.4, "extra": True},
        {"kind": "repeat", "count": 2, "body": []},
    ):
        ast = canonical(
            [
                {"kind": "takeoff", "height_m": 0.8},
                statement,
                {"kind": "land"},
            ]
        )
        expect_error(lambda ast=ast: sequence.PhysicalProgramSequence(ast), "next")


def test_wait_bounds_match_authoritative_semantic_ast() -> None:
    source = SEMANTIC_AST.read_text(encoding="utf-8")
    require(
        "wait_s:{min:0.1,max:5.0}" in source,
        "authoritative semantic AST wait envelope changed without physical contract update",
    )
    require(sequence.MIN_WAIT_SECONDS == 0.1, "physical wait minimum must match Runtime v2")
    require(sequence.MAX_WAIT_SECONDS == 5.0, "physical wait maximum must match Runtime v2")
    sequence.PhysicalProgramSequence(wait_ast(sequence.MIN_WAIT_SECONDS))
    # JSON.stringify serializes the integer-valued Number 5.0 as 5; keep this
    # fixture byte-canonical while exercising the exact same maximum bound.
    sequence.PhysicalProgramSequence(wait_ast(int(sequence.MAX_WAIT_SECONDS)))


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


def test_exact_bound_command_10_landing_semantics() -> None:
    binding = sample_ast()
    command = landing.derive_bound_landing_command(binding)
    require(command.ast_binding == binding, "landing command preserves exact AST binding")
    require(command.descent_m == 0.8, "landing descent derives exact bound takeoff height")
    require(
        len(command.request) == struct.calcsize("<BBf?f?f"),
        "command 10 packet size matches pinned firmware layout",
    )
    fields = struct.unpack("<BBf?f?f", command.request)
    require(fields[0] == 10, "command id is LAND_WITH_VELOCITY")
    require(fields[1] == 0, "landing group mask is zero")
    require(abs(fields[2] - 0.8) < 1e-6, "relative descent is exact takeoff height")
    require(fields[3] is True, "landing height is relative and positive downward")
    require(fields[4] == 0.0, "ignored yaw payload stays neutral")
    require(fields[5] is True, "current yaw is preserved")
    require(abs(fields[6] - 0.5) < 1e-6, "explicit landing velocity is 0.5 m/s")

    boundary_only = canonical(
        [
            {"kind": "takeoff", "height_m": 0.5},
            {"kind": "land"},
        ]
    )
    require(
        landing.derive_bound_landing_command(boundary_only).descent_m == 0.5,
        "boundary-only exact program derives the same relative landing policy",
    )
    require(
        landing.derive_bound_landing_command(wait_ast()).descent_m == 0.8,
        "no-effect wait remains inside exact landing command envelope",
    )


def test_landing_command_fails_closed_on_unsupported_envelope() -> None:
    unsupported = canonical(
        [
            {"kind": "takeoff", "height_m": 0.8},
            {"kind": "vertical", "direction": "down", "distance_m": 0.2},
            {"kind": "land"},
        ]
    )
    expect_landing_error(unsupported, "next")

    malformed_final = canonical(
        [
            {"kind": "takeoff", "height_m": 0.8},
            {"kind": "land", "extra": True},
        ]
    )
    expect_landing_error(malformed_final, "end")

    too_high = canonical(
        [
            {"kind": "takeoff", "height_m": 1.6},
            {"kind": "land"},
        ]
    )
    expect_landing_error(too_high, "bounds")


def test_landing_command_has_no_effect_or_caller_parameter_surface() -> None:
    source = (PHYSICAL / "landing_command.py").read_text(encoding="utf-8")
    for forbidden in (
        "send_packet(",
        "HighLevelCommander(",
        "PowerSwitch(",
        "teacher_decision",
        "caller_height",
        "caller_velocity",
        "COMMAND_STOP",
    ):
        require(forbidden not in source, "pure landing semantics leaked authority: " + forbidden)

    try:
        landing.derive_bound_landing_command(sample_ast(), 0.2)
    except TypeError:
        pass
    else:
        raise AssertionError("caller-selected landing distance entered pure command API")


def main() -> int:
    test_exact_order_and_claim_identity()
    test_exact_wait_is_no_effect_sequence_step()
    test_failed_wait_is_terminal_without_completion()
    test_caller_cannot_select_motion_wait_index_or_landing()
    test_ambiguous_motion_or_landing_is_terminal()
    test_complete_envelope_is_validated_before_flight()
    test_wait_bounds_match_authoritative_semantic_ast()
    test_exact_canonical_ast_and_flight_boundaries_are_required()
    test_exact_bound_command_10_landing_semantics()
    test_landing_command_fails_closed_on_unsupported_envelope()
    test_landing_command_has_no_effect_or_caller_parameter_surface()
    print(
        "PASS exact physical-program sequencing validates the complete supported envelope, "
        "preserves exact no-effect wait pacing and terminal landing order, and derives "
        "pinned command 10 solely from the teacher-bound canonical AST"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

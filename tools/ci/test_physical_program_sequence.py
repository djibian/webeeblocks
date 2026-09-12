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


def vertical_ast() -> str:
    return canonical(
        [
            {"kind": "takeoff", "height_m": 0.8},
            {"kind": "vertical", "direction": "up", "distance_m": 0.3},
            {"kind": "move", "direction": "forward", "distance_m": 0.2},
            {"kind": "vertical", "direction": "down", "distance_m": 0.2},
            {"kind": "land"},
        ]
    )


def light_ast() -> str:
    return canonical(
        [
            {"kind": "takeoff", "height_m": 0.8},
            {"kind": "set_light", "color": "red"},
            {"kind": "set_light", "color": "off"},
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


def test_exact_vertical_sequence_tracks_only_completed_nominal_altitude() -> None:
    domain = sequence.PhysicalProgramSequence(vertical_ast())
    require(abs(domain.nominal_altitude_m - 0.8) < 1e-9, "nominal altitude starts at exact takeoff height")
    require(abs(domain.planned_terminal_altitude_m - 0.9) < 1e-9, "whole-program vertical path derives exact final altitude")
    require(domain.next_step_kind == "vertical", "first vertical statement remains exact next kind")

    first = domain.reserve_next_motion()
    vertical_up = domain.motion_for_claim(first)
    require(
        vertical_up == sequence.SequencedInflightMotion(1, "vertical", "up", 0.3, None),
        "vertical claim must preserve exact AST direction and distance",
    )
    domain.release_unemitted(first)
    require(abs(domain.nominal_altitude_m - 0.8) < 1e-9, "rejected vertical effect cannot change nominal altitude")
    require(domain.next_index == 1, "rejected vertical effect cannot advance exact cursor")

    first = domain.reserve_next_motion()
    domain.complete_motion(first)
    require(abs(domain.nominal_altitude_m - 1.1) < 1e-9, "completed climb advances host-owned nominal altitude")

    horizontal = domain.reserve_next_motion()
    require(domain.motion_for_claim(horizontal).kind == "move", "horizontal step remains exact")
    domain.complete_motion(horizontal)
    require(abs(domain.nominal_altitude_m - 1.1) < 1e-9, "horizontal completion is altitude-neutral")

    descent = domain.reserve_next_motion()
    require(
        domain.motion_for_claim(descent) == sequence.SequencedInflightMotion(3, "vertical", "down", 0.2, None),
        "descent must preserve exact AST direction and distance",
    )
    domain.complete_motion(descent)
    require(abs(domain.nominal_altitude_m - 0.9) < 1e-9, "completed descent updates exact nominal altitude")
    require(domain.next_step_kind == "land", "vertical sequence reaches exact terminal landing")


def test_exact_light_sequence_is_effectful_and_altitude_neutral() -> None:
    domain = sequence.PhysicalProgramSequence(light_ast())
    require(domain.next_step_kind == "set_light", "exact set_light must remain visible as next step")
    require(domain.planned_terminal_altitude_m == 0.8, "light effects are altitude-neutral")

    first = domain.reserve_next_light()
    require(
        domain.light_for_claim(first) == sequence.SequencedLight(1, "red"),
        "first light effect must preserve exact AST color and index",
    )
    expect_error(domain.reserve_next_light, "pending")
    expect_error(lambda: domain.light_for_claim(object()), "set_light claim")

    domain.release_unemitted(first)
    require(domain.next_index == 1, "unemitted/rejected light effect cannot advance cursor")
    retry = domain.reserve_next_light()
    require(
        domain.light_for_claim(retry) == sequence.SequencedLight(1, "red"),
        "released light statement must remain exact next effect",
    )
    domain.complete_light(retry)
    require(domain.next_index == 2, "definitive light completion advances exactly once")
    require(domain.nominal_altitude_m == 0.8, "completed light effect is altitude-neutral")

    second = domain.reserve_next_light()
    require(
        domain.light_for_claim(second) == sequence.SequencedLight(2, "off"),
        "second exact light color must remain teacher-bound",
    )
    domain.complete_light(second)
    require(domain.next_step_kind == "land", "completed exact light effects expose terminal landing")
    landing_claim = domain.reserve_terminal_landing()
    domain.complete_landing(landing_claim)
    require(domain.completed, "light program completes only after exact terminal landing")


def test_light_palette_and_shape_are_validated_before_flight() -> None:
    source = SEMANTIC_AST.read_text(encoding="utf-8")
    for color in sequence.LIGHT_COLORS:
        require(
            f"'{color}'" in source,
            "authoritative semantic AST light palette changed without physical contract update",
        )
        ast = canonical(
            [
                {"kind": "takeoff", "height_m": 0.8},
                {"kind": "set_light", "color": color},
                {"kind": "land"},
            ]
        )
        domain = sequence.PhysicalProgramSequence(ast)
        claim = domain.reserve_next_light()
        require(domain.light_for_claim(claim).color == color, "exact palette color must round-trip")

    for statement in (
        {"kind": "set_light", "color": "purple"},
        {"kind": "set_light", "color": 1},
        {"kind": "set_light", "color": "red", "extra": True},
    ):
        ast = canonical(
            [
                {"kind": "takeoff", "height_m": 0.8},
                statement,
                {"kind": "land"},
            ]
        )
        expect_error(lambda ast=ast: sequence.PhysicalProgramSequence(ast), "set_light")


def test_ambiguous_light_is_terminal() -> None:
    domain = sequence.PhysicalProgramSequence(light_ast())
    claim = domain.reserve_next_light()
    domain.mark_ambiguous(claim, "Color LED acknowledgement/readback became uncertain")
    require(domain.terminal, "ambiguous emitted light effect must make sequencing terminal")
    require(domain.next_index == 1, "ambiguous light effect cannot manufacture completion")
    expect_error(domain.reserve_next_light, "terminal")


def test_vertical_cumulative_bounds_are_rejected_before_flight() -> None:
    source = SEMANTIC_AST.read_text(encoding="utf-8")
    require(
        "vertical_m:{min:0.1,max:0.8}" in source,
        "authoritative semantic AST vertical envelope changed without physical contract update",
    )
    require(sequence.MIN_NOMINAL_ALTITUDE_M == 0.2, "physical nominal altitude minimum matches Runtime v2")
    require(sequence.MAX_NOMINAL_ALTITUDE_M == 1.5, "physical nominal altitude maximum matches Runtime v2")

    for direction, distance_m in (("up", 0.8), ("down", 0.7)):
        ast = canonical(
            [
                {"kind": "takeoff", "height_m": 0.8},
                {"kind": "vertical", "direction": direction, "distance_m": distance_m},
                {"kind": "land"},
            ]
        )
        expect_error(
            lambda ast=ast: sequence.PhysicalProgramSequence(ast),
            "nominal physical altitude",
        )


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

    light_domain = sequence.PhysicalProgramSequence(light_ast())
    try:
        light_domain.reserve_next_light("blue")
    except TypeError:
        pass
    else:
        raise AssertionError("caller-selected light color unexpectedly entered sequencing API")

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
        {"kind": "vertical", "direction": "up", "distance_m": 0.9},
        {"kind": "vertical", "direction": "sideways", "distance_m": 0.2},
        {"kind": "move", "direction": "forward", "distance_m": 0.3, "extra": True},
        {"kind": "move", "direction": "forward", "distance_m": 20},
        {"kind": "turn", "angle_deg": 0},
        {"kind": "wait", "seconds": 0},
        {"kind": "wait", "seconds": 5.1},
        {"kind": "wait", "seconds": 0.4, "extra": True},
        {"kind": "set_light", "color": "purple"},
        {"kind": "set_light", "color": "red", "extra": True},
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
    require(command.descent_m == 0.8, "altitude-neutral program lands from exact final nominal height")
    require(
        len(command.request) == struct.calcsize("<BBf?f?f"),
        "command 10 packet size matches pinned firmware layout",
    )
    fields = struct.unpack("<BBf?f?f", command.request)
    require(fields[0] == 10, "command id is LAND_WITH_VELOCITY")
    require(fields[1] == 0, "landing group mask is zero")
    require(abs(fields[2] - 0.8) < 1e-6, "relative descent is exact final nominal altitude")
    require(fields[3] is True, "landing height is relative and positive downward")
    require(fields[4] == 0.0, "ignored yaw payload stays neutral")
    require(fields[5] is True, "current yaw is preserved")
    require(abs(fields[6] - 0.5) < 1e-6, "explicit landing velocity is 0.5 m/s")

    vertical = landing.derive_bound_landing_command(vertical_ast())
    require(abs(vertical.descent_m - 0.9) < 1e-9, "terminal descent follows exact cumulative vertical program")
    vertical_fields = struct.unpack("<BBf?f?f", vertical.request)
    require(abs(vertical_fields[2] - 0.9) < 1e-6, "command 10 carries exact final nominal altitude")

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
    require(
        landing.derive_bound_landing_command(light_ast()).descent_m == 0.8,
        "bottom Color LED effects remain altitude-neutral for terminal landing",
    )


def test_landing_command_fails_closed_on_unsupported_envelope() -> None:
    out_of_bounds = canonical(
        [
            {"kind": "takeoff", "height_m": 0.8},
            {"kind": "vertical", "direction": "down", "distance_m": 0.7},
            {"kind": "land"},
        ]
    )
    expect_landing_error(out_of_bounds, "nominal physical altitude")

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
    test_exact_vertical_sequence_tracks_only_completed_nominal_altitude()
    test_exact_light_sequence_is_effectful_and_altitude_neutral()
    test_light_palette_and_shape_are_validated_before_flight()
    test_ambiguous_light_is_terminal()
    test_vertical_cumulative_bounds_are_rejected_before_flight()
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
        "PASS exact physical-program sequencing validates bounded cumulative vertical state, "
        "preserves exact bottom Color LED effects, no-effect pacing and terminal landing order, "
        "and derives pinned command 10 solely from the teacher-bound canonical AST"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

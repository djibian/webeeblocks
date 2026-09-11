#!/usr/bin/env python3
"""Exact-AST sequencing state for trusted physical flight effects.

The #287 takeoff consumer derives its effect from the first statement in the
exact teacher-authorized canonical AST. Later effects must preserve that
property: a bounded caller-selected motion or landing request is not equivalent
to the next statement of the authorized program.

This module provides the small non-effect state machine needed by the physical
host. It starts only after a caller has already established the first takeoff
statement by other trusted means, eagerly validates the complete currently
supported envelope (move/turn statements followed by one exact terminal land),
reserves exactly the next statement, and advances only after the trusted effect
consumer reports definitive causal completion. A rejected/unemitted attempt may
be released without advancing; an ambiguous emitted outcome makes the sequence
terminal.

It emits no CRTP command and accepts no caller-selected motion, program index,
landing parameter, completion proof or authority object.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

import high_level_semantics
import takeoff_command


class PhysicalProgramSequenceError(RuntimeError):
    """Fail-closed error for exact physical-program sequencing."""


@dataclass(frozen=True, slots=True)
class SequencedInflightMotion:
    """One exact next motion derived from the immutable canonical AST."""

    index: int
    kind: str
    direction: str | None
    distance_m: float | None
    angle_deg: float | None


@dataclass(frozen=True, slots=True)
class SequencedTerminalLanding:
    """The one exact terminal landing boundary of the immutable canonical AST."""

    index: int


class _MotionClaim:
    __slots__ = ("motion",)

    def __init__(self, motion: SequencedInflightMotion) -> None:
        self.motion = motion


class _LandingClaim:
    __slots__ = ("landing",)

    def __init__(self, landing: SequencedTerminalLanding) -> None:
        self.landing = landing


class PhysicalProgramSequence:
    """Trusted-host-local cursor beginning immediately after completed takeoff."""

    def __init__(self, ast_binding: str) -> None:
        # Reuse the exact canonical parser and first-statement validation already
        # integrated for #289. The return value is intentionally discarded: the
        # call proves that index 0 is the exact bounded takeoff statement.
        try:
            takeoff_command.derive_bound_takeoff_command(ast_binding)
            parsed = takeoff_command._parse_ast_binding(ast_binding)
        except takeoff_command.TakeoffCommandError as exc:
            raise PhysicalProgramSequenceError(str(exc)) from exc

        program = parsed["program"]
        if not isinstance(program, list):
            raise PhysicalProgramSequenceError("physical AST program is unavailable")
        final_statement = program[-1]
        if (
            not isinstance(final_statement, dict)
            or set(final_statement) != {"kind"}
            or final_statement.get("kind") != "land"
        ):
            raise PhysicalProgramSequenceError(
                "physical AST must end with the exact landing statement"
            )

        self._ast_binding = ast_binding
        self._program = tuple(program)

        # This production slice supports only horizontal move / turn between the
        # exact takeoff and terminal landing boundaries. Validate the complete
        # envelope before reset/takeoff, rather than discovering an unsupported
        # statement only after the aircraft is already flying.
        for index in range(1, len(self._program) - 1):
            self._motion_at(index)

        self._next_index = 1
        self._pending: _MotionClaim | _LandingClaim | None = None
        self._terminal_reason: str | None = None
        self._lock = Lock()

    @property
    def ast_binding(self) -> str:
        return self._ast_binding

    @property
    def next_index(self) -> int:
        with self._lock:
            return self._next_index

    @property
    def terminal(self) -> bool:
        with self._lock:
            return self._terminal_reason is not None

    @property
    def terminal_reason(self) -> str | None:
        with self._lock:
            return self._terminal_reason

    @property
    def completed(self) -> bool:
        with self._lock:
            return (
                self._terminal_reason is None
                and self._pending is None
                and self._next_index == len(self._program)
            )

    @property
    def next_effect_kind(self) -> str:
        """Expose only the exact next validated effect kind for trusted dispatch."""
        with self._lock:
            if self._terminal_reason is not None:
                raise PhysicalProgramSequenceError(
                    "physical program sequence is terminal: " + self._terminal_reason
                )
            if self._pending is not None:
                raise PhysicalProgramSequenceError(
                    "physical program already has a pending effect"
                )
            if self._next_index >= len(self._program):
                raise PhysicalProgramSequenceError(
                    "physical program sequence is already completed"
                )
            statement = self._program[self._next_index]
            if not isinstance(statement, dict):
                raise PhysicalProgramSequenceError(
                    "next physical statement is malformed"
                )
            kind = statement.get("kind")
            if kind not in {"move", "turn", "land"}:
                raise PhysicalProgramSequenceError(
                    "next exact AST statement is outside the validated physical envelope"
                )
            return kind

    def _motion_at(self, index: int) -> SequencedInflightMotion:
        if index >= len(self._program) - 1:
            raise PhysicalProgramSequenceError(
                "no in-flight motion remains before the final landing boundary"
            )
        statement = self._program[index]
        if not isinstance(statement, dict):
            raise PhysicalProgramSequenceError("next physical statement is malformed")

        kind = statement.get("kind")
        try:
            if kind == "move":
                if set(statement) != {"kind", "direction", "distance_m"}:
                    raise PhysicalProgramSequenceError(
                        "next move statement contains unsupported fields"
                    )
                direction = statement["direction"]
                distance = statement["distance_m"]
                if not isinstance(direction, str):
                    raise PhysicalProgramSequenceError(
                        "next move direction is malformed"
                    )
                # #256 remains the source of horizontal direction/distance bounds.
                target = high_level_semantics.body_relative_move(
                    direction,
                    distance,
                    0.0,
                )
                validated_distance = (
                    target.x_m
                    if direction in {"forward", "right"}
                    else -target.x_m
                )
                # body_relative_move at yaw=0 maps left/right onto Y, so preserve
                # the exact canonical scalar instead of reverse-engineering the
                # target. The call above is solely the authoritative validation.
                del validated_distance
                return SequencedInflightMotion(
                    index=index,
                    kind="move",
                    direction=direction,
                    distance_m=float(distance),
                    angle_deg=None,
                )

            if kind == "turn":
                if set(statement) != {"kind", "angle_deg"}:
                    raise PhysicalProgramSequenceError(
                        "next turn statement contains unsupported fields"
                    )
                angle = statement["angle_deg"]
                # #256 remains the source of signed turn bounds.
                high_level_semantics.relative_turn(angle)
                return SequencedInflightMotion(
                    index=index,
                    kind="turn",
                    direction=None,
                    distance_m=None,
                    angle_deg=float(angle),
                )
        except (TypeError, ValueError, high_level_semantics.HighLevelSemanticError) as exc:
            raise PhysicalProgramSequenceError(
                "next in-flight motion violates integrated #256 semantics"
            ) from exc

        raise PhysicalProgramSequenceError(
            "next exact AST statement is not a supported horizontal/turn effect"
        )

    def reserve_next_motion(self) -> object:
        """Reserve the exact next motion; no caller motion/index is accepted."""
        with self._lock:
            if self._terminal_reason is not None:
                raise PhysicalProgramSequenceError(
                    "physical program sequence is terminal: " + self._terminal_reason
                )
            if self._pending is not None:
                raise PhysicalProgramSequenceError(
                    "physical program already has a pending effect"
                )
            motion = self._motion_at(self._next_index)
            claim = _MotionClaim(motion)
            self._pending = claim
            return claim

    def motion_for_claim(self, claim: object) -> SequencedInflightMotion:
        with self._lock:
            if claim is not self._pending or not isinstance(claim, _MotionClaim):
                raise PhysicalProgramSequenceError(
                    "exact pending physical-program motion claim is required"
                )
            return claim.motion

    def complete_motion(self, claim: object) -> None:
        """Advance only after the trusted consumer proves causal completion."""
        with self._lock:
            if claim is not self._pending or not isinstance(claim, _MotionClaim):
                raise PhysicalProgramSequenceError(
                    "exact pending physical-program motion claim is required"
                )
            if claim.motion.index != self._next_index:
                raise PhysicalProgramSequenceError(
                    "pending physical-program motion claim no longer matches the cursor"
                )
            self._next_index += 1
            self._pending = None

    def reserve_terminal_landing(self) -> object:
        """Reserve the exact final land only when all prior motions completed."""
        with self._lock:
            if self._terminal_reason is not None:
                raise PhysicalProgramSequenceError(
                    "physical program sequence is terminal: " + self._terminal_reason
                )
            if self._pending is not None:
                raise PhysicalProgramSequenceError(
                    "physical program already has a pending effect"
                )
            final_index = len(self._program) - 1
            if self._next_index != final_index:
                raise PhysicalProgramSequenceError(
                    "terminal landing is not the next exact physical statement"
                )
            statement = self._program[final_index]
            if (
                not isinstance(statement, dict)
                or set(statement) != {"kind"}
                or statement.get("kind") != "land"
            ):
                raise PhysicalProgramSequenceError(
                    "exact terminal landing statement is unavailable"
                )
            claim = _LandingClaim(SequencedTerminalLanding(final_index))
            self._pending = claim
            return claim

    def landing_for_claim(self, claim: object) -> SequencedTerminalLanding:
        with self._lock:
            if claim is not self._pending or not isinstance(claim, _LandingClaim):
                raise PhysicalProgramSequenceError(
                    "exact pending physical-program landing claim is required"
                )
            return claim.landing

    def complete_landing(self, claim: object) -> None:
        """Advance past the exact terminal land only after causal completion."""
        with self._lock:
            if claim is not self._pending or not isinstance(claim, _LandingClaim):
                raise PhysicalProgramSequenceError(
                    "exact pending physical-program landing claim is required"
                )
            if (
                claim.landing.index != self._next_index
                or self._next_index != len(self._program) - 1
            ):
                raise PhysicalProgramSequenceError(
                    "pending terminal landing claim no longer matches the cursor"
                )
            self._next_index += 1
            self._pending = None

    def release_unemitted(self, claim: object) -> None:
        """Release one definitively unemitted/rejected effect without advancing."""
        with self._lock:
            if claim is not self._pending or not isinstance(
                claim, (_MotionClaim, _LandingClaim)
            ):
                raise PhysicalProgramSequenceError(
                    "exact pending physical-program claim is required"
                )
            self._pending = None

    def mark_ambiguous(self, claim: object, reason: str) -> None:
        """Make sequencing terminal after an ambiguous emitted effect."""
        if not isinstance(reason, str) or not reason.strip():
            raise PhysicalProgramSequenceError(
                "ambiguous physical-program outcome requires a reason"
            )
        with self._lock:
            if claim is not self._pending or not isinstance(
                claim, (_MotionClaim, _LandingClaim)
            ):
                raise PhysicalProgramSequenceError(
                    "exact pending physical-program claim is required"
                )
            self._terminal_reason = reason.strip()
            self._pending = None

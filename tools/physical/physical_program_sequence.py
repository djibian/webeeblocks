#!/usr/bin/env python3
"""Exact-AST sequencing state for trusted physical program steps.

The #287 takeoff consumer derives its effect from the first statement in the
exact teacher-authorized canonical AST. Later effects and no-effect semantic
steps must preserve that property: a bounded caller-selected motion, wait,
speed state or landing request is not equivalent to the next statement of the
authorized program.

This module provides the small non-effect state machine needed by the physical
host. It starts only after a caller has already established the first takeoff
statement by other trusted means, eagerly validates the complete currently
supported envelope (move/turn/wait/set_speed statements followed by one exact
terminal land), reserves exactly the next statement, and advances only after
the trusted consumer reports definitive completion. A rejected/unemitted
physical effect may be released without advancing; an ambiguous emitted outcome
makes the sequence terminal. Failed exact wait/speed no-effect steps are terminal
without being classified as emitted physical effects.

It emits no CRTP command and accepts no caller-selected motion, wait duration,
speed, program index, landing parameter, completion proof or authority object.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from threading import Lock

import high_level_semantics
import high_level_timing
import takeoff_command

# Keep the trusted physical parser aligned with semantic_ast.js's established
# Runtime v2 wait_s envelope. The CI sequencing regression asserts this exact
# cross-language contract so either side changing alone fails closed.
MIN_WAIT_SECONDS = 0.1
MAX_WAIT_SECONDS = 5.0


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
class SequencedWait:
    """One exact no-effect wait derived from the immutable canonical AST."""

    index: int
    seconds: float


@dataclass(frozen=True, slots=True)
class SequencedSpeed:
    """One exact no-effect horizontal speed-state change from the canonical AST."""

    index: int
    speed_m_s: float


@dataclass(frozen=True, slots=True)
class SequencedTerminalLanding:
    """The one exact terminal landing boundary of the immutable canonical AST."""

    index: int


class _MotionClaim:
    __slots__ = ("motion",)

    def __init__(self, motion: SequencedInflightMotion) -> None:
        self.motion = motion


class _WaitClaim:
    __slots__ = ("wait",)

    def __init__(self, wait: SequencedWait) -> None:
        self.wait = wait


class _SpeedClaim:
    __slots__ = ("speed",)

    def __init__(self, speed: SequencedSpeed) -> None:
        self.speed = speed


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

        # Validate the complete supported envelope before reset/takeoff, rather
        # than discovering an unsupported statement only after the aircraft is
        # already flying. Wait and set_speed are deliberately no-effect steps.
        for index in range(1, len(self._program) - 1):
            statement = self._program[index]
            kind = statement.get("kind") if isinstance(statement, dict) else None
            if kind == "wait":
                self._wait_at(index)
            elif kind == "set_speed":
                self._speed_at(index)
            else:
                self._motion_at(index)

        self._next_index = 1
        self._pending: _MotionClaim | _WaitClaim | _SpeedClaim | _LandingClaim | None = None
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
    def next_step_kind(self) -> str | None:
        """Return only the immutable next statement kind, never caller semantics."""
        with self._lock:
            if self._terminal_reason is not None:
                raise PhysicalProgramSequenceError(
                    "physical program sequence is terminal: " + self._terminal_reason
                )
            if self._pending is not None:
                raise PhysicalProgramSequenceError(
                    "physical program already has a pending step"
                )
            if self._next_index >= len(self._program):
                return None
            statement = self._program[self._next_index]
            if not isinstance(statement, dict) or not isinstance(statement.get("kind"), str):
                raise PhysicalProgramSequenceError("next physical statement is malformed")
            return statement["kind"]

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
                high_level_semantics.body_relative_move(direction, distance, 0.0)
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

    def _wait_at(self, index: int) -> SequencedWait:
        if index >= len(self._program) - 1:
            raise PhysicalProgramSequenceError(
                "no wait remains before the final landing boundary"
            )
        statement = self._program[index]
        if not isinstance(statement, dict) or set(statement) != {"kind", "seconds"}:
            raise PhysicalProgramSequenceError(
                "next wait statement contains unsupported fields"
            )
        if statement.get("kind") != "wait":
            raise PhysicalProgramSequenceError("next exact AST statement is not a wait")
        seconds = statement["seconds"]
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
            raise PhysicalProgramSequenceError("next wait seconds must be finite")
        parsed = float(seconds)
        if not isfinite(parsed):
            raise PhysicalProgramSequenceError("next wait seconds must be finite")
        if parsed < MIN_WAIT_SECONDS or parsed > MAX_WAIT_SECONDS:
            raise PhysicalProgramSequenceError(
                "next wait seconds violate established Runtime v2 bounds"
            )
        return SequencedWait(index=index, seconds=parsed)

    def _speed_at(self, index: int) -> SequencedSpeed:
        if index >= len(self._program) - 1:
            raise PhysicalProgramSequenceError(
                "no set_speed remains before the final landing boundary"
            )
        statement = self._program[index]
        if not isinstance(statement, dict) or set(statement) != {"kind", "speed_m_s"}:
            raise PhysicalProgramSequenceError(
                "next set_speed statement contains unsupported fields"
            )
        if statement.get("kind") != "set_speed":
            raise PhysicalProgramSequenceError(
                "next exact AST statement is not a set_speed state change"
            )
        speed = statement["speed_m_s"]
        if isinstance(speed, bool) or not isinstance(speed, (int, float)):
            raise PhysicalProgramSequenceError("next set_speed speed_m_s must be finite")
        parsed = float(speed)
        if not isfinite(parsed):
            raise PhysicalProgramSequenceError("next set_speed speed_m_s must be finite")
        if (
            parsed < high_level_timing.MIN_HORIZONTAL_SPEED_M_S
            or parsed > high_level_timing.MAX_HORIZONTAL_SPEED_M_S
        ):
            raise PhysicalProgramSequenceError(
                "next set_speed violates established physical horizontal-speed bounds"
            )
        return SequencedSpeed(index=index, speed_m_s=parsed)

    def reserve_next_motion(self) -> object:
        """Reserve the exact next motion; no caller motion/index is accepted."""
        with self._lock:
            if self._terminal_reason is not None:
                raise PhysicalProgramSequenceError(
                    "physical program sequence is terminal: " + self._terminal_reason
                )
            if self._pending is not None:
                raise PhysicalProgramSequenceError(
                    "physical program already has a pending step"
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

    def reserve_next_wait(self) -> object:
        """Reserve the exact next no-effect wait; no caller duration is accepted."""
        with self._lock:
            if self._terminal_reason is not None:
                raise PhysicalProgramSequenceError(
                    "physical program sequence is terminal: " + self._terminal_reason
                )
            if self._pending is not None:
                raise PhysicalProgramSequenceError(
                    "physical program already has a pending step"
                )
            wait = self._wait_at(self._next_index)
            claim = _WaitClaim(wait)
            self._pending = claim
            return claim

    def wait_for_claim(self, claim: object) -> SequencedWait:
        with self._lock:
            if claim is not self._pending or not isinstance(claim, _WaitClaim):
                raise PhysicalProgramSequenceError(
                    "exact pending physical-program wait claim is required"
                )
            return claim.wait

    def complete_wait(self, claim: object) -> None:
        """Advance a no-effect wait only after its full trusted duration elapsed."""
        with self._lock:
            if claim is not self._pending or not isinstance(claim, _WaitClaim):
                raise PhysicalProgramSequenceError(
                    "exact pending physical-program wait claim is required"
                )
            if claim.wait.index != self._next_index:
                raise PhysicalProgramSequenceError(
                    "pending physical-program wait claim no longer matches the cursor"
                )
            self._next_index += 1
            self._pending = None

    def fail_wait(self, claim: object, reason: str) -> None:
        """Fail closed after an incomplete no-effect wait without advancing it."""
        if not isinstance(reason, str) or not reason.strip():
            raise PhysicalProgramSequenceError(
                "failed physical-program wait requires a reason"
            )
        with self._lock:
            if claim is not self._pending or not isinstance(claim, _WaitClaim):
                raise PhysicalProgramSequenceError(
                    "exact pending physical-program wait claim is required"
                )
            self._terminal_reason = reason.strip()
            self._pending = None

    def reserve_next_speed(self) -> object:
        """Reserve the exact next no-effect speed state; no caller speed is accepted."""
        with self._lock:
            if self._terminal_reason is not None:
                raise PhysicalProgramSequenceError(
                    "physical program sequence is terminal: " + self._terminal_reason
                )
            if self._pending is not None:
                raise PhysicalProgramSequenceError(
                    "physical program already has a pending step"
                )
            speed = self._speed_at(self._next_index)
            claim = _SpeedClaim(speed)
            self._pending = claim
            return claim

    def speed_for_claim(self, claim: object) -> SequencedSpeed:
        with self._lock:
            if claim is not self._pending or not isinstance(claim, _SpeedClaim):
                raise PhysicalProgramSequenceError(
                    "exact pending physical-program set_speed claim is required"
                )
            return claim.speed

    def complete_speed(self, claim: object) -> None:
        """Advance only after the exact run-local speed state was accepted."""
        with self._lock:
            if claim is not self._pending or not isinstance(claim, _SpeedClaim):
                raise PhysicalProgramSequenceError(
                    "exact pending physical-program set_speed claim is required"
                )
            if claim.speed.index != self._next_index:
                raise PhysicalProgramSequenceError(
                    "pending physical-program set_speed claim no longer matches the cursor"
                )
            self._next_index += 1
            self._pending = None

    def fail_speed(self, claim: object, reason: str) -> None:
        """Fail closed if exact no-effect speed state cannot be safely applied."""
        if not isinstance(reason, str) or not reason.strip():
            raise PhysicalProgramSequenceError(
                "failed physical-program set_speed requires a reason"
            )
        with self._lock:
            if claim is not self._pending or not isinstance(claim, _SpeedClaim):
                raise PhysicalProgramSequenceError(
                    "exact pending physical-program set_speed claim is required"
                )
            self._terminal_reason = reason.strip()
            self._pending = None

    def reserve_terminal_landing(self) -> object:
        """Reserve the exact final land only when all prior steps completed."""
        with self._lock:
            if self._terminal_reason is not None:
                raise PhysicalProgramSequenceError(
                    "physical program sequence is terminal: " + self._terminal_reason
                )
            if self._pending is not None:
                raise PhysicalProgramSequenceError(
                    "physical program already has a pending step"
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
        """Release one definitively unemitted/rejected physical effect."""
        with self._lock:
            if claim is not self._pending or not isinstance(
                claim, (_MotionClaim, _LandingClaim)
            ):
                raise PhysicalProgramSequenceError(
                    "exact pending physical-program effect claim is required"
                )
            self._pending = None

    def mark_ambiguous(self, claim: object, reason: str) -> None:
        """Make sequencing terminal after an ambiguous emitted physical effect."""
        if not isinstance(reason, str) or not reason.strip():
            raise PhysicalProgramSequenceError(
                "ambiguous physical-program outcome requires a reason"
            )
        with self._lock:
            if claim is not self._pending or not isinstance(
                claim, (_MotionClaim, _LandingClaim)
            ):
                raise PhysicalProgramSequenceError(
                    "exact pending physical-program effect claim is required"
                )
            self._terminal_reason = reason.strip()
            self._pending = None

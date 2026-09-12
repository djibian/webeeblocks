#!/usr/bin/env python3
"""Pure terminal HighLevel landing request semantics for the physical backend.

The legacy flat physical-program path derives landing descent from the exact
teacher-bound canonical AST through :class:`PhysicalProgramSequence`.

Dynamic physical control flow cannot use that static terminal altitude because
different already-proven branches may complete at different world-Z values. For
that path, the trusted host supplies opaque non-authority runtime-altitude
evidence minted only after definitively completed selected vertical effects.
Both paths produce the same pinned Crazyflie ``COMMAND_LAND_WITH_VELOCITY``
packet and expose no caller-selected velocity, yaw, raw bytes or effect
authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import struct

import physical_dynamic_preflight
import physical_program_sequence
import runtime_nominal_altitude

LAND_WITH_VELOCITY_COMMAND = 10
LAND_GROUP_MASK = 0
LAND_VELOCITY_M_S = 0.5
_LAND_PACKET = struct.Struct("<BBf?f?f")
_EPSILON = 1e-9


class LandingCommandError(RuntimeError):
    """Fail-closed error for an unavailable exact-bound landing request."""


@dataclass(frozen=True)
class BoundLandingCommand:
    """Pure typed command derived from one exact canonical student AST binding."""

    ast_binding: str
    descent_m: float
    request: bytes


def _pack_landing(ast_binding: str, descent_m: object) -> BoundLandingCommand:
    if not isinstance(ast_binding, str) or not ast_binding.strip():
        raise LandingCommandError("landing command requires exact AST binding")
    if isinstance(descent_m, bool) or not isinstance(descent_m, (int, float)):
        raise LandingCommandError("landing descent must be finite")
    descent = float(descent_m)
    if not isfinite(descent):
        raise LandingCommandError("landing descent must be finite")
    if (
        descent < physical_program_sequence.MIN_NOMINAL_ALTITUDE_M
        or descent > physical_program_sequence.MAX_NOMINAL_ALTITUDE_M
    ):
        raise LandingCommandError(
            "landing descent violates established 0.2-1.5 m nominal-altitude bounds"
        )

    request = _LAND_PACKET.pack(
        LAND_WITH_VELOCITY_COMMAND,
        LAND_GROUP_MASK,
        descent,
        True,  # relative downward distance; firmware LAND semantics define + as down
        0.0,  # ignored because current yaw is explicitly preserved
        True,
        LAND_VELOCITY_M_S,
    )
    return BoundLandingCommand(
        ast_binding=ast_binding,
        descent_m=descent,
        request=request,
    )


def derive_bound_landing_command(ast_binding: object) -> BoundLandingCommand:
    """Derive command 10 solely from one supported flat canonical AST."""
    try:
        sequence = physical_program_sequence.PhysicalProgramSequence(ast_binding)
    except physical_program_sequence.PhysicalProgramSequenceError as exc:
        raise LandingCommandError(str(exc)) from exc
    return _pack_landing(sequence.ast_binding, sequence.planned_terminal_altitude_m)


def derive_runtime_landing_command(
    evidence: object,
) -> BoundLandingCommand:
    """Derive command 10 from host-minted branch-selected runtime altitude data.

    ``evidence`` carries no execution authority. The exact AST is revalidated
    through the conservative dynamic preflight here so forged/stale altitude data
    cannot widen the already-proven terminal envelope.
    """
    if type(evidence) is not runtime_nominal_altitude.RuntimeLandingAltitudeEvidence:
        raise LandingCommandError(
            "exact host-minted runtime landing altitude evidence is required"
        )

    try:
        safety = physical_dynamic_preflight.validate_bound_dynamic_program(
            evidence.ast_binding
        )
    except physical_dynamic_preflight.DynamicPhysicalPreflightError as exc:
        raise LandingCommandError(str(exc)) from exc

    descent = evidence.altitude_m
    if isinstance(descent, bool) or not isinstance(descent, (int, float)):
        raise LandingCommandError("runtime landing altitude is malformed")
    descent = float(descent)
    if not isfinite(descent):
        raise LandingCommandError("runtime landing altitude is malformed")

    if (
        abs(evidence.terminal_low_m - safety.terminal_min_altitude_m) > _EPSILON
        or abs(evidence.terminal_high_m - safety.terminal_max_altitude_m) > _EPSILON
    ):
        raise LandingCommandError(
            "runtime landing evidence does not match current dynamic safety proof"
        )
    if not (
        safety.terminal_min_altitude_m - _EPSILON
        <= descent
        <= safety.terminal_max_altitude_m + _EPSILON
    ):
        raise LandingCommandError(
            "runtime landing altitude is outside the proven terminal envelope"
        )

    return _pack_landing(safety.ast_binding, descent)

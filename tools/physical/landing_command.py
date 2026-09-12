#!/usr/bin/env python3
"""Pure exact-AST -> typed terminal HighLevel landing request semantics.

This module is deliberately non-authority and emits no CRTP packet. It consumes
only the exact canonical ``astBinding`` already bound by the trusted physical
host and derives the one terminal ``land`` statement after validating the whole
currently supported physical program envelope.

For the original flat deterministic slice, ``PhysicalProgramSequence`` remains
the exact source of the planned terminal altitude. Dynamic control-flow programs
are also admissible when the conservative pre-takeoff envelope proves that every
reachable branch has the same terminal nominal altitude. In that path-invariant
case the landing distance is still derived solely from the immutable teacher-
bound AST; no runtime sensor value, branch choice or caller-supplied altitude can
select the landing command. A branch-dependent terminal altitude remains fail
closed until the trusted host owns completed runtime altitude progression.

The resulting request is the pinned Crazyflie firmware
``COMMAND_LAND_WITH_VELOCITY`` packet (command 10). It descends by the exact
AST-derived terminal nominal altitude, targets the estimator-zero landing level,
preserves current yaw and uses the firmware's explicit safe-default 0.5 m/s
landing velocity.

No caller-supplied height, velocity, yaw, raw packet bytes, teacher decision,
session object or other effect authority is accepted here. A trusted physical-
host consumer must still compose this pure request with the existing teacher,
powered-session, watchdog, supervisor, SafeLink, acknowledgement, execution-
domain and fresh current-program provenance immediately before emission.
"""

from __future__ import annotations

from dataclasses import dataclass
import struct

import physical_dynamic_preflight
import physical_program_sequence

LAND_WITH_VELOCITY_COMMAND = 10
LAND_GROUP_MASK = 0
LAND_VELOCITY_M_S = 0.5
_LAND_PACKET = struct.Struct("<BBf?f?f")


class LandingCommandError(RuntimeError):
    """Fail-closed error for an unavailable exact-bound landing request."""


@dataclass(frozen=True)
class BoundLandingCommand:
    """Pure typed command derived from one exact canonical student AST binding."""

    ast_binding: str
    descent_m: float
    request: bytes


def _derive_terminal_altitude(ast_binding: object) -> tuple[str, float]:
    """Return an AST-only terminal altitude, never a runtime-selected value."""
    try:
        sequence = physical_program_sequence.PhysicalProgramSequence(ast_binding)
    except physical_program_sequence.PhysicalProgramSequenceError:
        try:
            envelope = physical_dynamic_preflight.validate_bound_dynamic_program(
                ast_binding
            )
        except physical_dynamic_preflight.DynamicPhysicalPreflightError as exc:
            raise LandingCommandError(str(exc)) from exc

        low = envelope.terminal_min_altitude_m
        high = envelope.terminal_max_altitude_m
        if low != high:
            raise LandingCommandError(
                "dynamic physical program has branch-dependent terminal nominal altitude"
            )
        return envelope.ast_binding, low

    return sequence.ast_binding, sequence.planned_terminal_altitude_m


def derive_bound_landing_command(ast_binding: object) -> BoundLandingCommand:
    """Derive command 10 solely from the exact supported canonical AST."""
    canonical_binding, descent_m = _derive_terminal_altitude(ast_binding)

    request = _LAND_PACKET.pack(
        LAND_WITH_VELOCITY_COMMAND,
        LAND_GROUP_MASK,
        descent_m,
        True,  # relative downward distance; firmware LAND semantics define + as down
        0.0,  # ignored because current yaw is explicitly preserved
        True,
        LAND_VELOCITY_M_S,
    )
    return BoundLandingCommand(
        ast_binding=canonical_binding,
        descent_m=descent_m,
        request=request,
    )

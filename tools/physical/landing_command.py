#!/usr/bin/env python3
"""Pure exact-AST -> typed terminal HighLevel landing request semantics.

This module is deliberately non-authority and emits no CRTP packet. It consumes
only the exact canonical ``astBinding`` already bound by the trusted physical
host and derives the one terminal ``land`` statement after validating the whole
currently supported physical program envelope through
:class:`physical_program_sequence.PhysicalProgramSequence`.

The resulting request is the pinned Crazyflie firmware
``COMMAND_LAND_WITH_VELOCITY`` packet (command 10). The bounded physical slice
tracks every accepted vertical statement from the exact teacher-bound program as
a host-owned nominal world-Z state. Landing therefore descends by the exact final
nominal altitude derived from that immutable AST, rather than assuming the
original takeoff height still describes the aircraft after vertical effects.
This deterministically targets the estimator-zero landing level without exposing
an independent caller-selected landing height. The command preserves current yaw
and uses the firmware's explicit safe-default 0.5 m/s landing velocity.

No caller-supplied height, velocity, yaw, raw packet bytes, teacher decision,
session object or other effect authority is accepted here. A trusted physical-
host consumer must still compose this pure request with the existing teacher,
powered-session, watchdog, supervisor, SafeLink, acknowledgement, execution-
domain and fresh current-program provenance immediately before emission.
"""

from __future__ import annotations

from dataclasses import dataclass
import struct

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


def derive_bound_landing_command(ast_binding: object) -> BoundLandingCommand:
    """Derive command 10 solely from the exact supported canonical AST."""
    try:
        sequence = physical_program_sequence.PhysicalProgramSequence(ast_binding)
        descent_m = sequence.planned_terminal_altitude_m
    except physical_program_sequence.PhysicalProgramSequenceError as exc:
        raise LandingCommandError(str(exc)) from exc

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
        ast_binding=sequence.ast_binding,
        descent_m=descent_m,
        request=request,
    )

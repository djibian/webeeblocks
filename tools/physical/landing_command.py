#!/usr/bin/env python3
"""Pure exact-AST -> typed terminal HighLevel landing request semantics.

This module is deliberately non-authority and emits no CRTP packet. It consumes
only the exact canonical ``astBinding`` already bound by the trusted physical
host and derives the one terminal ``land`` statement after validating the whole
currently supported physical program envelope through
:class:`physical_program_sequence.PhysicalProgramSequence`.

The resulting request is the pinned Crazyflie firmware
``COMMAND_LAND_WITH_VELOCITY`` packet (command 10). The bounded physical slice
supports no vertical motion between takeoff and land, so landing descends by the
exact teacher-bound absolute takeoff height relative to the current high-level
setpoint. With command 9's absolute takeoff contract and no intervening vertical
effects, this deterministically targets the estimator-zero landing level without
exposing an independent caller-selected landing height. The command preserves
current yaw and uses the firmware's explicit safe-default 0.5 m/s landing
velocity.

No caller-supplied height, velocity, yaw, raw packet bytes, teacher decision,
session object or other effect authority is accepted here. A later trusted
physical-host consumer must still compose this pure request with
#267/#266/#262/#257/#264/#272/#271/#273 and fresh #278/#249 provenance
immediately before emission.
"""

from __future__ import annotations

from dataclasses import dataclass
import struct

import physical_program_sequence
import takeoff_command

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
        takeoff = takeoff_command.derive_bound_takeoff_command(sequence.ast_binding)
    except (
        physical_program_sequence.PhysicalProgramSequenceError,
        takeoff_command.TakeoffCommandError,
    ) as exc:
        raise LandingCommandError(str(exc)) from exc

    request = _LAND_PACKET.pack(
        LAND_WITH_VELOCITY_COMMAND,
        LAND_GROUP_MASK,
        takeoff.height_m,
        True,  # relative downward distance; firmware LAND semantics define + as down
        0.0,  # ignored because current yaw is explicitly preserved
        True,
        LAND_VELOCITY_M_S,
    )
    return BoundLandingCommand(
        ast_binding=sequence.ast_binding,
        descent_m=takeoff.height_m,
        request=request,
    )

#!/usr/bin/env python3
"""Exact-program sequencing for the first trusted in-flight physical slice.

This module is deliberately not a second general WebeeBlocks interpreter.  It
consumes the canonical AST string already bound into the exact #267 run and
exposes only the next top-level in-flight statement after the separately proven
#293/#289 takeoff.  Unsupported control-flow/non-effect statements fail closed
until the shared-interpreter physical backend is extended for them.

No caller supplies motion parameters here: the next effect is derived from the
teacher-authorized/current canonical AST.  Sequence state advances only after
the trusted SETPOINT_HL transport has returned a positive, causally completed
result.
"""

from __future__ import annotations

import json
from typing import Any

from teacher_run_authorization import PhysicalRunBinding


class InflightProgramSequenceError(RuntimeError):
    """Fail-closed error for unavailable or inconsistent physical sequencing."""


class ExactInflightProgramSequence:
    """Run-local cursor over exact top-level move/turn statements."""

    def __init__(self, binding: PhysicalRunBinding) -> None:
        if type(binding) is not PhysicalRunBinding:
            raise InflightProgramSequenceError("exact #267 PhysicalRunBinding is required")
        try:
            ast = json.loads(binding.ast_binding)
        except (TypeError, json.JSONDecodeError) as exc:
            raise InflightProgramSequenceError("teacher-authorized AST binding is not JSON") from exc
        if not isinstance(ast, dict) or ast.get("version") != 1 or ast.get("semantics") != "webeeblocks-ast-v1":
            raise InflightProgramSequenceError("unsupported teacher-authorized AST envelope")
        program = ast.get("program")
        if not isinstance(program, list) or len(program) < 2:
            raise InflightProgramSequenceError("teacher-authorized program is incomplete")
        if not isinstance(program[0], dict) or program[0].get("kind") != "takeoff":
            raise InflightProgramSequenceError("teacher-authorized program does not start with takeoff")
        if not isinstance(program[-1], dict) or program[-1].get("kind") != "land":
            raise InflightProgramSequenceError("teacher-authorized program does not end with land")

        self._binding = binding
        self._program = tuple(program)
        # #293/#289 has already consumed and causally completed top-level takeoff.
        self._index = 1

    @property
    def binding(self) -> PhysicalRunBinding:
        return self._binding

    @property
    def next_program_index(self) -> int:
        return self._index

    @property
    def exhausted_for_this_slice(self) -> bool:
        return self._index >= len(self._program) - 1

    def _next_statement(self) -> dict[str, Any]:
        if self.exhausted_for_this_slice:
            raise InflightProgramSequenceError(
                "no supported in-flight statement remains before landing"
            )
        statement = self._program[self._index]
        if not isinstance(statement, dict) or not isinstance(statement.get("kind"), str):
            raise InflightProgramSequenceError("next teacher-authorized statement is malformed")
        return statement

    @property
    def next_effect_kind(self) -> str:
        """Return the next exact supported effect kind without advancing the cursor."""
        kind = self._next_statement()["kind"]
        if kind not in {"move", "turn"}:
            raise InflightProgramSequenceError(
                "next teacher-authorized statement is outside the bounded move/turn slice: "
                + kind
            )
        return kind

    def execute_next(self, transport: object, *, yaw_reader: object, timing_policy: object):
        """Execute exactly the next authorized move/turn and advance only on success."""
        if getattr(transport, "teacher_binding", None) != self._binding:
            raise InflightProgramSequenceError(
                "in-flight transport is not bound to the exact sequenced run"
            )

        statement = self._next_statement()
        kind = statement["kind"]
        if kind == "move":
            if set(statement) != {"kind", "direction", "distance_m"}:
                raise InflightProgramSequenceError(
                    "next teacher-authorized move statement is malformed"
                )
            sender = getattr(transport, "send_horizontal_move", None)
            if not callable(sender):
                raise InflightProgramSequenceError("trusted horizontal transport is unavailable")
            result = sender(
                direction=statement["direction"],
                distance_m=statement["distance_m"],
                yaw_reader=yaw_reader,
                timing_policy=timing_policy,
            )
        elif kind == "turn":
            if set(statement) != {"kind", "angle_deg"}:
                raise InflightProgramSequenceError(
                    "next teacher-authorized turn statement is malformed"
                )
            sender = getattr(transport, "send_turn", None)
            if not callable(sender):
                raise InflightProgramSequenceError("trusted turn transport is unavailable")
            result = sender(
                angle_deg=statement["angle_deg"],
                timing_policy=timing_policy,
            )
        else:
            raise InflightProgramSequenceError(
                "next teacher-authorized statement is outside the bounded move/turn slice: "
                + kind
            )

        if getattr(result, "accepted", None) is True:
            # The trusted transport returns only after its private #279 permit has
            # been paired with causal #257 completion evidence.
            self._index += 1
        return result

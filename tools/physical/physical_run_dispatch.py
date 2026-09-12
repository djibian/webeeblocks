#!/usr/bin/env python3
"""Choose the integrated static or shared-interpreter physical activation path.

The existing flat ``PhysicalProgramSequence`` remains authoritative for programs
it can represent exactly.  Programs containing shared Runtime control-flow,
variables or range expressions are rejected by that flat cursor before any
physical effect and are instead admitted only through the dynamic activation
path, whose pre-effect validator and shared interpreter own their semantics.

This module is process-local dispatch only.  It accepts no caller-selected
semantic parameter beyond the already host-staged exact binding.
"""

from __future__ import annotations

from dynamic_run_activation import activate_validated_dynamic_run
from physical_program_sequence import PhysicalProgramSequence, PhysicalProgramSequenceError
from physical_run_activation import activate_validated_run as activate_validated_static_run


def activate_validated_run(**kwargs):
    staged_binding = kwargs.get("staged_binding")
    ast_binding = getattr(staged_binding, "ast_binding", None)
    try:
        PhysicalProgramSequence(ast_binding)
    except PhysicalProgramSequenceError:
        # The dynamic path performs its complete backend-free shared-language and
        # conservative physical validation before reset/takeoff.  An invalid AST
        # therefore still fails before effect; this fallback does not authorize it.
        return activate_validated_dynamic_run(**kwargs)
    return activate_validated_static_run(**kwargs)

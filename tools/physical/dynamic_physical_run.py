#!/usr/bin/env python3
"""One-shot shared-interpreter execution inside an already activated physical run.

This helper is intentionally process-local and exposes no caller-selected semantics.
It binds the exact teacher/current-program AST to the integrated shared Runtime
interpreter and the trusted dynamic physical backend.  The causal takeoff has
already completed before this helper is entered; the interpreter's takeoff call is
verification-only inside ``TrustedDynamicPhysicalBackend``.

The helper does not own reset/teacher activation.  It owns only the interpreter
worker lifetime and the dynamic backend observers.  Any interpreter/backend
failure is returned as a fail-closed error so the surrounding trusted host can
enter its existing terminal shutdown/recovery path rather than continue ordinary
execution after a partially evaluated dynamic program.
"""

from __future__ import annotations

from dataclasses import dataclass

from dynamic_physical_backend import TrustedDynamicPhysicalBackend
from shared_interpreter_host import BoundSharedInterpreter, SharedInterpreterHostError


class DynamicPhysicalRunError(RuntimeError):
    """Fail-closed error for one exact dynamic physical interpreter run."""


@dataclass(frozen=True, slots=True)
class DynamicPhysicalRunResult:
    accepted: bool = True


class BoundDynamicPhysicalRun:
    """One-shot owner of an exact bound shared-interpreter physical execution."""

    def __init__(self, backend: TrustedDynamicPhysicalBackend) -> None:
        if type(backend) is not TrustedDynamicPhysicalBackend:
            raise DynamicPhysicalRunError("exact trusted dynamic physical backend is required")
        self._backend = backend
        self._used = False

    @property
    def ast_binding(self) -> str:
        return self._backend.ast_binding

    def execute(self) -> DynamicPhysicalRunResult:
        if self._used:
            raise DynamicPhysicalRunError("bound dynamic physical run is one-shot")
        self._used = True
        try:
            BoundSharedInterpreter(self._backend.ast_binding, self._backend).run()
        except Exception as exc:
            if isinstance(exc, DynamicPhysicalRunError):
                raise
            raise DynamicPhysicalRunError(
                "bound shared-interpreter physical run failed closed"
            ) from exc
        return DynamicPhysicalRunResult()

    def close(self) -> None:
        try:
            self._backend.close()
        except Exception as exc:
            raise DynamicPhysicalRunError(
                "dynamic physical run observer teardown is uncertain"
            ) from exc

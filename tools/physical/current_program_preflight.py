#!/usr/bin/env python3
"""Concrete non-authority freshness guard for the #249 current-program preflight.

The browser-side #249 bridge already owns the exact-current activity/profile,
backend-neutral AST and reconnect-sensitive preflight re-assertion. A physical
effect consumer must not accept an arbitrary assertion-shaped callback in place
of that boundary.

This module separates the trust adapter from the effect surface. The trusted
host integration supplies the one concrete callback that actually invokes the
#249 current-program re-assertion and returns its exact PhysicalRunBinding. That
callback is captured only by TrustedCurrentProgramPreflightFactory. The factory
mints a LiveCurrentProgramPreflightGuard through a private key; callers of the
physical effect transport receive only that guard and cannot substitute a
lambda/no-op for preflight at the effect boundary.

The guard is deliberately non-authority. A successful assertion proves only
that the trusted #249 adapter just re-established the exact profile/AST/epoch
binding expected for this run. It does not grant teacher approval, watchdog
liveness, powered-session authority, command acknowledgement or flight
completion. Those remain separate concrete gates.

The trusted-host adapter is the integration trust boundary. It must invoke the
real production #249 assertCurrentProgram path and must not be exposed to the
student/browser as a command or authority surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Callable

from teacher_run_authorization import PhysicalRunBinding


class CurrentProgramPreflightError(RuntimeError):
    """Fail-closed error for unavailable or mismatched current-program evidence."""


_MINT_KEY = object()


@dataclass(frozen=True)
class CurrentProgramPreflightEvidence:
    """One fresh non-authority exact-program assertion from the trusted adapter."""

    binding: PhysicalRunBinding
    sequence: int


class LiveCurrentProgramPreflightGuard:
    """Non-forgeable handle that re-invokes the trusted #249 adapter on demand."""

    def __init__(
        self,
        binding: PhysicalRunBinding,
        reassert_current_program: Callable[[], PhysicalRunBinding],
        *,
        _mint_key: object,
    ) -> None:
        if _mint_key is not _MINT_KEY:
            raise CurrentProgramPreflightError(
                "current-program preflight guard may only be minted by trusted host factory"
            )
        if type(binding) is not PhysicalRunBinding:
            raise CurrentProgramPreflightError(
                "exact PhysicalRunBinding is required for current-program preflight"
            )
        if not callable(reassert_current_program):
            raise CurrentProgramPreflightError(
                "trusted #249 current-program adapter is unavailable"
            )
        self._binding = binding
        self._reassert_current_program = reassert_current_program
        self._lock = Lock()
        self._sequence = 0

    @property
    def binding(self) -> PhysicalRunBinding:
        return self._binding

    def assert_current(self) -> CurrentProgramPreflightEvidence:
        """Synchronously obtain one fresh exact binding from the trusted #249 path."""
        with self._lock:
            try:
                current = self._reassert_current_program()
            except Exception as exc:
                raise CurrentProgramPreflightError(
                    "trusted #249 current-program re-assertion failed"
                ) from exc
            if type(current) is not PhysicalRunBinding:
                raise CurrentProgramPreflightError(
                    "trusted #249 adapter returned invalid current-program evidence"
                )
            if current != self._binding:
                raise CurrentProgramPreflightError(
                    "current profile/AST/connection binding differs from authorized run"
                )
            self._sequence += 1
            return CurrentProgramPreflightEvidence(
                binding=current,
                sequence=self._sequence,
            )


class TrustedCurrentProgramPreflightFactory:
    """Trusted-host adapter boundary for the production #249 re-assertion path."""

    def __init__(
        self,
        reassert_current_program: Callable[[], PhysicalRunBinding],
    ) -> None:
        if not callable(reassert_current_program):
            raise CurrentProgramPreflightError(
                "trusted #249 current-program adapter must be callable"
            )
        self._reassert_current_program = reassert_current_program

    def bind(
        self,
        binding: PhysicalRunBinding,
    ) -> LiveCurrentProgramPreflightGuard:
        """Mint one non-authority guard for one exact preflight/run binding."""
        return LiveCurrentProgramPreflightGuard(
            binding,
            self._reassert_current_program,
            _mint_key=_MINT_KEY,
        )

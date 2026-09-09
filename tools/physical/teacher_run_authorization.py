#!/usr/bin/env python3
"""Host-only one-run teacher authorization binding for future physical effects.

This module deliberately emits no Crazyflie command and exposes no HTTP/browser
surface. It captures the product trust invariant established on #157/#72:
one explicit trusted-host teacher decision may authorize one exact physical run,
bound to the canonical profile/AST preflight identity and live connection epoch.
Every later flight-capable effect must re-check that exact binding immediately
before emission. A changed profile, AST binding or connection epoch invalidates
the run authority permanently.

The teacher decision source itself remains outside this bounded primitive. A
future trusted host UI/service may supply it, but the existing browser-held
capability bearer must never be reused as that source.
"""

from __future__ import annotations

from dataclasses import dataclass
from secrets import token_urlsafe
from threading import Lock
from typing import Callable


class TeacherRunAuthorizationError(RuntimeError):
    """Fail-closed error for unavailable or invalid teacher run authority."""


@dataclass(frozen=True)
class PhysicalRunBinding:
    """Exact non-authority preflight identity that one teacher decision approves."""

    profile_id: str
    ast_binding: str
    connection_epoch: str

    def __post_init__(self) -> None:
        for name, value in (
            ("profile_id", self.profile_id),
            ("ast_binding", self.ast_binding),
            ("connection_epoch", self.connection_epoch),
        ):
            if not isinstance(value, str) or not value.strip():
                raise TeacherRunAuthorizationError(
                    f"physical run {name} must be a non-empty string"
                )
            if value != value.strip():
                raise TeacherRunAuthorizationError(
                    f"physical run {name} must not contain surrounding whitespace"
                )


_MINT_KEY = object()


class TeacherRunAuthorization:
    """One exact run authorization minted only by TrustedTeacherAuthorizer."""

    def __init__(
        self,
        binding: PhysicalRunBinding,
        run_id: str,
        *,
        _mint_key: object,
    ) -> None:
        if _mint_key is not _MINT_KEY:
            raise TeacherRunAuthorizationError(
                "teacher run authorization may only be minted by trusted host authority"
            )
        self._binding = binding
        self._run_id = run_id
        self._lock = Lock()
        self._active = True
        self._invalid_reason: str | None = None

    @property
    def binding(self) -> PhysicalRunBinding:
        return self._binding

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active

    @property
    def invalid_reason(self) -> str | None:
        with self._lock:
            return self._invalid_reason

    def invalidate(self, reason: str) -> None:
        if not isinstance(reason, str) or not reason.strip():
            raise TeacherRunAuthorizationError(
                "teacher run invalidation reason must be a non-empty string"
            )
        with self._lock:
            if self._active:
                self._active = False
                self._invalid_reason = reason.strip()

    def assert_effect_binding(
        self,
        *,
        profile_id: str,
        ast_binding: str,
        connection_epoch: str,
    ) -> None:
        """Re-check run identity immediately before one flight-capable effect.

        This method authorizes no command by itself. It only proves that this
        still-active teacher decision names the exact current binding. Any
        mismatch permanently invalidates the run so correcting inputs later
        cannot resurrect stale authority.
        """
        candidate = PhysicalRunBinding(
            profile_id=profile_id,
            ast_binding=ast_binding,
            connection_epoch=connection_epoch,
        )
        with self._lock:
            if not self._active:
                detail = self._invalid_reason or "run authority is inactive"
                raise TeacherRunAuthorizationError(
                    "teacher run authorization is unavailable: " + detail
                )
            if candidate != self._binding:
                self._active = False
                self._invalid_reason = "physical run binding changed"
                raise TeacherRunAuthorizationError(
                    "teacher run binding changed; a new explicit teacher decision is required"
                )


class TrustedTeacherAuthorizer:
    """Trusted-host boundary that turns one explicit decision into one run receipt.

    This object is intentionally process-local. A host-process restart restores
    no prior run authority. The future teacher UI remains separate; callers must
    provide a trusted decision callback for each new run.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._current: TeacherRunAuthorization | None = None

    @property
    def has_active_run(self) -> bool:
        with self._lock:
            current = self._current
        return current is not None and current.active

    def authorize_run(
        self,
        binding: PhysicalRunBinding,
        teacher_decision: Callable[[PhysicalRunBinding], bool],
    ) -> TeacherRunAuthorization:
        if not isinstance(binding, PhysicalRunBinding):
            raise TeacherRunAuthorizationError(
                "exact physical run binding is required before teacher authorization"
            )
        if not callable(teacher_decision):
            raise TeacherRunAuthorizationError(
                "trusted teacher decision callback is required"
            )

        with self._lock:
            if self._current is not None and self._current.active:
                raise TeacherRunAuthorizationError(
                    "an authorized physical run is already active"
                )

        try:
            decision = teacher_decision(binding)
        except Exception as exc:
            raise TeacherRunAuthorizationError(
                "trusted teacher decision failed"
            ) from exc
        if decision is not True:
            raise TeacherRunAuthorizationError(
                "teacher did not explicitly authorize this exact physical run"
            )

        receipt = TeacherRunAuthorization(
            binding,
            token_urlsafe(24),
            _mint_key=_MINT_KEY,
        )
        with self._lock:
            if self._current is not None and self._current.active:
                receipt.invalidate("another physical run became active")
                raise TeacherRunAuthorizationError(
                    "an authorized physical run is already active"
                )
            self._current = receipt
        return receipt

    def close_run(self, receipt: TeacherRunAuthorization, reason: str) -> None:
        if not isinstance(receipt, TeacherRunAuthorization):
            raise TeacherRunAuthorizationError(
                "trusted teacher run receipt is required"
            )
        with self._lock:
            if receipt is not self._current:
                raise TeacherRunAuthorizationError(
                    "teacher run receipt does not belong to this host authority"
                )
            receipt.invalidate(reason)
            self._current = None

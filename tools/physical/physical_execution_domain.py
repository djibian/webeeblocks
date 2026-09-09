#!/usr/bin/env python3
"""Process-local reset/effect exclusion for the trusted Crazyflie host path.

This module is deliberately a no-effect prerequisite. It owns only the
process-local lifecycle needed to compose the already established physical
safety primitives without allowing reset and flight-capable command emission to
race.

A fresh process starts in ``recovery-required``. It may not emit a physical
effect until the caller has completed the trusted #266 reset-establishment
transaction under :meth:`run_reset_establishment`. That transaction's own
fresh flight-inactive gate therefore executes while this domain holds the same
exclusion used by every later effect boundary.

An effect transaction holds that exclusion across all supplied immediate
preconditions and the caller's emission/acknowledgement boundary. Once emission
is marked, any unresolved or exceptional outcome moves the domain back to
``recovery-required``. A definitive firmware rejection restores the prior
stable phase. A positive acknowledgement moves to ``awaiting-completion`` and
no reset or later effect is eligible until a separately supplied fresh
completion proof establishes either ``flying`` or ``inactive``.

The module imports no cflib/CRTP command API and emits no packet. The later
trusted transport must compose exact preflight, #267 teacher binding, #266/#262
powered-session/watchdog state, #272 SafeLink, #271 acknowledgement freshness,
action-specific #257/#260 evidence and #256/#268 semantics/timing. Completion
proof must come from the appropriate fresh #257/#264 path; this domain does not
mint such evidence.
"""

from __future__ import annotations

from threading import RLock, get_ident
from typing import Callable

RECOVERY_REQUIRED = "recovery-required"
INACTIVE = "inactive"
FLYING = "flying"
EFFECT_UNRESOLVED = "effect-unresolved"
AWAITING_COMPLETION = "awaiting-completion"

_STABLE_EFFECT_PHASES = frozenset((INACTIVE, FLYING))
_COMPLETION_PHASES = frozenset((INACTIVE, FLYING))


class PhysicalExecutionDomainError(RuntimeError):
    """Fail-closed error for the trusted physical execution exclusion domain."""


def _require_callable(value: object, name: str) -> Callable:
    if not callable(value):
        raise PhysicalExecutionDomainError(f"{name} must be callable")
    return value


class PhysicalExecutionDomain:
    """Serialize trusted reset establishment and flight-capable effect boundaries."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._phase = RECOVERY_REQUIRED
        self._active_section: str | None = None
        self._section_owner: int | None = None

    @property
    def phase(self) -> str:
        with self._lock:
            return self._phase

    def _enter_section(self, name: str) -> None:
        self._lock.acquire()
        if self._active_section is not None:
            self._lock.release()
            raise PhysicalExecutionDomainError(
                "physical execution exclusion is already active"
            )
        self._active_section = name
        self._section_owner = get_ident()

    def _leave_section(self, expected: str) -> None:
        if (
            self._active_section != expected
            or self._section_owner != get_ident()
        ):
            raise PhysicalExecutionDomainError(
                "physical execution exclusion ownership was lost"
            )
        self._active_section = None
        self._section_owner = None
        self._lock.release()

    def run_reset_establishment(self, establish_reset: Callable[[], object]) -> object:
        """Run the complete trusted #266 reset-establishment path under exclusion.

        ``establish_reset`` must be the trusted host transaction whose own
        ``require_flight_known_inactive`` check occurs immediately before #266
        invalidates prior evidence and attempts the STM+deck reset. A failed or
        ambiguous transaction leaves this domain in ``recovery-required``.
        """
        transaction = _require_callable(
            establish_reset,
            "trusted reset-establishment transaction",
        )
        self._enter_section("reset")
        try:
            if self._phase not in (RECOVERY_REQUIRED, INACTIVE):
                raise PhysicalExecutionDomainError(
                    "STM+deck reset is blocked by current physical execution state"
                )
            # Invalidate ordinary effect eligibility before invoking any reset
            # collaborator. #266 performs its own evidence invalidation and
            # fresh flight-inactive check inside this same exclusion.
            self._phase = RECOVERY_REQUIRED
            try:
                result = transaction()
            except Exception as exc:
                raise PhysicalExecutionDomainError(
                    "trusted reset-establishment failed or is ambiguous"
                ) from exc
            if result is None:
                raise PhysicalExecutionDomainError(
                    "trusted reset-establishment returned no established session"
                )
            self._phase = INACTIVE
            return result
        finally:
            self._leave_section("reset")

    def effect_transaction(
        self,
        *immediate_preconditions: Callable[[], object],
    ) -> "PhysicalEffectTransaction":
        """Create one no-effect transaction for the next trusted command boundary.

        Preconditions are assertion-style trusted-host callables: success means
        returning normally; failure must raise. They are executed only after
        the exclusion is held and immediately before the transaction becomes
        eligible for :meth:`PhysicalEffectTransaction.mark_emitted`.
        """
        checks = tuple(
            _require_callable(check, "physical effect precondition")
            for check in immediate_preconditions
        )
        if not checks:
            raise PhysicalExecutionDomainError(
                "at least one immediate physical effect precondition is required"
            )
        return PhysicalEffectTransaction(self, checks)

    def _begin_effect(
        self,
        checks: tuple[Callable[[], object], ...],
    ) -> str:
        self._enter_section("effect")
        try:
            if self._phase not in _STABLE_EFFECT_PHASES:
                raise PhysicalExecutionDomainError(
                    "physical effect is not eligible in current execution state"
                )
            prior_phase = self._phase
            for check in checks:
                check()
            return prior_phase
        except Exception:
            self._leave_section("effect")
            raise

    def _mark_effect_emitted(self) -> None:
        if (
            self._active_section != "effect"
            or self._section_owner != get_ident()
        ):
            raise PhysicalExecutionDomainError(
                "physical effect emission is outside the execution exclusion"
            )
        self._phase = EFFECT_UNRESOLVED

    def _mark_effect_rejected(self, prior_phase: str) -> None:
        if self._phase != EFFECT_UNRESOLVED:
            raise PhysicalExecutionDomainError(
                "definitive rejection requires one emitted unresolved effect"
            )
        if prior_phase not in _STABLE_EFFECT_PHASES:
            raise PhysicalExecutionDomainError(
                "prior physical execution phase is invalid"
            )
        self._phase = prior_phase

    def _mark_effect_accepted(self) -> None:
        if self._phase != EFFECT_UNRESOLVED:
            raise PhysicalExecutionDomainError(
                "positive acknowledgement requires one emitted unresolved effect"
            )
        self._phase = AWAITING_COMPLETION

    def _close_effect(
        self,
        *,
        prior_phase: str | None,
        emitted: bool,
        resolved: bool,
    ) -> None:
        try:
            if emitted and not resolved:
                # Any exception/return after the caller crossed the effect
                # boundary without a definitive application result is
                # consequential uncertainty. Only #266 recovery may re-open
                # ordinary effect eligibility.
                self._phase = RECOVERY_REQUIRED
            elif not emitted and prior_phase in _STABLE_EFFECT_PHASES:
                self._phase = prior_phase
        finally:
            self._leave_section("effect")

    def complete_accepted_effect(
        self,
        next_phase: str,
        prove_completion: Callable[[], object],
    ) -> None:
        """Establish a fresh post-effect stable phase after positive acknowledgement.

        The proof callable runs under the same exclusion and must return exactly
        ``True``. The caller is responsible for binding it to fresh #257/#264
        evidence appropriate to the command. Unavailable/negative proof moves
        the run to ``recovery-required`` rather than guessing completion.
        """
        if next_phase not in _COMPLETION_PHASES:
            raise PhysicalExecutionDomainError(
                "post-effect phase must be exactly 'flying' or 'inactive'"
            )
        proof = _require_callable(prove_completion, "fresh effect-completion proof")
        self._enter_section("completion")
        try:
            if self._phase != AWAITING_COMPLETION:
                raise PhysicalExecutionDomainError(
                    "no positively acknowledged effect is awaiting completion"
                )
            try:
                proven = proof()
            except Exception as exc:
                self._phase = RECOVERY_REQUIRED
                raise PhysicalExecutionDomainError(
                    "fresh effect-completion proof failed or is ambiguous"
                ) from exc
            if proven is not True:
                self._phase = RECOVERY_REQUIRED
                raise PhysicalExecutionDomainError(
                    "fresh effect completion was not positively established"
                )
            self._phase = next_phase
        finally:
            self._leave_section("completion")


class PhysicalEffectTransaction:
    """One exclusion-held precondition -> emission -> acknowledgement boundary."""

    def __init__(
        self,
        domain: PhysicalExecutionDomain,
        checks: tuple[Callable[[], object], ...],
    ) -> None:
        self._domain = domain
        self._checks = checks
        self._prior_phase: str | None = None
        self._entered = False
        self._emitted = False
        self._resolved = False
        self._closed = False

    @property
    def emitted(self) -> bool:
        return self._emitted

    def __enter__(self) -> "PhysicalEffectTransaction":
        if self._entered or self._closed:
            raise PhysicalExecutionDomainError(
                "physical effect transaction cannot be re-entered"
            )
        self._prior_phase = self._domain._begin_effect(self._checks)
        self._entered = True
        return self

    def mark_emitted(self) -> None:
        """Cross the physical effect boundary immediately before the one-shot send."""
        if not self._entered or self._closed or self._emitted:
            raise PhysicalExecutionDomainError(
                "physical effect transaction is not prepared for emission"
            )
        self._domain._mark_effect_emitted()
        self._emitted = True

    def mark_definitive_rejection(self) -> None:
        """Record a definitive non-zero firmware result from the exact request."""
        if not self._emitted or self._resolved or self._prior_phase is None:
            raise PhysicalExecutionDomainError(
                "definitive rejection requires one unresolved emitted effect"
            )
        self._domain._mark_effect_rejected(self._prior_phase)
        self._resolved = True

    def mark_accepted(self) -> None:
        """Record a definitive zero firmware result; completion remains required."""
        if not self._emitted or self._resolved:
            raise PhysicalExecutionDomainError(
                "positive acknowledgement requires one unresolved emitted effect"
            )
        self._domain._mark_effect_accepted()
        self._resolved = True

    def close(self) -> None:
        if self._closed:
            return
        if not self._entered:
            self._closed = True
            return
        self._domain._close_effect(
            prior_phase=self._prior_phase,
            emitted=self._emitted,
            resolved=self._resolved,
        )
        self._closed = True

    def __exit__(self, exc_type, exc, traceback) -> bool:
        self.close()
        return False

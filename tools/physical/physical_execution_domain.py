#!/usr/bin/env python3
"""Process-local reset/effect exclusion for the trusted Crazyflie host path.

This module is deliberately a no-effect prerequisite. It owns one
process-wide lifecycle, shared by every `PhysicalExecutionDomain` handle, needed
to compose the already established physical safety primitives without allowing
reset and flight-capable command emission to race through independently
constructed handles.

A fresh process starts in ``recovery-required``. It may not emit a physical
effect until the caller has completed the trusted #266 reset-establishment
transaction under :meth:`run_reset_establishment`. That transaction's own
fresh flight-inactive gate therefore executes while this domain holds the same
exclusion used by every later effect boundary.

An effect transaction holds that exclusion across all supplied immediate
preconditions and the caller's emission/acknowledgement boundary. Once emission
is marked, any unresolved or exceptional outcome moves the domain back to
``recovery-required``. A definitive firmware rejection restores the prior
stable phase. A positive acknowledgement moves to ``awaiting-completion`` and mints one
opaque one-shot completion permit. No reset or later effect is eligible until
the trusted consumer presents that exact permit together with a fresh completion
proof establishing either ``flying`` or ``inactive``.

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
_COMPLETION_MINT_KEY = object()


class PhysicalExecutionDomainError(RuntimeError):
    """Fail-closed error for the trusted physical execution exclusion domain."""


def _require_callable(value: object, name: str) -> Callable:
    if not callable(value):
        raise PhysicalExecutionDomainError(f"{name} must be callable")
    return value


class AcceptedEffectCompletionPermit:
    """Opaque one-shot capability for completing one exact accepted effect.

    This permit proves only which positive acknowledgement is pending. It grants
    no physical authority and does not prove trajectory completion by itself.
    The trusted effect consumer must keep it private and pair it with the
    appropriate fresh #257/#264 completion observation.
    """

    __slots__ = ()

    def __init__(self, *, _mint_key: object) -> None:
        if _mint_key is not _COMPLETION_MINT_KEY:
            raise PhysicalExecutionDomainError(
                "accepted-effect completion permit may only be minted by the execution domain"
            )


class _ProcessExecutionState:
    """Single trusted-host lifecycle shared by every handle in this process."""

    def __init__(self) -> None:
        self.lock = RLock()
        self.phase = RECOVERY_REQUIRED
        self.pending_completion: AcceptedEffectCompletionPermit | None = None
        self.active_section: str | None = None
        self.section_owner: int | None = None


_PROCESS_STATE = _ProcessExecutionState()


class PhysicalExecutionDomain:
    """Handle onto the one process-wide trusted physical execution domain."""

    @property
    def phase(self) -> str:
        with _PROCESS_STATE.lock:
            return _PROCESS_STATE.phase

    def _enter_section(self, name: str) -> None:
        _PROCESS_STATE.lock.acquire()
        if _PROCESS_STATE.active_section is not None:
            _PROCESS_STATE.lock.release()
            raise PhysicalExecutionDomainError(
                "physical execution exclusion is already active"
            )
        _PROCESS_STATE.active_section = name
        _PROCESS_STATE.section_owner = get_ident()

    def _leave_section(self, expected: str) -> None:
        if (
            _PROCESS_STATE.active_section != expected
            or _PROCESS_STATE.section_owner != get_ident()
        ):
            raise PhysicalExecutionDomainError(
                "physical execution exclusion ownership was lost"
            )
        _PROCESS_STATE.active_section = None
        _PROCESS_STATE.section_owner = None
        _PROCESS_STATE.lock.release()

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
            if _PROCESS_STATE.phase not in (RECOVERY_REQUIRED, INACTIVE):
                raise PhysicalExecutionDomainError(
                    "STM+deck reset is blocked by current physical execution state"
                )
            # Invalidate ordinary effect eligibility before invoking any reset
            # collaborator. #266 performs its own evidence invalidation and
            # fresh flight-inactive check inside this same exclusion.
            _PROCESS_STATE.phase = RECOVERY_REQUIRED
            _PROCESS_STATE.pending_completion = None
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
            _PROCESS_STATE.phase = INACTIVE
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
            if _PROCESS_STATE.phase not in _STABLE_EFFECT_PHASES:
                raise PhysicalExecutionDomainError(
                    "physical effect is not eligible in current execution state"
                )
            prior_phase = _PROCESS_STATE.phase
            for check in checks:
                check()
            return prior_phase
        except Exception:
            self._leave_section("effect")
            raise

    def _mark_effect_emitted(self) -> None:
        if (
            _PROCESS_STATE.active_section != "effect"
            or _PROCESS_STATE.section_owner != get_ident()
        ):
            raise PhysicalExecutionDomainError(
                "physical effect emission is outside the execution exclusion"
            )
        _PROCESS_STATE.pending_completion = None
        _PROCESS_STATE.phase = EFFECT_UNRESOLVED

    def _mark_effect_rejected(self, prior_phase: str) -> None:
        if _PROCESS_STATE.phase != EFFECT_UNRESOLVED:
            raise PhysicalExecutionDomainError(
                "definitive rejection requires one emitted unresolved effect"
            )
        if prior_phase not in _STABLE_EFFECT_PHASES:
            raise PhysicalExecutionDomainError(
                "prior physical execution phase is invalid"
            )
        _PROCESS_STATE.pending_completion = None
        _PROCESS_STATE.phase = prior_phase

    def _mark_effect_accepted(self) -> AcceptedEffectCompletionPermit:
        if _PROCESS_STATE.phase != EFFECT_UNRESOLVED:
            raise PhysicalExecutionDomainError(
                "positive acknowledgement requires one emitted unresolved effect"
            )
        permit = AcceptedEffectCompletionPermit(_mint_key=_COMPLETION_MINT_KEY)
        _PROCESS_STATE.pending_completion = permit
        _PROCESS_STATE.phase = AWAITING_COMPLETION
        return permit

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
                _PROCESS_STATE.pending_completion = None
                _PROCESS_STATE.phase = RECOVERY_REQUIRED
            elif not emitted and prior_phase in _STABLE_EFFECT_PHASES:
                _PROCESS_STATE.pending_completion = None
                _PROCESS_STATE.phase = prior_phase
        finally:
            self._leave_section("effect")

    def complete_accepted_effect(
        self,
        permit: AcceptedEffectCompletionPermit,
        next_phase: str,
        prove_completion: Callable[[], object],
    ) -> None:
        """Establish a fresh stable phase for one exact accepted effect.

        ``permit`` is minted only by the transaction that recorded this
        positive acknowledgement. A second domain handle, stale permit or
        assertion-shaped completion callback cannot substitute for it.

        The exact permit is consumed before the potentially blocking fresh
        #257/#264 completion proof. If that proof is unavailable, negative or
        ambiguous, recovery is required and the accepted effect cannot be
        retried with stale completion evidence.
        """
        if type(permit) is not AcceptedEffectCompletionPermit:
            raise PhysicalExecutionDomainError(
                "exact accepted-effect completion permit is required"
            )
        if next_phase not in _COMPLETION_PHASES:
            raise PhysicalExecutionDomainError(
                "post-effect phase must be exactly 'flying' or 'inactive'"
            )
        proof = _require_callable(prove_completion, "fresh effect-completion proof")
        self._enter_section("completion")
        try:
            if _PROCESS_STATE.phase != AWAITING_COMPLETION:
                raise PhysicalExecutionDomainError(
                    "no positively acknowledged effect is awaiting completion"
                )
            if _PROCESS_STATE.pending_completion is not permit:
                raise PhysicalExecutionDomainError(
                    "completion permit does not match the pending accepted effect"
                )

            _PROCESS_STATE.pending_completion = None
            try:
                proven = proof()
            except Exception as exc:
                _PROCESS_STATE.phase = RECOVERY_REQUIRED
                raise PhysicalExecutionDomainError(
                    "fresh effect-completion proof failed or is ambiguous"
                ) from exc
            if proven is not True:
                _PROCESS_STATE.phase = RECOVERY_REQUIRED
                raise PhysicalExecutionDomainError(
                    "fresh effect completion was not positively established"
                )
            _PROCESS_STATE.phase = next_phase
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

    def mark_accepted(self) -> AcceptedEffectCompletionPermit:
        """Record a definitive zero result and return its one-shot completion permit."""
        if not self._emitted or self._resolved:
            raise PhysicalExecutionDomainError(
                "positive acknowledgement requires one unresolved emitted effect"
            )
        permit = self._domain._mark_effect_accepted()
        self._resolved = True
        return permit

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

#!/usr/bin/env python3
"""Trusted powered-session/reset authority for the physical Crazyflie path.

The stock emergency-stop watchdog survives ordinary Crazyradio reconnects and has
no benign disable operation. A fresh watchdog lifecycle may therefore exist
only after an explicit trusted STM+deck reset plus fresh post-reset evidence.

This module provides the concrete host-only authority consumed by
watchdog_liveness.EmergencyWatchdogLivenessGuard and the smallest factory that
can mint it. A replacement host process starts with no authority: there is no
restore/import API and reconnecting or constructing a new object cannot mint
"new" state.

Reset is a recovery/setup effect because powering the STM down cuts motor
control. The factory consequently requires an explicit fresh "flight is known
inactive" gate immediately before invalidating prior evidence and issuing the
reset. Transport success alone is not reset proof: a genuinely live post-reset
session, exact reference identity/self-test evidence, an exact-bound preflight
assertion and one fresh non-fault supervisor observation are required before a
new authority is returned.

This module exposes no browser/student endpoint, teacher authorization, arming,
HighLevelCommander, setpoint, movement or landing command surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from secrets import token_hex
from threading import Lock
from typing import Callable, Mapping

from watchdog_liveness import PoweredSessionWatchdogAuthority

_STATE_NEW = "new"
_STATE_ACTIVATING = "activating"
_STATE_ACTIVE = "active"
_STATE_TERMINAL = "terminal"

_MIN_SUPERVISOR_PROTOCOL_VERSION = 12
_EXACT_AIRFRAME_MODEL = "crazyflie-2.1"
_FACTORY_TOKEN = object()


class PoweredSessionAuthorityError(RuntimeError):
    """Fail-closed trusted powered-session establishment/lifecycle error."""


def _nonempty_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PoweredSessionAuthorityError(f"{name} must be a non-empty string")
    return value.strip()


def _require_callable(value: object, name: str) -> Callable:
    if not callable(value):
        raise PoweredSessionAuthorityError(f"{name} must be callable")
    return value


class EphemeralPoweredSessionWatchdogAuthority(PoweredSessionWatchdogAuthority):
    """One non-restorable watchdog lifecycle minted only by the reset factory."""

    def __init__(
        self,
        identity: str,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise PoweredSessionAuthorityError(
                "powered-session authority can only be minted after trusted reset proof"
            )
        self._identity = _nonempty_text(identity, "powered-session identity")
        self._state = _STATE_NEW
        self._terminal_reason: str | None = None
        self._fresh_reset_proof = True
        self._lock = Lock()

    @property
    def identity(self) -> str:
        return self._identity

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def terminal_reason(self) -> str | None:
        with self._lock:
            return self._terminal_reason

    def require_fresh_reset_proof(self) -> None:
        with self._lock:
            if self._state != _STATE_NEW or not self._fresh_reset_proof:
                raise PoweredSessionAuthorityError(
                    "fresh STM+deck reset proof is unavailable for this powered session"
                )

    def begin_activation(self) -> None:
        with self._lock:
            if self._state != _STATE_NEW or not self._fresh_reset_proof:
                raise PoweredSessionAuthorityError(
                    "powered-session watchdog activation requires unconsumed reset proof"
                )
            self._fresh_reset_proof = False
            self._state = _STATE_ACTIVATING

    def mark_active(self) -> None:
        with self._lock:
            if self._state != _STATE_ACTIVATING:
                raise PoweredSessionAuthorityError(
                    "powered-session watchdog can become active only from activating"
                )
            self._state = _STATE_ACTIVE

    def mark_terminal(self, reason: str) -> None:
        normalized = _nonempty_text(reason, "powered-session terminal reason")
        with self._lock:
            if self._state == _STATE_TERMINAL:
                return
            self._fresh_reset_proof = False
            self._terminal_reason = normalized
            self._state = _STATE_TERMINAL


@dataclass(frozen=True)
class EstablishedPoweredSession:
    """Successful trusted reset/postcondition result for later host composition."""

    session: object
    connection_epoch: str
    watchdog_authority: EphemeralPoweredSessionWatchdogAuthority


class TrustedPoweredSessionFactory:
    """Establish a fresh powered-session authority from reset + live evidence.

    All collaborators are trusted-host callables. The factory owns the safety
    ordering and refuses to mint authority unless every postcondition succeeds.

    assert_bound_preflight(session, epoch) must re-assert the exact profile/AST
    preflight on the new epoch and return exactly True.
    read_fresh_supervisor(session, epoch) must use the #257 freshness path and
    return a state whose blocking_fault attribute is exactly False.
    """

    def __init__(
        self,
        *,
        require_flight_known_inactive: Callable[[], object],
        invalidate_prior_evidence: Callable[[], object],
        stm_deck_power_cycle: Callable[[], object],
        open_post_reset_session: Callable[[], object],
        close_post_reset_session: Callable[[object], object],
        read_connection_epoch: Callable[[object], str],
        read_capabilities: Callable[[object], Mapping[str, object]],
        assert_bound_preflight: Callable[[object, str], object],
        read_fresh_supervisor: Callable[[object, str], object],
        identity_factory: Callable[[], str] | None = None,
    ) -> None:
        self._require_flight_known_inactive = _require_callable(
            require_flight_known_inactive,
            "flight-inactive safety gate",
        )
        self._invalidate_prior_evidence = _require_callable(
            invalidate_prior_evidence,
            "prior-evidence invalidation",
        )
        self._stm_deck_power_cycle = _require_callable(
            stm_deck_power_cycle,
            "STM+deck power-cycle transaction",
        )
        self._open_post_reset_session = _require_callable(
            open_post_reset_session,
            "post-reset session opener",
        )
        self._close_post_reset_session = _require_callable(
            close_post_reset_session,
            "post-reset session closer",
        )
        self._read_connection_epoch = _require_callable(
            read_connection_epoch,
            "connection-epoch reader",
        )
        self._read_capabilities = _require_callable(
            read_capabilities,
            "capability reader",
        )
        self._assert_bound_preflight = _require_callable(
            assert_bound_preflight,
            "exact-bound preflight assertion",
        )
        self._read_fresh_supervisor = _require_callable(
            read_fresh_supervisor,
            "fresh supervisor reader",
        )
        self._identity_factory = identity_factory or (lambda: token_hex(16))
        _require_callable(self._identity_factory, "powered-session identity factory")

    def _validate_capabilities(self, descriptor: object) -> None:
        if not isinstance(descriptor, Mapping):
            raise PoweredSessionAuthorityError(
                "post-reset capability descriptor is unavailable"
            )
        if descriptor.get("connected") is not True:
            raise PoweredSessionAuthorityError(
                "post-reset capability descriptor is not live"
            )
        if descriptor.get("executionAuthority") is not False:
            raise PoweredSessionAuthorityError(
                "post-reset capability descriptor crossed the non-authority boundary"
            )

        identity = descriptor.get("identity")
        if not isinstance(identity, Mapping):
            raise PoweredSessionAuthorityError(
                "post-reset exact Crazyflie identity evidence is unavailable"
            )
        if (
            identity.get("model") != _EXACT_AIRFRAME_MODEL
            or identity.get("modelEvidence") != "verified"
        ):
            raise PoweredSessionAuthorityError(
                "post-reset exact Crazyflie 2.1 identity is unproven"
            )

        evidence = descriptor.get("evidence")
        if not isinstance(evidence, Mapping):
            raise PoweredSessionAuthorityError(
                "post-reset firmware/self-test evidence is unavailable"
            )
        if evidence.get("systemSelfTestPassed") is not True:
            raise PoweredSessionAuthorityError(
                "post-reset Crazyflie self-test did not pass"
            )
        protocol = evidence.get("protocolVersion")
        if isinstance(protocol, bool) or not isinstance(protocol, int):
            raise PoweredSessionAuthorityError(
                "post-reset supervisor protocol version is unavailable"
            )
        if protocol < _MIN_SUPERVISOR_PROTOCOL_VERSION:
            raise PoweredSessionAuthorityError(
                "post-reset supervisor protocol is too old for watchdog safety"
            )

    def _safe_close(self, session: object) -> str | None:
        try:
            self._close_post_reset_session(session)
            return None
        except Exception as exc:
            return f"post-reset session cleanup failed: {exc}"

    def establish(
        self,
        *,
        previous_connection_epoch: str | None = None,
    ) -> EstablishedPoweredSession:
        """Perform one explicit reset-establishment transaction.

        Prior evidence is invalidated before the physical reset attempt so an
        ambiguous transaction can never leave old authority reusable. No
        authority object exists until all postconditions have succeeded.
        """
        previous = None
        if previous_connection_epoch is not None:
            previous = _nonempty_text(
                previous_connection_epoch,
                "previous connection epoch",
            )

        try:
            safe = self._require_flight_known_inactive()
        except Exception as exc:
            raise PoweredSessionAuthorityError(
                "STM+deck reset safety gate is unavailable"
            ) from exc
        if safe is not True:
            raise PoweredSessionAuthorityError(
                "STM+deck reset requires physical flight to be explicitly known inactive"
            )

        try:
            self._invalidate_prior_evidence()
        except Exception as exc:
            raise PoweredSessionAuthorityError(
                "could not invalidate prior physical evidence before reset"
            ) from exc

        try:
            self._stm_deck_power_cycle()
        except Exception as exc:
            raise PoweredSessionAuthorityError(
                "STM+deck power-cycle transaction failed or is ambiguous"
            ) from exc

        session: object | None = None
        try:
            session = self._open_post_reset_session()
            if session is None:
                raise PoweredSessionAuthorityError(
                    "post-reset live Crazyflie session was not established"
                )

            epoch = _nonempty_text(
                self._read_connection_epoch(session),
                "post-reset connection epoch",
            )
            if previous is not None and epoch == previous:
                raise PoweredSessionAuthorityError(
                    "post-reset session reused the previous connection epoch"
                )

            descriptor = self._read_capabilities(session)
            self._validate_capabilities(descriptor)

            try:
                preflight_ok = self._assert_bound_preflight(session, epoch)
            except Exception as exc:
                raise PoweredSessionAuthorityError(
                    "exact profile/AST preflight was not re-established after reset"
                ) from exc
            if preflight_ok is not True:
                raise PoweredSessionAuthorityError(
                    "exact profile/AST preflight was not positively established after reset"
                )

            try:
                supervisor_state = self._read_fresh_supervisor(session, epoch)
            except Exception as exc:
                raise PoweredSessionAuthorityError(
                    "fresh supervisor safety observation failed after reset"
                ) from exc
            if getattr(supervisor_state, "blocking_fault", None) is not False:
                raise PoweredSessionAuthorityError(
                    "post-reset supervisor safety state is unavailable or blocking"
                )

            identity = _nonempty_text(
                self._identity_factory(),
                "powered-session identity",
            )
            authority = EphemeralPoweredSessionWatchdogAuthority(
                identity,
                _factory_token=_FACTORY_TOKEN,
            )
            return EstablishedPoweredSession(
                session=session,
                connection_epoch=epoch,
                watchdog_authority=authority,
            )
        except Exception as exc:
            cleanup_failure = None
            if session is not None:
                cleanup_failure = self._safe_close(session)
            if isinstance(exc, PoweredSessionAuthorityError):
                if cleanup_failure is None:
                    raise
                raise PoweredSessionAuthorityError(
                    f"{exc}; {cleanup_failure}"
                ) from exc
            message = f"post-reset authority establishment failed: {exc}"
            if cleanup_failure is not None:
                message += "; " + cleanup_failure
            raise PoweredSessionAuthorityError(message) from exc


def make_cflib_stm_deck_power_cycle(
    uri: str,
    *,
    power_switch_factory: Callable[[str], object] | None = None,
) -> Callable[[], None]:
    """Build, but do not execute, the trusted cflib STM+deck power-cycle effect."""
    radio_uri = _nonempty_text(uri, "Crazyradio URI")
    if not radio_uri.startswith("radio://"):
        raise PoweredSessionAuthorityError(
            "STM+deck reset requires an explicit Crazyradio radio:// URI"
        )

    def reset() -> None:
        factory = power_switch_factory
        if factory is None:
            try:
                from cflib.utils.power_switch import PowerSwitch
            except ImportError as exc:
                raise PoweredSessionAuthorityError(
                    "cflib PowerSwitch support is unavailable"
                ) from exc
            factory = PowerSwitch
        switch = factory(radio_uri)
        failure: Exception | None = None
        try:
            method = getattr(switch, "stm_power_cycle", None)
            if not callable(method):
                raise PoweredSessionAuthorityError(
                    "cflib PowerSwitch STM power-cycle operation is unavailable"
                )
            method()
        except Exception as exc:
            failure = exc

        try:
            close_method = getattr(switch, "close", None)
            if not callable(close_method):
                raise PoweredSessionAuthorityError(
                    "cflib PowerSwitch close operation is unavailable"
                )
            close_method()
        except Exception as close_exc:
            detail = f"cflib PowerSwitch cleanup failed: {close_exc}"
            if failure is not None:
                raise PoweredSessionAuthorityError(
                    f"STM+deck power-cycle failed or is ambiguous: {failure}; {detail}"
                ) from failure
            raise PoweredSessionAuthorityError(detail) from close_exc

        if failure is not None:
            raise failure

    return reset

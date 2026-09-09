#!/usr/bin/env python3
"""Independent Crazyflie emergency-stop watchdog liveness guard.

The stock Crazyflie supervisor watchdog is a fail-closed firmware safety
primitive: after the first keepalive it must continue receiving keepalives or it
enters the latching locked state. The command has no application-level reply.

Activation therefore uses the established same-supervisor-port causal fence:
send one watchdog keepalive, then require a fresh #257 GET_STATE observation on
the same unchanged connection epoch. Strict CRTP in-port ordering makes the
successful later response evidence that the earlier watchdog command reached
the firmware path first.

Watchdog state belongs to the powered STM session, not the Crazyradio
connection epoch or this Python process. A reconnect or host-process restart
must therefore never manufacture fresh watchdog certainty. This module neither
creates nor resets powered-session lifecycle state: a distinct trusted host
reset/session layer must supply that lifecycle and attest its fresh reset proof.
If that external proof is unavailable after reconstruction, this guard fails
closed before emitting a watchdog command. This module does not perform or infer
the STM+deck reset/power-cycle.

This module is safety infrastructure, not flight authority. It exposes no
arming, high-level commander, setpoint, landing, reset/power-cycle or
student/browser API.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from math import isfinite
from threading import Event, Lock, Thread, current_thread
from time import monotonic
from typing import Callable

MIN_SUPERVISOR_PROTOCOL_VERSION = 12
FIRMWARE_WATCHDOG_TIMEOUT_SECONDS = 1.0
DEFAULT_KEEPALIVE_INTERVAL_SECONDS = 0.25
DEFAULT_MAX_HOST_GAP_SECONDS = 0.75

_STATE_NEW = "new"
_STATE_ACTIVATING = "activating"
_STATE_ACTIVE = "active"
_STATE_TERMINAL = "terminal"


class WatchdogLivenessError(RuntimeError):
    """Fail-closed error for an unproven or lost watchdog liveness domain."""


class PoweredSessionWatchdogAuthority(ABC):
    """External trust boundary for powered-session watchdog certainty.

    Production implementations belong to the distinct trusted reset/session
    layer. They must preserve state across guard replacement, reconnect and
    host-process restart, and may report "new" only after separately proving the
    STM+deck reset boundary. This watchdog module provides no concrete authority.
    """

    @property
    @abstractmethod
    def identity(self) -> str:
        """Stable identity of the externally established powered session."""

    @property
    @abstractmethod
    def state(self) -> str:
        """Externally durable watchdog lifecycle state."""

    @property
    @abstractmethod
    def terminal_reason(self) -> str | None:
        """Durable terminal reason, when applicable."""

    @abstractmethod
    def require_fresh_reset_proof(self) -> None:
        """Fail unless fresh powered-session reset proof is externally established."""

    @abstractmethod
    def begin_activation(self) -> None:
        """Atomically consume external freshness before the first watchdog effect."""

    @abstractmethod
    def mark_active(self) -> None:
        """Durably commit successful causal activation."""

    @abstractmethod
    def mark_terminal(self, reason: str) -> None:
        """Durably commit terminal/lost watchdog certainty."""


def _positive_finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WatchdogLivenessError(f"{name} must be a positive finite number")
    parsed = float(value)
    if not isfinite(parsed) or parsed <= 0:
        raise WatchdogLivenessError(f"{name} must be a positive finite number")
    return parsed


def _read_powered_session_identity(lifecycle: object) -> str:
    try:
        identity = getattr(lifecycle, "identity")
    except Exception as exc:
        raise WatchdogLivenessError(
            "external trusted powered-session identity is unavailable"
        ) from exc
    if not isinstance(identity, str) or not identity.strip():
        raise WatchdogLivenessError(
            "external trusted powered-session identity must be a non-empty string"
        )
    return identity.strip()


def _read_powered_session_state(lifecycle: object) -> str:
    try:
        state = getattr(lifecycle, "state")
    except Exception as exc:
        raise WatchdogLivenessError(
            "external trusted powered-session watchdog state is unavailable"
        ) from exc
    if state not in (_STATE_NEW, _STATE_ACTIVATING, _STATE_ACTIVE, _STATE_TERMINAL):
        raise WatchdogLivenessError(
            "external trusted powered-session watchdog state is invalid"
        )
    return state


def _read_powered_session_terminal_reason(lifecycle: object) -> str | None:
    try:
        reason = getattr(lifecycle, "terminal_reason")
    except Exception as exc:
        raise WatchdogLivenessError(
            "external trusted powered-session terminal reason is unavailable"
        ) from exc
    if reason is not None and (not isinstance(reason, str) or not reason.strip()):
        raise WatchdogLivenessError(
            "external trusted powered-session terminal reason is invalid"
        )
    return reason.strip() if isinstance(reason, str) else None


def _require_powered_session_contract(lifecycle: object) -> None:
    if not isinstance(lifecycle, PoweredSessionWatchdogAuthority):
        raise WatchdogLivenessError(
            "external trusted powered-session watchdog authority is required"
        )
    _read_powered_session_identity(lifecycle)
    _read_powered_session_state(lifecycle)
    _read_powered_session_terminal_reason(lifecycle)
    for method_name in (
        "require_fresh_reset_proof",
        "begin_activation",
        "mark_active",
        "mark_terminal",
    ):
        if not callable(getattr(lifecycle, method_name, None)):
            raise WatchdogLivenessError(
                "external trusted powered-session watchdog lifecycle contract is incomplete"
            )


def _require_powered_session_reset_proof(lifecycle: object) -> None:
    try:
        lifecycle.require_fresh_reset_proof()
    except Exception as exc:
        raise WatchdogLivenessError(
            "external trusted powered-session fresh reset proof is unavailable"
        ) from exc


def _require_powered_session_new(lifecycle: object) -> None:
    _require_powered_session_reset_proof(lifecycle)
    state = _read_powered_session_state(lifecycle)
    if state == _STATE_NEW:
        return
    if state == _STATE_TERMINAL:
        reason = _read_powered_session_terminal_reason(lifecycle)
        raise WatchdogLivenessError(
            "powered-session watchdog lifecycle is terminal until a separately "
            "proven STM+deck reset establishes a fresh external lifecycle: "
            + (reason or "unknown reason")
        )
    raise WatchdogLivenessError(
        "powered-session watchdog lifecycle is not externally established fresh: "
        + state
    )


def _begin_powered_session_activation(lifecycle: object) -> None:
    _require_powered_session_new(lifecycle)
    try:
        lifecycle.begin_activation()
    except Exception as exc:
        raise WatchdogLivenessError(
            "external powered-session watchdog activation claim failed"
        ) from exc
    if _read_powered_session_state(lifecycle) != _STATE_ACTIVATING:
        raise WatchdogLivenessError(
            "external powered-session watchdog lifecycle did not enter activating state"
        )


def _mark_powered_session_active(lifecycle: object) -> None:
    try:
        lifecycle.mark_active()
    except Exception as exc:
        raise WatchdogLivenessError(
            "external powered-session watchdog active transition failed"
        ) from exc
    if _read_powered_session_state(lifecycle) != _STATE_ACTIVE:
        raise WatchdogLivenessError(
            "external powered-session watchdog lifecycle did not enter active state"
        )


def _try_mark_powered_session_terminal(lifecycle: object, reason: str) -> str | None:
    try:
        lifecycle.mark_terminal(reason)
        if _read_powered_session_state(lifecycle) != _STATE_TERMINAL:
            return "external powered-session watchdog lifecycle did not enter terminal state"
        return None
    except Exception as exc:
        return "external powered-session watchdog terminal transition failed: " + str(exc)


class EmergencyWatchdogLivenessGuard:
    """One live watchdog guard bound to connection and powered-session identity.

    Once activate() succeeds, keepalives continue until a terminal condition.
    There is deliberately no benign close/context-manager API: stopping the stock
    watchdog after activation means accepting its eventual locked/reboot state.
    """

    def __init__(
        self,
        cf: object,
        connection_epoch_reader: Callable[[], str],
        supervisor_reader: object,
        powered_session: PoweredSessionWatchdogAuthority,
        *,
        keepalive_interval_seconds: float = DEFAULT_KEEPALIVE_INTERVAL_SECONDS,
        max_host_gap_seconds: float = DEFAULT_MAX_HOST_GAP_SECONDS,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        interval = _positive_finite(
            keepalive_interval_seconds,
            "watchdog keepalive interval",
        )
        max_gap = _positive_finite(
            max_host_gap_seconds,
            "watchdog maximum host gap",
        )
        if interval >= max_gap:
            raise WatchdogLivenessError(
                "watchdog keepalive interval must be below maximum host gap"
            )
        if max_gap >= FIRMWARE_WATCHDOG_TIMEOUT_SECONDS:
            raise WatchdogLivenessError(
                "watchdog maximum host gap must be below firmware timeout"
            )
        _require_powered_session_contract(powered_session)

        self._cf = cf
        self._connection_epoch_reader = connection_epoch_reader
        self._supervisor_reader = supervisor_reader
        self._powered_session = powered_session
        self._powered_session_identity = _read_powered_session_identity(powered_session)
        self._keepalive_interval_seconds = interval
        self._max_host_gap_seconds = max_gap
        self._clock = clock
        self._bound_connection_epoch = self._read_epoch()

        reader_epoch = getattr(supervisor_reader, "bound_connection_epoch", None)
        if reader_epoch != self._bound_connection_epoch:
            raise WatchdogLivenessError(
                "watchdog and supervisor reader must share one connection epoch"
            )
        if getattr(supervisor_reader, "bound_crazyflie", None) is not cf:
            raise WatchdogLivenessError(
                "watchdog and supervisor reader must share the exact Crazyflie object"
            )
        self._require_reader_ready()
        _require_powered_session_new(self._powered_session)

        self._state_lock = Lock()
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._active = False
        self._terminal_reason: str | None = None
        self._last_keepalive_at: float | None = None

    @property
    def bound_connection_epoch(self) -> str:
        return self._bound_connection_epoch

    @property
    def powered_session_identity(self) -> str:
        return self._powered_session_identity

    @property
    def active(self) -> bool:
        with self._state_lock:
            locally_active = self._active and self._terminal_reason is None
        return locally_active and _read_powered_session_state(self._powered_session) == _STATE_ACTIVE

    @property
    def terminal_reason(self) -> str | None:
        with self._state_lock:
            local_reason = self._terminal_reason
        return local_reason or _read_powered_session_terminal_reason(self._powered_session)

    def _read_epoch(self) -> str:
        try:
            epoch = self._connection_epoch_reader()
        except Exception as exc:
            raise WatchdogLivenessError(
                "connection epoch is unavailable for watchdog liveness"
            ) from exc
        if not isinstance(epoch, str) or not epoch.strip():
            raise WatchdogLivenessError(
                "connection epoch is invalid for watchdog liveness"
            )
        return epoch.strip()

    def _verify_epoch(self) -> None:
        if self._read_epoch() != self._bound_connection_epoch:
            raise WatchdogLivenessError(
                "connection epoch changed during watchdog liveness domain"
            )

    def _require_reader_ready(self) -> None:
        poisoned = getattr(self._supervisor_reader, "poisoned", None)
        if poisoned is not False:
            raise WatchdogLivenessError(
                "fresh supervisor reader poison state is unavailable or poisoned "
                "for watchdog activation"
            )
        if not callable(getattr(self._supervisor_reader, "read", None)):
            raise WatchdogLivenessError(
                "fresh supervisor reader is unavailable for watchdog activation"
            )

    def _read_protocol_version(self) -> int:
        try:
            version = int(self._cf.platform.get_protocol_version())
        except Exception as exc:
            raise WatchdogLivenessError(
                "Crazyflie protocol version is unavailable for watchdog liveness"
            ) from exc
        if version < MIN_SUPERVISOR_PROTOCOL_VERSION:
            raise WatchdogLivenessError(
                "watchdog activation fence requires supervisor protocol version 12 or later"
            )
        return version

    def _watchdog_sender(self):
        supervisor = getattr(self._cf, "supervisor", None)
        sender = getattr(supervisor, "send_emergency_stop_watchdog", None)
        if not callable(sender):
            raise WatchdogLivenessError(
                "cflib supervisor watchdog command is unavailable"
            )
        return sender

    def _clock_now(self) -> float:
        try:
            now = float(self._clock())
        except Exception as exc:
            raise WatchdogLivenessError(
                "watchdog monotonic clock is unavailable"
            ) from exc
        if not isfinite(now):
            raise WatchdogLivenessError("watchdog monotonic clock is invalid")
        return now

    def _record_terminal(self, reason: str) -> None:
        lifecycle_failure = _try_mark_powered_session_terminal(
            self._powered_session,
            reason,
        )
        recorded_reason = reason if lifecycle_failure is None else reason + "; " + lifecycle_failure
        with self._state_lock:
            if self._terminal_reason is None:
                self._terminal_reason = recorded_reason
            self._active = False
        self._stop_event.set()

    def _last_keepalive(self) -> float | None:
        with self._state_lock:
            return self._last_keepalive_at

    def _verify_host_gap(self) -> None:
        last = self._last_keepalive()
        now = self._clock_now()
        if last is None or now - last > self._max_host_gap_seconds:
            raise WatchdogLivenessError(
                "watchdog host keepalive deadline was missed"
            )

    def _send_keepalive(self, sender) -> None:
        self._verify_epoch()
        previous = self._last_keepalive()
        before = self._clock_now()
        if previous is not None and before - previous > self._max_host_gap_seconds:
            raise WatchdogLivenessError(
                "watchdog host keepalive deadline was missed"
            )

        try:
            sender()
        except Exception as exc:
            raise WatchdogLivenessError(
                f"watchdog keepalive enqueue failed: {exc}"
            ) from exc

        after = self._clock_now()
        if previous is None:
            if after - before > self._max_host_gap_seconds:
                raise WatchdogLivenessError(
                    "watchdog host keepalive deadline was missed during initial enqueue"
                )
        elif after - previous > self._max_host_gap_seconds:
            raise WatchdogLivenessError(
                "watchdog host keepalive deadline was missed during enqueue"
            )
        with self._state_lock:
            self._last_keepalive_at = after

    def activate(self, *, supervisor_timeout_seconds: float = 0.2) -> object:
        """Activate and causally fence the watchdog before any flight effect.

        Local preconditions are checked before claiming powered-session
        activation. Once the first keepalive can be attempted, any ambiguity is
        terminal for that powered-session identity and cannot be cleared by a
        Crazyradio reconnect/new connection epoch.
        """
        timeout = _positive_finite(
            supervisor_timeout_seconds,
            "watchdog supervisor fence timeout",
        )
        with self._state_lock:
            if self._active:
                raise WatchdogLivenessError("watchdog liveness guard is already active")
            if self._terminal_reason is not None:
                raise WatchdogLivenessError(
                    "watchdog liveness guard is terminal: " + self._terminal_reason
                )

        # Exhaust all locally decidable preconditions before the first effect.
        self._verify_epoch()
        self._read_protocol_version()
        self._require_reader_ready()
        sender = self._watchdog_sender()
        # Re-check externally owned reset proof at the last lifecycle transition
        # before a watchdog command can be emitted.
        _require_powered_session_reset_proof(self._powered_session)
        _begin_powered_session_activation(self._powered_session)

        try:
            # Same-port causal fence: watchdog command first, fresh GET_STATE next.
            self._send_keepalive(sender)
            state = self._supervisor_reader.read(timeout_seconds=timeout)
            self._verify_epoch()
            self._verify_host_gap()

            if bool(getattr(state, "blocking_fault", True)):
                raise WatchdogLivenessError(
                    "watchdog activation fence observed a blocking supervisor fault"
                )
            _mark_powered_session_active(self._powered_session)
        except Exception as exc:
            error = (
                exc
                if isinstance(exc, WatchdogLivenessError)
                else WatchdogLivenessError(f"watchdog activation fence failed: {exc}")
            )
            self._record_terminal(str(error))
            raise error

        with self._state_lock:
            self._active = True
        self._stop_event.clear()
        thread = Thread(
            target=self._keepalive_loop,
            name="webeeblocks-watchdog-liveness",
            daemon=True,
        )
        self._thread = thread
        try:
            thread.start()
        except Exception as exc:
            error = WatchdogLivenessError(
                "watchdog keepalive service could not start: " + str(exc)
            )
            self._record_terminal(str(error))
            raise error
        self.assert_live()
        return state

    def _keepalive_loop(self) -> None:
        try:
            sender = self._watchdog_sender()
        except Exception as exc:
            reason = (
                str(exc)
                if isinstance(exc, WatchdogLivenessError)
                else "watchdog keepalive service failed: " + str(exc)
            )
            self._record_terminal(reason)
            return
        while not self._stop_event.wait(self._keepalive_interval_seconds):
            try:
                if _read_powered_session_state(self._powered_session) != _STATE_ACTIVE:
                    raise WatchdogLivenessError(
                        "powered-session watchdog lifecycle is no longer active"
                    )
                self._send_keepalive(sender)
            except Exception as exc:
                reason = (
                    str(exc)
                    if isinstance(exc, WatchdogLivenessError)
                    else f"watchdog keepalive service failed: {exc}"
                )
                self._record_terminal(reason)
                return

    def assert_live(self) -> None:
        """Fail closed unless the trusted host keepalive service is still valid."""
        with self._state_lock:
            reason = self._terminal_reason
            active = self._active
            thread = self._thread
        powered_state = _read_powered_session_state(self._powered_session)
        if reason is not None or powered_state == _STATE_TERMINAL:
            detail = reason or _read_powered_session_terminal_reason(self._powered_session) or "unknown reason"
            raise WatchdogLivenessError("watchdog liveness is terminal: " + detail)
        if not active:
            raise WatchdogLivenessError("watchdog liveness service is not active")
        if powered_state != _STATE_ACTIVE:
            reason = "powered-session watchdog lifecycle is not active"
            self._record_terminal(reason)
            raise WatchdogLivenessError(reason)
        if thread is None or not thread.is_alive():
            reason = "watchdog liveness service is not active"
            self._record_terminal(reason)
            raise WatchdogLivenessError(reason)
        try:
            self._verify_epoch()
            self._verify_host_gap()
        except WatchdogLivenessError as exc:
            self._record_terminal(str(exc))
            raise

    def stop_for_terminal_reboot(self, *, join_timeout_seconds: float = 1.0) -> None:
        """Intentionally end keepalives, accepting eventual firmware lock/reboot.

        This is not normal landing completion. A reusable powered session must
        keep the guard alive even while safely landed/idle. Reuse after this call
        requires a separately proven STM+deck reset and a new powered-session
        identity plus complete reconnect/re-preflight.
        """
        timeout = _positive_finite(
            join_timeout_seconds,
            "watchdog terminal join timeout",
        )
        self._record_terminal(
            "watchdog keepalives intentionally stopped; firmware lock/reboot is expected"
        )
        thread = self._thread
        if thread is not None and thread is not current_thread():
            thread.join(timeout)
            if thread.is_alive():
                raise WatchdogLivenessError(
                    "watchdog keepalive thread did not terminate"
                )

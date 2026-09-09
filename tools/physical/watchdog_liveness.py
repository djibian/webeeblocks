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

This module is safety infrastructure, not flight authority. It exposes no
arming, high-level commander, setpoint, landing or student/browser API.
"""

from __future__ import annotations

from math import isfinite
from threading import Event, Lock, Thread, current_thread
from time import monotonic
from typing import Callable

MIN_SUPERVISOR_PROTOCOL_VERSION = 12
FIRMWARE_WATCHDOG_TIMEOUT_SECONDS = 1.0
DEFAULT_KEEPALIVE_INTERVAL_SECONDS = 0.25
DEFAULT_MAX_HOST_GAP_SECONDS = 0.75


class WatchdogLivenessError(RuntimeError):
    """Fail-closed error for an unproven or lost watchdog liveness domain."""


def _positive_finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WatchdogLivenessError(f"{name} must be a positive finite number")
    parsed = float(value)
    if not isfinite(parsed) or parsed <= 0:
        raise WatchdogLivenessError(f"{name} must be a positive finite number")
    return parsed


class EmergencyWatchdogLivenessGuard:
    """One watchdog liveness domain bound to one physical connection epoch.

    Once activate() succeeds, keepalives continue until a terminal condition.
    There is deliberately no benign close/context-manager API: stopping the stock
    watchdog after activation means accepting its eventual locked/reboot state.
    """

    def __init__(
        self,
        cf: object,
        connection_epoch_reader: Callable[[], str],
        supervisor_reader: object,
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

        self._cf = cf
        self._connection_epoch_reader = connection_epoch_reader
        self._supervisor_reader = supervisor_reader
        self._keepalive_interval_seconds = interval
        self._max_host_gap_seconds = max_gap
        self._clock = clock
        self._bound_connection_epoch = self._read_epoch()

        reader_epoch = getattr(supervisor_reader, "bound_connection_epoch", None)
        if reader_epoch != self._bound_connection_epoch:
            raise WatchdogLivenessError(
                "watchdog and supervisor reader must share one connection epoch"
            )
        self._require_reader_ready()

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
    def active(self) -> bool:
        with self._state_lock:
            return self._active and self._terminal_reason is None

    @property
    def terminal_reason(self) -> str | None:
        with self._state_lock:
            return self._terminal_reason

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
        with self._state_lock:
            if self._terminal_reason is None:
                self._terminal_reason = reason
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

    def _send_keepalive(self) -> None:
        self._verify_epoch()
        supervisor = getattr(self._cf, "supervisor", None)
        sender = getattr(supervisor, "send_emergency_stop_watchdog", None)
        if not callable(sender):
            raise WatchdogLivenessError(
                "cflib supervisor watchdog command is unavailable"
            )

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
        if previous is not None and after - previous > self._max_host_gap_seconds:
            raise WatchdogLivenessError(
                "watchdog host keepalive deadline was missed during enqueue"
            )
        with self._state_lock:
            self._last_keepalive_at = after

    def activate(self, *, supervisor_timeout_seconds: float = 0.2) -> object:
        """Activate and causally fence the watchdog before any flight effect.

        If the initial keepalive is sent but the fence later fails, no periodic
        service is started. The already-armed firmware watchdog is then allowed to
        fail closed into its locked/reboot state.
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

        try:
            self._verify_epoch()
            self._read_protocol_version()
            self._require_reader_ready()

            # Same-port causal fence: watchdog command first, fresh GET_STATE next.
            self._send_keepalive()
            state = self._supervisor_reader.read(timeout_seconds=timeout)
            self._verify_epoch()
            self._verify_host_gap()

            if bool(getattr(state, "blocking_fault", True)):
                raise WatchdogLivenessError(
                    "watchdog activation fence observed a blocking supervisor fault"
                )
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
        thread.start()
        return state

    def _keepalive_loop(self) -> None:
        while not self._stop_event.wait(self._keepalive_interval_seconds):
            try:
                self._send_keepalive()
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
        if reason is not None:
            raise WatchdogLivenessError("watchdog liveness is terminal: " + reason)
        if not active or thread is None or not thread.is_alive():
            raise WatchdogLivenessError("watchdog liveness service is not active")
        self._verify_epoch()
        try:
            self._verify_host_gap()
        except WatchdogLivenessError as exc:
            self._record_terminal(str(exc))
            raise

    def stop_for_terminal_reboot(self, *, join_timeout_seconds: float = 1.0) -> None:
        """Intentionally end keepalives, accepting eventual firmware lock/reboot.

        This is not normal landing completion. A reusable powered session must
        keep the guard alive even while safely landed/idle.
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

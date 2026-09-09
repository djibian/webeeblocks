#!/usr/bin/env python3
"""Causal activation fence for the stock Crazyflie emergency-stop watchdog.

The stock supervisor watchdog is disabled until its first keepalive and has no
application-level acknowledgement. WebeeBlocks therefore cannot treat a call to
cflib's send_emergency_stop_watchdog() as proof that the watchdog is active.

This module proves only the bounded activation fence established by #157:
enqueue one watchdog keepalive, then require a fresh fail-closed supervisor-state
read on the same unchanged connection epoch. CRTP strict ordering within the
supervisor port makes the later observed GET_STATE response a causal fence for
the earlier keepalive.

The fence is deliberately single-use. Once a keepalive send is attempted the
stock watchdog may be active and cannot be disabled without a power cycle. A
failed or ambiguous fence must never be blindly retried on the same powered
session. This primitive does not maintain periodic keepalives and exposes no
arming, flight-command, setpoint or emergency-stop authority.
"""

from __future__ import annotations

from typing import Callable, NamedTuple


class WatchdogFenceError(RuntimeError):
    """Fail-closed error for an unavailable or ambiguous activation fence."""


class WatchdogFenceResult(NamedTuple):
    connection_epoch: str
    supervisor_state: object


class WatchdogActivationFence:
    """Single-use causal proof that the first watchdog keepalive reached firmware.

    The supplied supervisor_reader must be the #257-style exclusive fresh reader
    for the same connection epoch. This class intentionally delegates GET_STATE
    to that reader and never invokes cflib Supervisor state getters itself.
    """

    def __init__(
        self,
        cf: object,
        connection_epoch_reader: Callable[[], str],
        supervisor_reader: object,
    ) -> None:
        self._cf = cf
        self._connection_epoch_reader = connection_epoch_reader
        self._supervisor_reader = supervisor_reader
        self._bound_connection_epoch = self._read_epoch()
        self._activation_attempted = False
        self._verified = False

        reader_epoch = getattr(supervisor_reader, "bound_connection_epoch", None)
        if reader_epoch != self._bound_connection_epoch:
            raise WatchdogFenceError(
                "supervisor reader is not bound to the watchdog connection epoch"
            )

    @property
    def bound_connection_epoch(self) -> str:
        return self._bound_connection_epoch

    @property
    def activation_attempted(self) -> bool:
        return self._activation_attempted

    @property
    def verified(self) -> bool:
        return self._verified

    @property
    def power_cycle_required_to_disable(self) -> bool:
        """Whether the stock watchdog may now be armed for this powered session."""
        return self._activation_attempted

    def _read_epoch(self) -> str:
        try:
            epoch = self._connection_epoch_reader()
        except Exception as exc:
            raise WatchdogFenceError(
                "connection epoch is unavailable for watchdog activation"
            ) from exc
        if not isinstance(epoch, str) or not epoch.strip():
            raise WatchdogFenceError(
                "connection epoch is invalid for watchdog activation"
            )
        return epoch

    def _verify_connection_epoch(self) -> None:
        if self._read_epoch() != self._bound_connection_epoch:
            raise WatchdogFenceError(
                "connection epoch changed during watchdog activation fence"
            )

    def _verify_reader_ready(self) -> None:
        if getattr(self._supervisor_reader, "poisoned", False):
            raise WatchdogFenceError(
                "fresh supervisor reader is poisoned; reconnect before watchdog activation"
            )
        if not callable(getattr(self._supervisor_reader, "read", None)):
            raise WatchdogFenceError(
                "fresh supervisor reader is unavailable for watchdog activation"
            )

    def _watchdog_sender(self):
        supervisor = getattr(self._cf, "supervisor", None)
        sender = getattr(supervisor, "send_emergency_stop_watchdog", None)
        if not callable(sender):
            raise WatchdogFenceError(
                "Crazyflie watchdog keepalive sender is unavailable"
            )
        return sender

    def activate_and_verify(
        self,
        *,
        timeout_seconds: float = 0.2,
    ) -> WatchdogFenceResult:
        """Send the first keepalive and prove it with a later fresh GET_STATE.

        A call is single-use even when it fails after the send attempt. That
        preserves the unknown-outcome rule: the stock watchdog may have become
        active, so the same powered session cannot safely blind-retry the fence.
        """
        if timeout_seconds <= 0:
            raise WatchdogFenceError("watchdog activation timeout must be positive")
        if self._activation_attempted:
            raise WatchdogFenceError(
                "watchdog activation fence is single-use for this powered session"
            )

        self._verify_connection_epoch()
        self._verify_reader_ready()
        sender = self._watchdog_sender()

        # From this point onward the watchdog command may have reached firmware,
        # even if a later host-side operation fails or its outcome is ambiguous.
        self._activation_attempted = True
        try:
            sender()
            state = self._supervisor_reader.read(timeout_seconds=timeout_seconds)
            self._verify_connection_epoch()
        except Exception as exc:
            if isinstance(exc, WatchdogFenceError):
                raise
            raise WatchdogFenceError(
                "watchdog activation fence is ambiguous after keepalive attempt; "
                "do not retry on this powered session"
            ) from exc

        if getattr(state, "blocking_fault", None) is not False:
            raise WatchdogFenceError(
                "fresh supervisor state is not demonstrably fault-free after "
                "watchdog activation"
            )

        self._verified = True
        return WatchdogFenceResult(
            connection_epoch=self._bound_connection_epoch,
            supervisor_state=state,
        )

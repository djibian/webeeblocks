#!/usr/bin/env python3
"""Fresh fail-closed evidence for controlled high-level landing completion.

This module deliberately emits no Crazyflie command. It consumes only the
exclusive fresh #257 supervisor-state reader and one reconnect-sensitive
connection epoch.

The future trusted authority path is expected to:
1. capture a fresh in-flight baseline;
2. issue the separately authorized high-level landing effect;
3. await completion here while the independent watchdog/session remains live.

Completion is accepted only after the same observer has first established
physical flight under active high-level control, and a later fresh supervisor
state reports:
- no blocking fault;
- physical flight ended;
- high-level control no longer actively flying;
- the high-level trajectory finished.

Stock auto-arming is intentionally not treated as a failure: after a normal
landing the firmware may become armed/ReadyToFly again, so teacher authorization
must remain a separate gate for every later flight-capable effect.
"""

from __future__ import annotations

from math import isfinite
from threading import Lock
from time import monotonic, sleep
from typing import Callable, NamedTuple


class LandingCompletionError(RuntimeError):
    """Fail-closed error for unavailable or inconsistent landing evidence."""


class PreLandingFlightEvidence(NamedTuple):
    connection_epoch: str
    bitfield: int


class LandingCompletionEvidence(NamedTuple):
    connection_epoch: str
    observations: int
    supervisor_state: object


def _positive_finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LandingCompletionError(f"{name} must be a positive finite number")
    parsed = float(value)
    if not isfinite(parsed) or parsed <= 0:
        raise LandingCompletionError(f"{name} must be a positive finite number")
    return parsed


class ControlledLandingCompletionObserver:
    """Observe a fresh physical-flight -> controlled-completion transition."""

    def __init__(
        self,
        supervisor_reader: object,
        connection_epoch_reader: Callable[[], str],
        *,
        clock: Callable[[], float] = monotonic,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        self._supervisor_reader = supervisor_reader
        self._connection_epoch_reader = connection_epoch_reader
        self._clock = clock
        self._sleeper = sleeper
        self._state_lock = Lock()
        self._pending_baseline: PreLandingFlightEvidence | None = None

        bound_epoch = getattr(supervisor_reader, "bound_connection_epoch", None)
        if not isinstance(bound_epoch, str) or not bound_epoch.strip():
            raise LandingCompletionError(
                "fresh supervisor reader has no valid connection epoch"
            )
        if not callable(getattr(supervisor_reader, "read", None)):
            raise LandingCompletionError(
                "fresh supervisor reader is unavailable for landing completion"
            )
        if getattr(supervisor_reader, "poisoned", None) is not False:
            raise LandingCompletionError(
                "fresh supervisor reader is poisoned for landing completion"
            )

        self._bound_connection_epoch = bound_epoch.strip()
        self._verify_epoch()

    @property
    def bound_connection_epoch(self) -> str:
        return self._bound_connection_epoch

    def _read_epoch(self) -> str:
        try:
            value = self._connection_epoch_reader()
        except Exception as exc:
            raise LandingCompletionError(
                "connection epoch is unavailable for landing completion"
            ) from exc
        if not isinstance(value, str) or not value.strip():
            raise LandingCompletionError(
                "connection epoch is invalid for landing completion"
            )
        return value.strip()

    def _verify_epoch(self) -> None:
        if self._read_epoch() != self._bound_connection_epoch:
            raise LandingCompletionError(
                "connection epoch changed during landing completion observation"
            )

    def _clock_now(self) -> float:
        try:
            value = float(self._clock())
        except Exception as exc:
            raise LandingCompletionError(
                "landing completion monotonic clock is unavailable"
            ) from exc
        if not isfinite(value):
            raise LandingCompletionError(
                "landing completion monotonic clock is invalid"
            )
        return value

    def _verify_reader_ready(self) -> None:
        poisoned = getattr(self._supervisor_reader, "poisoned", None)
        if poisoned is not False:
            raise LandingCompletionError(
                "fresh supervisor reader is poisoned for landing completion"
            )

    @staticmethod
    def _validate_state(state: object) -> None:
        bitfield = getattr(state, "bitfield", None)
        if isinstance(bitfield, bool) or not isinstance(bitfield, int) or bitfield < 0:
            raise LandingCompletionError(
                "fresh supervisor landing state has an invalid bitfield"
            )
        for name in (
            "blocking_fault",
            "is_flying",
            "hl_control_active",
            "hl_traj_finished",
        ):
            if not isinstance(getattr(state, name, None), bool):
                raise LandingCompletionError(
                    f"fresh supervisor landing state has invalid {name}"
                )

    def _read_fresh(self, timeout_seconds: float) -> object:
        self._verify_epoch()
        self._verify_reader_ready()
        try:
            state = self._supervisor_reader.read(timeout_seconds=timeout_seconds)
        except Exception as exc:
            raise LandingCompletionError(
                f"fresh supervisor landing observation failed: {exc}"
            ) from exc
        self._verify_epoch()
        self._validate_state(state)
        return state

    @staticmethod
    def _raise_on_fault(state: object) -> None:
        if state.blocking_fault:
            raise LandingCompletionError(
                "blocking supervisor fault during controlled landing completion"
            )

    def capture_pre_land_flight(
        self,
        *,
        timeout_seconds: float = 0.2,
    ) -> PreLandingFlightEvidence:
        """Establish fresh same-epoch evidence of flight under high-level control."""
        timeout = _positive_finite(
            timeout_seconds,
            "pre-land supervisor read timeout",
        )
        state = self._read_fresh(timeout)
        self._raise_on_fault(state)
        if not state.is_flying:
            raise LandingCompletionError(
                "pre-land baseline did not observe active physical flight"
            )
        if not state.hl_control_active:
            raise LandingCompletionError(
                "pre-land baseline did not observe active high-level control"
            )
        evidence = PreLandingFlightEvidence(
            connection_epoch=self._bound_connection_epoch,
            bitfield=state.bitfield,
        )
        with self._state_lock:
            # A newer fresh baseline supersedes any earlier unused baseline.
            self._pending_baseline = evidence
        return evidence

    def await_completion(
        self,
        baseline: PreLandingFlightEvidence,
        *,
        total_timeout_seconds: float = 8.0,
        per_read_timeout_seconds: float = 0.2,
        poll_interval_seconds: float = 0.05,
    ) -> LandingCompletionEvidence:
        """Wait for a later fresh same-epoch finished-and-not-flying state."""
        total_timeout = _positive_finite(
            total_timeout_seconds,
            "landing completion timeout",
        )
        per_read_timeout = _positive_finite(
            per_read_timeout_seconds,
            "landing supervisor read timeout",
        )
        poll_interval = _positive_finite(
            poll_interval_seconds,
            "landing poll interval",
        )
        if not isinstance(baseline, PreLandingFlightEvidence):
            raise LandingCompletionError(
                "landing completion requires pre-land flight evidence"
            )
        if baseline.connection_epoch != self._bound_connection_epoch:
            raise LandingCompletionError(
                "pre-land evidence belongs to a different connection epoch"
            )
        with self._state_lock:
            if baseline is not self._pending_baseline:
                raise LandingCompletionError(
                    "pre-land evidence was not freshly issued by this observer "
                    "for the current completion attempt"
                )
            # Completion observation is one-shot. Any timeout/fault/reader failure
            # remains fail-closed and cannot be retried using the same baseline.
            self._pending_baseline = None

        started_at = self._clock_now()
        deadline = started_at + total_timeout
        observations = 0

        while True:
            self._verify_epoch()
            now = self._clock_now()
            remaining = deadline - now
            if remaining <= 0:
                raise LandingCompletionError(
                    "controlled landing completion timed out"
                )

            state = self._read_fresh(min(per_read_timeout, remaining))
            observations += 1
            now = self._clock_now()
            if deadline - now <= 0:
                raise LandingCompletionError(
                    "controlled landing completion timed out"
                )
            self._raise_on_fault(state)

            if (
                not state.is_flying
                and not state.hl_control_active
                and state.hl_traj_finished
            ):
                return LandingCompletionEvidence(
                    connection_epoch=self._bound_connection_epoch,
                    observations=observations,
                    supervisor_state=state,
                )

            now = self._clock_now()
            remaining = deadline - now
            if remaining <= 0:
                raise LandingCompletionError(
                    "controlled landing completion timed out"
                )
            delay = min(poll_interval, remaining)
            try:
                self._sleeper(delay)
            except Exception as exc:
                raise LandingCompletionError(
                    "landing completion polling delay failed"
                ) from exc

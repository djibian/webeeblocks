#!/usr/bin/env python3
"""Fresh, non-authority directional range observation for the physical backend.

Issue #345 needs exact teacher-bound conditions to consume the same generic
``range(direction)`` semantics that Runtime v2 already exposes in simulation.
This module is deliberately narrower: it only establishes a fresh same-epoch
physical observation for one already-supported student-facing direction. It
contains no branch selection, caller IPC, motor command or execution authority.

Pinned Crazyflie firmware exposes ``range.front/back/left/right/up`` as
``LOG_UINT16`` millimetres. The Multi-ranger driver publishes ``32767`` when the
VL53L1 measurement status is not accepted. Runtime v2 exposes metres with a
2.0 m observable horizon, so values beyond that horizon (including the firmware
no-range sentinel) normalize to exactly 2.0 m instead of leaking firmware-specific
sentinel semantics into the backend-neutral program.

Opening a stream establishes only a timestamp baseline. Every ``read()`` requires
one strictly later firmware timestamp received after that call began on the same
reconnect-sensitive connection epoch. Cached, duplicate, pre-read, malformed,
missing or epoch-crossing observations therefore cannot decide a later condition.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from threading import Condition, Lock
from time import monotonic
from typing import Callable

SUPPORTED_DIRECTIONS = ("front", "back", "left", "right", "up")
_RANGE_VARIABLES = {direction: f"range.{direction}" for direction in SUPPORTED_DIRECTIONS}
LOG_PERIOD_MS = 100
FIRMWARE_NO_RANGE_MM = 32767
RUNTIME_MAX_RANGE_M = 2.0
_TIMESTAMP_MASK = (1 << 24) - 1
_TIMESTAMP_HALF_RANGE = 1 << 23


class RangeReadError(RuntimeError):
    """Fail-closed error for unavailable or stale physical range evidence."""


@dataclass(frozen=True, slots=True)
class RangeObservation:
    connection_epoch: str
    firmware_timestamp_ms: int
    direction: str
    raw_mm: int
    range_m: float


def _timestamp_is_later(new_timestamp: int, old_timestamp: int) -> bool:
    delta = (new_timestamp - old_timestamp) & _TIMESTAMP_MASK
    return 0 < delta < _TIMESTAMP_HALF_RANGE


def normalize_runtime_range_m(raw_mm: object) -> float:
    """Normalize exact firmware millimetres to Runtime v2's metre horizon."""
    if isinstance(raw_mm, bool) or not isinstance(raw_mm, int):
        raise RangeReadError("range sample is not an exact uint16 millimetre value")
    if raw_mm < 0 or raw_mm > FIRMWARE_NO_RANGE_MM:
        raise RangeReadError("range sample is outside the pinned firmware domain")
    if raw_mm == FIRMWARE_NO_RANGE_MM:
        return RUNTIME_MAX_RANGE_M
    value = raw_mm / 1000.0
    if not isfinite(value) or value < 0.0:
        raise RangeReadError("range sample cannot be normalized")
    return min(value, RUNTIME_MAX_RANGE_M)


class FreshRangeObserver:
    """Continuous one-direction log observer bound to one live connection epoch."""

    def __init__(
        self,
        cf: object,
        connection_epoch_reader: Callable[[], str],
        direction: str,
        *,
        log_config_factory: Callable[[], object] | None = None,
    ) -> None:
        if not isinstance(direction, str) or direction not in SUPPORTED_DIRECTIONS:
            raise RangeReadError("unsupported physical range direction")
        self._cf = cf
        self._connection_epoch_reader = connection_epoch_reader
        self._direction = direction
        self._variable = _RANGE_VARIABLES[direction]
        self._log_config_factory = log_config_factory
        self._read_lock = Lock()
        self._condition = Condition(Lock())
        self._bound_connection_epoch: str | None = None
        self._config: object | None = None
        self._opened = False
        self._sequence = 0
        self._latest: tuple[int, int] | None = None
        self._stream_error: RangeReadError | None = None

    @property
    def direction(self) -> str:
        return self._direction

    @property
    def variable(self) -> str:
        return self._variable

    @property
    def bound_connection_epoch(self) -> str | None:
        return self._bound_connection_epoch

    @property
    def bound_crazyflie(self) -> object:
        return self._cf

    @property
    def is_open(self) -> bool:
        return self._opened

    def _read_epoch(self) -> str:
        try:
            epoch = self._connection_epoch_reader()
        except Exception as exc:
            raise RangeReadError("connection epoch is unavailable for range observation") from exc
        if not isinstance(epoch, str) or not epoch.strip() or epoch != epoch.strip():
            raise RangeReadError("connection epoch is invalid for range observation")
        return epoch

    def _verify_epoch(self) -> str:
        current = self._read_epoch()
        if self._bound_connection_epoch is not None and current != self._bound_connection_epoch:
            raise RangeReadError("connection epoch changed during range observation")
        return current

    def _require_exact_toc_entry(self) -> None:
        log = getattr(self._cf, "log", None)
        toc = getattr(log, "toc", None)
        lookup = getattr(toc, "get_element_by_complete_name", None)
        if not callable(lookup):
            raise RangeReadError("live log TOC is unavailable for range observation")
        try:
            element = lookup(self._variable)
        except Exception as exc:
            raise RangeReadError("live range log TOC lookup failed") from exc
        if element is None:
            raise RangeReadError(f"live log TOC is missing {self._variable}")
        expected_group, expected_name = self._variable.split(".", 1)
        if (
            getattr(element, "group", None) != expected_group
            or getattr(element, "name", None) != expected_name
            or getattr(element, "ctype", None) != "uint16_t"
            or getattr(element, "pytype", None) != "<H"
        ):
            raise RangeReadError(
                f"live log TOC entry {self._variable} does not match pinned uint16_t range semantics"
            )

    def _make_config(self) -> object:
        if self._log_config_factory is not None:
            return self._log_config_factory()
        try:
            from cflib.crazyflie.log import LogConfig
        except ImportError as exc:
            raise RangeReadError("cflib logging support is unavailable") from exc
        config = LogConfig(f"WebeeBlocks fresh {self._direction} range", LOG_PERIOD_MS)
        config.add_variable(self._variable, "uint16_t")
        return config

    def _set_error(self, message: str) -> None:
        with self._condition:
            if self._stream_error is None:
                self._stream_error = RangeReadError(message)
            self._condition.notify_all()

    def _on_log_error(self, _config: object, message: object) -> None:
        self._set_error(f"range logging failed: {message}")

    def _on_disconnect(self, _uri: str) -> None:
        self._set_error("Crazyflie disconnected during range observation")

    def _on_data(self, timestamp: object, data: object, config: object) -> None:
        if config is not self._config:
            return
        try:
            if not isinstance(timestamp, int) or timestamp < 0 or timestamp > _TIMESTAMP_MASK:
                raise RangeReadError("range sample has an invalid firmware timestamp")
            if not isinstance(data, dict) or self._variable not in data:
                raise RangeReadError(f"range sample is missing {self._variable}")
            raw_mm = data[self._variable]
            normalize_runtime_range_m(raw_mm)
        except RangeReadError as exc:
            self._set_error(str(exc))
            return

        with self._condition:
            if self._stream_error is not None:
                return
            self._sequence += 1
            self._latest = (timestamp, raw_mm)
            self._condition.notify_all()

    def _wait_for_sample(
        self,
        *,
        after_sequence: int,
        after_timestamp: int | None,
        timeout_seconds: float,
    ) -> tuple[int, int]:
        deadline = monotonic() + timeout_seconds
        with self._condition:
            while True:
                if self._stream_error is not None:
                    raise self._stream_error
                if self._sequence > after_sequence and self._latest is not None:
                    timestamp, raw_mm = self._latest
                    if after_timestamp is None or _timestamp_is_later(timestamp, after_timestamp):
                        return timestamp, raw_mm
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise RangeReadError("fresh range sample timed out")
                self._condition.wait(remaining)

    def open(self, *, timeout_seconds: float = 0.7) -> None:
        """Start one read-only log stream and establish a timestamp baseline."""
        if timeout_seconds <= 0:
            raise RangeReadError("range timeout must be positive")

        with self._read_lock:
            if self._opened:
                self._verify_epoch()
                return

            self._bound_connection_epoch = self._read_epoch()
            self._require_exact_toc_entry()
            with self._condition:
                self._sequence = 0
                self._latest = None
                self._stream_error = None

            config = self._make_config()
            self._config = config
            data_registered = False
            error_registered = False
            disconnect_registered = False
            try:
                config.data_received_cb.add_callback(self._on_data)
                data_registered = True
                config.error_cb.add_callback(self._on_log_error)
                error_registered = True
                self._cf.disconnected.add_callback(self._on_disconnect)
                disconnect_registered = True
                self._cf.log.add_config(config)
                config.start()
                self._wait_for_sample(
                    after_sequence=0,
                    after_timestamp=None,
                    timeout_seconds=timeout_seconds,
                )
                self._verify_epoch()
                self._opened = True
            except RangeReadError:
                self._cleanup_failed_open(
                    config,
                    data_registered=data_registered,
                    error_registered=error_registered,
                    disconnect_registered=disconnect_registered,
                )
                raise
            except Exception as exc:
                self._cleanup_failed_open(
                    config,
                    data_registered=data_registered,
                    error_registered=error_registered,
                    disconnect_registered=disconnect_registered,
                )
                raise RangeReadError(f"could not start fresh range logging: {exc}") from exc

    def _cleanup_failed_open(
        self,
        config: object,
        *,
        data_registered: bool,
        error_registered: bool,
        disconnect_registered: bool,
    ) -> None:
        for action in (getattr(config, "stop", None), getattr(config, "delete", None)):
            if callable(action):
                try:
                    action()
                except Exception:
                    pass
        if data_registered:
            try:
                config.data_received_cb.remove_callback(self._on_data)
            except Exception:
                pass
        if error_registered:
            try:
                config.error_cb.remove_callback(self._on_log_error)
            except Exception:
                pass
        if disconnect_registered:
            try:
                self._cf.disconnected.remove_callback(self._on_disconnect)
            except Exception:
                pass
        self._config = None
        self._opened = False

    def read(self, *, timeout_seconds: float = 0.7) -> RangeObservation:
        """Return one newly arrived post-call sample from the bound epoch."""
        if timeout_seconds <= 0:
            raise RangeReadError("range timeout must be positive")

        with self._read_lock:
            if not self._opened or self._config is None or self._bound_connection_epoch is None:
                raise RangeReadError("range observer is not open")
            self._verify_epoch()
            with self._condition:
                if self._stream_error is not None:
                    raise self._stream_error
                baseline_sequence = self._sequence
                if self._latest is None:
                    raise RangeReadError("range observer has no established baseline")
                baseline_timestamp = self._latest[0]

            timestamp, raw_mm = self._wait_for_sample(
                after_sequence=baseline_sequence,
                after_timestamp=baseline_timestamp,
                timeout_seconds=timeout_seconds,
            )
            epoch = self._verify_epoch()
            return RangeObservation(
                connection_epoch=epoch,
                firmware_timestamp_ms=timestamp,
                direction=self._direction,
                raw_mm=raw_mm,
                range_m=normalize_runtime_range_m(raw_mm),
            )

    def close(self) -> None:
        """Stop/delete the non-authority log stream and remove callbacks."""
        with self._read_lock:
            config = self._config
            if config is None:
                self._opened = False
                return
            errors: list[str] = []
            for label, action in (("stop", config.stop), ("delete", config.delete)):
                try:
                    action()
                except Exception as exc:
                    errors.append(f"{label}: {exc}")
            for callback_list, callback in (
                (config.data_received_cb, self._on_data),
                (config.error_cb, self._on_log_error),
                (self._cf.disconnected, self._on_disconnect),
            ):
                try:
                    callback_list.remove_callback(callback)
                except Exception as exc:
                    errors.append(f"callback cleanup: {exc}")
            self._config = None
            self._opened = False
            if errors:
                raise RangeReadError(
                    "could not close range observer cleanly: " + "; ".join(errors)
                )

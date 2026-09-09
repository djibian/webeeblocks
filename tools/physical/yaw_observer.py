#!/usr/bin/env python3
"""Fresh, non-authority yaw observation for the physical HighLevel path.

Integrated physical movement semantics require an accepted current yaw to rotate
body-relative horizontal intent into a world-frame displacement. This module
obtains that yaw from the firmware's stateEstimate.yaw log variable without
exposing any motor, arming, watchdog or commander operation.

Opening establishes a first sample only as a timestamp baseline. Each read then
requires a later firmware timestamp received after the read began on the same
reconnect-sensitive connection epoch, so cached/UI values are not accepted as
fresh execution evidence.
"""

from __future__ import annotations

from math import isfinite, radians
from threading import Condition, Lock
from time import monotonic
from typing import Callable, NamedTuple

YAW_VARIABLE = "stateEstimate.yaw"
LOG_PERIOD_MS = 10
_TIMESTAMP_MASK = (1 << 24) - 1
_TIMESTAMP_HALF_RANGE = 1 << 23


class YawReadError(RuntimeError):
    """Fail-closed error for unavailable or stale physical yaw evidence."""


class YawObservation(NamedTuple):
    connection_epoch: str
    firmware_timestamp_ms: int
    yaw_deg: float
    yaw_rad: float


def _timestamp_is_later(new_timestamp: int, old_timestamp: int) -> bool:
    delta = (new_timestamp - old_timestamp) & _TIMESTAMP_MASK
    return 0 < delta < _TIMESTAMP_HALF_RANGE


class FreshYawObserver:
    """Continuous log observer bound to one live physical connection epoch."""

    def __init__(
        self,
        cf: object,
        connection_epoch_reader: Callable[[], str],
        *,
        log_config_factory: Callable[[], object] | None = None,
    ) -> None:
        self._cf = cf
        self._connection_epoch_reader = connection_epoch_reader
        self._log_config_factory = log_config_factory
        self._read_lock = Lock()
        self._condition = Condition(Lock())
        self._bound_connection_epoch: str | None = None
        self._config: object | None = None
        self._opened = False
        self._sequence = 0
        self._latest: tuple[int, float] | None = None
        self._stream_error: YawReadError | None = None

    @property
    def bound_connection_epoch(self) -> str | None:
        return self._bound_connection_epoch

    @property
    def is_open(self) -> bool:
        return self._opened

    def _read_epoch(self) -> str:
        try:
            epoch = self._connection_epoch_reader()
        except Exception as exc:
            raise YawReadError("connection epoch is unavailable for yaw observation") from exc
        if not isinstance(epoch, str) or not epoch.strip():
            raise YawReadError("connection epoch is invalid for yaw observation")
        return epoch

    def _verify_epoch(self) -> str:
        current = self._read_epoch()
        if self._bound_connection_epoch is not None and current != self._bound_connection_epoch:
            raise YawReadError("connection epoch changed during yaw observation")
        return current

    def _make_config(self) -> object:
        if self._log_config_factory is not None:
            return self._log_config_factory()
        try:
            from cflib.crazyflie.log import LogConfig
        except ImportError as exc:
            raise YawReadError("cflib logging support is unavailable") from exc
        config = LogConfig("WebeeBlocks fresh yaw", LOG_PERIOD_MS)
        config.add_variable(YAW_VARIABLE, "float")
        return config

    def _set_error(self, message: str) -> None:
        with self._condition:
            if self._stream_error is None:
                self._stream_error = YawReadError(message)
            self._condition.notify_all()

    def _on_log_error(self, _config: object, message: object) -> None:
        self._set_error(f"yaw logging failed: {message}")

    def _on_disconnect(self, _uri: str) -> None:
        self._set_error("Crazyflie disconnected during yaw observation")

    def _on_data(self, timestamp: object, data: object, config: object) -> None:
        if config is not self._config:
            return
        try:
            if not isinstance(timestamp, int) or timestamp < 0 or timestamp > _TIMESTAMP_MASK:
                raise YawReadError("yaw sample has an invalid firmware timestamp")
            if not isinstance(data, dict) or YAW_VARIABLE not in data:
                raise YawReadError("yaw sample is missing stateEstimate.yaw")
            yaw_deg = float(data[YAW_VARIABLE])
            if not isfinite(yaw_deg):
                raise YawReadError("yaw sample is not finite")
        except (TypeError, ValueError, YawReadError) as exc:
            message = str(exc) if isinstance(exc, YawReadError) else f"invalid yaw sample: {exc}"
            self._set_error(message)
            return

        with self._condition:
            if self._stream_error is not None:
                return
            self._sequence += 1
            self._latest = (timestamp, yaw_deg)
            self._condition.notify_all()

    def _wait_for_sample(
        self,
        *,
        after_sequence: int,
        after_timestamp: int | None,
        timeout_seconds: float,
    ) -> tuple[int, float]:
        deadline = monotonic() + timeout_seconds
        with self._condition:
            while True:
                if self._stream_error is not None:
                    raise self._stream_error
                if self._sequence > after_sequence and self._latest is not None:
                    timestamp, yaw_deg = self._latest
                    if after_timestamp is None or _timestamp_is_later(timestamp, after_timestamp):
                        return timestamp, yaw_deg
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise YawReadError("fresh yaw sample timed out")
                self._condition.wait(remaining)

    def open(self, *, timeout_seconds: float = 0.5) -> None:
        """Start one session log stream and establish a fresh timestamp baseline."""
        if timeout_seconds <= 0:
            raise YawReadError("yaw timeout must be positive")

        with self._read_lock:
            if self._opened:
                self._verify_epoch()
                return

            self._bound_connection_epoch = self._read_epoch()
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
            except YawReadError:
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
                raise YawReadError(f"could not start fresh yaw logging: {exc}") from exc

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

    def read(self, *, timeout_seconds: float = 0.5) -> YawObservation:
        """Return one newly arrived post-call yaw sample from the bound epoch."""
        if timeout_seconds <= 0:
            raise YawReadError("yaw timeout must be positive")

        with self._read_lock:
            if not self._opened or self._config is None or self._bound_connection_epoch is None:
                raise YawReadError("yaw observer is not open")
            self._verify_epoch()
            with self._condition:
                if self._stream_error is not None:
                    raise self._stream_error
                baseline_sequence = self._sequence
                if self._latest is None:
                    raise YawReadError("yaw observer has no established baseline")
                baseline_timestamp = self._latest[0]

            timestamp, yaw_deg = self._wait_for_sample(
                after_sequence=baseline_sequence,
                after_timestamp=baseline_timestamp,
                timeout_seconds=timeout_seconds,
            )
            epoch = self._verify_epoch()
            return YawObservation(
                connection_epoch=epoch,
                firmware_timestamp_ms=timestamp,
                yaw_deg=yaw_deg,
                yaw_rad=radians(yaw_deg),
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
                raise YawReadError("could not close yaw observer cleanly: " + "; ".join(errors))

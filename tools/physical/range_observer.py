#!/usr/bin/env python3
"""Fresh, non-authority Multi-ranger observation for the physical backend.

This module exposes exactly the existing student-facing directions
``front/back/left/right/up`` as fresh same-connection-epoch observations. It
contains no caller IPC, branch selection, generic log-variable API, command,
parameter write, or execution authority.

Pinned firmware publishes the five values as ``LOG_UINT16`` millimetres. Pinned
cflib's official ``Multiranger`` helper treats values >= 8000 mm as unavailable
and otherwise converts millimetres to metres. We preserve that boundary exactly:
an unavailable value never becomes a numeric student distance.

Opening establishes only a timestamp baseline. Every ``read()`` advances a
host-local request generation before taking its baseline and accepts only a
callback that entered at that generation with a strictly later firmware
timestamp on the same reconnect-sensitive connection epoch. This prevents a
pre-request callback that finishes late from becoming fresh evidence.
"""

from __future__ import annotations

from threading import Condition, Lock
from time import monotonic
from typing import Callable, NamedTuple

SUPPORTED_DIRECTIONS = ("front", "back", "left", "right", "up")
_RANGE_VARIABLES = {
    direction: f"range.{direction}" for direction in SUPPORTED_DIRECTIONS
}
LOG_PERIOD_MS = 100
CFLIB_UNAVAILABLE_MM = 8000
_UINT16_MAX = 0xFFFF
_TIMESTAMP_MASK = (1 << 24) - 1
_TIMESTAMP_HALF_RANGE = 1 << 23


class RangeReadError(RuntimeError):
    """Fail-closed error for unavailable or stale physical range evidence."""


class RangeObservation(NamedTuple):
    connection_epoch: str
    firmware_timestamp_ms: int
    direction: str
    raw_mm: int
    range_m: float


def _timestamp_is_later(new_timestamp: int, old_timestamp: int) -> bool:
    delta = (new_timestamp - old_timestamp) & _TIMESTAMP_MASK
    return 0 < delta < _TIMESTAMP_HALF_RANGE


def range_mm_to_m(raw_mm: object) -> float:
    """Apply the exact pinned cflib Multi-ranger availability/unit contract."""
    if isinstance(raw_mm, bool) or not isinstance(raw_mm, int):
        raise RangeReadError("range sample is not an exact uint16 millimetre value")
    if raw_mm < 0 or raw_mm > _UINT16_MAX:
        raise RangeReadError("range sample is outside the uint16 firmware domain")
    if raw_mm >= CFLIB_UNAVAILABLE_MM:
        raise RangeReadError("range sample is unavailable in pinned cflib semantics")
    return raw_mm / 1000.0


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
        if not callable(connection_epoch_reader):
            raise RangeReadError("connection epoch reader is unavailable")
        self._cf = cf
        self._connection_epoch_reader = connection_epoch_reader
        self._direction = direction
        self._variable = _RANGE_VARIABLES[direction]
        self._log_config_factory = log_config_factory
        self._read_lock = Lock()
        self._arrival_lock = Lock()
        self._condition = Condition(Lock())
        self._bound_connection_epoch: str | None = None
        self._config: object | None = None
        self._opened = False
        self._sequence = 0
        self._request_generation = 0
        self._latest: tuple[int, int, int] | None = None
        self._stream_error: RangeReadError | None = None
        self._poisoned_reason: str | None = None

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

    @property
    def poisoned(self) -> bool:
        return self._poisoned_reason is not None

    def _require_not_poisoned(self) -> None:
        if self._poisoned_reason is not None:
            raise RangeReadError(
                "range observer is poisoned by uncertain teardown: "
                + self._poisoned_reason
            )

    def _read_epoch(self) -> str:
        try:
            epoch = self._connection_epoch_reader()
        except Exception as exc:
            raise RangeReadError(
                "connection epoch is unavailable for range observation"
            ) from exc
        if (
            not isinstance(epoch, str)
            or not epoch.strip()
            or epoch != epoch.strip()
        ):
            raise RangeReadError("connection epoch is invalid for range observation")
        return epoch

    def _verify_epoch(self) -> str:
        current = self._read_epoch()
        if (
            self._bound_connection_epoch is not None
            and current != self._bound_connection_epoch
        ):
            raise RangeReadError(
                "connection epoch changed during range observation"
            )
        return current

    def _require_exact_toc_entry(self) -> None:
        log = getattr(self._cf, "log", None)
        toc = getattr(log, "toc", None)
        lookup = getattr(toc, "get_element_by_complete_name", None)
        if not callable(lookup):
            raise RangeReadError(
                "live log TOC is unavailable for range observation"
            )
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
                f"live log TOC entry {self._variable} does not match "
                "pinned uint16_t range semantics"
            )

    def _make_config(self) -> object:
        if self._log_config_factory is not None:
            return self._log_config_factory()
        try:
            from cflib.crazyflie.log import LogConfig
        except ImportError as exc:
            raise RangeReadError("cflib logging support is unavailable") from exc
        config = LogConfig(
            f"WebeeBlocks fresh {self._direction} range",
            LOG_PERIOD_MS,
        )
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

    @staticmethod
    def _validate_raw_mm(raw_mm: object) -> int:
        if isinstance(raw_mm, bool) or not isinstance(raw_mm, int):
            raise RangeReadError(
                "range sample is not an exact uint16 millimetre value"
            )
        if raw_mm < 0 or raw_mm > _UINT16_MAX:
            raise RangeReadError(
                "range sample is outside the uint16 firmware domain"
            )
        return raw_mm

    def _on_data(self, timestamp: object, data: object, config: object) -> None:
        # Capture request generation at callback entry, before any processing
        # that may block behind the read-side condition lock.
        with self._arrival_lock:
            arrival_generation = self._request_generation

        if config is not self._config:
            return
        try:
            if (
                not isinstance(timestamp, int)
                or isinstance(timestamp, bool)
                or timestamp < 0
                or timestamp > _TIMESTAMP_MASK
            ):
                raise RangeReadError(
                    "range sample has an invalid firmware timestamp"
                )
            if not isinstance(data, dict) or self._variable not in data:
                raise RangeReadError(
                    f"range sample is missing {self._variable}"
                )
            raw_mm = self._validate_raw_mm(data[self._variable])
        except RangeReadError as exc:
            self._set_error(str(exc))
            return

        with self._condition:
            if self._stream_error is not None:
                return
            self._sequence += 1
            self._latest = (
                timestamp,
                raw_mm,
                arrival_generation,
            )
            self._condition.notify_all()

    def _wait_for_sample(
        self,
        *,
        after_sequence: int,
        after_timestamp: int | None,
        request_generation: int,
        timeout_seconds: float,
    ) -> tuple[int, int]:
        deadline = monotonic() + timeout_seconds
        with self._condition:
            while True:
                if self._stream_error is not None:
                    raise self._stream_error
                if self._sequence > after_sequence and self._latest is not None:
                    timestamp, raw_mm, sample_generation = self._latest
                    if (
                        sample_generation == request_generation
                        and (
                            after_timestamp is None
                            or _timestamp_is_later(timestamp, after_timestamp)
                        )
                    ):
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
            self._require_not_poisoned()
            if self._opened:
                self._verify_epoch()
                return

            self._bound_connection_epoch = self._read_epoch()
            self._require_exact_toc_entry()
            with self._arrival_lock:
                self._request_generation = 0
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
                    request_generation=0,
                    timeout_seconds=timeout_seconds,
                )
                self._verify_epoch()
                self._opened = True
            except Exception as exc:
                cleanup_errors = self._cleanup(
                    config,
                    data_registered=data_registered,
                    error_registered=error_registered,
                    disconnect_registered=disconnect_registered,
                )
                if cleanup_errors:
                    self._poisoned_reason = "; ".join(cleanup_errors)
                if isinstance(exc, RangeReadError):
                    raise
                raise RangeReadError(
                    f"could not start fresh range logging: {exc}"
                ) from exc

    def _cleanup(
        self,
        config: object,
        *,
        data_registered: bool,
        error_registered: bool,
        disconnect_registered: bool,
    ) -> list[str]:
        errors: list[str] = []
        for label, action in (
            ("stop", getattr(config, "stop", None)),
            ("delete", getattr(config, "delete", None)),
        ):
            if callable(action):
                try:
                    action()
                except Exception as exc:
                    errors.append(f"{label}: {exc}")
        if data_registered:
            try:
                config.data_received_cb.remove_callback(self._on_data)
            except Exception as exc:
                errors.append(f"data callback cleanup: {exc}")
        if error_registered:
            try:
                config.error_cb.remove_callback(self._on_log_error)
            except Exception as exc:
                errors.append(f"error callback cleanup: {exc}")
        if disconnect_registered:
            try:
                self._cf.disconnected.remove_callback(self._on_disconnect)
            except Exception as exc:
                errors.append(f"disconnect callback cleanup: {exc}")
        self._config = None
        self._opened = False
        return errors

    def read(self, *, timeout_seconds: float = 0.7) -> RangeObservation:
        """Return one newly arrived post-call sample from the bound epoch."""
        if timeout_seconds <= 0:
            raise RangeReadError("range timeout must be positive")

        with self._read_lock:
            self._require_not_poisoned()
            if (
                not self._opened
                or self._config is None
                or self._bound_connection_epoch is None
            ):
                raise RangeReadError("range observer is not open")
            self._verify_epoch()

            # This lock order is shared with callback entry. A callback that
            # already crossed entry before this generation increment retains the
            # prior generation even if condition processing completes later.
            with self._arrival_lock:
                self._request_generation += 1
                request_generation = self._request_generation
                with self._condition:
                    if self._stream_error is not None:
                        raise self._stream_error
                    baseline_sequence = self._sequence
                    if self._latest is None:
                        raise RangeReadError(
                            "range observer has no established baseline"
                        )
                    baseline_timestamp = self._latest[0]

            timestamp, raw_mm = self._wait_for_sample(
                after_sequence=baseline_sequence,
                after_timestamp=baseline_timestamp,
                request_generation=request_generation,
                timeout_seconds=timeout_seconds,
            )
            epoch = self._verify_epoch()
            return RangeObservation(
                connection_epoch=epoch,
                firmware_timestamp_ms=timestamp,
                direction=self._direction,
                raw_mm=raw_mm,
                range_m=range_mm_to_m(raw_mm),
            )

    def close(self) -> None:
        """Stop/delete the stream; uncertain teardown poisons this observer."""
        with self._read_lock:
            self._require_not_poisoned()
            config = self._config
            if config is None:
                self._opened = False
                return
            errors = self._cleanup(
                config,
                data_registered=True,
                error_registered=True,
                disconnect_registered=True,
            )
            if errors:
                self._poisoned_reason = "; ".join(errors)
                raise RangeReadError(
                    "could not close range observer cleanly: "
                    + self._poisoned_reason
                )

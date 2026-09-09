#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import math
import pathlib
import threading

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "physical" / "yaw_observer.py"

spec = importlib.util.spec_from_file_location("webeeblocks_yaw_observer", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load yaw observer")
yaw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(yaw)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except yaw.YawReadError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError(f"expected YawReadError containing {pattern!r}")


class FakeCaller:
    def __init__(self) -> None:
        self.callbacks = []

    def add_callback(self, callback) -> None:
        self.callbacks.append(callback)

    def remove_callback(self, callback) -> None:
        self.callbacks.remove(callback)

    def call(self, *args) -> None:
        for callback in list(self.callbacks):
            callback(*args)


class FakeConfig:
    def __init__(self, initial_sample=None) -> None:
        self.data_received_cb = FakeCaller()
        self.error_cb = FakeCaller()
        self.initial_sample = initial_sample
        self.started = False
        self.stopped = False
        self.deleted = False
        self.start_error = None

    def start(self) -> None:
        if self.start_error is not None:
            raise self.start_error
        self.started = True
        if self.initial_sample is not None:
            timestamp, value = self.initial_sample
            self.emit(timestamp, value)

    def stop(self) -> None:
        self.stopped = True

    def delete(self) -> None:
        self.deleted = True

    def emit(self, timestamp, value) -> None:
        data = value if isinstance(value, dict) else {yaw.YAW_VARIABLE: value}
        self.data_received_cb.call(timestamp, data, self)

    def fail(self, message: str) -> None:
        self.error_cb.call(self, message)


class FakeLog:
    def __init__(self) -> None:
        self.configs = []
        self.add_error = None

    def add_config(self, config) -> None:
        if self.add_error is not None:
            raise self.add_error
        self.configs.append(config)


class FakeCf:
    def __init__(self) -> None:
        self.log = FakeLog()
        self.disconnected = FakeCaller()


class Epoch:
    def __init__(self, value: str) -> None:
        self.value = value

    def __call__(self) -> str:
        return self.value


def make_observer(initial=(100, 10.0), epoch_value="epoch-yaw"):
    cf = FakeCf()
    epoch = Epoch(epoch_value)
    config = FakeConfig(initial)
    observer = yaw.FreshYawObserver(cf, epoch, log_config_factory=lambda: config)
    return observer, cf, epoch, config


def delayed(delay: float, function) -> None:
    timer = threading.Timer(delay, function)
    timer.daemon = True
    timer.start()


def test_open_baseline_and_later_read() -> None:
    observer, _cf, _epoch, config = make_observer()
    observer.open(timeout_seconds=0.05)
    require(observer.is_open and observer.bound_connection_epoch == "epoch-yaw", "open epoch")
    delayed(0.01, lambda: config.emit(110, 20.0))
    result = observer.read(timeout_seconds=0.2)
    require(result.firmware_timestamp_ms == 110 and result.yaw_deg == 20.0, "later sample")
    require(math.isclose(result.yaw_rad, math.radians(20.0), abs_tol=1e-15), "degrees to radians")
    observer.close()


def test_cached_baseline_not_returned() -> None:
    observer, _cf, _epoch, _config = make_observer()
    observer.open(timeout_seconds=0.05)
    expect_error(lambda: observer.read(timeout_seconds=0.01), "fresh yaw sample timed out")
    observer.close()


def test_duplicate_timestamp_ignored() -> None:
    observer, _cf, _epoch, config = make_observer()
    observer.open(timeout_seconds=0.05)
    delayed(0.005, lambda: config.emit(100, 99.0))
    delayed(0.015, lambda: config.emit(120, 30.0))
    result = observer.read(timeout_seconds=0.2)
    require(result.firmware_timestamp_ms == 120 and result.yaw_deg == 30.0, "duplicate timestamp")
    observer.close()


def test_timestamp_wrap() -> None:
    observer, _cf, _epoch, config = make_observer(initial=(0xFFFFF8, -179.0), epoch_value="epoch-wrap")
    observer.open(timeout_seconds=0.05)
    delayed(0.01, lambda: config.emit(5, 179.0))
    result = observer.read(timeout_seconds=0.2)
    require(result.firmware_timestamp_ms == 5 and result.yaw_deg == 179.0, "24-bit wrap")
    observer.close()


def test_epoch_rotation_fails_closed() -> None:
    observer, _cf, epoch, _config = make_observer(epoch_value="epoch-before")
    observer.open(timeout_seconds=0.05)
    epoch.value = "epoch-after"
    expect_error(lambda: observer.read(timeout_seconds=0.05), "connection epoch changed")
    observer.close()


def test_disconnect_and_log_error_fail_closed() -> None:
    observer, cf, _epoch, _config = make_observer(epoch_value="epoch-disconnect")
    observer.open(timeout_seconds=0.05)
    delayed(0.01, lambda: cf.disconnected.call("radio://test"))
    expect_error(lambda: observer.read(timeout_seconds=0.2), "disconnected during yaw observation")
    observer.close()

    observer2, _cf2, _epoch2, config2 = make_observer(epoch_value="epoch-log-error")
    observer2.open(timeout_seconds=0.05)
    delayed(0.01, lambda: config2.fail("firmware log rejected"))
    expect_error(lambda: observer2.read(timeout_seconds=0.2), "yaw logging failed")
    observer2.close()


def test_invalid_samples_fail_open_and_cleanup() -> None:
    for epoch_value, initial, pattern in (
        ("epoch-nan", (100, float("nan")), "not finite"),
        ("epoch-missing", (100, {}), "missing stateEstimate.yaw"),
        ("epoch-ts", (0x1000000, 0.0), "invalid firmware timestamp"),
    ):
        observer, cf, _epoch, config = make_observer(initial=initial, epoch_value=epoch_value)
        expect_error(lambda o=observer: o.open(timeout_seconds=0.05), pattern)
        require(config.stopped and config.deleted, "failed-open log cleanup")
        require(cf.disconnected.callbacks == [], "failed-open disconnect cleanup")


def test_add_and_start_failures_are_typed() -> None:
    observer, cf, _epoch, config = make_observer(epoch_value="epoch-add-fail")
    cf.log.add_error = RuntimeError("TOC unavailable")
    expect_error(lambda: observer.open(timeout_seconds=0.05), "could not start fresh yaw logging")
    require(config.stopped and config.deleted and cf.disconnected.callbacks == [], "add failure cleanup")

    observer2, cf2, _epoch2, config2 = make_observer(epoch_value="epoch-start-fail")
    config2.start_error = RuntimeError("start failed")
    expect_error(lambda: observer2.open(timeout_seconds=0.05), "could not start fresh yaw logging")
    require(config2.stopped and config2.deleted and cf2.disconnected.callbacks == [], "start failure cleanup")


def test_close_removes_callbacks_and_is_idempotent() -> None:
    observer, cf, _epoch, config = make_observer(epoch_value="epoch-close")
    observer.open(timeout_seconds=0.05)
    observer.close()
    require(config.stopped and config.deleted, "close stops/deletes")
    require(config.data_received_cb.callbacks == [] and config.error_cb.callbacks == [], "log callbacks removed")
    require(cf.disconnected.callbacks == [], "disconnect callback removed")
    require(not observer.is_open, "closed state")
    observer.close()


def test_local_errors_emit_no_log_request() -> None:
    observer, cf, _epoch, config = make_observer(epoch_value="epoch-local")
    expect_error(lambda: observer.open(timeout_seconds=0), "timeout must be positive")
    require(cf.log.configs == [] and not config.started, "invalid open has no log effect")
    expect_error(lambda: observer.read(timeout_seconds=0.01), "not open")


def main() -> int:
    test_open_baseline_and_later_read()
    test_cached_baseline_not_returned()
    test_duplicate_timestamp_ignored()
    test_timestamp_wrap()
    test_epoch_rotation_fails_closed()
    test_disconnect_and_log_error_fail_closed()
    test_invalid_samples_fail_open_and_cleanup()
    test_add_and_start_failures_are_typed()
    test_close_removes_callbacks_and_is_idempotent()
    test_local_errors_emit_no_log_request()

    source = MODULE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "send_arming_request",
        "send_emergency_stop",
        "send_emergency_stop_watchdog",
        "HighLevelCommander(",
        "send_setpoint",
        "send_hover_setpoint",
        "send_velocity_world_setpoint",
    ):
        require(forbidden not in source, f"yaw observer exposes authority surface: {forbidden}")

    print("PASS fresh same-epoch stateEstimate.yaw observation has no execution authority")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

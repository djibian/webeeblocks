#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import threading

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "physical" / "range_observer.py"

spec = importlib.util.spec_from_file_location("webeeblocks_range_observer", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load range observer")
range_observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(range_observer)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except range_observer.RangeReadError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError(f"expected RangeReadError containing {pattern!r}")


class FakeCaller:
    def __init__(self):
        self.callbacks = []

    def add_callback(self, callback):
        self.callbacks.append(callback)

    def remove_callback(self, callback):
        self.callbacks.remove(callback)

    def call(self, *args):
        for callback in list(self.callbacks):
            callback(*args)


class FakeTocElement:
    def __init__(self, direction, *, ctype="uint16_t", pytype="<H"):
        self.group = "range"
        self.name = direction
        self.ctype = ctype
        self.pytype = pytype


class FakeToc:
    def __init__(self, direction, *, present=True, ctype="uint16_t", pytype="<H"):
        self.variable = f"range.{direction}"
        self.element = (
            FakeTocElement(direction, ctype=ctype, pytype=pytype)
            if present
            else None
        )

    def get_element_by_complete_name(self, name):
        return self.element if name == self.variable else None


class FakeConfig:
    def __init__(self, variable, initial_sample=None):
        self.variable = variable
        self.data_received_cb = FakeCaller()
        self.error_cb = FakeCaller()
        self.initial_sample = initial_sample
        self.started = False
        self.stopped = False
        self.deleted = False
        self.start_error = None

    def start(self):
        if self.start_error:
            raise self.start_error
        self.started = True
        if self.initial_sample is not None:
            timestamp, value = self.initial_sample
            self.emit(timestamp, value)

    def stop(self):
        self.stopped = True

    def delete(self):
        self.deleted = True

    def emit(self, timestamp, value):
        data = value if isinstance(value, dict) else {self.variable: value}
        self.data_received_cb.call(timestamp, data, self)

    def fail(self, message):
        self.error_cb.call(self, message)


class FakeLog:
    def __init__(self, toc):
        self.toc = toc
        self.configs = []
        self.add_error = None

    def add_config(self, config):
        if self.add_error:
            raise self.add_error
        self.configs.append(config)


class FakeCf:
    def __init__(self, direction, **toc_kwargs):
        self.log = FakeLog(FakeToc(direction, **toc_kwargs))
        self.disconnected = FakeCaller()


class Epoch:
    def __init__(self, value):
        self.value = value

    def __call__(self):
        return self.value


def delayed(delay, function):
    timer = threading.Timer(delay, function)
    timer.daemon = True
    timer.start()


def make_observer(
    direction="front",
    initial=(100, 1500),
    epoch_value="epoch-range",
    **toc_kwargs,
):
    cf = FakeCf(direction, **toc_kwargs)
    epoch = Epoch(epoch_value)
    variable = f"range.{direction}"
    config = FakeConfig(variable, initial)
    observer = range_observer.FreshRangeObserver(
        cf, epoch, direction, log_config_factory=lambda: config
    )
    return observer, cf, epoch, config


def test_exact_direction_and_fresh_read():
    for direction in range_observer.SUPPORTED_DIRECTIONS:
        observer, _cf, _epoch, config = make_observer(direction=direction)
        observer.open(timeout_seconds=0.05)
        require(observer.variable == f"range.{direction}", "exact firmware variable")
        delayed(0.01, lambda c=config: c.emit(110, 750))
        result = observer.read(timeout_seconds=0.2)
        require(
            result.direction == direction and result.raw_mm == 750,
            "exact fresh sample",
        )
        require(result.range_m == 0.75, "firmware mm normalize to Runtime metres")
        observer.close()


def test_down_and_substitution_fail_before_log_setup():
    expect_error(
        lambda: range_observer.FreshRangeObserver(
            FakeCf("front"), Epoch("e"), "down"
        ),
        "unsupported physical range direction",
    )


def test_cached_and_duplicate_samples_cannot_decide():
    observer, _cf, _epoch, config = make_observer()
    observer.open(timeout_seconds=0.05)
    expect_error(
        lambda: observer.read(timeout_seconds=0.01), "fresh range sample timed out"
    )
    delayed(0.005, lambda: config.emit(100, 200))
    delayed(0.015, lambda: config.emit(120, 300))
    result = observer.read(timeout_seconds=0.2)
    require(
        result.firmware_timestamp_ms == 120 and result.raw_mm == 300,
        "duplicate ignored",
    )
    observer.close()


def test_each_read_requires_a_new_sample():
    observer, _cf, _epoch, config = make_observer()
    observer.open(timeout_seconds=0.05)
    delayed(0.01, lambda: config.emit(110, 500))
    first = observer.read(timeout_seconds=0.2)
    require(first.range_m == 0.5, "first fresh read")
    expect_error(
        lambda: observer.read(timeout_seconds=0.01), "fresh range sample timed out"
    )
    delayed(0.01, lambda: config.emit(120, 600))
    second = observer.read(timeout_seconds=0.2)
    require(
        second.range_m == 0.6 and second.firmware_timestamp_ms == 120,
        "second fresh read",
    )
    observer.close()


def test_runtime_horizon_and_firmware_no_range_normalization():
    require(range_observer.normalize_runtime_range_m(0) == 0.0, "zero range")
    require(
        range_observer.normalize_runtime_range_m(1999) == 1.999, "direct metres"
    )
    require(
        range_observer.normalize_runtime_range_m(2500) == 2.0,
        "Runtime horizon caps distant obstacle",
    )
    require(
        range_observer.normalize_runtime_range_m(
            range_observer.FIRMWARE_NO_RANGE_MM
        )
        == 2.0,
        "firmware unavailable sentinel maps to Runtime no-obstacle horizon",
    )
    for invalid in (True, 1.5, -1, 32768, 65535):
        expect_error(
            lambda value=invalid: range_observer.normalize_runtime_range_m(value),
            "range sample",
        )


def test_exact_live_toc_contract():
    observer, cf, _epoch, config = make_observer(present=False)
    expect_error(lambda: observer.open(timeout_seconds=0.05), "missing range.front")
    require(
        cf.log.configs == [] and not config.started,
        "missing TOC fails before log setup",
    )
    for field, kwargs in (
        ("ctype", {"ctype": "float"}),
        ("pytype", {"pytype": "<L"}),
    ):
        observer2, cf2, _epoch2, config2 = make_observer(**kwargs)
        expect_error(
            lambda o=observer2: o.open(timeout_seconds=0.05), "pinned uint16_t"
        )
        require(
            cf2.log.configs == [] and not config2.started,
            field + " mismatch is pre-stream",
        )


def test_epoch_rotation_disconnect_and_log_error_fail_closed():
    observer, _cf, epoch, _config = make_observer(epoch_value="before")
    observer.open(timeout_seconds=0.05)
    epoch.value = "after"
    expect_error(
        lambda: observer.read(timeout_seconds=0.05), "connection epoch changed"
    )
    observer.close()

    observer2, cf2, _epoch2, _config2 = make_observer(epoch_value="disconnect")
    observer2.open(timeout_seconds=0.05)
    delayed(0.01, lambda: cf2.disconnected.call("radio://test"))
    expect_error(
        lambda: observer2.read(timeout_seconds=0.2),
        "disconnected during range observation",
    )
    observer2.close()

    observer3, _cf3, _epoch3, config3 = make_observer(epoch_value="log-error")
    observer3.open(timeout_seconds=0.05)
    delayed(0.01, lambda: config3.fail("firmware log rejected"))
    expect_error(
        lambda: observer3.read(timeout_seconds=0.2), "range logging failed"
    )
    observer3.close()


def test_invalid_samples_fail_open_and_cleanup():
    for initial, pattern in (
        ((100, {"other": 1}), "missing range.front"),
        ((0x1000000, 1000), "invalid firmware timestamp"),
        ((100, 32768), "outside the pinned firmware domain"),
    ):
        observer, cf, _epoch, config = make_observer(initial=initial)
        expect_error(lambda o=observer: o.open(timeout_seconds=0.05), pattern)
        require(config.stopped and config.deleted, "failed open cleanup")
        require(cf.disconnected.callbacks == [], "disconnect cleanup")


def test_add_start_close_and_local_failures():
    observer, cf, _epoch, config = make_observer()
    cf.log.add_error = RuntimeError("TOC unavailable")
    expect_error(
        lambda: observer.open(timeout_seconds=0.05),
        "could not start fresh range logging",
    )
    require(config.stopped and config.deleted, "add failure cleanup")

    observer2, cf2, _epoch2, config2 = make_observer()
    config2.start_error = RuntimeError("start failed")
    expect_error(
        lambda: observer2.open(timeout_seconds=0.05),
        "could not start fresh range logging",
    )
    require(
        config2.stopped and config2.deleted and cf2.disconnected.callbacks == [],
        "start failure cleanup",
    )

    observer3, cf3, _epoch3, config3 = make_observer()
    observer3.open(timeout_seconds=0.05)
    observer3.close()
    require(config3.stopped and config3.deleted, "clean close")
    require(
        config3.data_received_cb.callbacks == []
        and config3.error_cb.callbacks == [],
        "log callbacks removed",
    )
    require(cf3.disconnected.callbacks == [], "disconnect callback removed")
    observer3.close()

    observer4, cf4, _epoch4, config4 = make_observer()
    expect_error(lambda: observer4.open(timeout_seconds=0), "timeout must be positive")
    require(
        cf4.log.configs == [] and not config4.started,
        "invalid open has no log setup",
    )
    expect_error(lambda: observer4.read(timeout_seconds=0.01), "not open")


def main():
    test_exact_direction_and_fresh_read()
    test_down_and_substitution_fail_before_log_setup()
    test_cached_and_duplicate_samples_cannot_decide()
    test_each_read_requires_a_new_sample()
    test_runtime_horizon_and_firmware_no_range_normalization()
    test_exact_live_toc_contract()
    test_epoch_rotation_disconnect_and_log_error_fail_closed()
    test_invalid_samples_fail_open_and_cleanup()
    test_add_start_close_and_local_failures()
    source = MODULE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "send_arming_request",
        "send_emergency_stop",
        "send_emergency_stop_watchdog",
        "HighLevelCommander(",
        "send_setpoint",
        "send_hover_setpoint",
        "send_velocity_world_setpoint",
        "effect_transaction(",
    ):
        require(
            forbidden not in source,
            f"range observer exposes authority surface: {forbidden}",
        )
    print(
        "PASS fresh same-epoch physical range observation normalizes exact 5-direction Runtime semantics without execution authority"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "physical" / "range_observer.py"

spec = importlib.util.spec_from_file_location("webeeblocks_range_observer", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load range observer")
rng = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rng)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except rng.RangeReadError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError(f"expected RangeReadError containing {pattern!r}")


class FakeCaller:
    def __init__(self) -> None:
        self.callbacks = []

    def add_callback(self, callback) -> None:
        if callback not in self.callbacks:
            self.callbacks.append(callback)

    def remove_callback(self, callback) -> None:
        self.callbacks.remove(callback)

    def call(self, *args) -> None:
        for callback in list(self.callbacks):
            callback(*args)


class FakeTocElement:
    def __init__(
        self,
        *,
        group="range",
        name="front",
        ctype="uint16_t",
        pytype="<H",
    ) -> None:
        self.group = group
        self.name = name
        self.ctype = ctype
        self.pytype = pytype


class FakeToc:
    def __init__(self, variable: str) -> None:
        group, name = variable.split(".", 1)
        self.element = FakeTocElement(group=group, name=name)
        self.lookups = []

    def get_element_by_complete_name(self, name: str):
        self.lookups.append(name)
        if self.element is None:
            return None
        expected = f"{self.element.group}.{self.element.name}"
        return self.element if name == expected else None


class FakeConfig:
    def __init__(self, variable: str, initial_sample=(100, 500)) -> None:
        self.variable = variable
        self.data_received_cb = FakeCaller()
        self.error_cb = FakeCaller()
        self.initial_sample = initial_sample
        self.started = False
        self.stopped = False
        self.deleted = False
        self.start_error = None
        self.stop_error = None
        self.delete_error = None

    def start(self) -> None:
        if self.start_error is not None:
            raise self.start_error
        self.started = True
        if self.initial_sample is not None:
            timestamp, value = self.initial_sample
            self.emit(timestamp, value)

    def stop(self) -> None:
        self.stopped = True
        if self.stop_error is not None:
            raise self.stop_error

    def delete(self) -> None:
        self.deleted = True
        if self.delete_error is not None:
            raise self.delete_error

    def emit(self, timestamp, value) -> None:
        data = value if isinstance(value, dict) else {self.variable: value}
        self.data_received_cb.call(timestamp, data, self)

    def fail(self, message: str) -> None:
        self.error_cb.call(self, message)


class FakeLog:
    def __init__(self, variable: str) -> None:
        self.toc = FakeToc(variable)
        self.configs = []
        self.add_error = None

    def add_config(self, config) -> None:
        if self.add_error is not None:
            raise self.add_error
        self.configs.append(config)


class FakeCf:
    def __init__(self, variable: str) -> None:
        self.log = FakeLog(variable)
        self.disconnected = FakeCaller()


class Epoch:
    def __init__(self, value: str) -> None:
        self.value = value

    def __call__(self) -> str:
        return self.value


def make_observer(
    direction="front",
    *,
    initial=(100, 500),
    epoch_value="epoch-range",
):
    variable = f"range.{direction}"
    cf = FakeCf(variable)
    epoch = Epoch(epoch_value)
    config = FakeConfig(variable, initial)
    observer = rng.FreshRangeObserver(
        cf,
        epoch,
        direction,
        log_config_factory=lambda: config,
    )
    return observer, cf, epoch, config


def delayed(delay: float, function) -> threading.Timer:
    timer = threading.Timer(delay, function)
    timer.daemon = True
    timer.start()
    return timer


def test_exact_direction_mapping_and_conversion() -> None:
    values = {
        "front": 1234,
        "back": 2345,
        "left": 3456,
        "right": 4567,
        "up": 5678,
    }
    for direction, raw_mm in values.items():
        observer, cf, _epoch, config = make_observer(direction)
        require(observer.variable == f"range.{direction}", "exact range variable")
        observer.open(timeout_seconds=0.05)
        require(
            cf.log.toc.lookups == [f"range.{direction}"],
            "TOC lookup must be exact",
        )
        delayed(0.005, lambda c=config, value=raw_mm: c.emit(110, value))
        result = observer.read(timeout_seconds=0.2)
        require(result.direction == direction, "direction preserved")
        require(result.raw_mm == raw_mm, "raw millimetres preserved")
        require(
            result.range_m == raw_mm / 1000.0,
            "millimetres converted to metres exactly once",
        )
        observer.close()


def test_pinned_cflib_unavailable_boundary_is_not_clamped() -> None:
    require(rng.range_mm_to_m(7999) == 7.999, "last available value")
    for raw in (8000, 32767, 65535):
        expect_error(
            lambda value=raw: rng.range_mm_to_m(value),
            "unavailable",
        )

    observer, _cf, _epoch, config = make_observer(initial=(100, 9000))
    observer.open(timeout_seconds=0.05)
    delayed(0.005, lambda: config.emit(110, 8000))
    expect_error(
        lambda: observer.read(timeout_seconds=0.2),
        "unavailable",
    )
    delayed(0.005, lambda: config.emit(120, 1250))
    result = observer.read(timeout_seconds=0.2)
    require(result.range_m == 1.25, "later valid sample remains observable")
    observer.close()


def test_cached_and_duplicate_samples_are_not_fresh() -> None:
    observer, _cf, _epoch, config = make_observer()
    observer.open(timeout_seconds=0.05)
    expect_error(
        lambda: observer.read(timeout_seconds=0.01),
        "fresh range sample timed out",
    )

    delayed(0.005, lambda: config.emit(100, 900))
    delayed(0.015, lambda: config.emit(120, 1000))
    result = observer.read(timeout_seconds=0.2)
    require(
        result.firmware_timestamp_ms == 120 and result.range_m == 1.0,
        "duplicate timestamp must not satisfy fresh read",
    )
    observer.close()


def test_callback_entered_before_read_cannot_finish_as_fresh() -> None:
    observer, _cf, _epoch, config = make_observer()
    observer.open(timeout_seconds=0.05)

    observer._condition.acquire()
    stale_done = threading.Event()
    stale = threading.Thread(
        target=lambda: (
            config.emit(110, 700),
            stale_done.set(),
        ),
        daemon=True,
    )
    stale.start()

    with observer._arrival_lock:
        pass

    outcome = {}

    def do_read() -> None:
        try:
            outcome["value"] = observer.read(timeout_seconds=0.3)
        except Exception as exc:
            outcome["error"] = exc

    reader = threading.Thread(target=do_read, daemon=True)
    reader.start()

    deadline = time.monotonic() + 0.2
    while observer._request_generation != 1:
        if time.monotonic() >= deadline:
            raise AssertionError("read did not establish request generation")
        time.sleep(0.001)

    observer._condition.release()
    require(stale_done.wait(0.1), "stale callback completed")
    delayed(0.01, lambda: config.emit(120, 800))
    reader.join(timeout=0.3)
    require(not reader.is_alive(), "fresh read completed")
    require("error" not in outcome, f"unexpected read error: {outcome.get('error')!r}")
    result = outcome["value"]
    require(
        result.firmware_timestamp_ms == 120 and result.range_m == 0.8,
        "pre-request callback must not become fresh after delayed processing",
    )
    observer.close()


def test_timestamp_wrap_and_epoch_rotation() -> None:
    observer, _cf, epoch, config = make_observer(
        initial=(0xFFFFF8, 500),
        epoch_value="epoch-before",
    )
    observer.open(timeout_seconds=0.05)
    delayed(0.005, lambda: config.emit(5, 600))
    result = observer.read(timeout_seconds=0.2)
    require(result.firmware_timestamp_ms == 5, "24-bit timestamp wrap")
    epoch.value = "epoch-after"
    expect_error(
        lambda: observer.read(timeout_seconds=0.05),
        "connection epoch changed",
    )
    observer.close()


def test_malformed_disconnect_and_log_error_fail_closed() -> None:
    for bad, pattern in (
        (True, "exact uint16"),
        (1.5, "exact uint16"),
        (-1, "uint16 firmware domain"),
        (65536, "uint16 firmware domain"),
        ({}, "missing range.front"),
    ):
        observer, _cf, _epoch, config = make_observer(
            epoch_value=f"epoch-bad-{pattern}"
        )
        observer.open(timeout_seconds=0.05)
        delayed(0.005, lambda c=config, value=bad: c.emit(110, value))
        expect_error(
            lambda o=observer: o.read(timeout_seconds=0.2),
            pattern,
        )
        observer.close()

    observer, cf, _epoch, _config = make_observer(
        epoch_value="epoch-disconnect"
    )
    observer.open(timeout_seconds=0.05)
    delayed(0.005, lambda: cf.disconnected.call("radio://test"))
    expect_error(
        lambda: observer.read(timeout_seconds=0.2),
        "disconnected during range observation",
    )
    observer.close()

    observer2, _cf2, _epoch2, config2 = make_observer(
        epoch_value="epoch-log-error"
    )
    observer2.open(timeout_seconds=0.05)
    delayed(0.005, lambda: config2.fail("firmware log rejected"))
    expect_error(
        lambda: observer2.read(timeout_seconds=0.2),
        "range logging failed",
    )
    observer2.close()


def test_toc_and_setup_failures_fail_closed() -> None:
    observer, cf, _epoch, config = make_observer()
    cf.log.toc.element = None
    expect_error(
        lambda: observer.open(timeout_seconds=0.05),
        "missing range.front",
    )
    require(not config.started, "missing TOC emits no log request")

    observer2, cf2, _epoch2, config2 = make_observer(
        epoch_value="epoch-wrong-type"
    )
    cf2.log.toc.element.ctype = "float"
    expect_error(
        lambda: observer2.open(timeout_seconds=0.05),
        "does not match pinned uint16_t",
    )
    require(not config2.started, "wrong TOC emits no log request")

    observer3, cf3, _epoch3, config3 = make_observer(
        epoch_value="epoch-add"
    )
    cf3.log.add_error = RuntimeError("TOC unavailable")
    expect_error(
        lambda: observer3.open(timeout_seconds=0.05),
        "could not start fresh range logging",
    )
    require(config3.stopped and config3.deleted, "failed setup cleaned")


def test_uncertain_close_poison_prevents_reuse() -> None:
    observer, _cf, _epoch, config = make_observer(
        epoch_value="epoch-close"
    )
    observer.open(timeout_seconds=0.05)
    config.stop_error = RuntimeError("stop uncertain")
    expect_error(
        observer.close,
        "could not close range observer cleanly",
    )
    require(observer.poisoned and not observer.is_open, "uncertain close poisons")
    expect_error(
        lambda: observer.open(timeout_seconds=0.05),
        "poisoned by uncertain teardown",
    )


def test_local_validation_and_no_authority_surface() -> None:
    expect_error(
        lambda: rng.FreshRangeObserver(FakeCf("range.front"), Epoch("x"), "down"),
        "unsupported physical range direction",
    )
    observer, cf, _epoch, config = make_observer()
    expect_error(
        lambda: observer.open(timeout_seconds=0),
        "timeout must be positive",
    )
    require(cf.log.configs == [] and not config.started, "local error has no log effect")
    expect_error(
        lambda: observer.read(timeout_seconds=0.01),
        "not open",
    )

    source = MODULE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "send_arming_request",
        "send_emergency_stop",
        "send_emergency_stop_watchdog",
        "HighLevelCommander(",
        "send_setpoint",
        "send_hover_setpoint",
        "send_velocity_world_setpoint",
        "send_packet(",
        "Param.set_value",
    ):
        require(
            forbidden not in source,
            f"range observer exposes authority/effect surface: {forbidden}",
        )


def main() -> int:
    test_exact_direction_mapping_and_conversion()
    test_pinned_cflib_unavailable_boundary_is_not_clamped()
    test_cached_and_duplicate_samples_are_not_fresh()
    test_callback_entered_before_read_cannot_finish_as_fresh()
    test_timestamp_wrap_and_epoch_rotation()
    test_malformed_disconnect_and_log_error_fail_closed()
    test_toc_and_setup_failures_fail_closed()
    test_uncertain_close_poison_prevents_reuse()
    test_local_validation_and_no_authority_surface()
    print(
        "PASS fresh same-epoch Multi-ranger observation preserves pinned "
        ">=8000 mm unavailable semantics and exposes no execution authority"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

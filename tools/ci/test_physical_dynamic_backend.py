#!/usr/bin/env python3
from __future__ import annotations

from contextlib import contextmanager
import inspect
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
if str(PHYSICAL) not in sys.path:
    sys.path.insert(0, str(PHYSICAL))

from dynamic_physical_backend import (  # noqa: E402
    DynamicPhysicalBackendError,
    TrustedDynamicPhysicalBackend,
)
from physical_execution_domain import FLYING, INACTIVE  # noqa: E402
from shared_interpreter_host import BoundSharedInterpreter  # noqa: E402
import takeoff_command  # noqa: E402


EVENTS: list[object] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def canonical(program: list[dict[str, object]]) -> str:
    return takeoff_command._canonical_json(
        {
            "program": program,
            "semantics": "webeeblocks-ast-v1",
            "version": 1,
        }
    )


class FakeDomain:
    def __init__(self) -> None:
        self.phase = FLYING

    def observation_transaction(self, *checks):
        @contextmanager
        def transaction():
            EVENTS.append("observation-enter")
            require(self.phase == FLYING, "observation requires flying")
            for check in checks:
                check()
            try:
                yield object()
            finally:
                require(self.phase == FLYING, "observation changed physical phase")
                EVENTS.append("observation-exit")

        return transaction()


class FakeAuthorization:
    def __init__(self, ast_binding: str) -> None:
        self.binding = SimpleNamespace(
            profile_id="activity-physical",
            ast_binding=ast_binding,
            connection_epoch="epoch-live",
        )

    def assert_effect_binding(self, *, profile_id: str, ast_binding: str, connection_epoch: str) -> None:
        EVENTS.append("teacher-assert")
        require(profile_id == self.binding.profile_id, "profile binding changed")
        require(ast_binding == self.binding.ast_binding, "AST binding changed")
        require(connection_epoch == self.binding.connection_epoch, "teacher epoch changed")


class FakeWatchdog:
    def assert_live(self) -> None:
        EVENTS.append("watchdog-live")


class FakeRun:
    def __init__(self, ast_binding: str, domain: FakeDomain) -> None:
        self.crazyflie = object()
        self.execution_domain = domain
        self.teacher_authorization = FakeAuthorization(ast_binding)
        self.powered_session = SimpleNamespace(connection_epoch="epoch-live")
        self.watchdog_guard = FakeWatchdog()


class FakeRangeObserver:
    def __init__(self, run: FakeRun, direction: str, value: float, *, fail_read: bool = False, fail_close: bool = False) -> None:
        self.bound_crazyflie = run.crazyflie
        self.bound_connection_epoch = None
        self.direction = direction
        self._epoch = run.powered_session.connection_epoch
        self._value = value
        self._fail_read = fail_read
        self._fail_close = fail_close

    def open(self) -> None:
        EVENTS.append(("range-open", self.direction))
        self.bound_connection_epoch = self._epoch

    def read(self):
        EVENTS.append(("range-read", self.direction))
        if self._fail_read:
            raise RuntimeError("unavailable")
        return SimpleNamespace(
            connection_epoch=self._epoch,
            direction=self.direction,
            range_m=self._value,
        )

    def close(self) -> None:
        EVENTS.append(("range-close", self.direction))
        if self._fail_close:
            raise RuntimeError("uncertain teardown")


class FakeYawObserver:
    def __init__(self, run: FakeRun) -> None:
        self.bound_crazyflie = run.crazyflie
        self.bound_connection_epoch = run.powered_session.connection_epoch

    def open(self) -> None:
        EVENTS.append("yaw-open")

    def close(self) -> None:
        EVENTS.append("yaw-close")


class Accepted:
    accepted = True


class Rejected:
    accepted = False


class FakeTransport:
    def __init__(self, domain: FakeDomain, initial_nominal_altitude_m: float = 0.8) -> None:
        self.domain = domain
        self.initial_nominal_altitude_m = initial_nominal_altitude_m
        self.reject_next = False

    def _result(self):
        if self.reject_next:
            self.reject_next = False
            return Rejected()
        return Accepted()

    def send_horizontal_move(self, *, direction, distance_m, yaw_reader, timing_policy):
        EVENTS.append(("move", direction, distance_m, yaw_reader, timing_policy))
        return self._result()

    def send_vertical_move(self, *, direction, distance_m, timing_policy):
        EVENTS.append(("vertical", direction, distance_m, timing_policy))
        return self._result()

    def send_turn(self, *, angle_deg, timing_policy):
        EVENTS.append(("turn", angle_deg, timing_policy))
        return self._result()

    def send_controlled_landing(self):
        EVENTS.append("land")
        result = self._result()
        if result.accepted:
            self.domain.phase = INACTIVE
        return result


class FakeColorTransport:
    def __init__(self) -> None:
        self.reject_next = False

    def send_color(self, *, color: str):
        EVENTS.append(("light", color))
        if self.reject_next:
            self.reject_next = False
            return Rejected()
        return Accepted()


class FakeTimingPolicy:
    def __init__(self) -> None:
        self.speed = None

    def set_horizontal_speed(self, speed_m_s: float) -> None:
        EVENTS.append(("speed", speed_m_s))
        self.speed = speed_m_s


def representative_program() -> list[dict[str, object]]:
    variable = {"id": "front-distance", "name": "distance"}
    return [
        {"height_m": 0.8, "kind": "takeoff"},
        {
            "kind": "set_variable",
            "value": {"direction": "front", "kind": "range", "unit": "m"},
            "variable": variable,
        },
        {
            "condition": {
                "kind": "compare",
                "left": {"kind": "variable_get", "variable": variable},
                "op": "LT",
                "right": {"kind": "number", "value": 1.0},
            },
            "else": [{"angle_deg": 45.0, "kind": "turn"}],
            "kind": "if",
            "then": [{"direction": "left", "distance_m": 0.2, "kind": "move"}],
        },
        {
            "body": [{"color": "green", "kind": "set_light"}],
            "count": 2,
            "kind": "repeat",
        },
        {"kind": "wait", "seconds": 0.1},
        {"kind": "set_speed", "speed_m_s": 0.25},
        {"kind": "land"},
    ]


def make_backend(
    *,
    range_value: float = 0.4,
    fail_read: bool = False,
    fail_close: bool = False,
    transport_initial_altitude_m: float = 0.8,
):
    exact = canonical(representative_program())
    domain = FakeDomain()
    run = FakeRun(exact, domain)
    epoch = {"value": "epoch-live"}
    transport = FakeTransport(domain, transport_initial_altitude_m)
    color = FakeColorTransport()
    timing = FakeTimingPolicy()

    def current_program() -> None:
        EVENTS.append("current-program")
        require(epoch["value"] == "epoch-live", "current program must use live epoch")

    def range_factory(direction: str):
        EVENTS.append(("range-factory", direction))
        return FakeRangeObserver(
            run,
            direction,
            range_value,
            fail_read=fail_read,
            fail_close=fail_close,
        )

    def exact_wait(seconds: float) -> None:
        EVENTS.append(("wait", seconds))
        require(domain.phase == FLYING, "wait must remain in flying phase")

    backend = TrustedDynamicPhysicalBackend(
        ast_binding=exact,
        active_run=run,
        connection_epoch_reader=lambda: epoch["value"],
        assert_current_program=current_program,
        inflight_transport=transport,
        color_transport=color,
        timing_policy=timing,
        execute_wait=exact_wait,
        range_observer_factory=range_factory,
        yaw_observer_factory=lambda: FakeYawObserver(run),
    )
    return backend, domain, run, epoch, transport, color, timing


def test_real_shared_interpreter_drives_fresh_range_and_existing_consumers() -> None:
    EVENTS.clear()
    backend, domain, _run, _epoch, _transport, _color, timing = make_backend(range_value=0.4)
    try:
        result = BoundSharedInterpreter(backend.ast_binding, backend).run()
        require(result.variables == {"distance": 0.4}, "range value did not remain interpreter data")
        require(domain.phase == INACTIVE, "terminal controlled landing did not establish inactive")
        require(timing.speed == 0.25, "interpreter-selected speed state was not consumed")
        require(
            [event for event in EVENTS if isinstance(event, tuple) and event and event[0] in {"move", "turn"}][0][0]
            == "move",
            "range-driven branch did not reach the expected existing motion consumer",
        )
        require(not any(isinstance(event, tuple) and event and event[0] == "turn" for event in EVENTS), "non-selected branch emitted an action")
        require(EVENTS.count(("light", "green")) == 2, "repeat progression did not stay in shared interpreter")
        require(EVENTS.count(("range-read", "front")) == 1, "interpreter demand did not produce exactly one fresh range read")
        require(EVENTS.count("land") == 1, "terminal landing was not consumed exactly once")
        require("yaw-open" in EVENTS, "horizontal action did not retain fresh yaw consumer")
    finally:
        backend.close()
    require(EVENTS.count("yaw-close") == 1, "dynamic backend did not close its yaw observer")


def test_range_observation_is_exclusion_held_and_reasserted_around_sample() -> None:
    EVENTS.clear()
    backend, _domain, _run, _epoch, _transport, _color, _timing = make_backend()
    backend.takeoff(0.8)
    start = len(EVENTS)
    value = backend.readRange("front")
    require(value == 0.4, "fresh range metres changed")
    trace = EVENTS[start:]
    enter = trace.index("observation-enter")
    factory = trace.index(("range-factory", "front"))
    opened = trace.index(("range-open", "front"))
    read = trace.index(("range-read", "front"))
    closed = trace.index(("range-close", "front"))
    exit_ = trace.index("observation-exit")
    require(enter < factory < opened < read < closed < exit_, "fresh range escaped observation exclusion")
    require(trace.count("current-program") >= 2, "current-program provenance was not reasserted around observation")
    require(trace.count("watchdog-live") >= 2, "watchdog provenance was not reasserted around observation")


def test_takeoff_is_verification_only_and_cannot_repeat() -> None:
    EVENTS.clear()
    backend, domain, _run, _epoch, _transport, _color, _timing = make_backend()
    backend.takeoff(0.8)
    require(domain.phase == FLYING, "verification-only takeoff changed physical phase")
    require(backend.initial_takeoff_height_m == 0.8, "takeoff verification height did not come from exact preflight")
    require(not any(event == "land" or (isinstance(event, tuple) and event and event[0] in {"move", "turn", "vertical"}) for event in EVENTS), "takeoff verification emitted a downstream action")
    try:
        backend.takeoff(0.8)
    except DynamicPhysicalBackendError as exc:
        require("repeated bound takeoff" in str(exc), "repeat takeoff failed for wrong reason")
    else:
        raise AssertionError("shared interpreter could repeat causal takeoff")


def test_initial_altitude_has_no_auxiliary_authority_root() -> None:
    EVENTS.clear()
    signature = inspect.signature(TrustedDynamicPhysicalBackend)
    require(
        "initial_takeoff_height_m" not in signature.parameters,
        "dynamic backend still accepts an independent initial takeoff height",
    )
    try:
        make_backend(transport_initial_altitude_m=0.6)
    except DynamicPhysicalBackendError as exc:
        require("altitude differs" in str(exc), "split dynamic landing root failed for wrong reason")
    else:
        raise AssertionError("mismatched dynamic landing altitude survived composition")
    require(
        not any(
            event == "land"
            or (isinstance(event, tuple) and event and event[0] in {"move", "turn", "vertical", "range-read"})
            for event in EVENTS
        ),
        "altitude-root mismatch was discovered only after interpreter progression",
    )


def test_stale_epoch_and_unavailable_range_fail_before_progression() -> None:
    EVENTS.clear()
    backend, _domain, _run, epoch, _transport, _color, _timing = make_backend()
    backend.takeoff(0.8)
    epoch["value"] = "epoch-reconnected"
    try:
        backend.readRange("front")
    except DynamicPhysicalBackendError as exc:
        require("epoch" in str(exc), "stale epoch failed for wrong reason")
    else:
        raise AssertionError("stale epoch reached a fresh range result")
    require(("range-open", "front") not in EVENTS, "stale epoch opened a range observer")

    EVENTS.clear()
    backend, _domain, _run, _epoch, _transport, _color, _timing = make_backend(fail_read=True)
    backend.takeoff(0.8)
    try:
        backend.readRange("front")
    except DynamicPhysicalBackendError:
        pass
    else:
        raise AssertionError("unavailable range was converted into interpreter data")
    require(("range-close", "front") in EVENTS, "failed fresh range read leaked its observer")


def test_observer_teardown_uncertainty_and_action_rejection_fail_closed() -> None:
    EVENTS.clear()
    backend, _domain, _run, _epoch, transport, _color, _timing = make_backend(fail_close=True)
    backend.takeoff(0.8)
    try:
        backend.readRange("front")
    except DynamicPhysicalBackendError as exc:
        require("teardown" in str(exc), "range teardown uncertainty failed for wrong reason")
    else:
        raise AssertionError("uncertain range observer teardown was accepted")

    EVENTS.clear()
    backend, _domain, _run, _epoch, transport, _color, _timing = make_backend()
    backend.takeoff(0.8)
    transport.reject_next = True
    try:
        backend.turn(45.0)
    except DynamicPhysicalBackendError as exc:
        require("positively acknowledged" in str(exc), "definitive action rejection failed for wrong reason")
    else:
        raise AssertionError("rejected physical action was treated as interpreter progress")


def test_no_caller_sensor_or_effect_surface_is_introduced() -> None:
    source = (PHYSICAL / "dynamic_physical_backend.py").read_text(encoding="utf-8")
    require("FreshRangeObserver" in source, "live range composition does not use integrated observer")
    require("observation_transaction" in source, "live range composition bypasses physical exclusion")
    require("assert_effect_binding" in source and "assert_current_program" in source, "live range provenance chain is incomplete")
    for forbidden in ("socket.", "http.server", "serve_forever", "send_packet(", "caller_direction", "caller_value"):
        require(forbidden not in source, "dynamic backend exposed a caller/effect bypass: " + forbidden)


def main() -> int:
    test_real_shared_interpreter_drives_fresh_range_and_existing_consumers()
    test_range_observation_is_exclusion_held_and_reasserted_around_sample()
    test_takeoff_is_verification_only_and_cannot_repeat()
    test_initial_altitude_has_no_auxiliary_authority_root()
    test_stale_epoch_and_unavailable_range_fail_before_progression()
    test_observer_teardown_uncertainty_and_action_rejection_fail_closed()
    test_no_caller_sensor_or_effect_surface_is_introduced()
    print(
        "PASS dynamic physical backend: canonical shared-interpreter demand -> exclusion-held fresh "
        "range data -> existing trusted action consumers, with preflight-derived single altitude root"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

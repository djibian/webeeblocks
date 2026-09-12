#!/usr/bin/env python3
from __future__ import annotations

from contextlib import contextmanager
from math import isclose
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / "tools" / "ci"
PHYSICAL = ROOT / "tools" / "physical"
for directory in (CI, PHYSICAL):
    text = str(directory)
    if text not in sys.path:
        sys.path.insert(0, text)

import dynamic_physical_backend as backend_module  # noqa: E402
import dynamic_run_activation as activation  # noqa: E402
import physical_dynamic_preflight  # noqa: E402
import physical_run_dispatch as dispatch  # noqa: E402
import takeoff_command  # noqa: E402
import test_physical_host_activation as base  # noqa: E402
import test_physical_host_inflight_sequence as host  # noqa: E402


RANGE_VALUE = 0.4
RANGE_FAIL = False


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


def dynamic_ast() -> str:
    variable = {"id": "front-distance", "name": "distance"}
    return canonical(
        [
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
                "then": [
                    {"direction": "left", "distance_m": 0.2, "kind": "move"}
                ],
            },
            {"direction": "up", "distance_m": 0.2, "kind": "vertical"},
            {"kind": "land"},
        ]
    )


def language_invalid_ast() -> str:
    target = {"id": "target", "name": "target"}
    missing = {"id": "missing", "name": "missing"}
    return canonical(
        [
            {"height_m": 0.8, "kind": "takeoff"},
            {
                "kind": "set_variable",
                "value": {"kind": "variable_get", "variable": missing},
                "variable": target,
            },
            {"kind": "land"},
        ]
    )


def flat_ast() -> str:
    return canonical(
        [
            {"height_m": 0.8, "kind": "takeoff"},
            {"kind": "land"},
        ]
    )


class FakeDynamicTransport:
    def __init__(
        self,
        *,
        crazyflie: object,
        execution_domain: object,
        acknowledgement_domain: object,
        safelink_guard: object,
        teacher_authorization: object,
        powered_session: object,
        watchdog_guard: object,
        supervisor_reader: object,
        connection_epoch_reader=None,
    ) -> None:
        del acknowledgement_domain, safelink_guard, supervisor_reader
        require(powered_session.session is crazyflie, "dynamic transport exact powered session")
        require(
            execution_domain.phase == base.physical_execution_domain.FLYING,
            "dynamic transport requires completed causal takeoff",
        )
        if connection_epoch_reader is not None:
            require(
                connection_epoch_reader() == powered_session.connection_epoch,
                "dynamic transport binds exact active epoch",
            )
        self.teacher_binding = teacher_authorization.binding
        self.bound_connection_epoch = powered_session.connection_epoch
        self.execution_domain = execution_domain
        self._crazyflie = crazyflie
        self._watchdog = watchdog_guard
        safety = physical_dynamic_preflight.validate_bound_dynamic_program(
            self.teacher_binding.ast_binding
        )
        self.initial_nominal_altitude_m = safety.initial_altitude_m
        self.nominal_altitude_m = safety.initial_altitude_m

    def _read_current_binding(self):
        raise AssertionError("dynamic activation must provide host-local current-program binding")

    def _binding(self):
        require(self._watchdog.active, "dynamic effect requires live watchdog")
        binding = self._read_current_binding()
        require(binding == self.teacher_binding, "dynamic effect lost exact teacher binding")
        return binding

    def send_horizontal_move(self, *, direction, distance_m, yaw_reader, timing_policy):
        del timing_policy
        binding = self._binding()
        require(yaw_reader is not None and yaw_reader.is_open, "dynamic move requires fresh yaw")
        require(yaw_reader.bound_crazyflie is self._crazyflie, "dynamic yaw exact Crazyflie")
        base.EVENTS.append(
            ("dynamic-move", direction, distance_m, binding.connection_epoch)
        )
        return SimpleNamespace(accepted=True, status=0)

    def send_vertical_move(self, *, direction, distance_m, timing_policy):
        del timing_policy
        binding = self._binding()
        delta = float(distance_m) if direction == "up" else -float(distance_m)
        self.nominal_altitude_m += delta
        base.EVENTS.append(
            (
                "dynamic-vertical",
                direction,
                distance_m,
                self.nominal_altitude_m,
                binding.connection_epoch,
            )
        )
        return SimpleNamespace(accepted=True, status=0)

    def send_turn(self, *, angle_deg, timing_policy):
        del timing_policy
        binding = self._binding()
        base.EVENTS.append(("dynamic-turn", angle_deg, binding.connection_epoch))
        return SimpleNamespace(accepted=True, status=0)

    def send_controlled_landing(self):
        binding = self._binding()
        require(
            self.execution_domain.phase == base.physical_execution_domain.FLYING,
            "dynamic landing starts from flying",
        )
        base.EVENTS.append(
            ("dynamic-land", self.nominal_altitude_m, binding.connection_epoch)
        )
        self.execution_domain.phase = base.physical_execution_domain.INACTIVE
        return SimpleNamespace(accepted=True, status=0)


class FakeColorTransport:
    def __init__(
        self,
        *,
        crazyflie: object,
        execution_domain: object,
        safelink_guard: object,
        teacher_authorization: object,
        powered_session: object,
        watchdog_guard: object,
        connection_epoch_reader=None,
    ) -> None:
        del crazyflie, execution_domain, safelink_guard
        self.teacher_binding = teacher_authorization.binding
        self.bound_connection_epoch = powered_session.connection_epoch
        self._watchdog = watchdog_guard
        if connection_epoch_reader is not None:
            require(
                connection_epoch_reader() == self.bound_connection_epoch,
                "dynamic color transport binds exact active epoch",
            )

    def _read_current_binding(self):
        raise AssertionError("dynamic activation must provide host-local color binding")

    def send_color(self, *, color: str):
        require(self._watchdog.active, "dynamic light requires live watchdog")
        binding = self._read_current_binding()
        require(binding == self.teacher_binding, "dynamic light lost exact teacher binding")
        base.EVENTS.append(("dynamic-light", color, binding.connection_epoch))
        return SimpleNamespace(accepted=True, status=0)


class FakeRangeObserver:
    def __init__(self, crazyflie: object, epoch_reader, direction: str) -> None:
        self.bound_crazyflie = crazyflie
        self._epoch_reader = epoch_reader
        self.bound_connection_epoch = None
        self.direction = direction
        self.is_open = False

    def open(self) -> None:
        self.bound_connection_epoch = self._epoch_reader()
        self.is_open = True
        base.EVENTS.append(("dynamic-range-open", self.direction))

    def read(self):
        base.EVENTS.append(("dynamic-range-read", self.direction))
        if RANGE_FAIL:
            raise RuntimeError("injected fresh range failure")
        return SimpleNamespace(
            connection_epoch=self.bound_connection_epoch,
            direction=self.direction,
            range_m=RANGE_VALUE,
        )

    def close(self) -> None:
        if self.is_open:
            base.EVENTS.append(("dynamic-range-close", self.direction))
        self.is_open = False


class FakeYawObserver:
    def __init__(self, crazyflie: object, epoch_reader) -> None:
        self.bound_crazyflie = crazyflie
        self.bound_connection_epoch = epoch_reader()
        self.is_open = False

    def open(self) -> None:
        self.is_open = True
        base.EVENTS.append(("dynamic-yaw-open", self.bound_connection_epoch))

    def close(self) -> None:
        if self.is_open:
            base.EVENTS.append(("dynamic-yaw-close", self.bound_connection_epoch))
        self.is_open = False


def install_dynamic_fakes() -> None:
    host.install_fakes()

    @contextmanager
    def observation_transaction(self, *checks):
        base.EVENTS.append("dynamic-observation-enter")
        require(
            self.phase == base.physical_execution_domain.FLYING,
            "dynamic observation requires flying",
        )
        for check in checks:
            check()
        try:
            yield object()
        finally:
            base.EVENTS.append("dynamic-observation-exit")

    base.FakeExecutionDomain.observation_transaction = observation_transaction

    activation.TrustedPoweredSessionFactory = base.FakePoweredFactory
    activation.PostResetTeacherDecisionChannel = base.FakeTeacherChannel
    activation.TrustedTeacherAuthorizer = base.FakeAuthorizer
    activation.FreshSupervisorStateReader = base.FakeSupervisorReader
    activation.TrustedTakeoffTransport = base.FakeTransportBase
    activation.PhysicalExecutionDomain = base.FakeExecutionDomain
    activation.make_cflib_stm_deck_power_cycle = (
        lambda _uri: lambda: base.EVENTS.append("power-cycle")
    )
    activation.TrustedDynamicControlledLandingTransport = FakeDynamicTransport
    activation.TrustedBottomColorLedTransport = FakeColorTransport

    backend_module.FreshRangeObserver = FakeRangeObserver
    backend_module.FreshYawObserver = FakeYawObserver


def test_dispatch_preserves_static_path_and_routes_only_dynamic_ast() -> None:
    original_static = dispatch.activate_validated_static_run
    original_dynamic = dispatch.activate_validated_dynamic_run
    calls: list[str] = []

    def static(**_kwargs):
        calls.append("static")
        return "static"

    def dynamic(**_kwargs):
        calls.append("dynamic")
        return "dynamic"

    dispatch.activate_validated_static_run = static
    dispatch.activate_validated_dynamic_run = dynamic
    try:
        result = dispatch.activate_validated_run(
            staged_binding=SimpleNamespace(ast_binding=flat_ast())
        )
        require(result == "static" and calls == ["static"], "flat exact program left static path")
        calls.clear()
        result = dispatch.activate_validated_run(
            staged_binding=SimpleNamespace(ast_binding=dynamic_ast())
        )
        require(
            result == "dynamic" and calls == ["dynamic"],
            "dynamic exact program did not use shared-interpreter path",
        )
    finally:
        dispatch.activate_validated_static_run = original_static
        dispatch.activate_validated_dynamic_run = original_dynamic


def test_production_host_runs_one_dynamic_program_from_fresh_range() -> None:
    global RANGE_FAIL, RANGE_VALUE
    RANGE_FAIL = False
    RANGE_VALUE = 0.4
    base.EVENTS.clear()
    install_dynamic_fakes()

    replies = host.run_host_sequence(dynamic_ast(), steps=1)
    require(replies[0]["ok"] is True, "dynamic run context validation failed")
    require(replies[1]["ok"] is False, "caller semantic substitution was accepted")
    require(
        replies[2] == {
            "executionAuthority": False,
            "ok": True,
            "requestId": "step-1",
        },
        "parameter-free dynamic execution did not complete",
    )

    require(
        base.EVENTS.count(("transport-send", "epoch-after")) == 1,
        "dynamic program did not preserve exactly one causal takeoff",
    )
    require(
        base.EVENTS.count(("dynamic-range-read", "front")) == 1,
        "exact interpreter demand did not produce one fresh front range",
    )
    require(
        "dynamic-observation-enter" in base.EVENTS
        and "dynamic-observation-exit" in base.EVENTS,
        "fresh range did not stay inside physical observation exclusion",
    )
    require(
        ("dynamic-move", "left", 0.2, "epoch-after") in base.EVENTS,
        "range-selected branch did not reach trusted motion consumer",
    )
    require(
        not any(
            isinstance(event, tuple) and event and event[0] == "dynamic-turn"
            for event in base.EVENTS
        ),
        "non-selected dynamic branch emitted an action",
    )
    vertical = [
        event
        for event in base.EVENTS
        if isinstance(event, tuple) and event and event[0] == "dynamic-vertical"
    ]
    require(len(vertical) == 1, "dynamic vertical path did not complete exactly once")
    require(
        vertical[0][1:3] == ("up", 0.2)
        and isclose(vertical[0][3], 1.0, abs_tol=1e-9),
        "accepted selected vertical effect did not advance runtime nominal altitude",
    )
    require(
        any(
            isinstance(event, tuple)
            and event[0] == "dynamic-land"
            and isclose(event[1], 1.0, abs_tol=1e-9)
            and event[2] == "epoch-after"
            for event in base.EVENTS
        ),
        "terminal dynamic landing did not derive from completed selected path",
    )
    require(
        not any(
            isinstance(event, tuple)
            and event
            and event[0] in {"inflight-move", "inflight-turn", "inflight-vertical", "terminal-land"}
            for event in base.EVENTS
        ),
        "dynamic program retained the flat PhysicalProgramSequence effect cursor",
    )
    require(
        base.EVENTS.count(("current-program", "epoch-after")) >= 4,
        "dynamic range/effects did not repeatedly re-establish current-program provenance",
    )
    require(("dynamic-yaw-close", "epoch-after") in base.EVENTS, "dynamic yaw observer leaked")


def test_post_takeoff_range_failure_enters_terminal_recovery() -> None:
    global RANGE_FAIL, RANGE_VALUE
    RANGE_FAIL = True
    RANGE_VALUE = 0.4
    base.EVENTS.clear()
    install_dynamic_fakes()
    try:
        replies = host.run_host_sequence(dynamic_ast(), steps=2)
    finally:
        RANGE_FAIL = False

    require(replies[2]["ok"] is False, "post-takeoff range failure was accepted")
    require(replies[3]["ok"] is False, "terminal dynamic failure allowed later execution")
    require(
        base.EVENTS.count(("transport-send", "epoch-after")) == 1,
        "failure path changed the one causal takeoff boundary",
    )
    require(("dynamic-range-close", "front") in base.EVENTS, "failed range observer leaked")
    require("watchdog-stop" in base.EVENTS, "dynamic failure did not enter terminal watchdog recovery")
    require(
        any(
            isinstance(event, tuple) and event and event[0] == "teacher-close"
            for event in base.EVENTS
        ),
        "dynamic failure did not close exact teacher authority",
    )
    require(
        not any(
            isinstance(event, tuple)
            and event
            and event[0] in {"dynamic-move", "dynamic-turn", "dynamic-vertical", "dynamic-land"}
            for event in base.EVENTS
        ),
        "failed fresh range advanced into a later physical action",
    )


def test_shared_language_invalidity_fails_before_reset_or_takeoff() -> None:
    global RANGE_FAIL
    RANGE_FAIL = False
    base.EVENTS.clear()
    install_dynamic_fakes()
    replies = host.run_host_sequence(language_invalid_ast(), steps=1)

    require(replies[0]["ok"] is True, "run-context bridge should remain diagnostic")
    require(replies[2]["ok"] is False, "language-invalid program acquired execution")
    require(
        not any(
            isinstance(event, tuple) and event and event[0] == "bridge-begin"
            for event in base.EVENTS
        ),
        "shared-language invalidity was discovered only after reset cutover",
    )
    require("power-cycle" not in base.EVENTS, "language-invalid program reached reset effect")
    require(
        ("transport-send", "epoch-after") not in base.EVENTS,
        "language-invalid program reached causal takeoff",
    )


def main() -> int:
    test_dispatch_preserves_static_path_and_routes_only_dynamic_ast()
    test_production_host_runs_one_dynamic_program_from_fresh_range()
    test_post_takeoff_range_failure_enters_terminal_recovery()
    test_shared_language_invalidity_fails_before_reset_or_takeoff()
    print(
        "PASS production dynamic activation: static dispatch preserved, one causal takeoff, "
        "fresh range-driven shared control flow, runtime landing and terminal recovery"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import ast
import inspect
from math import pi
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
CI = ROOT / "tools" / "ci"
sys.path.insert(0, str(PHYSICAL))
sys.path.insert(0, str(CI))

import high_level_timing as timing  # noqa: E402
import serve_reference_capabilities as capability_bridge  # noqa: E402
import setpoint_hl_transport as transport  # noqa: E402
import yaw_observer as yaw  # noqa: E402
import test_physical_setpoint_hl_transport as existing  # noqa: E402

HOST = PHYSICAL / "serve_physical_host.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class HostSession:
    def __init__(self, epoch_reader) -> None:
        self._epoch_reader = epoch_reader

    def read_connection_epoch(self) -> str:
        return self._epoch_reader()


def production_activation(bridge, session):
    """Execute the exact nested production composition definitions in a TCB fixture."""
    source = HOST.read_text(encoding="utf-8")
    tree = ast.parse(source)
    main_if = next(
        node
        for node in tree.body
        if isinstance(node, ast.If) and "__name__" in ast.unparse(node.test)
    )
    runner = next(
        node
        for node in main_if.body
        if isinstance(node, ast.FunctionDef) and node.name == "_run_physical_host"
    )
    wanted = {
        "_HostBoundSetpointHlTransport",
        "_compose_inflight_setpoint_transport",
        "_ActiveInflightRun",
        "_activate_inflight_run",
    }
    definitions = [
        node
        for node in runner.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in wanted
    ]
    require({node.name for node in definitions} == wanted, "production host activation path is incomplete")

    wrapper = ast.FunctionDef(
        name="_build_production_activation",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="bridge"), ast.arg(arg="session")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=definitions + [ast.Return(value=ast.Name(id="_activate_inflight_run", ctx=ast.Load()))],
        decorator_list=[],
    )
    module = ast.Module(body=[wrapper], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {
        "CurrentProgramPreflightEvidence": capability_bridge.CurrentProgramPreflightEvidence,
        "FreshYawObserver": yaw.FreshYawObserver,
        "HighLevelTimingPolicy": timing.HighLevelTimingPolicy,
        "SetpointHlTransportError": transport.SetpointHlTransportError,
        "TrustedSetpointHlTransport": transport.TrustedSetpointHlTransport,
        "assertion_timeout_seconds": 0.25,
    }
    exec(compile(module, str(HOST), "exec"), namespace)
    return namespace["_build_production_activation"](bridge, session)


def open_test_yaw(cf, epoch_reader):
    observer = yaw.FreshYawObserver(cf, epoch_reader)
    observer._bound_connection_epoch = epoch_reader()
    observer._opened = True
    observer._config = object()
    observer.read = lambda *, timeout_seconds=0.5: yaw.YawObservation(
        epoch_reader(), 10, 90.0, pi / 2
    )
    return observer


def activation_kwargs(fixture, observer, policy):
    return {
        **fixture.kwargs,
        "yaw_reader": observer,
        "timing_policy": policy,
    }


def test_exact_production_host_path_reaches_one_bounded_effect() -> None:
    cf = existing.FakeCrazyflie(reply_status=0)
    fixture = existing.Fixture("production-host", cf)
    try:
        session = HostSession(fixture.epoch)
        activate = production_activation(fixture.bridge, session)
        signature = inspect.signature(activate)
        for forbidden in (
            "bridge",
            "current_program",
            "provenance",
            "responder",
            "reset",
            "decision",
        ):
            require(
                all(forbidden not in name for name in signature.parameters),
                "host activation must not accept caller-selectable authority/provenance",
            )

        observer = open_test_yaw(cf, fixture.epoch)
        policy = timing.HighLevelTimingPolicy()
        events: list[str] = []
        original_assert = fixture.bridge.assert_current_program
        original_send = cf.send_packet

        def record_assert(**kwargs):
            events.append("fresh-current-program")
            return original_assert(**kwargs)

        def record_send(*args, **kwargs):
            events.append("send")
            return original_send(*args, **kwargs)

        fixture.bridge.assert_current_program = record_assert
        cf.send_packet = record_send

        active_run = activate(**activation_kwargs(fixture, observer, policy))
        result = active_run.execute({"motion": "turn", "angleDeg": 30})
        require(result.accepted, "production host bounded turn must consume accepted SETPOINT_HL reply")
        require(len(cf.send_calls) == 1, "production host path emits exactly one packet")
        require(events.count("send") == 1, "production host path has exactly one physical effect")
        require(
            events.count("fresh-current-program") >= 2,
            "production host effect must perform fresh #249 assertions inside the effect transaction",
        )
        require(
            events.index("send") > max(i for i, event in enumerate(events) if event == "fresh-current-program"),
            "final fresh #249 assertion must precede the one physical effect",
        )
    finally:
        fixture.close()


def test_caller_semantics_cannot_supply_or_replace_authorities() -> None:
    cf = existing.FakeCrazyflie(reply_status=0)
    fixture = existing.Fixture("production-negative", cf)
    try:
        activate = production_activation(fixture.bridge, HostSession(fixture.epoch))
        observer = open_test_yaw(cf, fixture.epoch)
        policy = timing.HighLevelTimingPolicy()
        kwargs = activation_kwargs(fixture, observer, policy)

        forged = dict(kwargs)
        forged["teacher_authorization"] = object()
        try:
            activate(**forged)
        except transport.SetpointHlTransportError:
            pass
        else:
            raise AssertionError("fake run authority must not compose production effect transport")
        require(not cf.send_calls, "fake authority must fail before effect")

        active_run = activate(**kwargs)
        for request in (
            {"motion": "turn", "angleDeg": 20, "bridge": object()},
            {"motion": "turn", "angleDeg": 20, "teacherAuthorization": "caller"},
            {"motion": "raw", "bytes": "0000"},
        ):
            try:
                active_run.execute(request)
            except transport.SetpointHlTransportError:
                pass
            else:
                raise AssertionError("ordinary semantic request must not carry authority/raw effect data")
        require(not cf.send_calls, "caller authority/provenance substitution must never reach effect")
    finally:
        fixture.close()


def test_production_activation_is_lexical_only() -> None:
    source = HOST.read_text(encoding="utf-8")
    require("def _activate_inflight_run(" in source, "production host must own a run activation path")
    require("class _ActiveInflightRun:" in source, "production host must own bounded semantic dispatch")
    require(
        'if request.get("op") != "validate-run-context":' in source,
        "ordinary caller IPC remains limited to non-authority run validation",
    )
    require("bridge=" not in source.split("def _activate_inflight_run(", 1)[1].split("):", 1)[0],
            "host activation signature must not accept a bridge")


def main() -> int:
    test_exact_production_host_path_reaches_one_bounded_effect()
    test_caller_semantics_cannot_supply_or_replace_authorities()
    test_production_activation_is_lexical_only()
    print(
        "PASS production-shaped physical host composition: exact run-scoped authorities "
        "activate bounded semantics with host-owned fresh provenance and one no-retry effect"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

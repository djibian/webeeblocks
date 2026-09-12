#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
if str(PHYSICAL) not in sys.path:
    sys.path.insert(0, str(PHYSICAL))

import takeoff_command
from physical_dynamic_preflight import DynamicPhysicalPreflightError
import shared_interpreter_host as subject
from shared_interpreter_host import BoundSharedInterpreter, SharedInterpreterHostError


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def binding(ast: dict[str, object]) -> str:
    return takeoff_command._canonical_json(ast)


VARIABLE = {"id": "distance", "name": "distance-é"}


def representative_ast() -> dict[str, object]:
    return {
        "version": 1,
        "semantics": "webeeblocks-ast-v1",
        "program": [
            {"kind": "takeoff", "height_m": 0.8},
            {
                "kind": "set_variable",
                "variable": VARIABLE,
                "value": {"kind": "range", "direction": "front", "unit": "m"},
            },
            {
                "kind": "repeat",
                "count": 2,
                "body": [
                    {
                        "kind": "if",
                        "condition": {
                            "kind": "logic",
                            "op": "AND",
                            "left": {
                                "kind": "compare",
                                "op": "LT",
                                "left": {"kind": "variable_get", "variable": VARIABLE},
                                "right": {"kind": "number", "value": 1},
                            },
                            "right": {
                                "kind": "compare",
                                "op": "LT",
                                "left": {
                                    "kind": "range",
                                    "direction": "right",
                                    "unit": "m",
                                },
                                "right": {"kind": "number", "value": 0.5},
                            },
                        },
                        "then": [
                            {"kind": "move", "direction": "left", "distance_m": 0.2}
                        ],
                        "else": [{"kind": "turn", "angle_deg": 45}],
                    }
                ],
            },
            {
                "kind": "if",
                "condition": {
                    "kind": "logic",
                    "op": "OR",
                    "left": {
                        "kind": "compare",
                        "op": "EQ",
                        "left": {"kind": "number", "value": 1},
                        "right": {"kind": "number", "value": 1},
                    },
                    "right": {
                        "kind": "compare",
                        "op": "GT",
                        "left": {"kind": "range", "direction": "up", "unit": "m"},
                        "right": {"kind": "number", "value": 0},
                    },
                },
                "then": [{"kind": "set_light", "color": "green"}],
                "else": [],
            },
            {"kind": "land"},
        ],
    }


class FakeBackend:
    def __init__(self) -> None:
        self.trace: list[tuple[object, ...]] = []
        self.ranges = {"front": [0.8], "right": [0.3, 0.7], "up": [0.2]}

    def takeoff(self, height_m):
        self.trace.append(("takeoff", height_m))
        return {"authority": "must-not-cross"}

    def land(self):
        self.trace.append(("land",))
        return {"authority": "must-not-cross"}

    def move(self, direction, distance_m):
        self.trace.append(("move", direction, distance_m))
        return {"authority": "must-not-cross"}

    def vertical(self, direction, distance_m):
        self.trace.append(("vertical", direction, distance_m))
        return {"authority": "must-not-cross"}

    def turn(self, angle_deg):
        self.trace.append(("turn", angle_deg))
        return {"authority": "must-not-cross"}

    def wait(self, seconds):
        self.trace.append(("wait", seconds))
        return {"authority": "must-not-cross"}

    def setSpeed(self, speed_m_s):
        self.trace.append(("setSpeed", speed_m_s))
        return {"authority": "must-not-cross"}

    def setLight(self, color):
        self.trace.append(("setLight", color))
        return {"authority": "must-not-cross"}

    def readRange(self, direction):
        self.trace.append(("readRange", direction))
        return self.ranges[direction].pop(0)


def test_real_shared_interpreter_owns_control_flow_and_sensor_demand() -> None:
    backend = FakeBackend()
    exact = binding(representative_ast())
    host = BoundSharedInterpreter(exact, backend)
    require(host.safety_evidence.ast_binding == exact, "exact AST safety binding changed")
    result = host.run()
    require(
        backend.trace
        == [
            ("takeoff", 0.8),
            ("readRange", "front"),
            ("readRange", "right"),
            ("move", "left", 0.2),
            ("readRange", "right"),
            ("turn", 45.0),
            ("setLight", "green"),
            ("land",),
        ],
        f"shared interpreter emitted unexpected trace: {backend.trace!r}",
    )
    require(
        ("readRange", "up") not in backend.trace,
        "OR short-circuit manufactured a phantom sensor read",
    )
    require(
        result.variables == {"distance-é": 0.8},
        "shared interpreter variable environment or UTF-8 protocol changed",
    )
    try:
        host.run()
    except SharedInterpreterHostError as exc:
        require("one-shot" in str(exc), "interpreter reuse failed for wrong reason")
    else:
        raise AssertionError("bound shared interpreter reuse must fail closed")


def test_dynamic_safety_and_language_validation_precede_backend_use() -> None:
    unsafe = {
        "version": 1,
        "semantics": "webeeblocks-ast-v1",
        "program": [
            {"kind": "takeoff", "height_m": 1.4},
            {
                "kind": "if",
                "condition": {"kind": "range", "direction": "front", "unit": "m"},
                "then": [{"kind": "vertical", "direction": "up", "distance_m": 0.2}],
                "else": [],
            },
            {"kind": "land"},
        ],
    }
    backend = FakeBackend()
    try:
        BoundSharedInterpreter(binding(unsafe), backend)
    except DynamicPhysicalPreflightError as exc:
        require("nominal-altitude" in str(exc), "unsafe path failed for wrong reason")
    else:
        raise AssertionError("reachable unsafe altitude must fail before interpreter start")
    require(backend.trace == [], "unsafe preflight emitted a backend call")

    invalid = representative_ast()
    invalid["program"][1] = {
        "kind": "set_variable",
        "variable": VARIABLE,
        "value": {"kind": "variable_get", "variable": VARIABLE},
    }
    backend = FakeBackend()
    try:
        BoundSharedInterpreter(binding(invalid), backend).run()
    except SharedInterpreterHostError as exc:
        require("failed closed" in str(exc), "JS validation failed for wrong reason")
    else:
        raise AssertionError("shared interpreter must reject read-before-assignment")
    require(backend.trace == [], "language validation must precede backend use")


def test_range_data_and_backend_failure_fail_closed() -> None:
    exact = binding(representative_ast())

    class BadRange(FakeBackend):
        def readRange(self, direction):
            self.trace.append(("readRange", direction))
            return float("nan")

    backend = BadRange()
    try:
        BoundSharedInterpreter(exact, backend).run()
    except SharedInterpreterHostError as exc:
        require("range result" in str(exc), "non-finite range failed for wrong reason")
    else:
        raise AssertionError("non-finite range must fail closed")
    require(
        backend.trace[:2] == [("takeoff", 0.8), ("readRange", "front")],
        "failure escaped exact interpreter demand",
    )


def _run_with_fake_worker(source: str, backend: FakeBackend, timeout: float = 0.5) -> str:
    original_worker = subject._WORKER
    original_timeout = subject._PROTOCOL_IDLE_TIMEOUT_SECONDS
    with tempfile.TemporaryDirectory() as temp:
        worker = Path(temp) / "worker.js"
        worker.write_text(source, encoding="utf-8")
        subject._WORKER = worker
        subject._PROTOCOL_IDLE_TIMEOUT_SECONDS = timeout
        try:
            BoundSharedInterpreter(binding(representative_ast()), backend).run()
        except SharedInterpreterHostError as exc:
            return str(exc)
        finally:
            subject._WORKER = original_worker
            subject._PROTOCOL_IDLE_TIMEOUT_SECONDS = original_timeout
    raise AssertionError("fake worker unexpectedly completed")


def test_private_protocol_rejects_substitution_and_silence() -> None:
    backend = FakeBackend()
    message = _run_with_fake_worker(
        """
'use strict';
const fs=require('fs');
const b=Buffer.alloc(65536); fs.readSync(0,b,0,b.length,null);
process.stdout.write(JSON.stringify({type:'call',id:1,method:'readRange',args:['down']})+'\\n');
setInterval(()=>{},1000);
""",
        backend,
    )
    require("range direction is unsupported" in message, "down substitution wrong failure")
    require(backend.trace == [], "rejected worker substitution reached backend")

    backend = FakeBackend()
    message = _run_with_fake_worker(
        """
'use strict';
const fs=require('fs');
const b=Buffer.alloc(65536); fs.readSync(0,b,0,b.length,null);
setInterval(()=>{},1000);
""",
        backend,
        timeout=0.2,
    )
    require("timed out" in message, "silent worker did not fail on protocol timeout")
    require(backend.trace == [], "silent worker reached backend")


def test_surface_contains_no_second_language_engine_or_caller_semantics() -> None:
    host_source = (PHYSICAL / "shared_interpreter_host.py").read_text(encoding="utf-8")
    worker_source = (PHYSICAL / "shared_interpreter_worker.js").read_text(encoding="utf-8")
    interpreter_source = (
        ROOT / "plugins/robot_windows/blockly/webeeblocks/interpreter.js"
    ).read_text(encoding="utf-8")
    require("interpreter.js" in worker_source, "worker does not load product interpreter")
    require("Interpreter.run(ast, backend)" in worker_source, "worker bypasses shared run()")
    for forbidden in ("case 'if'", "case 'repeat'", "statement.kind", "expression.kind"):
        require(forbidden not in worker_source, f"worker duplicates evaluator: {forbidden}")
    for forbidden in ("cflib", "send_packet", "setpoint", "commander"):
        require(forbidden not in host_source.lower(), f"adapter leaked physical authority: {forbidden}")
    for forbidden in ("--ast", "--direction", "--value", "--branch", "--iteration"):
        require(forbidden not in host_source + worker_source, f"caller semantic option: {forbidden}")
    require("module.exports = factory()" in interpreter_source, "shared interpreter lost CommonJS")
    require("requireMethod(backend,'readRange')" in interpreter_source, "range path changed")


def main() -> int:
    test_real_shared_interpreter_owns_control_flow_and_sensor_demand()
    test_dynamic_safety_and_language_validation_precede_backend_use()
    test_range_data_and_backend_failure_fail_closed()
    test_private_protocol_rejects_substitution_and_silence()
    test_surface_contains_no_second_language_engine_or_caller_semantics()
    print(
        "PASS exact teacher-bound AST executes through the existing shared Runtime interpreter "
        "with host-owned control flow/sensor demand and a fail-closed private backend protocol"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

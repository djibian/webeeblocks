#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
if str(PHYSICAL) not in sys.path:
    sys.path.insert(0, str(PHYSICAL))

import takeoff_command  # noqa: E402
from shared_interpreter_session import (  # noqa: E402
    SelectedPhysicalAction,
    SharedInterpreterSession,
    SharedInterpreterSessionError,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except SharedInterpreterSessionError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {str(exc)!r}")
        return
    raise AssertionError(f"expected SharedInterpreterSessionError containing {pattern!r}")


def canonical(program: list[dict[str, object]]) -> str:
    return takeoff_command._canonical_json(
        {"version": 1, "semantics": "webeeblocks-ast-v1", "program": program}
    )


def ref() -> dict[str, str]:
    return {"id": "v-range", "name": "distance"}


def number(value: float) -> dict[str, object]:
    return {"kind": "number", "value": value}


def program() -> list[dict[str, object]]:
    variable = ref()
    return [
        {"kind": "takeoff", "height_m": 0.8},
        {
            "kind": "set_variable",
            "variable": variable,
            "value": {"kind": "range", "direction": "front", "unit": "m"},
        },
        {
            "kind": "if",
            "condition": {
                "kind": "logic",
                "op": "AND",
                "left": {
                    "kind": "compare",
                    "op": "LT",
                    "left": {"kind": "variable_get", "variable": variable},
                    "right": number(1.0),
                },
                "right": {
                    "kind": "compare",
                    "op": "LT",
                    "left": {"kind": "range", "direction": "right", "unit": "m"},
                    "right": number(1.0),
                },
            },
            "then": [{"kind": "set_light", "color": "green"}],
            "else": [{"kind": "set_light", "color": "red"}],
        },
        {
            "kind": "repeat",
            "count": 2,
            "body": [{"kind": "move", "direction": "forward", "distance_m": 0.3}],
        },
        {"kind": "land"},
    ]


def consume(session: SharedInterpreterSession) -> list[SelectedPhysicalAction]:
    actions = [session.acknowledge_bound_takeoff()]
    while True:
        action = session.next_inflight_action()
        if action is None:
            break
        actions.append(action)
        session.acknowledge_action(action)
    return actions


def test_exact_bound_interpreter_selects_branch_and_repeat_path() -> None:
    reads: list[str] = []

    def read_range(direction: str) -> float:
        reads.append(direction)
        return {"front": 1.2, "right": 0.4}[direction]

    session = SharedInterpreterSession(canonical(program()), read_range)
    try:
        actions = consume(session)
        require(
            [action.kind for action in actions]
            == ["takeoff", "set_light", "move", "move", "land"],
            "shared interpreter selected wrong action sequence",
        )
        require(
            actions[1].statement == {"kind": "set_light", "color": "red"},
            "wrong branch selected",
        )
        require(reads == ["front"], "short-circuit evaluated a phantom right range read")
        require(session.completed, "interpreter did not complete after exact landing acknowledgement")
        require(session.variables == {"distance": 1.2}, "shared interpreter variable environment changed")
    finally:
        session.close()


def test_true_left_operand_evaluates_second_exact_range_expression() -> None:
    reads: list[str] = []

    def read_range(direction: str) -> float:
        reads.append(direction)
        return {"front": 0.5, "right": 0.4}[direction]

    session = SharedInterpreterSession(canonical(program()), read_range)
    try:
        actions = consume(session)
        require(
            actions[1].statement == {"kind": "set_light", "color": "green"},
            "then branch not selected",
        )
        require(reads == ["front", "right"], "exact interpreter range demand trace changed")
    finally:
        session.close()


def test_action_progression_requires_exact_opaque_claim_identity() -> None:
    session = SharedInterpreterSession(canonical(program()), lambda _direction: 1.2)
    try:
        session.acknowledge_bound_takeoff()
        action = session.next_inflight_action()
        require(action is not None and action.kind == "set_light", "expected selected light action")
        forged = SelectedPhysicalAction(
            path=action.path,
            kind=action.kind,
            statement=dict(action.statement),
        )
        expect_error(
            lambda: session.acknowledge_action(forged),
            "exact pending interpreter action claim",
        )
        require(
            session.next_inflight_action() is action,
            "failed forged acknowledgement advanced interpreter",
        )
        session.acknowledge_action(action)
    finally:
        session.close()


def test_worker_payload_cannot_substitute_bound_ast_action() -> None:
    binding = canonical(
        [
            {"kind": "takeoff", "height_m": 0.8},
            {"kind": "wait", "seconds": 0.1},
            {"kind": "land"},
        ]
    )
    with tempfile.TemporaryDirectory() as directory:
        worker = Path(directory) / "forged_worker.js"
        worker.write_text(
            "const readline=require('readline');"
            "const rl=readline.createInterface({input:process.stdin});"
            "rl.once('line',()=>{process.stdout.write(JSON.stringify({"
            "event:'action',id:1,path:['program',0],"
            "node:{height_m:0.8,kind:'takeoff'},kind:'move',direction:'forward',distance_m:0.3"
            "})+'\\n');});\n",
            encoding="utf-8",
        )
        session = SharedInterpreterSession(
            binding,
            lambda _direction: 0.5,
            worker_path=worker,
        )
        try:
            expect_error(session.acknowledge_bound_takeoff, "interpreter action differs")
            require(session.terminal, "forged worker event did not poison interpreter session")
        finally:
            session.close()


def test_worker_loss_fails_closed_without_fabricating_progress() -> None:
    session = SharedInterpreterSession(canonical(program()), lambda _direction: 1.2)
    try:
        session._process.kill()
        session._process.wait(timeout=1.0)
        expect_error(session.acknowledge_bound_takeoff, "exited before completion")
        require(session.terminal, "worker loss did not poison session")
    finally:
        session.close()


def test_local_surface_exposes_no_browser_or_physical_effect_api() -> None:
    source = (PHYSICAL / "shared_interpreter_session.py").read_text(encoding="utf-8")
    worker = (PHYSICAL / "shared_interpreter_worker.js").read_text(encoding="utf-8")
    for forbidden in (
        "send_packet(",
        "send_setpoint",
        "HighLevelCommander(",
        "Param.set_value",
        "http.server",
        "serve_forever",
        "socket.socket",
    ):
        require(forbidden not in source, f"session crossed authority/browser boundary: {forbidden}")
    require("interpreter.js" in worker, "worker does not load authoritative shared interpreter")
    require("readRange" in worker and "range" in source, "shared range demand bridge missing")


def main() -> int:
    test_exact_bound_interpreter_selects_branch_and_repeat_path()
    test_true_left_operand_evaluates_second_exact_range_expression()
    test_action_progression_requires_exact_opaque_claim_identity()
    test_worker_payload_cannot_substitute_bound_ast_action()
    test_worker_loss_fails_closed_without_fabricating_progress()
    test_local_surface_exposes_no_browser_or_physical_effect_api()
    print(
        "PASS trusted host-owned shared interpreter preserves exact range demand, "
        "short-circuit/control flow and opaque action selection without effects"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import socket
import sys
import threading
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(PHYSICAL))

import physical_program_sequence as sequence  # noqa: E402
import physical_run_activation as activation  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_host_module():
    spec = importlib.util.spec_from_file_location(
        "run_physical_host_test", PHYSICAL / "run_physical_host.py"
    )
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load physical host module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


host = load_host_module()
base = host.base
REAL_EXACT_WAIT = activation._execute_exact_wait


def canonical(program: list[dict[str, object]]) -> str:
    return json.dumps(
        {
            "program": program,
            "semantics": "webeeblocks-ast-v1",
            "version": 1,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def wait_ast(seconds: object = 0.12) -> str:
    return canonical(
        [
            {"kind": "takeoff", "height_m": 0.8},
            {"kind": "wait", "seconds": seconds},
            {"kind": "land"},
        ]
    )


def motion_ast() -> str:
    return canonical(
        [
            {"kind": "takeoff", "height_m": 0.8},
            {"kind": "move", "direction": "forward", "distance_m": 0.3},
            {"kind": "turn", "angle_deg": 45},
            {"kind": "land"},
        ]
    )


def send_line(sock: socket.socket, payload: object) -> None:
    sock.sendall((json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n").encode())


def read_line(stream) -> dict[str, object]:
    raw = stream.readline()
    if not raw:
        raise AssertionError("unexpected EOF from host")
    return json.loads(raw)


class FakeBridge:
    def __init__(self, binding: base.PhysicalRunBinding) -> None:
        self.binding = binding
        self.events: list[str] = []

    def assert_current_program(self, **kwargs):
        self.events.append("assert")
        require(kwargs["profile_id"] == self.binding.profile_id, "profile drift")
        require(kwargs["ast_binding"] == self.binding.ast_binding, "AST drift")
        require(kwargs["connection_epoch"] == self.binding.connection_epoch, "epoch drift")
        return base.CurrentProgramPreflightEvidence(
            profile_id=self.binding.profile_id,
            ast_binding=self.binding.ast_binding,
            connection_epoch=self.binding.connection_epoch,
            execution_authority=False,
            challenge_id="challenge",
        )

    def begin_post_reset_replacement(self, epoch: str) -> None:
        self.events.append("begin-replacement")

    def install_post_reset_session(self, session: object) -> str:
        self.events.append("install-replacement")
        self.binding = base.PhysicalRunBinding(
            profile_id=self.binding.profile_id,
            ast_binding=self.binding.ast_binding,
            connection_epoch=session.read_connection_epoch(),
        )
        return self.binding.connection_epoch


class FakeSession:
    def __init__(self, binding: base.PhysicalRunBinding) -> None:
        self.epoch = binding.connection_epoch
        self.opened = True
        self.events: list[str] = []
        self.cf = SimpleNamespace()
        self._scf = SimpleNamespace(is_link_open=lambda: self.opened, cf=self.cf)

    def read_connection_epoch(self) -> str:
        return self.epoch

    def read_capabilities(self):
        return SimpleNamespace()

    def close(self) -> None:
        self.events.append("close")
        self.opened = False

    def open(self) -> None:
        self.events.append("open")
        self.opened = True
        self.epoch = "epoch-post-reset"


class FakeExecutionDomain:
    pass


def make_binding(ast_binding: str) -> base.PhysicalRunBinding:
    return base.PhysicalRunBinding(
        profile_id="progression-1",
        ast_binding=ast_binding,
        connection_epoch="epoch-pre-reset",
    )


def production_host_roundtrip(ast_binding: str, *, steps: int) -> list[dict[str, object]]:
    binding = make_binding(ast_binding)
    bridge = FakeBridge(binding)
    session = FakeSession(binding)
    teacher_host, teacher_peer = socket.socketpair()
    caller_host, caller_peer = socket.socketpair()
    caller_stream = caller_peer.makefile("r", encoding="utf-8", newline="\n")
    outcome: dict[str, object] = {}

    class FakeActivatedController:
        def __init__(self) -> None:
            self.domain = sequence.PhysicalProgramSequence(ast_binding)
            self.closed = False

        def execute_next_inflight(self):
            kind = self.domain.next_step_kind
            if kind == "wait":
                claim = self.domain.reserve_next_wait()
                self.domain.complete_wait(claim)
                return activation._NoEffectStepResult()
            if kind in ("move", "turn"):
                claim = self.domain.reserve_next_motion()
                self.domain.complete_motion(claim)
                return SimpleNamespace(accepted=True, emitted=True)
            if kind == "land":
                claim = self.domain.reserve_terminal_landing()
                self.domain.complete_landing(claim)
                return SimpleNamespace(accepted=True, emitted=True)
            raise AssertionError("unexpected next kind " + repr(kind))

        def shutdown(self) -> None:
            self.closed = True

    activated = FakeActivatedController()

    def fake_activate_validated_run(**kwargs):
        require(kwargs["staged_binding"] == binding, "host must preserve staged exact binding")
        return activated

    original_activate = host.base.activate_validated_run
    host.base.activate_validated_run = fake_activate_validated_run
    try:
        worker = threading.Thread(
            target=lambda: outcome.setdefault(
                "value",
                host._serve_validated_run(
                    uri="radio://0/80/2M/E7E7E7E7E7",
                    validated_binding=binding,
                    bridge=bridge,
                    teacher_socket=teacher_host,
                    caller_socket=caller_host,
                    session=session,
                    execution_domain=SimpleNamespace(),
                ),
            ),
            daemon=True,
        )
        worker.start()
        replies: list[dict[str, object]] = []
        send_line(
            caller_peer,
            {
                "op": "activate-run",
                "profileId": "caller-forged-profile",
                "astBinding": canonical(
                    [
                        {"kind": "takeoff", "height_m": 1.5},
                        {"kind": "wait", "seconds": 5.0},
                        {"kind": "land"},
                    ]
                ),
                "connectionEpoch": "caller-forged-epoch",
                "direction": "left",
                "distanceM": 0.9,
                "seconds": 5.0,
            },
        )
        replies.append(read_line(caller_stream))

        for index in range(steps):
            send_line(
                caller_peer,
                {"op": "execute-next-inflight", "requestId": f"step-{index + 1}"},
            )
            replies.append(read_line(caller_stream))

        caller_peer.shutdown(socket.SHUT_WR)
        worker.join(timeout=3.0)
        require(not worker.is_alive(), "actual production host must terminate after caller EOF")
        require("error" not in outcome, "production host failed: " + repr(outcome.get("error")))
        require(activated.closed, "production host must close activated controller on EOF")
    finally:
        host.base.activate_validated_run = original_activate
        caller_stream.close()
        caller_peer.close()
        teacher_peer.close()
        teacher_host.close()
        caller_host.close()
    return replies


def test_exact_wait_pacer_uses_monotonic_slices_and_no_effect_surface() -> None:
    class Clock:
        def __init__(self) -> None:
            self.value = 10.0
            self.sleeps: list[float] = []

        def __call__(self) -> float:
            return self.value

        def sleep(self, duration: float) -> None:
            self.sleeps.append(duration)
            self.value += duration

    class Guard:
        def __init__(self) -> None:
            self.assertions = 0

        def assert_live(self) -> None:
            self.assertions += 1

    clock = Clock()
    guard = Guard()
    REAL_EXACT_WAIT(
        0.12,
        guard,
        lambda: "epoch-wait",
        "epoch-wait",
        clock=clock,
        sleeper=clock.sleep,
    )
    require(clock.value >= 10.0 + 0.12, "wait cannot complete before its monotonic deadline")
    require(all(0 < value <= 0.05 for value in clock.sleeps), "wait checks liveness in bounded slices")
    require(guard.assertions >= 3, "watchdog liveness is checked throughout exact wait")

    epoch = {"value": "epoch-wait"}
    clock2 = Clock()

    def change_epoch(duration: float) -> None:
        clock2.sleep(duration)
        epoch["value"] = "epoch-changed"

    try:
        REAL_EXACT_WAIT(
            0.12,
            Guard(),
            lambda: epoch["value"],
            "epoch-wait",
            clock=clock2,
            sleeper=change_epoch,
        )
    except base.activation.PhysicalRunActivationError as exc:
        require("epoch changed" in str(exc), "epoch loss must fail exact wait closed")
    else:
        raise AssertionError("exact wait survived connection-epoch change")

    source = (PHYSICAL / "physical_run_activation.py").read_text(encoding="utf-8")
    helper = source[source.index("def _execute_exact_wait("):source.index("def _live_crazyflie(")]
    for forbidden in (
        "send_packet(",
        "HighLevelCommander(",
        "send_setpoint",
        "send_extpos",
        "acknowledgement",
        "reserve_effect",
    ):
        require(forbidden not in helper, "wait helper leaked physical effect surface: " + forbidden)


def test_wait_failure_does_not_advance_exact_sequence() -> None:
    domain = sequence.PhysicalProgramSequence(wait_ast())
    claim = domain.reserve_next_wait()
    domain.fail_wait(claim, "trusted wait interrupted")
    require(domain.terminal, "failed trusted wait must make exact sequence terminal")
    require(domain.next_index == 1, "failed wait cannot skip into terminal landing")
    require(not domain.completed, "failed wait cannot manufacture program completion")


def test_actual_host_accepts_no_caller_wait_semantics() -> None:
    source = (PHYSICAL / "run_physical_host.py").read_text(encoding="utf-8")
    require('operation == "execute-next-inflight"' in source, "host must expose one parameter-free next-step operation")
    require('set(message) != {"op", "requestId"}' in source, "host must reject caller-selected next-step semantics")
    for forbidden in ("waitSeconds", "wait_seconds", "durationSeconds"):
        require(forbidden not in source, "caller-selected wait semantic entered production host: " + forbidden)


def test_actual_production_host_wait_composition() -> None:
    replies = production_host_roundtrip(wait_ast(0.4), steps=2)
    require(replies[0]["status"] == "activated", "host must activate exact teacher-bound run")
    require(replies[1] == {"emitted": False, "ok": True, "requestId": "step-1"}, "wait must report no emitted effect")
    require(replies[2] == {"emitted": True, "ok": True, "requestId": "step-2"}, "terminal land remains the next exact emitted effect")


def test_existing_motion_and_landing_composition_remain_emitted() -> None:
    replies = production_host_roundtrip(motion_ast(), steps=3)
    require(replies[1]["emitted"] is True, "move remains an emitted effect")
    require(replies[2]["emitted"] is True, "turn remains an emitted effect")
    require(replies[3]["emitted"] is True, "terminal landing remains an emitted effect")


def test_activated_run_dispatches_wait_without_effect_transport() -> None:
    source = (PHYSICAL / "physical_run_activation.py").read_text(encoding="utf-8")
    require('if next_kind == "wait":' in source, "activated run must dispatch exact wait distinctly")
    require("sequence.reserve_next_wait()" in source, "wait must derive claim from exact sequence")
    require("sequence.complete_wait(claim)" in source, "full wait completion must advance exact sequence")
    require("sequence.fail_wait(claim" in source, "interrupted wait must terminalize exact sequence")
    require("return _NoEffectStepResult()" in source, "wait must return explicit no-effect marker")


def main() -> int:
    test_exact_wait_pacer_uses_monotonic_slices_and_no_effect_surface()
    test_wait_failure_does_not_advance_exact_sequence()
    test_actual_host_accepts_no_caller_wait_semantics()
    test_actual_production_host_wait_composition()
    test_existing_motion_and_landing_composition_remain_emitted()
    test_activated_run_dispatches_wait_without_effect_transport()
    print(
        "PASS actual physical-host exact-program in-flight composition preserves no-effect wait pacing, "
        "watchdog/epoch liveness, caller non-authority, and existing emitted move/turn/land semantics"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

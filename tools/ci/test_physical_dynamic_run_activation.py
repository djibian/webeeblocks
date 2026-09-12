#!/usr/bin/env python3
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import runpy
import socket
import sys
from types import SimpleNamespace
from threading import Thread

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / "tools" / "ci"
PHYSICAL = ROOT / "tools" / "physical"
for directory in (CI, PHYSICAL):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

HOST = PHYSICAL / "serve_physical_host.py"

import dynamic_physical_backend  # noqa: E402
import dynamic_run_activation  # noqa: E402
import physical_execution_domain  # noqa: E402
import test_physical_host_activation as base  # noqa: E402


RANGE_STATE = {"value": 0.4, "fail": False}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def canonical(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def dynamic_ast() -> str:
    return canonical(
        {
            "program": [
                {"height_m": 0.8, "kind": "takeoff"},
                {
                    "condition": {
                        "kind": "compare",
                        "left": {"direction": "front", "kind": "range", "unit": "m"},
                        "op": "LT",
                        "right": {"kind": "number", "value": 1.0},
                    },
                    "else": [{"color": "red", "kind": "set_light"}],
                    "kind": "if",
                    "then": [{"color": "green", "kind": "set_light"}],
                },
                {"kind": "land"},
            ],
            "semantics": "webeeblocks-ast-v1",
            "version": 1,
        }
    )


def unsupported_language_ast() -> str:
    return canonical(
        {
            "program": [
                {"height_m": 0.8, "kind": "takeoff"},
                {
                    "condition": {
                        "kind": "compare",
                        "left": {
                            "kind": "arithmetic",
                            "left": {"kind": "number", "value": 2.0},
                            "op": "POWER",
                            "right": {"kind": "number", "value": 3.0},
                        },
                        "op": "GT",
                        "right": {"kind": "number", "value": 1.0},
                    },
                    "else": [{"kind": "wait", "seconds": 0.1}],
                    "kind": "if",
                    "then": [{"kind": "wait", "seconds": 0.1}],
                },
                {"kind": "land"},
            ],
            "semantics": "webeeblocks-ast-v1",
            "version": 1,
        }
    )


class DynamicFakeExecutionDomain(base.FakeExecutionDomain):
    def observation_transaction(self, *checks):
        @contextmanager
        def transaction():
            require(
                self.phase == physical_execution_domain.FLYING,
                "dynamic observation must start from flying",
            )
            base.EVENTS.append("dynamic-observation-enter")
            for check in checks:
                check()
            try:
                yield object()
            finally:
                require(
                    self.phase == physical_execution_domain.FLYING,
                    "dynamic observation changed physical phase",
                )
                base.EVENTS.append("dynamic-observation-exit")

        return transaction()


class FakeDynamicInflightTransport:
    def __init__(self, **kwargs) -> None:
        self.execution_domain = kwargs["execution_domain"]
        self.teacher_binding = kwargs["teacher_authorization"].binding
        self.bound_connection_epoch = kwargs["powered_session"].connection_epoch
        self._watchdog = kwargs["watchdog_guard"]
        self._epoch_reader = kwargs["connection_epoch_reader"]
        ast = json.loads(self.teacher_binding.ast_binding)
        self.initial_nominal_altitude_m = float(ast["program"][0]["height_m"])

    def _read_current_binding(self):
        raise AssertionError("dynamic host adapter must override current-program binding")

    def send_horizontal_move(self, **_kwargs):
        raise AssertionError("non-selected dynamic move reached transport")

    def send_vertical_move(self, **_kwargs):
        raise AssertionError("non-selected dynamic vertical move reached transport")

    def send_turn(self, **_kwargs):
        raise AssertionError("non-selected dynamic turn reached transport")

    def send_controlled_landing(self):
        require(self._watchdog.active, "watchdog must remain live through dynamic landing")
        require(
            self._epoch_reader() == self.bound_connection_epoch,
            "dynamic landing must stay on exact active epoch",
        )
        binding = self._read_current_binding()
        require(binding == self.teacher_binding, "dynamic landing lost exact teacher binding")
        require(
            self.execution_domain.phase == physical_execution_domain.FLYING,
            "dynamic landing must start from flying",
        )
        base.EVENTS.append(("dynamic-land", binding.connection_epoch))
        self.execution_domain.phase = physical_execution_domain.INACTIVE
        return base.FakeAckResult()


class FakeDynamicColorTransport:
    def __init__(self, **kwargs) -> None:
        self.teacher_binding = kwargs["teacher_authorization"].binding
        self.bound_connection_epoch = kwargs["powered_session"].connection_epoch
        self._watchdog = kwargs["watchdog_guard"]
        self._epoch_reader = kwargs["connection_epoch_reader"]

    def _read_current_binding(self):
        raise AssertionError("dynamic color host adapter must override current-program binding")

    def send_color(self, *, color: str):
        require(self._watchdog.active, "watchdog must remain live through dynamic color effect")
        require(
            self._epoch_reader() == self.bound_connection_epoch,
            "dynamic color effect must stay on exact active epoch",
        )
        binding = self._read_current_binding()
        require(binding == self.teacher_binding, "dynamic color effect lost exact teacher binding")
        base.EVENTS.append(("dynamic-light", color, binding.connection_epoch))
        return base.FakeAckResult()


class FakeRangeObserver:
    def __init__(self, crazyflie: object, epoch_reader, direction: str) -> None:
        self.bound_crazyflie = crazyflie
        self._epoch_reader = epoch_reader
        self.bound_connection_epoch = epoch_reader()
        self.direction = direction
        self._open = False

    def open(self) -> None:
        require(not self._open, "range observer is one-shot")
        self._open = True
        base.EVENTS.append(("dynamic-range-open", self.direction))

    def read(self):
        require(self._open, "range observer must be open")
        base.EVENTS.append(("dynamic-range-read", self.direction))
        if RANGE_STATE["fail"]:
            raise RuntimeError("synthetic fresh range failure")
        return SimpleNamespace(
            connection_epoch=self._epoch_reader(),
            direction=self.direction,
            range_m=float(RANGE_STATE["value"]),
        )

    def close(self) -> None:
        if self._open:
            base.EVENTS.append(("dynamic-range-close", self.direction))
        self._open = False


def install_dynamic_fakes() -> None:
    base.install_fakes()

    physical_execution_domain.PhysicalExecutionDomain = DynamicFakeExecutionDomain
    base.activation.PhysicalExecutionDomain = DynamicFakeExecutionDomain

    dynamic_run_activation.PhysicalExecutionDomain = DynamicFakeExecutionDomain
    dynamic_run_activation.TrustedPoweredSessionFactory = base.FakePoweredFactory
    dynamic_run_activation.PostResetTeacherDecisionChannel = base.FakeTeacherChannel
    dynamic_run_activation.TrustedTeacherAuthorizer = base.FakeAuthorizer
    dynamic_run_activation.FreshSupervisorStateReader = base.FakeSupervisorReader
    dynamic_run_activation.TrustedTakeoffTransport = base.FakeTransportBase
    dynamic_run_activation.TrustedDynamicControlledLandingTransport = (
        FakeDynamicInflightTransport
    )
    dynamic_run_activation.TrustedBottomColorLedTransport = FakeDynamicColorTransport
    dynamic_run_activation.make_cflib_stm_deck_power_cycle = (
        lambda _uri: lambda: base.EVENTS.append("power-cycle")
    )

    dynamic_physical_backend.FreshRangeObserver = FakeRangeObserver


def _send(sock: socket.socket, payload: dict[str, object]) -> None:
    sock.sendall(
        (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
    )


def _read(stream) -> dict[str, object]:
    line = stream.readline()
    require(bool(line), "physical host closed caller channel unexpectedly")
    value = json.loads(line)
    require(isinstance(value, dict), "caller response must be an object")
    return value


def run_dynamic_host(
    ast_binding: str,
    *,
    range_fail: bool = False,
    execute: bool = True,
) -> list[dict[str, object]]:
    base.ACTIVATION_COMPLETED.clear()
    RANGE_STATE["fail"] = range_fail

    caller_host, caller_peer = socket.socketpair()
    caller_stream = caller_peer.makefile("r", encoding="utf-8")
    browser_read, browser_write = os.pipe()
    teacher_host, teacher_peer = socket.socketpair()

    argv = [
        str(HOST),
        "--uri",
        "radio://0/80/2M/E7E7E7E7E7",
        "--caller-fd",
        str(caller_host.detach()),
        "--browser-config-fd",
        str(browser_write),
        "--teacher-fd",
        str(teacher_host.detach()),
    ]
    outcome: dict[str, object] = {}
    old_argv = sys.argv[:]

    def target() -> None:
        sys.argv = argv
        try:
            runpy.run_path(str(HOST), run_name="__main__")
        except Exception as exc:
            outcome["error"] = exc
        finally:
            sys.argv = old_argv

    worker = Thread(target=target, daemon=True)
    worker.start()

    with os.fdopen(browser_read, "r", encoding="utf-8") as stream:
        bootstrap = json.loads(stream.readline())
    require(bootstrap["executionAuthority"] is False, "browser bootstrap remains non-authority")

    _send(
        caller_peer,
        {
            "op": "validate-run-context",
            "requestId": "validate-dynamic",
            "profileId": "activity-dynamic",
            "astBinding": ast_binding,
            "connectionEpoch": "epoch-before",
        },
    )
    replies = [_read(caller_stream)]

    if execute:
        _send(
            caller_peer,
            {
                "op": "execute-next-inflight",
                "requestId": "substitute-dynamic",
                "direction": "right",
                "rangeM": 0.01,
                "branch": "else",
            },
        )
        replies.append(_read(caller_stream))

        _send(
            caller_peer,
            {"op": "execute-next-inflight", "requestId": "execute-dynamic"},
        )
        replies.append(_read(caller_stream))

    caller_peer.shutdown(socket.SHUT_WR)
    worker.join(timeout=5.0)
    require(not worker.is_alive(), "dynamic production host must terminate after caller EOF")
    require("error" not in outcome, "dynamic production host failed: " + repr(outcome.get("error")))

    caller_stream.close()
    caller_peer.close()
    teacher_peer.close()
    return replies


def test_dynamic_host_runs_range_branch_once_after_single_causal_takeoff() -> None:
    base.EVENTS.clear()
    install_dynamic_fakes()
    replies = run_dynamic_host(dynamic_ast())

    require(
        replies[0]
        == {
            "executionAuthority": False,
            "ok": True,
            "requestId": "validate-dynamic",
        },
        "dynamic validation must remain diagnostic",
    )
    require(
        replies[1]["ok"] is False and replies[1]["executionAuthority"] is False,
        "caller-selected dynamic semantics must be rejected",
    )
    require(
        replies[2]
        == {
            "executionAuthority": False,
            "ok": True,
            "requestId": "execute-dynamic",
        },
        "parameter-free dynamic execution did not complete",
    )

    require(
        base.EVENTS.count(("transport-send", "epoch-after")) == 1,
        "shared interpreter emitted or caused a second causal takeoff",
    )
    require(
        base.EVENTS.count(("dynamic-range-read", "front")) == 1,
        "bound interpreter did not issue exactly one fresh front range demand",
    )
    require(
        ("dynamic-light", "green", "epoch-after") in base.EVENTS,
        "range-driven selected branch did not reach trusted color consumer",
    )
    require(
        not any(
            isinstance(event, tuple)
            and event[:2] == ("dynamic-light", "red")
            for event in base.EVENTS
        ),
        "non-selected dynamic branch emitted an effect",
    )
    require(
        base.EVENTS.count(("dynamic-land", "epoch-after")) == 1,
        "dynamic terminal landing did not complete exactly once",
    )
    require(
        base.EVENTS.index(("dynamic-range-open", "front"))
        < base.EVENTS.index(("dynamic-range-read", "front"))
        < base.EVENTS.index(("dynamic-range-close", "front")),
        "fresh dynamic range observer lifecycle is not ordered",
    )


def test_post_takeoff_range_failure_enters_terminal_recovery() -> None:
    base.EVENTS.clear()
    install_dynamic_fakes()
    replies = run_dynamic_host(dynamic_ast(), range_fail=True)

    require(replies[2]["ok"] is False, "post-takeoff range failure was reported as success")
    require(
        replies[2]["executionAuthority"] is False,
        "post-takeoff failure minted caller execution authority",
    )
    require(
        base.EVENTS.count(("transport-send", "epoch-after")) == 1,
        "failure test did not establish exactly one causal takeoff",
    )
    require(
        ("dynamic-range-close", "front") in base.EVENTS,
        "failed fresh range observation leaked its observer",
    )
    require("watchdog-stop" in base.EVENTS, "post-takeoff failure did not enter terminal watchdog recovery")
    require(
        any(
            isinstance(event, tuple) and event[0] == "teacher-close"
            for event in base.EVENTS
        ),
        "post-takeoff failure did not close teacher run authority",
    )
    require(
        not any(
            isinstance(event, tuple) and event[0] in {"dynamic-light", "dynamic-land"}
            for event in base.EVENTS
        ),
        "execution continued after failed range observation",
    )


def test_unsupported_shared_language_fallback_remains_pre_effect() -> None:
    base.EVENTS.clear()
    install_dynamic_fakes()
    replies = run_dynamic_host(unsupported_language_ast())

    require(replies[2]["ok"] is False, "unsupported shared-language program was executed")
    require(
        not base.ACTIVATION_COMPLETED.is_set(),
        "unsupported language reached causal takeoff",
    )
    for forbidden in ("power-cycle", "watchdog-activate"):
        require(forbidden not in base.EVENTS, "unsupported language reached effect preparation")
    require(
        not any(
            isinstance(event, tuple)
            and event[0] in {"bridge-begin", "transport-send", "dynamic-range-open"}
            for event in base.EVENTS
        ),
        "unsupported language fallback crossed the pre-effect boundary",
    )


def main() -> int:
    test_dynamic_host_runs_range_branch_once_after_single_causal_takeoff()
    test_post_takeoff_range_failure_enters_terminal_recovery()
    test_unsupported_shared_language_fallback_remains_pre_effect()
    print(
        "PASS production dynamic physical host: pre-effect shared validation -> one causal "
        "takeoff -> interpreter-owned fresh range branch/effects/landing, with terminal recovery"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import socket
import sys
from threading import Thread
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / "tools" / "ci"
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(CI))
sys.path.insert(0, str(PHYSICAL))
HOST = PHYSICAL / "serve_physical_host.py"

import controlled_landing_transport  # noqa: E402
import setpoint_hl_transport  # noqa: E402
import test_physical_host_activation as base  # noqa: E402
import yaw_observer  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def canonical_ast(final_statement: dict[str, object] | None = None) -> str:
    final = {"kind": "land"} if final_statement is None else final_statement
    return json.dumps(
        {
            "program": [
                {"height_m": 0.8, "kind": "takeoff"},
                {"angle_deg": -25, "kind": "turn"},
                {"direction": "forward", "distance_m": 0.3, "kind": "move"},
                final,
            ],
            "semantics": "webeeblocks-ast-v1",
            "version": 1,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


class FakeYawObserver:
    def __init__(self, crazyflie: object, epoch_reader) -> None:
        self.bound_crazyflie = crazyflie
        self._epoch_reader = epoch_reader
        self.bound_connection_epoch = epoch_reader()
        self.is_open = False

    def open(self) -> None:
        require(self._epoch_reader() == self.bound_connection_epoch, "yaw opens on exact epoch")
        self.is_open = True
        base.EVENTS.append(("yaw-open", self.bound_connection_epoch))

    def close(self) -> None:
        if self.is_open:
            base.EVENTS.append(("yaw-close", self.bound_connection_epoch))
        self.is_open = False


class FakeInflightTransportBase:
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
    ) -> None:
        require(powered_session.session is crazyflie, "in-flight exact powered session")
        require(execution_domain.phase == base.physical_execution_domain.FLYING, "takeoff must complete first")
        self.teacher_binding = teacher_authorization.binding
        self.bound_connection_epoch = powered_session.connection_epoch
        self._crazyflie = crazyflie
        self._watchdog = watchdog_guard
        self._execution = execution_domain

    def _read_current_binding(self):
        raise AssertionError("host-local provenance override is required")

    def send_horizontal_move(self, *, direction, distance_m, yaw_reader, timing_policy):
        require(yaw_reader is not None and yaw_reader.is_open, "fresh yaw observer must be opened lazily for moves")
        require(yaw_reader.bound_crazyflie is self._crazyflie, "yaw exact Crazyflie")
        require(self._watchdog.active, "same-session watchdog remains live")
        binding = self._read_current_binding()
        require(binding == self.teacher_binding, "fresh #249 matches exact teacher run")
        base.EVENTS.append(("inflight-move", direction, distance_m, binding.connection_epoch))
        return SimpleNamespace(accepted=True, status=0)

    def send_turn(self, *, angle_deg, timing_policy):
        require(self._watchdog.active, "same-session watchdog remains live")
        binding = self._read_current_binding()
        require(binding == self.teacher_binding, "fresh #249 matches exact teacher run")
        base.EVENTS.append(("inflight-turn", angle_deg, binding.connection_epoch))
        return SimpleNamespace(accepted=True, status=0)


class FakeLandingTransportBase(FakeInflightTransportBase):
    def __init__(self, *, connection_epoch_reader, **kwargs) -> None:
        super().__init__(**kwargs)
        require(
            connection_epoch_reader() == self.bound_connection_epoch,
            "landing completion stays on exact active epoch",
        )

    def send_controlled_landing(self):
        require(self._watchdog.active, "same-session watchdog remains live through landing")
        binding = self._read_current_binding()
        require(binding == self.teacher_binding, "fresh #249 matches exact landing run")
        with self._execution.effect_transaction(lambda: None) as effect:
            effect.mark_emitted()
            permit = effect.mark_accepted()
        self._execution.complete_accepted_effect(
            permit,
            base.physical_execution_domain.INACTIVE,
            lambda: True,
        )
        base.EVENTS.append(("controlled-land", binding.connection_epoch))
        return SimpleNamespace(accepted=True, status=0)


def install_fakes() -> None:
    base.install_fakes()
    # ``physical_run_activation`` was imported by the reusable #293 fixture
    # before these substitutions, so patch its exact globals as well as the
    # modules future imports would see.
    base.activation.TrustedSetpointHlTransport = FakeInflightTransportBase
    base.activation.TrustedControlledLandingTransport = FakeLandingTransportBase
    base.activation.FreshYawObserver = FakeYawObserver
    setpoint_hl_transport.TrustedSetpointHlTransport = FakeInflightTransportBase
    controlled_landing_transport.TrustedControlledLandingTransport = FakeLandingTransportBase
    yaw_observer.FreshYawObserver = FakeYawObserver


def send_line(sock: socket.socket, payload: dict[str, object]) -> None:
    sock.sendall((json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8"))


def read_line(stream) -> dict[str, object]:
    line = stream.readline()
    require(bool(line), "physical host closed caller channel unexpectedly")
    value = json.loads(line)
    require(isinstance(value, dict), "caller response must be an object")
    return value


def run_host_sequence(ast_binding: str | None = None) -> list[dict[str, object]]:
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

    send_line(
        caller_peer,
        {
            "op": "validate-run-context",
            "requestId": "validate-1",
            "profileId": "activity-1",
            "astBinding": canonical_ast() if ast_binding is None else ast_binding,
            "connectionEpoch": "epoch-before",
        },
    )
    replies = [read_line(caller_stream)]

    # Caller-selected semantics are rejected before the exact-program operation.
    send_line(
        caller_peer,
        {
            "op": "execute-next-inflight",
            "requestId": "substitute-1",
            "direction": "right",
            "distanceM": 0.9,
        },
    )
    replies.append(read_line(caller_stream))

    send_line(caller_peer, {"op": "execute-next-inflight", "requestId": "step-1"})
    replies.append(read_line(caller_stream))
    send_line(caller_peer, {"op": "execute-next-inflight", "requestId": "step-2"})
    replies.append(read_line(caller_stream))

    # The same parameter-free operation owns the terminal landing. Caller-selected
    # height/velocity/landing semantics remain rejected before the exact claim.
    send_line(
        caller_peer,
        {
            "op": "execute-next-inflight",
            "requestId": "landing-substitute",
            "heightM": 0.1,
        },
    )
    replies.append(read_line(caller_stream))
    send_line(caller_peer, {"op": "execute-next-inflight", "requestId": "step-land"})
    replies.append(read_line(caller_stream))

    caller_peer.shutdown(socket.SHUT_WR)
    worker.join(timeout=3.0)
    require(not worker.is_alive(), "actual production host must terminate after caller EOF")
    require("error" not in outcome, "production host failed: " + repr(outcome.get("error")))

    caller_stream.close()
    caller_peer.close()
    teacher_peer.close()
    return replies


def test_started_activation_wait_is_outside_lifecycle_lock() -> None:
    """Keep the validate->execute handoff free of the scheduler race from #276."""
    source = HOST.read_text(encoding="utf-8")
    wait = 'if activation_state["started"]:\n                                    activation_complete.wait()'
    require(wait in source, "started activation must be awaited before in-flight availability is decided")
    wait_index = source.index(wait)
    lock_index = source.find("with lifecycle_lock:", wait_index)
    require(lock_index > wait_index, "activation wait must happen before reacquiring lifecycle lock")
    require(
        'finally:\n                    activation_complete.set()' in source,
        "every started activation path must release the host wait",
    )


def test_actual_host_uses_exact_program_sequence_through_landing() -> None:
    base.EVENTS.clear()
    install_fakes()
    replies = run_host_sequence()

    require(replies[0] == {"executionAuthority": False, "ok": True, "requestId": "validate-1"}, "validation stays diagnostic")
    require(replies[1]["ok"] is False, "caller-supplied motion fields must be rejected")
    require(replies[1]["executionAuthority"] is False, "rejected substitution mints no authority")
    require(replies[2] == {"executionAuthority": False, "ok": True, "requestId": "step-1"}, "exact next turn executes")
    require(replies[3] == {"executionAuthority": False, "ok": True, "requestId": "step-2"}, "exact next move executes")
    require(replies[4]["ok"] is False, "caller-selected landing fields must be rejected")
    require(replies[4]["executionAuthority"] is False, "landing substitution mints no authority")
    require(replies[5] == {"executionAuthority": False, "ok": True, "requestId": "step-land"}, "exact terminal landing executes")

    move_events = [event for event in base.EVENTS if isinstance(event, tuple) and event[0] == "inflight-move"]
    turn_events = [event for event in base.EVENTS if isinstance(event, tuple) and event[0] == "inflight-turn"]
    landing_events = [event for event in base.EVENTS if isinstance(event, tuple) and event[0] == "controlled-land"]
    require(
        turn_events == [("inflight-turn", -25.0, "epoch-after")],
        "caller substitution must not change the exact first authorized effect",
    )
    require(
        move_events == [("inflight-move", "forward", 0.3, "epoch-after")],
        "second in-flight effect must follow exact canonical AST order",
    )
    require(
        landing_events == [("controlled-land", "epoch-after")],
        "terminal landing must execute once on the exact same run/epoch",
    )

    takeoff_index = base.EVENTS.index(("transport-send", "epoch-after"))
    turn_index = base.EVENTS.index(turn_events[0])
    yaw_open_index = base.EVENTS.index(("yaw-open", "epoch-after"))
    move_index = base.EVENTS.index(move_events[0])
    landing_index = base.EVENTS.index(landing_events[0])
    require(
        takeoff_index < turn_index < yaw_open_index < move_index < landing_index,
        "exact AST order must remain takeoff -> turn -> move -> landing",
    )
    require(
        any(event == ("current-program", "epoch-after") for event in base.EVENTS[takeoff_index:turn_index]),
        "fresh host-local #278/#249 must guard the first in-flight effect",
    )
    require(
        any(event == ("current-program", "epoch-after") for event in base.EVENTS[move_index:landing_index]),
        "fresh host-local #278/#249 must guard the terminal landing",
    )
    require(("yaw-close", "epoch-after") in base.EVENTS, "host teardown closes #260 observer")


def test_actual_host_rejects_malformed_terminal_before_takeoff() -> None:
    base.EVENTS.clear()
    install_fakes()
    malformed = canonical_ast({"kind": "land", "extra": True})
    replies = run_host_sequence(malformed)

    require(replies[0] == {"executionAuthority": False, "ok": True, "requestId": "validate-1"}, "validation remains diagnostic before activation")
    require(replies[2]["ok"] is False, "malformed terminal must make exact activation unavailable")
    require(
        ("transport-send", "epoch-after") not in base.EVENTS,
        "malformed terminal must be rejected by #295 before the takeoff effect",
    )
    require(
        not any(isinstance(event, tuple) and event[0] in {"inflight-turn", "inflight-move", "controlled-land"} for event in base.EVENTS),
        "malformed terminal must never be skipped into any physical effect",
    )


def main() -> int:
    test_started_activation_wait_is_outside_lifecycle_lock()
    test_actual_host_uses_exact_program_sequence_through_landing()
    test_actual_host_rejects_malformed_terminal_before_takeoff()
    print(
        "PASS actual physical host sequencing: validate/activation handoff is race-free; "
        "successful takeoff hands the same run/epoch to exact turn/move/terminal-land execution; "
        "caller semantics remain non-authority and #260 yaw opens only for horizontal motion"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import socket
import sys
from threading import Event, Thread
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / "tools" / "ci"
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(CI))
sys.path.insert(0, str(PHYSICAL))
HOST = PHYSICAL / "serve_physical_host.py"

import controlled_landing_transport  # noqa: E402
import setpoint_hl_transport  # noqa: E402
import test_physical_controlled_landing_transport as landing_effect_test  # noqa: E402
import test_physical_host_activation as base  # noqa: E402
import yaw_observer  # noqa: E402

REAL_EXACT_WAIT = base.activation._execute_exact_wait


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


def boundary_only_ast() -> str:
    return json.dumps(
        {
            "program": [
                {"height_m": 0.6, "kind": "takeoff"},
                {"kind": "land"},
            ],
            "semantics": "webeeblocks-ast-v1",
            "version": 1,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def wait_ast() -> str:
    return json.dumps(
        {
            "program": [
                {"height_m": 0.6, "kind": "takeoff"},
                {"kind": "wait", "seconds": 0.2},
                {"kind": "land"},
            ],
            "semantics": "webeeblocks-ast-v1",
            "version": 1,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def vertical_ast() -> str:
    return json.dumps(
        {
            "program": [
                {"height_m": 0.8, "kind": "takeoff"},
                {"direction": "up", "distance_m": 0.3, "kind": "vertical"},
                {"direction": "down", "distance_m": 0.2, "kind": "vertical"},
                {"kind": "land"},
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


class FakePhysicalTransportBase:
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
        require(powered_session.session is crazyflie, "physical effect exact powered session")
        require(execution_domain.phase == base.physical_execution_domain.FLYING, "takeoff must complete first")
        if connection_epoch_reader is not None:
            require(
                connection_epoch_reader() == powered_session.connection_epoch,
                "landing completion observer must bind exact active epoch",
            )
        self.teacher_binding = teacher_authorization.binding
        self.bound_connection_epoch = powered_session.connection_epoch
        self.execution_domain = execution_domain
        self._crazyflie = crazyflie
        self._watchdog = watchdog_guard

    def _read_current_binding(self):
        raise AssertionError("host-local provenance override is required")

    def send_horizontal_move(self, *, direction, distance_m, yaw_reader, timing_policy):
        del timing_policy
        require(yaw_reader is not None and yaw_reader.is_open, "fresh yaw observer must be opened lazily for moves")
        require(yaw_reader.bound_crazyflie is self._crazyflie, "yaw exact Crazyflie")
        require(self._watchdog.active, "same-session watchdog remains live")
        binding = self._read_current_binding()
        require(binding == self.teacher_binding, "fresh #249 matches exact teacher run")
        base.EVENTS.append(("inflight-move", direction, distance_m, binding.connection_epoch))
        return SimpleNamespace(accepted=True, status=0)

    def send_vertical_move(self, *, direction, distance_m, timing_policy):
        require(self._watchdog.active, "same-session watchdog remains live")
        binding = self._read_current_binding()
        require(binding == self.teacher_binding, "fresh #249 matches exact teacher run")
        duration = timing_policy.vertical_move_duration(distance_m)
        base.EVENTS.append(
            ("inflight-vertical", direction, distance_m, duration, binding.connection_epoch)
        )
        return SimpleNamespace(accepted=True, status=0)

    def send_turn(self, *, angle_deg, timing_policy):
        del timing_policy
        require(self._watchdog.active, "same-session watchdog remains live")
        binding = self._read_current_binding()
        require(binding == self.teacher_binding, "fresh #249 matches exact teacher run")
        base.EVENTS.append(("inflight-turn", angle_deg, binding.connection_epoch))
        return SimpleNamespace(accepted=True, status=0)

    def send_controlled_landing(self):
        require(self._watchdog.active, "watchdog must remain live through controlled landing")
        binding = self._read_current_binding()
        require(binding == self.teacher_binding, "fresh #249 matches exact terminal landing")
        require(
            self.execution_domain.phase == base.physical_execution_domain.FLYING,
            "terminal landing starts only from causally established flying",
        )
        base.EVENTS.append(("terminal-land", binding.connection_epoch))
        self.execution_domain.phase = base.physical_execution_domain.INACTIVE
        return SimpleNamespace(accepted=True, status=0)


def fake_exact_wait(seconds, watchdog_guard, connection_epoch_reader, bound_epoch, *, assert_run_open=None):
    require(seconds == 0.2, "production wait derives exact canonical duration")
    require(watchdog_guard.active, "watchdog stays live across exact no-effect wait")
    require(connection_epoch_reader() == bound_epoch, "wait stays on exact active epoch")
    require(callable(assert_run_open), "production wait must carry host-local caller cancellation")
    assert_run_open()
    base.EVENTS.append(("exact-wait", seconds, bound_epoch))


def install_fakes() -> None:
    base.install_fakes()
    base.activation.TrustedControlledLandingTransport = FakePhysicalTransportBase
    base.activation.FreshYawObserver = FakeYawObserver
    base.activation._execute_exact_wait = fake_exact_wait
    controlled_landing_transport.TrustedControlledLandingTransport = FakePhysicalTransportBase
    setpoint_hl_transport.TrustedSetpointHlTransport = FakePhysicalTransportBase
    yaw_observer.FreshYawObserver = FakeYawObserver


def send_line(sock: socket.socket, payload: dict[str, object]) -> None:
    sock.sendall((json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8"))


def read_line(stream) -> dict[str, object]:
    line = stream.readline()
    require(bool(line), "physical host closed caller channel unexpectedly")
    value = json.loads(line)
    require(isinstance(value, dict), "caller response must be an object")
    return value


def run_host_sequence(
    ast_binding: str | None = None,
    *,
    steps: int = 3,
    discard_execution_reply: bool = False,
    disconnect_when_waiting: Event | None = None,
) -> list[dict[str, object]]:
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

    # Any caller-selected step semantics, including altitude/index state, are rejected.
    send_line(
        caller_peer,
        {
            "op": "execute-next-inflight",
            "requestId": "substitute-1",
            "direction": "right",
            "distanceM": 0.9,
            "heightM": 1.2,
            "index": 99,
            "seconds": 5.0,
        },
    )
    replies.append(read_line(caller_stream))

    for index in range(steps):
        if discard_execution_reply:
            # Keep request/authority direction alive but make response delivery
            # fail deterministically before the effect starts.
            caller_peer.shutdown(socket.SHUT_RD)
        send_line(
            caller_peer,
            {"op": "execute-next-inflight", "requestId": f"step-{index + 1}"},
        )
        if disconnect_when_waiting is not None:
            require(disconnect_when_waiting.wait(2), "exact wait did not start")
            caller_peer.shutdown(socket.SHUT_WR)
        if discard_execution_reply:
            worker.join(timeout=3.0)
            require(not worker.is_alive(), "host did not terminate after failed response delivery")
            require("error" not in outcome, "failed response masked execution: " + repr(outcome.get("error")))
            caller_stream.close()
            caller_peer.close()
            teacher_peer.close()
            return replies
        replies.append(read_line(caller_stream))

    if disconnect_when_waiting is None:
        caller_peer.shutdown(socket.SHUT_WR)
    worker.join(timeout=3.0)
    require(not worker.is_alive(), "actual production host must terminate after caller EOF")
    require("error" not in outcome, "production host failed: " + repr(outcome.get("error")))

    caller_stream.close()
    caller_peer.close()
    teacher_peer.close()
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
    for forbidden in ("send_packet(", "HighLevelCommander(", "effect_transaction(", "acknowledgement"):
        require(forbidden not in helper, "no-effect wait leaked physical effect surface: " + forbidden)


def test_started_activation_wait_is_outside_lifecycle_lock() -> None:
    source = HOST.read_text(encoding="utf-8")
    wait = 'if activation_state["started"]:\n                                    activation_complete.wait()'
    require(wait in source, "started activation must be awaited before physical availability is decided")
    wait_index = source.index(wait)
    lock_index = source.find("with lifecycle_lock:", wait_index)
    require(lock_index > wait_index, "activation wait must happen before reacquiring lifecycle lock")
    require(
        'finally:\n                    activation_complete.set()' in source,
        "every started activation path must release the host wait",
    )


def test_caller_loss_interrupts_every_wait_slice_including_final_slice() -> None:
    from caller_lifetime import CallerLifetime
    for seconds, already_closed in ((20.0, False), (0.02, False), (20.0, True)):
        host_socket, peer = socket.socketpair()
        stream = host_socket.makefile("r", encoding="utf-8")
        lifetime = CallerLifetime(stream, max_message_bytes=8192)
        clock = {"value": 0.0, "sleeps": []}
        guard = SimpleNamespace(assert_live=lambda: None)
        def lose_caller(delay):
            clock["value"] += delay
            clock["sleeps"].append(delay)
            peer.shutdown(socket.SHUT_WR)
            require(lifetime._closed.wait(1), "real socket EOF was not observed")
        try:
            if already_closed:
                peer.shutdown(socket.SHUT_WR)
                require(lifetime._closed.wait(1), "preclosed caller was not observed")
            try:
                REAL_EXACT_WAIT(seconds, guard, lambda: "epoch-live", "epoch-live",
                    clock=lambda: clock["value"], sleeper=lose_caller,
                    assert_run_open=lifetime.assert_open)
            except RuntimeError as exc:
                require("caller" in str(exc) and "revoked" in str(exc), "caller loss cause was replaced")
            else:
                raise AssertionError("wait completed despite caller loss")
            require(len(clock["sleeps"]) == (0 if already_closed else 1),
                    "caller loss waited through further AST delay slices")
            require(clock["value"] <= 0.05, "local cancellation ignored its first bounded wait slice")
        finally:
            peer.close()
            lifetime.stop()
            lifetime._thread.join(1)
            stream.close()
            host_socket.close()


def test_actual_static_and_dynamic_host_route_wait_eof_to_one_recovery() -> None:
    import dynamic_run_activation as dynamic_activation
    import test_dynamic_run_activation as dynamic_tests
    from contextlib import redirect_stderr
    from io import StringIO
    static_wait, dynamic_wait = base.activation._execute_exact_wait, dynamic_activation._execute_exact_wait
    try:
        for dynamic in (False, True):
            base.EVENTS.clear()
            if dynamic:
                dynamic_tests.install_dynamic_fakes()
            else:
                install_fakes()
            wait_started = Event()
            elapsed = {"value": 0.0}
            def wait(seconds, guard, epoch_reader, bound_epoch, *, assert_run_open=None):
                require(callable(assert_run_open), "host omitted local caller revocation from wait")
                def slice(delay):
                    wait_started.set()
                    # Model the external monotonic clock while using the real
                    # independently receiving CallerLifetime/socket EOF.
                    require(assert_run_open.__self__._closed.wait(1), "caller EOF did not reach local guard")
                    elapsed["value"] += delay
                return REAL_EXACT_WAIT(seconds, guard, epoch_reader, bound_epoch,
                    clock=lambda: elapsed["value"], sleeper=slice, assert_run_open=assert_run_open)
            base.activation._execute_exact_wait = wait
            dynamic_activation._execute_exact_wait = wait
            ast = json.loads(wait_ast())
            if dynamic:
                ast["program"].insert(1, {"kind": "set_variable", "variable": {"id": "x", "name": "x"},
                    "value": {"kind": "number", "value": 1}})
            output = StringIO()
            with redirect_stderr(output):
                replies = run_host_sequence(json.dumps(ast, sort_keys=True, separators=(",", ":")),
                    steps=1, disconnect_when_waiting=wait_started)
            require(replies[2]["ok"] is False, "lost caller completed a physical wait")
            require(any("caller" in cause["message"] and "revoked" in cause["message"]
                for cause in replies[2]["diagnostic"]["causes"]), "caller-loss diagnostic was masked")
            require(elapsed["value"] <= 0.05, "host waited through remaining student duration")
            records = [json.loads(line.removeprefix("HOST_RECOVERY ")) for line in output.getvalue().splitlines()
                       if line.startswith("HOST_RECOVERY ")]
            require(len(records) == 1 and records[0]["outcome"].startswith("landed:"),
                    "known-flight caller cancellation did not produce one confirmed recovery")
            require(records[0]["phase"] == "inactive", "recovery ACK was mistaken for inactive completion")
            require(base.EVENTS.count(("transport-send", "epoch-after")) == 1, "cancellation replayed takeoff")
            require(base.EVENTS.count("watchdog-stop") == 1, "cancellation duplicated powered teardown")
            land_indices = [i for i, e in enumerate(base.EVENTS)
                if isinstance(e, tuple) and e[0] in ("terminal-land", "dynamic-land")]
            revoke_indices = [i for i, e in enumerate(base.EVENTS)
                if isinstance(e, tuple) and e[0] == "teacher-close"]
            require(len(land_indices) == 1 and revoke_indices
                and revoke_indices[0] < land_indices[0] < base.EVENTS.index("watchdog-stop"),
                "landing was not one recovery after revocation with live watchdog")
    finally:
        base.activation._execute_exact_wait = static_wait
        dynamic_activation._execute_exact_wait = dynamic_wait


def test_actual_host_completes_exact_program_with_terminal_landing() -> None:
    base.EVENTS.clear()
    install_fakes()
    replies = run_host_sequence()

    require(replies[0] == {"executionAuthority": False, "ok": True, "requestId": "validate-1"}, "validation stays diagnostic")
    require(replies[1]["ok"] is False, "caller-supplied step fields must be rejected")
    require(replies[1]["executionAuthority"] is False, "rejected substitution mints no authority")
    require(replies[2] == {"executionAuthority": False, "ok": True, "requestId": "step-1"}, "exact next turn executes")
    require(replies[3] == {"executionAuthority": False, "ok": True, "requestId": "step-2"}, "exact next move executes")
    require(replies[4] == {"executionAuthority": False, "ok": True, "requestId": "step-3"}, "exact terminal landing completes")

    move_events = [event for event in base.EVENTS if isinstance(event, tuple) and event[0] == "inflight-move"]
    turn_events = [event for event in base.EVENTS if isinstance(event, tuple) and event[0] == "inflight-turn"]
    land_events = [event for event in base.EVENTS if isinstance(event, tuple) and event[0] == "terminal-land"]
    require(
        turn_events == [("inflight-turn", -25.0, "epoch-after")],
        "caller substitution must not change the exact first authorized effect",
    )
    require(
        move_events == [("inflight-move", "forward", 0.3, "epoch-after")],
        "second physical effect must follow exact canonical AST order",
    )
    require(
        land_events == [("terminal-land", "epoch-after")],
        "exact terminal landing must execute once on the same authorized epoch",
    )

    takeoff_index = base.EVENTS.index(("transport-send", "epoch-after"))
    turn_index = base.EVENTS.index(turn_events[0])
    yaw_open_index = base.EVENTS.index(("yaw-open", "epoch-after"))
    move_index = base.EVENTS.index(move_events[0])
    land_index = base.EVENTS.index(land_events[0])
    require(
        takeoff_index < turn_index < yaw_open_index < move_index < land_index,
        "takeoff, exact motions and terminal landing must preserve canonical order",
    )
    require(
        any(event == ("current-program", "epoch-after") for event in base.EVENTS[takeoff_index:turn_index]),
        "fresh host-local #278/#249 must guard the first post-takeoff effect",
    )
    require(("yaw-close", "epoch-after") in base.EVENTS, "host teardown closes #260 observer")


def test_actual_host_consumes_exact_vertical_program_parameter_free() -> None:
    base.EVENTS.clear()
    install_fakes()
    replies = run_host_sequence(vertical_ast(), steps=3)

    require(replies[1]["ok"] is False, "caller-selected vertical/altitude/index fields must be rejected")
    require(replies[2] == {"executionAuthority": False, "ok": True, "requestId": "step-1"}, "exact climb executes")
    require(replies[3] == {"executionAuthority": False, "ok": True, "requestId": "step-2"}, "exact descent executes")
    require(replies[4] == {"executionAuthority": False, "ok": True, "requestId": "step-3"}, "vertical program lands")

    vertical_events = [event for event in base.EVENTS if isinstance(event, tuple) and event[0] == "inflight-vertical"]
    land_events = [event for event in base.EVENTS if isinstance(event, tuple) and event[0] == "terminal-land"]
    require(len(vertical_events) == 2, "exact vertical program must emit exactly two vertical effects")
    require(vertical_events[0][1:3] == ("up", 0.3), "first exact vertical effect is the bound climb")
    require(vertical_events[1][1:3] == ("down", 0.2), "second exact vertical effect is the bound descent")
    require(vertical_events[0][-1] == "epoch-after" and vertical_events[1][-1] == "epoch-after", "vertical effects stay on exact epoch")
    require(land_events == [("terminal-land", "epoch-after")], "landing follows completed vertical effects once")
    require(
        not any(isinstance(event, tuple) and event[0] == "yaw-open" for event in base.EVENTS),
        "world-Z-only vertical program must not create a yaw-observer dependency",
    )

    takeoff_index = base.EVENTS.index(("transport-send", "epoch-after"))
    climb_index = base.EVENTS.index(vertical_events[0])
    descent_index = base.EVENTS.index(vertical_events[1])
    land_index = base.EVENTS.index(land_events[0])
    require(
        takeoff_index < climb_index < descent_index < land_index,
        "takeoff, exact vertical effects and terminal land preserve canonical order",
    )


def test_rejected_vertical_effect_terminates_program_without_retry() -> None:
    base.EVENTS.clear()
    install_fakes()
    original = FakePhysicalTransportBase.send_vertical_move
    attempts = {"count": 0}

    def reject_once(self, *, direction, distance_m, timing_policy):
        attempts["count"] += 1
        if attempts["count"] == 1:
            binding = self._read_current_binding()
            base.EVENTS.append(("inflight-vertical-rejected", direction, distance_m, binding.connection_epoch))
            return SimpleNamespace(accepted=False, status=22)
        return original(
            self,
            direction=direction,
            distance_m=distance_m,
            timing_policy=timing_policy,
        )

    FakePhysicalTransportBase.send_vertical_move = reject_once
    try:
        replies = run_host_sequence(vertical_ast(), steps=4)
    finally:
        FakePhysicalTransportBase.send_vertical_move = original

    require(replies[2]["ok"] is False, "definitive vertical rejection is surfaced fail-closed")
    require(all(reply["ok"] is False for reply in replies[3:]), "rejected program must remain terminal")
    accepted = [event for event in base.EVENTS if isinstance(event, tuple) and event[0] == "inflight-vertical"]
    rejected = [event for event in base.EVENTS if isinstance(event, tuple) and event[0] == "inflight-vertical-rejected"]
    require(rejected == [("inflight-vertical-rejected", "up", 0.3, "epoch-after")], "rejection is exact first climb")
    require(accepted == [] and attempts["count"] == 1, "rejected climb was retried or program continued")


def test_ambiguous_vertical_effect_makes_host_sequence_terminal() -> None:
    base.EVENTS.clear()
    install_fakes()
    original = FakePhysicalTransportBase.send_vertical_move

    def ambiguous(self, *, direction, distance_m, timing_policy):
        del timing_policy
        binding = self._read_current_binding()
        base.EVENTS.append(("inflight-vertical-ambiguous", direction, distance_m, binding.connection_epoch))
        self.execution_domain.phase = base.physical_execution_domain.RECOVERY_REQUIRED
        raise RuntimeError("injected ambiguous vertical effect")

    FakePhysicalTransportBase.send_vertical_move = ambiguous
    try:
        replies = run_host_sequence(vertical_ast(), steps=2)
    finally:
        FakePhysicalTransportBase.send_vertical_move = original

    require(replies[2]["ok"] is False and replies[3]["ok"] is False, "ambiguous vertical effect and every later step fail closed")
    require(
        not any(isinstance(event, tuple) and event[0] == "terminal-land" for event in base.EVENTS),
        "ambiguous vertical effect cannot advance into terminal landing",
    )


def test_boundary_only_program_lands_without_opening_yaw() -> None:
    base.EVENTS.clear()
    install_fakes()
    replies = run_host_sequence(boundary_only_ast(), steps=1)
    require(replies[2] == {"executionAuthority": False, "ok": True, "requestId": "step-1"}, "terminal land follows takeoff directly")
    require(
        [event for event in base.EVENTS if isinstance(event, tuple) and event[0] == "terminal-land"]
        == [("terminal-land", "epoch-after")],
        "boundary-only program consumes exactly one terminal landing",
    )
    require(
        not any(isinstance(event, tuple) and event[0] == "yaw-open" for event in base.EVENTS),
        "terminal landing must not create a yaw-observer dependency",
    )


def test_actual_host_consumes_exact_wait_without_effect_transport() -> None:
    base.EVENTS.clear()
    install_fakes()
    replies = run_host_sequence(wait_ast(), steps=2)
    require(replies[1]["ok"] is False, "caller-supplied wait duration must be rejected")
    require(replies[2] == {"executionAuthority": False, "ok": True, "requestId": "step-1"}, "exact wait completes")
    require(replies[3] == {"executionAuthority": False, "ok": True, "requestId": "step-2"}, "land follows exact wait")
    wait_events = [event for event in base.EVENTS if isinstance(event, tuple) and event[0] == "exact-wait"]
    land_events = [event for event in base.EVENTS if isinstance(event, tuple) and event[0] == "terminal-land"]
    require(wait_events == [("exact-wait", 0.2, "epoch-after")], "host waits exact canonical duration once")
    require(land_events == [("terminal-land", "epoch-after")], "terminal landing follows wait exactly once")
    require(
        not any(isinstance(event, tuple) and event[0] in {"inflight-turn", "inflight-move", "yaw-open"} for event in base.EVENTS),
        "no-effect wait must not manufacture motion or yaw dependencies",
    )
    takeoff_index = base.EVENTS.index(("transport-send", "epoch-after"))
    wait_index = base.EVENTS.index(wait_events[0])
    land_index = base.EVENTS.index(land_events[0])
    require(takeoff_index < wait_index < land_index, "takeoff/wait/land preserve exact AST order")
    current_program_events = [event for event in base.EVENTS if event == ("current-program", "epoch-after")]
    require(len(current_program_events) >= 3, "wait and later landing each re-establish current-program provenance")


def test_incomplete_host_wait_revokes_program_before_safety_landing() -> None:
    base.EVENTS.clear()
    install_fakes()
    prior = base.activation._execute_exact_wait

    def fail_wait(seconds, watchdog_guard, connection_epoch_reader, bound_epoch, *, assert_run_open=None):
        del seconds, watchdog_guard, connection_epoch_reader, bound_epoch
        raise base.activation.PhysicalRunActivationError("injected wait interruption")

    base.activation._execute_exact_wait = fail_wait
    try:
        replies = run_host_sequence(wait_ast(), steps=2)
    finally:
        base.activation._execute_exact_wait = prior
    require(replies[2]["ok"] is False, "interrupted wait must fail closed")
    require(replies[3]["ok"] is False, "terminal sequence cannot advance after failed wait")
    lands = [i for i, event in enumerate(base.EVENTS)
             if isinstance(event, tuple) and event[0] == "terminal-land"]
    revoked = next(i for i, event in enumerate(base.EVENTS)
                   if isinstance(event, tuple) and event[0] == "teacher-close")
    require(len(lands) == 1, "abort must attempt exactly one safety landing")
    require(revoked < lands[0] < base.EVENTS.index("watchdog-stop"),
            "safety landing requires revoked ordinary authority and a live watchdog")


def test_actual_host_rejects_malformed_terminal_before_takeoff() -> None:
    base.EVENTS.clear()
    install_fakes()
    malformed = canonical_ast({"kind": "land", "extra": True})
    replies = run_host_sequence(malformed)

    require(replies[0] == {"executionAuthority": False, "ok": True, "requestId": "validate-1"}, "validation remains diagnostic before activation")
    require(replies[2]["ok"] is False, "malformed terminal must make exact activation unavailable")
    require(
        ("transport-send", "epoch-after") not in base.EVENTS,
        "malformed terminal must be rejected before the takeoff effect",
    )
    require(
        not any(
            isinstance(event, tuple)
            and event[0] in {"inflight-turn", "inflight-move", "inflight-vertical", "exact-wait", "terminal-land"}
            for event in base.EVENTS
        ),
        "malformed terminal must never be skipped into a physical step",
    )


def main() -> int:
    require(
        landing_effect_test.main() == 0,
        "trusted controlled-landing transport regression must pass before host composition",
    )
    test_exact_wait_pacer_uses_monotonic_slices_and_no_effect_surface()
    test_started_activation_wait_is_outside_lifecycle_lock()
    test_actual_host_completes_exact_program_with_terminal_landing()
    test_actual_host_consumes_exact_vertical_program_parameter_free()
    test_rejected_vertical_effect_terminates_program_without_retry()
    test_ambiguous_vertical_effect_makes_host_sequence_terminal()
    test_boundary_only_program_lands_without_opening_yaw()
    test_actual_host_consumes_exact_wait_without_effect_transport()
    test_incomplete_host_wait_revokes_program_before_safety_landing()
    test_actual_host_rejects_malformed_terminal_before_takeoff()
    test_caller_loss_interrupts_every_wait_slice_including_final_slice()
    test_actual_static_and_dynamic_host_route_wait_eof_to_one_recovery()
    print(
        "PASS actual physical host sequencing: validated takeoff preserves exact ordered horizontal/vertical motion, "
        "no-effect wait pacing and one terminal controlled landing; caller-selected motion/altitude/index state is rejected, "
        "and rejected or ambiguous vertical effects cannot skip the exact sequence"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

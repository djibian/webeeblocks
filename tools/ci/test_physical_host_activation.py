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
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(PHYSICAL))
HOST = PHYSICAL / "serve_physical_host.py"

import high_level_ack  # noqa: E402
import physical_execution_domain  # noqa: E402
import physical_run_activation as activation  # noqa: E402
import post_reset_capability_bridge  # noqa: E402
import post_reset_teacher_decision  # noqa: E402
import powered_session_authority  # noqa: E402
import probe_reference_hardware  # noqa: E402
import production_takeoff_run  # noqa: E402
import safelink_precondition  # noqa: E402
import supervisor_state  # noqa: E402
import takeoff_transport  # noqa: E402
import teacher_run_authorization  # noqa: E402
import watchdog_liveness  # noqa: E402


EVENTS: list[object] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def canonical_ast() -> str:
    return json.dumps(
        {
            "program": [
                {"height_m": 0.8, "kind": "takeoff"},
                {"kind": "land"},
            ],
            "semantics": "webeeblocks-ast-v1",
            "version": 1,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


class FakeCrazyflie:
    pass


class FakeScf:
    def __init__(self, crazyflie: FakeCrazyflie) -> None:
        self.cf = crazyflie
        self.open = False

    def is_link_open(self) -> bool:
        return self.open


class FakeSession:
    latest: "FakeSession | None" = None

    def __init__(self, uri: str) -> None:
        require(uri.startswith("radio://"), "host must keep explicit radio URI")
        self.cf = FakeCrazyflie()
        self._scf = FakeScf(self.cf)
        self.epoch = ""
        self.opens = 0
        FakeSession.latest = self

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, _kind, _value, _traceback) -> None:
        self.close()

    def open(self) -> None:
        self.opens += 1
        self.epoch = "epoch-before" if self.opens == 1 else "epoch-after"
        self._scf.open = True
        EVENTS.append(("session-open", self.epoch))

    def close(self) -> None:
        EVENTS.append(("session-close", self.epoch))
        self._scf.open = False

    def read_connection_epoch(self) -> str:
        if not self._scf.open:
            raise RuntimeError("session is closed")
        return self.epoch

    def read_capabilities(self) -> dict[str, object]:
        return {
            "connected": True,
            "executionAuthority": False,
            "identity": {
                "model": "crazyflie-2.1",
                "modelEvidence": "verified",
            },
            "evidence": {
                "systemSelfTestPassed": True,
                "protocolVersion": 12,
            },
        }


class FakeEvidence:
    def __init__(self, profile_id: str, ast_binding: str, connection_epoch: str) -> None:
        self.profile_id = profile_id
        self.ast_binding = ast_binding
        self.connection_epoch = connection_epoch
        self.challenge_id = "challenge-" + connection_epoch
        self.execution_authority = False


class FakeBridge:
    latest: "FakeBridge | None" = None

    def __init__(self, session: FakeSession) -> None:
        self.session = session
        self.token = "capability-token"
        self.preflight_responder_token = "responder-token"
        self.address = ("127.0.0.1", 43117)
        self._shutdown = Event()
        self.pending_epoch: str | None = None
        FakeBridge.latest = self

    def serve_forever(self) -> None:
        self._shutdown.wait()

    def shutdown(self) -> None:
        self._shutdown.set()

    def assert_current_program(
        self,
        *,
        profile_id: str,
        ast_binding: str,
        connection_epoch: str,
        timeout_seconds: float,
    ) -> FakeEvidence:
        require(timeout_seconds > 0, "current-program assertion timeout")
        require(
            self.pending_epoch is None,
            "current-program assertion cannot cross bridge replacement",
        )
        require(
            self.session.read_connection_epoch() == connection_epoch,
            "current-program assertion must use the live session epoch",
        )
        EVENTS.append(("current-program", connection_epoch))
        return FakeEvidence(profile_id, ast_binding, connection_epoch)

    def begin_post_reset_replacement(self, previous_epoch: str) -> str:
        require(self.pending_epoch is None, "replacement is one-shot")
        require(
            self.session.read_connection_epoch() == previous_epoch,
            "replacement must cut over exact pre-reset epoch",
        )
        self.pending_epoch = previous_epoch
        EVENTS.append(("bridge-begin", previous_epoch))
        return previous_epoch

    def install_post_reset_session(self, session: FakeSession) -> str:
        require(session is self.session, "same bridge/session adapter identity")
        require(self.pending_epoch is not None, "replacement begin must precede install")
        epoch = session.read_connection_epoch()
        require(epoch != self.pending_epoch, "post-reset epoch must rotate")
        EVENTS.append(("bridge-install", epoch))
        self.pending_epoch = None
        return epoch


class FakeSupervisorReader:
    def __init__(self, crazyflie: object, epoch_reader) -> None:
        self.bound_crazyflie = crazyflie
        self._epoch_reader = epoch_reader
        self.bound_connection_epoch = epoch_reader()
        self.poisoned = False
        EVENTS.append(("supervisor-compose", self.bound_connection_epoch))

    def read(self, *, timeout_seconds: float):
        require(timeout_seconds > 0, "fresh supervisor timeout")
        return SimpleNamespace(
            blocking_fault=False,
            can_fly=True,
            is_flying=False,
            hl_control_active=False,
            hl_traj_finished=False,
        )


class FakePoweredSession:
    def __init__(self, session: object, connection_epoch: str, watchdog_authority: object) -> None:
        self.session = session
        self.connection_epoch = connection_epoch
        self.watchdog_authority = watchdog_authority


class FakePoweredFactory:
    def __init__(self, **callbacks) -> None:
        self.callbacks = callbacks

    def establish(self, *, previous_connection_epoch: str):
        EVENTS.append(("reset-enter", previous_connection_epoch))
        require(self.callbacks["require_flight_known_inactive"]() is True, "reset safety")
        self.callbacks["invalidate_prior_evidence"]()
        self.callbacks["stm_deck_power_cycle"]()
        crazyflie = self.callbacks["open_post_reset_session"]()
        epoch = self.callbacks["read_connection_epoch"](crazyflie)
        require(epoch != previous_connection_epoch, "reset must rotate epoch")
        self.callbacks["read_capabilities"](crazyflie)
        require(self.callbacks["assert_bound_preflight"](crazyflie, epoch) is True, "post-reset preflight")
        state = self.callbacks["read_fresh_supervisor"](crazyflie, epoch)
        require(state.blocking_fault is False, "post-reset state")
        EVENTS.append(("reset-complete", epoch))
        return FakePoweredSession(crazyflie, epoch, object())


class FakeExecutionDomain:
    def __init__(self) -> None:
        self.phase = physical_execution_domain.RECOVERY_REQUIRED

    def run_reset_establishment(self, establish):
        result = establish()
        self.phase = physical_execution_domain.INACTIVE
        return result


class FakeAuthorization:
    def __init__(self, binding: teacher_run_authorization.PhysicalRunBinding) -> None:
        self.binding = binding
        self.active = True

    def assert_effect_binding(self, *, profile_id: str, ast_binding: str, connection_epoch: str) -> None:
        require(self.active, "teacher receipt active")
        require(
            (profile_id, ast_binding, connection_epoch)
            == (
                self.binding.profile_id,
                self.binding.ast_binding,
                self.binding.connection_epoch,
            ),
            "teacher receipt exact binding",
        )

    def invalidate(self, reason: str) -> None:
        EVENTS.append(("teacher-invalidate", reason))
        self.active = False


class FakeAuthorizer:
    def close_run(self, receipt: FakeAuthorization, reason: str) -> None:
        EVENTS.append(("teacher-close", reason))
        receipt.active = False


class FakeTeacherChannel:
    def __init__(self, teacher_socket: socket.socket, epoch_reader) -> None:
        self.teacher_socket = teacher_socket
        self.epoch_reader = epoch_reader
        self.closed = False

    def receive_authorization_for_binding(self, authorizer: FakeAuthorizer, binding):
        require(type(authorizer) is FakeAuthorizer, "exact teacher authorizer")
        require(binding.connection_epoch == self.epoch_reader(), "teacher decision new epoch")
        EVENTS.append(("teacher-decision", binding.connection_epoch))
        return FakeAuthorization(binding)

    def close(self) -> None:
        self.closed = True


class FakeWatchdog:
    def __init__(self, crazyflie: object, epoch_reader, supervisor, authority: object) -> None:
        require(crazyflie is supervisor.bound_crazyflie, "watchdog exact session")
        self.active = False

    def activate(self) -> None:
        EVENTS.append("watchdog-activate")
        self.active = True

    def assert_live(self) -> None:
        require(self.active, "watchdog live")

    def stop_for_terminal_reboot(self) -> None:
        EVENTS.append("watchdog-stop")
        self.active = False


class FakeAckResult:
    def __init__(self) -> None:
        self.accepted = True
        self.status = 0


class FakeAckDomain:
    def __init__(self, epoch_reader) -> None:
        self.bound_connection_epoch = epoch_reader()


class FakeSafeLink:
    def __init__(self, crazyflie: object, epoch_reader) -> None:
        self.bound_crazyflie = crazyflie
        self.bound_connection_epoch = epoch_reader()


class FakeTransportBase:
    def __init__(
        self,
        *,
        crazyflie: object,
        execution_domain: FakeExecutionDomain,
        acknowledgement_domain: FakeAckDomain,
        safelink_guard: FakeSafeLink,
        teacher_authorization: FakeAuthorization,
        powered_session: FakePoweredSession,
        watchdog_guard: FakeWatchdog,
        supervisor_reader: FakeSupervisorReader,
    ) -> None:
        require(powered_session.session is crazyflie, "takeoff exact powered session")
        self.execution_domain = execution_domain
        self.teacher_binding = teacher_authorization.binding
        self.bound_connection_epoch = powered_session.connection_epoch

    def _read_current_binding(self):
        raise AssertionError("host adapter must override current-program binding")

    def send_from_authorized_ast(self) -> FakeAckResult:
        binding = self._read_current_binding()
        require(binding == self.teacher_binding, "fresh provenance exact teacher binding")
        EVENTS.append(("transport-send", binding.connection_epoch))
        self.execution_domain.phase = physical_execution_domain.FLYING
        return FakeAckResult()


def install_fakes() -> None:
    probe_reference_hardware.ReadOnlyCapabilitySession = FakeSession
    post_reset_capability_bridge.PostResetCapabilityHttpBridge = FakeBridge

    powered_session_authority.TrustedPoweredSessionFactory = FakePoweredFactory
    powered_session_authority.EstablishedPoweredSession = FakePoweredSession
    physical_execution_domain.PhysicalExecutionDomain = FakeExecutionDomain
    post_reset_teacher_decision.PostResetTeacherDecisionChannel = FakeTeacherChannel
    teacher_run_authorization.TeacherRunAuthorization = FakeAuthorization
    teacher_run_authorization.TrustedTeacherAuthorizer = FakeAuthorizer
    supervisor_state.FreshSupervisorStateReader = FakeSupervisorReader
    watchdog_liveness.EmergencyWatchdogLivenessGuard = FakeWatchdog
    high_level_ack.HighLevelAckResult = FakeAckResult
    high_level_ack.HighLevelAckDomain = FakeAckDomain
    safelink_precondition.LiveSafeLinkPrecondition = FakeSafeLink
    takeoff_transport.TrustedTakeoffTransport = FakeTransportBase

    activation.TrustedPoweredSessionFactory = FakePoweredFactory
    activation.PostResetTeacherDecisionChannel = FakeTeacherChannel
    activation.TrustedTeacherAuthorizer = FakeAuthorizer
    activation.FreshSupervisorStateReader = FakeSupervisorReader
    activation.TrustedTakeoffTransport = FakeTransportBase
    activation.CurrentProgramPreflightEvidence = FakeEvidence
    activation.PhysicalExecutionDomain = FakeExecutionDomain
    activation.make_cflib_stm_deck_power_cycle = (
        lambda _uri: lambda: EVENTS.append("power-cycle")
    )


def run_host(*, teacher_enabled: bool) -> dict[str, object]:
    caller_host, caller_peer = socket.socketpair()
    browser_read, browser_write = os.pipe()
    teacher_peer = None
    teacher_fd = None
    if teacher_enabled:
        teacher_host, teacher_peer = socket.socketpair()
        teacher_fd = teacher_host.detach()

    argv = [
        str(HOST),
        "--uri",
        "radio://0/80/2M/E7E7E7E7E7",
        "--caller-fd",
        str(caller_host.detach()),
        "--browser-config-fd",
        str(browser_write),
    ]
    if teacher_fd is not None:
        argv += ["--teacher-fd", str(teacher_fd)]

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
    require(bootstrap["executionAuthority"] is False, "browser bootstrap non-authority")
    require(bootstrap["token"] == "capability-token", "stable read-only token")
    require(bootstrap["preflightResponderToken"] == "responder-token", "responder token")

    request = {
        "op": "validate-run-context",
        "requestId": "request-1",
        "profileId": "activity-1",
        "astBinding": canonical_ast(),
        "connectionEpoch": "epoch-before",
    }
    caller_peer.sendall((json.dumps(request, separators=(",", ":")) + "\n").encode())
    response = json.loads(caller_peer.makefile("r", encoding="utf-8").readline())
    require(response == {"executionAuthority": False, "ok": True, "requestId": "request-1"}, "caller reply remains diagnostic")
    caller_peer.shutdown(socket.SHUT_WR)
    worker.join(timeout=3.0)
    require(not worker.is_alive(), "production host runner must terminate after caller EOF")
    require("error" not in outcome, "production host runner failed: " + repr(outcome.get("error")))

    caller_peer.close()
    if teacher_peer is not None:
        teacher_peer.close()
    return bootstrap


def test_actual_host_runs_exact_post_reset_activation_chain() -> None:
    EVENTS.clear()
    install_fakes()
    run_host(teacher_enabled=True)

    required = [
        ("session-open", "epoch-before"),
        ("current-program", "epoch-before"),
        ("bridge-begin", "epoch-before"),
        ("session-close", "epoch-before"),
        "power-cycle",
        ("session-open", "epoch-after"),
        ("bridge-install", "epoch-after"),
        ("current-program", "epoch-after"),
        ("teacher-decision", "epoch-after"),
        "watchdog-activate",
        ("transport-send", "epoch-after"),
    ]
    positions = []
    for event in required:
        require(event in EVENTS, "missing production-host event: " + repr(event))
        positions.append(EVENTS.index(event))
    require(positions == sorted(positions), "production host causal ordering changed")

    send_index = EVENTS.index(("transport-send", "epoch-after"))
    prior = [
        index
        for index, event in enumerate(EVENTS[:send_index])
        if event == ("current-program", "epoch-after")
    ]
    require(prior and prior[-1] < send_index, "fresh post-reset #249 must precede effect")
    require("watchdog-stop" in EVENTS, "host teardown must stop controller watchdog")
    require(
        any(isinstance(event, tuple) and event[0] == "teacher-close" for event in EVENTS),
        "host teardown must close the teacher-authorized run",
    )


def test_actual_host_validation_without_teacher_capability_is_effect_free() -> None:
    EVENTS.clear()
    install_fakes()
    run_host(teacher_enabled=False)
    forbidden = {"power-cycle", "watchdog-activate"}
    require(not any(event in forbidden for event in EVENTS), "caller-only validation triggered effect preparation")
    require(not any(isinstance(event, tuple) and event[0] == "bridge-begin" for event in EVENTS), "caller-only validation entered reset cutover")
    require(not any(isinstance(event, tuple) and event[0] == "transport-send" for event in EVENTS), "caller-only validation emitted effect")


def main() -> int:
    test_actual_host_runs_exact_post_reset_activation_chain()
    test_actual_host_validation_without_teacher_capability_is_effect_free()
    print(
        "PASS actual physical host runner: validated binding -> fail-closed bridge cutover -> "
        "post-reset teacher -> watchdog -> takeoff, while caller-only validation is effect-free"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

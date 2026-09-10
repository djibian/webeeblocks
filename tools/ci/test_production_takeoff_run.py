#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(PHYSICAL))

import production_takeoff_run as production  # noqa: E402

HOST = PHYSICAL / "serve_physical_host.py"
ADAPTER = PHYSICAL / "physical_run_activation.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class Epoch:
    def __init__(self, value: str = "epoch-before") -> None:
        self.value = value

    def read(self) -> str:
        EVENTS.append(("epoch", self.value))
        return self.value


EVENTS: list[object] = []


def install_fakes(epoch: Epoch):
    class FakeBinding:
        def __init__(self, profile_id: str, ast_binding: str, connection_epoch: str) -> None:
            self.profile_id = profile_id
            self.ast_binding = ast_binding
            self.connection_epoch = connection_epoch

        def __eq__(self, other: object) -> bool:
            return (
                type(other) is FakeBinding
                and self.profile_id == other.profile_id
                and self.ast_binding == other.ast_binding
                and self.connection_epoch == other.connection_epoch
            )

    class FakeAuthorization:
        def __init__(self, binding: FakeBinding) -> None:
            self.binding = binding
            self.active = True

        def assert_effect_binding(self, *, profile_id: str, ast_binding: str, connection_epoch: str) -> None:
            EVENTS.append(("teacher-assert", connection_epoch))
            require(self.active, "teacher receipt must be active")
            require(
                (profile_id, ast_binding, connection_epoch)
                == (self.binding.profile_id, self.binding.ast_binding, self.binding.connection_epoch),
                "teacher assertion must keep the exact binding",
            )

        def invalidate(self, reason: str) -> None:
            EVENTS.append(("teacher-invalidate", reason))
            self.active = False

    class FakeAuthorizer:
        def close_run(self, receipt: FakeAuthorization, reason: str) -> None:
            EVENTS.append(("teacher-close", reason))
            receipt.active = False

    class FakeTeacherChannel:
        def __init__(self) -> None:
            self.bindings: list[FakeBinding] = []

        def receive_authorization_for_binding(self, authorizer: FakeAuthorizer, binding: FakeBinding):
            require(type(authorizer) is FakeAuthorizer, "exact fake authorizer")
            EVENTS.append(("teacher-decision", binding.connection_epoch))
            self.bindings.append(binding)
            return FakeAuthorization(binding)

    class FakeEstablished:
        def __init__(self, session: object, connection_epoch: str, watchdog_authority: object) -> None:
            self.session = session
            self.connection_epoch = connection_epoch
            self.watchdog_authority = watchdog_authority

    crazyflie = object()

    class FakePoweredFactory:
        def __init__(self) -> None:
            self.calls = 0

        def establish(self, *, previous_connection_epoch: str):
            self.calls += 1
            EVENTS.append(("powered-establish", previous_connection_epoch))
            require(previous_connection_epoch == "epoch-before", "reset must bind the pre-reset epoch")
            epoch.value = "epoch-after"
            return FakeEstablished(crazyflie, epoch.value, object())

    class FakeExecutionDomain:
        def __init__(self) -> None:
            self.phase = production.physical_execution_domain.RECOVERY_REQUIRED

        def run_reset_establishment(self, establish):
            EVENTS.append("execution-reset-enter")
            result = establish()
            self.phase = production.physical_execution_domain.INACTIVE
            EVENTS.append("execution-reset-complete")
            return result

    class FakeSupervisorReader:
        def __init__(self, cf: object, epoch_reader) -> None:
            require(cf is crazyflie, "supervisor must bind exact post-reset Crazyflie")
            require(epoch_reader() == "epoch-after", "supervisor must bind post-reset epoch")
            EVENTS.append("supervisor")

    class FakeWatchdog:
        def __init__(self, cf: object, epoch_reader, supervisor: FakeSupervisorReader, authority: object) -> None:
            require(cf is crazyflie, "watchdog must bind exact post-reset Crazyflie")
            require(type(supervisor) is FakeSupervisorReader, "watchdog must share supervisor reader")
            require(epoch_reader() == "epoch-after", "watchdog must bind post-reset epoch")
            self.active = False
            EVENTS.append("watchdog-compose")

        def activate(self) -> None:
            EVENTS.append("watchdog-activate")
            self.active = True

        def assert_live(self) -> None:
            EVENTS.append("watchdog-live")
            require(self.active, "watchdog must stay active")

        def stop_for_terminal_reboot(self) -> None:
            EVENTS.append("watchdog-stop")
            self.active = False

    class FakeAckResult:
        def __init__(self, accepted: bool = True) -> None:
            self.accepted = accepted
            self.status = 0 if accepted else 7

    class FakeAckDomain:
        def __init__(self, epoch_reader) -> None:
            require(epoch_reader() == "epoch-after", "ack domain must bind post-reset epoch")
            EVENTS.append("ack")

    class FakeSafeLink:
        def __init__(self, cf: object, epoch_reader) -> None:
            require(cf is crazyflie, "SafeLink must bind exact Crazyflie")
            require(epoch_reader() == "epoch-after", "SafeLink must bind post-reset epoch")
            EVENTS.append("safelink")

    class FakeTrustedTakeoff:
        pass

    production.teacher_run_authorization.PhysicalRunBinding = FakeBinding
    production.teacher_run_authorization.TeacherRunAuthorization = FakeAuthorization
    production.teacher_run_authorization.TrustedTeacherAuthorizer = FakeAuthorizer
    production.post_reset_teacher_decision.PostResetTeacherDecisionChannel = FakeTeacherChannel
    production.powered_session_authority.TrustedPoweredSessionFactory = FakePoweredFactory
    production.powered_session_authority.EstablishedPoweredSession = FakeEstablished
    production.physical_execution_domain.PhysicalExecutionDomain = FakeExecutionDomain
    production.supervisor_state.FreshSupervisorStateReader = FakeSupervisorReader
    production.watchdog_liveness.EmergencyWatchdogLivenessGuard = FakeWatchdog
    production.high_level_ack.HighLevelAckResult = FakeAckResult
    production.high_level_ack.HighLevelAckDomain = FakeAckDomain
    production.safelink_precondition.LiveSafeLinkPrecondition = FakeSafeLink
    production.takeoff_transport.TrustedTakeoffTransport = FakeTrustedTakeoff

    class FakeTransport(FakeTrustedTakeoff):
        def __init__(self, **kwargs) -> None:
            require(kwargs["crazyflie"] is crazyflie, "transport exact Crazyflie")
            require(kwargs["execution_domain"].phase == production.physical_execution_domain.INACTIVE, "takeoff only after inactive")
            self._execution = kwargs["execution_domain"]
            self.bound_connection_epoch = "epoch-after"
            self.teacher_binding = kwargs["teacher_authorization"].binding
            EVENTS.append("transport-compose")

        def send_from_authorized_ast(self):
            EVENTS.append("takeoff-send")
            self._execution.phase = production.physical_execution_domain.FLYING
            return FakeAckResult(True)

    return {
        "Binding": FakeBinding,
        "Authorizer": FakeAuthorizer,
        "TeacherChannel": FakeTeacherChannel,
        "PoweredFactory": FakePoweredFactory,
        "Execution": FakeExecutionDomain,
        "Transport": FakeTransport,
    }


def test_real_controller_orders_post_reset_authority_before_takeoff() -> None:
    EVENTS.clear()
    epoch = Epoch()
    fake = install_fakes(epoch)
    powered = fake["PoweredFactory"]()
    teacher = fake["TeacherChannel"]()
    authorizer = fake["Authorizer"]()
    execution = fake["Execution"]()

    def transport_factory(**kwargs):
        return fake["Transport"](**kwargs)

    controller = production.ProductionTakeoffRunController(
        powered_session_factory=powered,
        teacher_channel=teacher,
        teacher_authorizer=authorizer,
        connection_epoch_reader=epoch.read,
        host_bound_transport_factory=transport_factory,
        execution_domain=execution,
    )
    active = controller.start(
        profile_id="activity-1",
        ast_binding="canonical-ast",
        previous_connection_epoch="epoch-before",
    )

    require(powered.calls == 1, "exactly one reset establishment")
    require(active.crazyflie is not None, "successful controller retains exact physical session")
    require(execution.phase == production.physical_execution_domain.FLYING, "takeoff completion establishes flying")
    teacher_event = EVENTS.index(("teacher-decision", "epoch-after"))
    watchdog_event = EVENTS.index("watchdog-activate")
    send_event = EVENTS.index("takeoff-send")
    reset_event = EVENTS.index("execution-reset-complete")
    require(reset_event < teacher_event < watchdog_event < send_event, "required #266 -> #290/#267 -> #262 -> #289 order")
    require(not any(event == ("teacher-decision", "epoch-before") for event in EVENTS), "pre-reset teacher receipt must never be minted")

    controller.shutdown()
    require("watchdog-stop" in EVENTS, "controller-owned teardown terminates watchdog deliberately")
    require(any(isinstance(event, tuple) and event[0] == "teacher-close" for event in EVENTS), "controller-owned teardown closes teacher run")


def test_stale_candidate_fails_before_reset() -> None:
    EVENTS.clear()
    epoch = Epoch("different-live-epoch")
    fake = install_fakes(epoch)
    powered = fake["PoweredFactory"]()
    controller = production.ProductionTakeoffRunController(
        powered_session_factory=powered,
        teacher_channel=fake["TeacherChannel"](),
        teacher_authorizer=fake["Authorizer"](),
        connection_epoch_reader=epoch.read,
        host_bound_transport_factory=lambda **kwargs: fake["Transport"](**kwargs),
        execution_domain=fake["Execution"](),
    )
    try:
        controller.start(
            profile_id="activity-1",
            ast_binding="canonical-ast",
            previous_connection_epoch="epoch-before",
        )
    except production.ProductionTakeoffRunError as exc:
        require("staged run" in str(exc), "stale candidate must fail for exact reason")
    else:
        raise AssertionError("stale pre-reset candidate unexpectedly reached reset")
    require(powered.calls == 0, "stale candidate cannot trigger reset")


def test_host_and_adapter_preserve_authority_ownership_boundaries() -> None:
    host = HOST.read_text(encoding="utf-8")
    adapter = ADAPTER.read_text(encoding="utf-8")

    for required in (
        "activate_validated_run(",
        'staged_state["binding"] = PhysicalRunBinding(',
        "active_controller.shutdown()",
        "PostResetCapabilityHttpBridge(session)",
    ):
        require(required in host, "production host missing lifecycle ownership: " + required)
    require(
        "active_run.teacher_authorization" not in host,
        "host must not reach through the controller using the obsolete authority-bundle shape",
    )

    for required in (
        "ProductionTakeoffRunController(",
        "session.close()",
        "session.open()",
        "begin_post_reset_replacement",
        "install_post_reset_session",
        "_assert_current_program(",
        "controller.start(",
    ):
        require(required in adapter, "host adapter missing exact composition seam: " + required)

    for forbidden in (
        "caller_height",
        "height_m=",
        "raw_packet",
        "send_packet(",
    ):
        require(forbidden not in adapter, "host adapter leaks caller/effect primitive: " + forbidden)


def test_actual_host_runner_contract() -> None:
    result = subprocess.run(
        [sys.executable, "tools/ci/test_physical_host_activation.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise AssertionError(
            "actual production-host activation regression failed\n"
            + result.stdout
            + "\n"
            + result.stderr
        )
    require(
        "PASS actual physical host runner:" in result.stdout,
        "actual host runner did not publish its exact PASS evidence",
    )


def test_actual_host_authority_path() -> None:
    result = subprocess.run(
        [sys.executable, "tools/ci/test_physical_host_authority_path.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise AssertionError(
            "actual production-host authority regression failed\n"
            + result.stdout
            + "\n"
            + result.stderr
        )
    require(
        "PASS actual host authority path:" in result.stdout,
        "actual host authority path did not publish its exact PASS evidence",
    )


def main() -> int:
    test_real_controller_orders_post_reset_authority_before_takeoff()
    test_stale_candidate_fails_before_reset()
    test_host_and_adapter_preserve_authority_ownership_boundaries()
    test_actual_host_runner_contract()
    test_actual_host_authority_path()
    print(
        "PASS production takeoff lifecycle: reset epoch -> post-reset teacher -> watchdog -> "
        "causal takeoff, stale candidate rejection, actual host runner and controller-owned teardown"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
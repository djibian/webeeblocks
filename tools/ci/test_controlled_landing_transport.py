#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from threading import Event, Thread

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / "tools" / "ci"
PHYSICAL = ROOT / "tools" / "physical"
import sys
sys.path.insert(0, str(CI))
sys.path.insert(0, str(PHYSICAL))

import controlled_landing_transport as landing_transport  # noqa: E402
import high_level_ack as ack  # noqa: E402
import landing_command  # noqa: E402
import physical_execution_domain as execution  # noqa: E402
import safelink_precondition as safelink  # noqa: E402
import serve_reference_capabilities as capability_bridge  # noqa: E402
import teacher_run_authorization as teacher  # noqa: E402
import test_physical_setpoint_hl_transport as base  # noqa: E402
import watchdog_liveness as watchdog  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_error(callable_, error_type, pattern: str) -> None:
    try:
        callable_()
    except error_type as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError(f"expected {error_type.__name__} containing {pattern!r}")


def canonical_ast(height: float = 0.8) -> str:
    return json.dumps(
        {
            "program": [
                {"height_m": height, "kind": "takeoff"},
                {"kind": "land"},
            ],
            "semantics": "webeeblocks-ast-v1",
            "version": 1,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


class TestHostBoundLandingTransport(landing_transport.TrustedControlledLandingTransport):
    """Test-only analogue of the lexical physical-host provenance subclass."""

    def __init__(self, *, bridge, **kwargs) -> None:
        self._test_bridge = bridge
        super().__init__(**kwargs)

    def _read_current_binding(self):
        binding = self.teacher_binding
        try:
            evidence = self._test_bridge.assert_current_program(
                profile_id=binding.profile_id,
                ast_binding=binding.ast_binding,
                connection_epoch=binding.connection_epoch,
                timeout_seconds=0.25,
            )
        except Exception as exc:
            raise landing_transport.ControlledLandingTransportError(
                "integrated #278/#249 current-program re-assertion failed"
            ) from exc
        if type(evidence) is not capability_bridge.CurrentProgramPreflightEvidence:
            raise landing_transport.ControlledLandingTransportError(
                "invalid current-program evidence"
            )
        if evidence.execution_authority is not False:
            raise landing_transport.ControlledLandingTransportError(
                "current-program evidence became authority"
            )
        if (
            evidence.profile_id != binding.profile_id
            or evidence.ast_binding != binding.ast_binding
            or evidence.connection_epoch != binding.connection_epoch
        ):
            raise landing_transport.ControlledLandingTransportError(
                "current-program binding mismatch"
            )
        return binding


class LandingFixture:
    def __init__(self, label: str, cf: base.FakeCrazyflie) -> None:
        self.cf = cf
        self.epoch = base.Epoch(base.unique("landing-" + label))
        self.domain = base.ensure_flying()
        self.powered = base.mint_powered_session(cf, self.epoch)
        (
            self.supervisor_reader,
            self.supervisor_reads,
            self.supervisor_observed,
        ) = base.make_supervisor_reader(cf, self.epoch)
        self.watchdog = watchdog.EmergencyWatchdogLivenessGuard(
            cf,
            self.epoch,
            self.supervisor_reader,
            self.powered.watchdog_authority,
            keepalive_interval_seconds=0.2,
            max_host_gap_seconds=0.7,
        )
        self.watchdog.activate(supervisor_timeout_seconds=0.05)
        self.supervisor_reads.extend(
            [
                base.state(hl_traj_finished=True),
                base.state(hl_traj_finished=True),
                base.state(
                    blocking_fault=False,
                    is_flying=False,
                    hl_control_active=False,
                    hl_traj_finished=True,
                ),
            ]
        )
        self.binding = teacher.PhysicalRunBinding(
            profile_id="activity-1",
            ast_binding=canonical_ast(),
            connection_epoch=self.epoch(),
        )
        self.authorizer = teacher.TrustedTeacherAuthorizer()
        self.authorization = self.authorizer.authorize_run(
            self.binding,
            lambda _binding: True,
        )
        self.current_binding = self.binding
        self.bridge = capability_bridge.ReadOnlyCapabilityHttpBridge(
            base.FakeCapabilitySession(self.epoch),
            token=base.unique("landing-capability"),
            preflight_responder_token=base.unique("landing-responder"),
        )
        self.bridge_thread = Thread(target=self.bridge.serve_forever, daemon=True)
        self.bridge_thread.start()
        self.stop = Event()

        def answer() -> None:
            while not self.stop.is_set():
                try:
                    challenge = self.bridge._claim_current_program_challenge(
                        timeout_seconds=0.05
                    )
                except capability_bridge.CapabilityBridgeError:
                    return
                if challenge is None:
                    continue
                current = self.current_binding
                try:
                    self.bridge._submit_current_program_assertion(
                        {
                            "challengeId": challenge,
                            "ok": True,
                            "profileId": current.profile_id,
                            "astBinding": current.ast_binding,
                            "connectionEpoch": current.connection_epoch,
                            "executionAuthority": False,
                        }
                    )
                except capability_bridge.CapabilityBridgeError:
                    pass

        self.responder_thread = Thread(target=answer, daemon=True)
        self.responder_thread.start()
        self.safelink = safelink.LiveSafeLinkPrecondition(cf, self.epoch)
        self.ack = ack.HighLevelAckDomain(self.epoch)
        self.transport = TestHostBoundLandingTransport(
            bridge=self.bridge,
            connection_epoch_reader=self.epoch,
            crazyflie=cf,
            execution_domain=self.domain,
            acknowledgement_domain=self.ack,
            safelink_guard=self.safelink,
            teacher_authorization=self.authorization,
            powered_session=self.powered,
            watchdog_guard=self.watchdog,
            supervisor_reader=self.supervisor_reader,
        )

    def close(self) -> None:
        try:
            self.watchdog.stop_for_terminal_reboot(join_timeout_seconds=0.2)
        except watchdog.WatchdogLivenessError:
            pass
        self.stop.set()
        self.bridge.shutdown()
        self.responder_thread.join(timeout=1.0)
        self.bridge_thread.join(timeout=1.0)


def test_accepted_landing_uses_exact_command_10_and_fresh_completion() -> None:
    cf = base.FakeCrazyflie(reply_status=0)
    fixture = LandingFixture("accept", cf)
    try:
        result = fixture.transport.send_controlled_landing()
        require(result.accepted, "zero firmware result accepts exact landing")
        require(len(cf.send_calls) == 1, "terminal landing emits exactly one packet")
        expected = landing_command.derive_bound_landing_command(
            fixture.binding.ast_binding
        ).request
        actual = bytes(cf.send_calls[0][0][0].data)
        require(actual == expected, "physical packet is exact #305 teacher-bound command 10")
        require(actual[0] == landing_command.LAND_WITH_VELOCITY_COMMAND, "command id is 10")
        require(fixture.domain.phase == execution.INACTIVE, "fresh #264 completion establishes inactive")
        require(
            any(
                getattr(item, "is_flying", None) is False
                and getattr(item, "hl_control_active", None) is False
                and getattr(item, "hl_traj_finished", None) is True
                for item in fixture.supervisor_observed
            ),
            "accepted landing requires fresh finished non-flying supervisor evidence",
        )
    finally:
        fixture.close()


def test_changed_current_program_blocks_before_landing_effect() -> None:
    cf = base.FakeCrazyflie(reply_status=0)
    fixture = LandingFixture("binding", cf)
    try:
        fixture.current_binding = teacher.PhysicalRunBinding(
            profile_id=fixture.binding.profile_id,
            ast_binding=canonical_ast(0.7),
            connection_epoch=fixture.binding.connection_epoch,
        )
        expect_error(
            fixture.transport.send_controlled_landing,
            landing_transport.ControlledLandingTransportError,
            "current-program re-assertion",
        )
        require(not cf.send_calls, "changed current program must prevent landing emission")
        require(fixture.domain.phase == execution.FLYING, "pre-effect failure preserves flying phase")
    finally:
        fixture.close()


def test_definitive_rejection_is_one_shot_and_retryable_by_sequence_layer() -> None:
    cf = base.FakeCrazyflie(reply_status=23)
    fixture = LandingFixture("reject", cf)
    try:
        result = fixture.transport.send_controlled_landing()
        require(not result.accepted and result.status == 23, "non-zero landing result is definitive rejection")
        require(len(cf.send_calls) == 1, "definitive landing rejection is never resent")
        require(fixture.domain.phase == execution.FLYING, "definitive rejection restores flying phase")
    finally:
        fixture.close()


def test_acknowledgement_timeout_is_ambiguous_and_never_retried() -> None:
    cf = base.FakeCrazyflie(reply_status=None)
    fixture = LandingFixture("timeout", cf)
    try:
        expect_error(
            fixture.transport.send_controlled_landing,
            ack.HighLevelAckError,
            "timeout",
        )
        require(len(cf.send_calls) == 1, "ambiguous landing is emitted exactly once")
        require(fixture.ack.poisoned, "ambiguous landing acknowledgement poisons epoch")
        require(
            fixture.domain.phase == execution.RECOVERY_REQUIRED,
            "ambiguous landing outcome requires recovery",
        )
    finally:
        fixture.close()


def test_importable_core_has_no_caller_landing_parameter_surface() -> None:
    cf = base.FakeCrazyflie(reply_status=0)
    fixture = LandingFixture("surface", cf)
    try:
        try:
            fixture.transport.send_controlled_landing(0.1)
        except TypeError:
            pass
        else:
            raise AssertionError("caller-selected landing parameter entered effect API")
        require(not cf.send_calls, "parameter substitution cannot emit")

        source = (PHYSICAL / "controlled_landing_transport.py").read_text(encoding="utf-8")
        for forbidden in (
            "COMMAND_LAND_2",
            "COMMAND_STOP",
            "caller_height",
            "caller_velocity",
            "retry=True",
        ):
            require(forbidden not in source, "controlled landing leaked alternate effect surface: " + forbidden)
        require(
            "landing_command.derive_bound_landing_command" in source,
            "effect must derive command bytes only from integrated exact-AST landing semantics",
        )
    finally:
        fixture.close()


def main() -> int:
    test_accepted_landing_uses_exact_command_10_and_fresh_completion()
    test_changed_current_program_blocks_before_landing_effect()
    test_definitive_rejection_is_one_shot_and_retryable_by_sequence_layer()
    test_acknowledgement_timeout_is_ambiguous_and_never_retried()
    test_importable_core_has_no_caller_landing_parameter_surface()
    print(
        "PASS trusted controlled landing transport derives exact command 10 from the "
        "teacher-bound AST, emits once under existing authorities, and accepts completion "
        "only from fresh same-epoch #264 evidence"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

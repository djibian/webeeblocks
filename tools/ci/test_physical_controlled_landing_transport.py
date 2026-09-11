#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(PHYSICAL))

import controlled_landing_transport as landing_transport  # noqa: E402
import physical_execution_domain as execution  # noqa: E402
import serve_reference_capabilities as capability_bridge  # noqa: E402
import teacher_run_authorization as teacher  # noqa: E402
import test_physical_setpoint_hl_transport as base  # noqa: E402


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


class TestHostBoundLandingTransport(landing_transport.TrustedControlledLandingTransport):
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


def make_fixture(label: str, *, reply_status: int | None = 0):
    cf = base.FakeCrazyflie(reply_status=reply_status)
    fixture = base.Fixture(label, cf)
    binding = teacher.PhysicalRunBinding(
        profile_id="activity-landing",
        ast_binding=canonical_ast(),
        connection_epoch=fixture.epoch(),
    )
    authorizer = teacher.TrustedTeacherAuthorizer()
    authorization = authorizer.authorize_run(binding, lambda _binding: True)
    fixture.binding = binding
    fixture.current_binding = binding
    fixture.authorization = authorization
    fixture.kwargs["teacher_authorization"] = authorization
    fixture.supervisor_reads.clear()
    transport = TestHostBoundLandingTransport(
        bridge=fixture.bridge,
        connection_epoch_reader=fixture.epoch,
        **fixture.kwargs,
    )
    return fixture, transport


def queue_pre_land(fixture, *, completion=None) -> None:
    fixture.supervisor_reads.extend(
        [
            base.state(hl_traj_finished=True),
            base.state(hl_traj_finished=True),
        ]
    )
    if completion is not None:
        fixture.supervisor_reads.append(completion)


def unpack_land(fixture):
    require(len(fixture.cf.send_calls) == 1, "controlled landing emits exactly one packet")
    data = bytes(fixture.cf.send_calls[0][0][0].data)
    return struct.unpack("<BBf?f?f", data)


landing_transport._LANDING_COMPLETION_TIMEOUT_SECONDS = 0.05


def test_accepted_landing_requires_fresh_nonflying_completion() -> None:
    fixture, transport = make_fixture("landing-success")
    try:
        queue_pre_land(
            fixture,
            completion=base.state(
                is_flying=False,
                hl_control_active=False,
                hl_traj_finished=True,
            ),
        )
        result = transport.send_controlled_landing()
        require(result.accepted, "zero firmware status accepts exact landing")
        command, group, height, relative, yaw, current_yaw, velocity = unpack_land(fixture)
        require(command == 10 and group == 0, "exact command-10 single-Crazyflie header")
        require(abs(height - 0.8) < 1e-6 and relative is True, "landing descent derives exact AST takeoff height")
        require(yaw == 0.0 and current_yaw is True, "terminal landing preserves current yaw")
        require(abs(velocity - 0.5) < 1e-6, "terminal landing uses explicit safe-default velocity")
        require(
            fixture.domain.phase == execution.INACTIVE,
            "accepted landing becomes inactive only after #264 completion evidence",
        )
        observed = fixture.supervisor_observed
        require(
            any(getattr(item, "is_flying", None) is False for item in observed),
            "fresh landing completion must observe non-flying state",
        )
    finally:
        fixture.close()


def test_positive_ack_without_completion_requires_recovery() -> None:
    fixture, transport = make_fixture("landing-completion-fault")
    try:
        queue_pre_land(
            fixture,
            completion=base.state(blocking_fault=True),
        )
        expect_error(
            transport.send_controlled_landing,
            Exception,
            "blocking supervisor fault",
        )
        require(len(fixture.cf.send_calls) == 1, "accepted but unproven landing is never resent")
        require(
            fixture.domain.phase == execution.RECOVERY_REQUIRED,
            "uncertain landing completion poisons ordinary effect eligibility",
        )
    finally:
        fixture.close()


def test_definitive_rejection_does_not_complete_or_retry() -> None:
    fixture, transport = make_fixture("landing-reject", reply_status=17)
    try:
        queue_pre_land(fixture)
        result = transport.send_controlled_landing()
        require(not result.accepted and result.status == 17, "non-zero firmware reply is definitive rejection")
        require(len(fixture.cf.send_calls) == 1, "definitive rejection remains one-shot")
        require(
            fixture.domain.phase == execution.FLYING,
            "definitive landing rejection restores exact prior flying phase",
        )
    finally:
        fixture.close()


def test_ack_timeout_is_ambiguous_and_never_retried() -> None:
    fixture, transport = make_fixture("landing-timeout", reply_status=None)
    try:
        queue_pre_land(fixture)
        expect_error(
            lambda: transport.send_controlled_landing(reply_timeout_seconds=0.02),
            Exception,
            "timeout",
        )
        require(len(fixture.cf.send_calls) == 1, "ambiguous landing emits exactly once")
        require(fixture.ack.poisoned, "ambiguous landing acknowledgement poisons epoch")
        require(
            fixture.domain.phase == execution.RECOVERY_REQUIRED,
            "ambiguous emitted landing requires recovery",
        )
    finally:
        fixture.close()


def test_changed_current_program_blocks_before_landing_effect() -> None:
    fixture, transport = make_fixture("landing-binding")
    try:
        fixture.current_binding = teacher.PhysicalRunBinding(
            profile_id=fixture.binding.profile_id,
            ast_binding=json.dumps(
                {
                    "program": [
                        {"height_m": 0.7, "kind": "takeoff"},
                        {"kind": "land"},
                    ],
                    "semantics": "webeeblocks-ast-v1",
                    "version": 1,
                },
                separators=(",", ":"),
                sort_keys=True,
            ),
            connection_epoch=fixture.binding.connection_epoch,
        )
        queue_pre_land(fixture)
        expect_error(
            transport.send_controlled_landing,
            landing_transport.ControlledLandingTransportError,
            "current-program re-assertion",
        )
        require(not fixture.cf.send_calls, "changed current program prevents landing emission")
        require(fixture.domain.phase == execution.FLYING, "pre-effect provenance failure preserves flying")
    finally:
        fixture.close()


def test_direct_importable_landing_core_has_no_positive_provenance_path() -> None:
    fixture, _transport = make_fixture("landing-unbound")
    try:
        direct = landing_transport.TrustedControlledLandingTransport(
            connection_epoch_reader=fixture.epoch,
            **fixture.kwargs,
        )
        queue_pre_land(fixture)
        expect_error(
            direct.send_controlled_landing,
            base.transport.SetpointHlTransportError,
            "trusted #283 physical host",
        )
        require(not fixture.cf.send_calls, "unbound controlled landing core cannot emit")
    finally:
        fixture.close()


def test_source_has_no_stop_retry_or_caller_landing_surface() -> None:
    source = (PHYSICAL / "controlled_landing_transport.py").read_text(encoding="utf-8")
    for forbidden in (
        "COMMAND_STOP",
        ".stop(",
        "HighLevelCommander(",
        "expected_reply=",
        "resend",
        "landing_height",
        "caller_height",
        "caller_velocity",
    ):
        require(forbidden not in source, "controlled landing leaked forbidden surface: " + forbidden)
    require(
        "add_callback(setpoint_hl_transport._SETPOINT_HL_PORT, on_reply)" in source
        and "send_packet(packet)" in source,
        "landing callback registration and one plain send must remain explicit",
    )


def main() -> int:
    test_accepted_landing_requires_fresh_nonflying_completion()
    test_positive_ack_without_completion_requires_recovery()
    test_definitive_rejection_does_not_complete_or_retry()
    test_ack_timeout_is_ambiguous_and_never_retried()
    test_changed_current_program_blocks_before_landing_effect()
    test_direct_importable_landing_core_has_no_positive_provenance_path()
    test_source_has_no_stop_retry_or_caller_landing_surface()
    print(
        "PASS trusted terminal landing transport derives command 10 from exact AST provenance, "
        "emits once under the shared physical authority domain, and requires fresh #264 completion"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

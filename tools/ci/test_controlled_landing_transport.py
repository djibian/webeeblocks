#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / "tools" / "ci"
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(CI))
sys.path.insert(0, str(PHYSICAL))

import controlled_landing_transport as controlled  # noqa: E402
import physical_execution_domain as execution  # noqa: E402
import serve_reference_capabilities as capability_bridge  # noqa: E402
import teacher_run_authorization as teacher  # noqa: E402
import test_physical_setpoint_hl_transport as base  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def canonical_ast() -> str:
    return json.dumps(
        {
            "program": [
                {"height_m": 0.8, "kind": "takeoff"},
                {"angle_deg": -25, "kind": "turn"},
                {"direction": "forward", "distance_m": 0.3, "kind": "move"},
                {"kind": "land"},
            ],
            "semantics": "webeeblocks-ast-v1",
            "version": 1,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def expect_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except Exception as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError(f"expected error containing {pattern!r}")


class TestHostBoundLandingTransport(controlled.TrustedControlledLandingTransport):
    """Test analogue of the lexical subclass in physical_run_activation.py."""

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
            raise controlled.ControlledLandingTransportError(
                "integrated #278/#249 current-program re-assertion failed"
            ) from exc
        if type(evidence) is not capability_bridge.CurrentProgramPreflightEvidence:
            raise controlled.ControlledLandingTransportError(
                "invalid current-program evidence"
            )
        if evidence.execution_authority is not False:
            raise controlled.ControlledLandingTransportError(
                "current-program evidence became authority"
            )
        if (
            evidence.profile_id != binding.profile_id
            or evidence.ast_binding != binding.ast_binding
            or evidence.connection_epoch != binding.connection_epoch
        ):
            raise controlled.ControlledLandingTransportError(
                "current-program binding mismatch"
            )
        return binding


def canonicalize_fixture(fixture: base.Fixture):
    binding = teacher.PhysicalRunBinding(
        profile_id="activity-1",
        ast_binding=canonical_ast(),
        connection_epoch=fixture.epoch(),
    )
    authorizer = teacher.TrustedTeacherAuthorizer()
    authorization = authorizer.authorize_run(binding, lambda _binding: True)
    fixture.current_binding = binding
    fixture.supervisor_reads.clear()
    fixture.supervisor_reads.extend(
        [
            base.state(hl_traj_finished=True),
            base.state(hl_traj_finished=True),
            base.state(
                is_flying=False,
                hl_control_active=False,
                hl_traj_finished=True,
            ),
        ]
    )
    kwargs = dict(fixture.kwargs)
    kwargs["teacher_authorization"] = authorization
    kwargs["connection_epoch_reader"] = fixture.epoch
    return binding, authorization, kwargs


def make_transport(fixture: base.Fixture):
    _binding, _authorization, kwargs = canonicalize_fixture(fixture)
    return TestHostBoundLandingTransport(bridge=fixture.bridge, **kwargs)


def unpack_landing(cf: base.FakeCrazyflie):
    require(len(cf.send_calls) == 1, "landing must emit exactly one packet")
    args, kwargs = cf.send_calls[0]
    require(len(args) == 1 and not kwargs, "landing send has no retry/alternate kwargs")
    return struct.unpack("<BBf?f?f", bytes(args[0].data))


# Shared #276 packet construction stays pinned but must not use its GO_TO-only
# validator. The fake still enforces callback-before-send and no retry kwargs.
base.transport._default_packet_factory = lambda request: base.Packet(request)
controlled._DEFAULT_REPLY_TIMEOUT_SECONDS = 0.02
controlled._LANDING_COMPLETION_TIMEOUT_SECONDS = 0.04


def test_importable_core_has_no_positive_provenance_path() -> None:
    cf = base.FakeCrazyflie(reply_status=0)
    fixture = base.Fixture("landing-unbound", cf)
    try:
        _binding, _authorization, kwargs = canonicalize_fixture(fixture)
        transport = controlled.TrustedControlledLandingTransport(**kwargs)
        expect_error(transport.send_controlled_landing, "trusted #283 physical host")
        require(not cf.send_calls, "unbound landing core must not emit")
    finally:
        fixture.close()


def test_exact_bound_landing_send_and_completion() -> None:
    cf = base.FakeCrazyflie(reply_status=0)
    fixture = base.Fixture("landing-success", cf)
    try:
        transport = make_transport(fixture)
        result = transport.send_controlled_landing()
        require(result.accepted, "zero firmware result accepts exact landing")
        command, group, height, relative, yaw, current_yaw, velocity = unpack_landing(cf)
        require((command, group) == (10, 0), "landing uses exact command-10 header")
        require(abs(height - 0.8) < 1e-6, "descent derives teacher-bound takeoff height")
        require(relative is True, "command-10 landing is relative positive-down")
        require(yaw == 0.0 and current_yaw is True, "landing preserves current yaw")
        require(abs(velocity - 0.5) < 1e-6, "landing uses explicit safe-default velocity")
        require(
            fixture.domain.phase == execution.INACTIVE,
            "#264 completion plus private permit establishes inactive state",
        )
        require(
            any(
                getattr(item, "is_flying", None) is False
                and getattr(item, "hl_control_active", None) is False
                and getattr(item, "hl_traj_finished", None) is True
                for item in fixture.supervisor_observed
            ),
            "positive acknowledgement alone is insufficient without fresh completion evidence",
        )
    finally:
        fixture.close()


def test_definitive_rejection_does_not_complete_landing() -> None:
    cf = base.FakeCrazyflie(reply_status=7)
    fixture = base.Fixture("landing-reject", cf)
    try:
        transport = make_transport(fixture)
        result = transport.send_controlled_landing()
        require(result.accepted is False, "non-zero firmware status is definitive rejection")
        require(len(cf.send_calls) == 1, "definitive rejection still has one exact send")
        require(
            fixture.domain.phase == execution.FLYING,
            "definitive rejection restores prior flying state",
        )
    finally:
        fixture.close()


def test_current_program_change_blocks_before_emission() -> None:
    cf = base.FakeCrazyflie(reply_status=0)
    fixture = base.Fixture("landing-binding", cf)
    try:
        transport = make_transport(fixture)
        fixture.current_binding = teacher.PhysicalRunBinding(
            profile_id=transport.teacher_binding.profile_id,
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
            connection_epoch=transport.teacher_binding.connection_epoch,
        )
        expect_error(transport.send_controlled_landing, "re-assertion failed")
        require(not cf.send_calls, "changed exact program must block before landing effect")
        require(fixture.domain.phase == execution.FLYING, "pre-effect failure stays retryable")
    finally:
        fixture.close()


def test_acknowledgement_ambiguity_poisoning_requires_recovery() -> None:
    cf = base.FakeCrazyflie(reply_status=None)
    fixture = base.Fixture("landing-ack-unknown", cf)
    try:
        transport = make_transport(fixture)
        expect_error(transport.send_controlled_landing, "acknowledgement timeout")
        require(len(cf.send_calls) == 1, "ambiguous landing is never retried")
        require(
            fixture.domain.phase == execution.RECOVERY_REQUIRED,
            "unknown post-send acknowledgement requires recovery",
        )
    finally:
        fixture.close()


def test_completion_uncertainty_poisoning_requires_recovery() -> None:
    cf = base.FakeCrazyflie(reply_status=0)
    fixture = base.Fixture("landing-completion-unknown", cf)
    try:
        transport = make_transport(fixture)
        fixture.supervisor_reads.clear()
        fixture.supervisor_reads.extend(
            [
                base.state(hl_traj_finished=True),
                base.state(hl_traj_finished=True),
                base.state(
                    is_flying=True,
                    hl_control_active=True,
                    hl_traj_finished=False,
                ),
            ]
        )
        expect_error(transport.send_controlled_landing, "timed out")
        require(len(cf.send_calls) == 1, "accepted but uncertain landing is never retried")
        require(
            fixture.domain.phase == execution.RECOVERY_REQUIRED,
            "unknown accepted landing completion requires recovery",
        )
    finally:
        fixture.close()


def test_landing_surface_accepts_no_caller_semantics() -> None:
    cf = base.FakeCrazyflie(reply_status=0)
    fixture = base.Fixture("landing-surface", cf)
    try:
        transport = make_transport(fixture)
        try:
            transport.send_controlled_landing(height_m=0.1)
        except TypeError:
            pass
        else:
            raise AssertionError("caller-selected landing height entered trusted effect API")
        require(not cf.send_calls, "rejected caller semantics must remain effect-free")

        source = (PHYSICAL / "controlled_landing_transport.py").read_text(encoding="utf-8")
        require("COMMAND_STOP" not in source, "normal landing must never use STOP/motor cut")
        require("expected_reply=" not in source, "landing transport must not enable cflib retries")
    finally:
        fixture.close()


def main() -> int:
    test_importable_core_has_no_positive_provenance_path()
    test_exact_bound_landing_send_and_completion()
    test_definitive_rejection_does_not_complete_landing()
    test_current_program_change_blocks_before_emission()
    test_acknowledgement_ambiguity_poisoning_requires_recovery()
    test_completion_uncertainty_poisoning_requires_recovery()
    test_landing_surface_accepts_no_caller_semantics()
    print(
        "PASS controlled physical landing: exact command-10 AST derivation, callback-before-one-send, "
        "definitive rejection without cursor authority, and #264/#279 completion-to-inactive fail closed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

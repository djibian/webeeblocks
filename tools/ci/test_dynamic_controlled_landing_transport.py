#!/usr/bin/env python3
from __future__ import annotations

from math import isclose
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / "tools" / "ci"
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(CI))
sys.path.insert(0, str(PHYSICAL))

import dynamic_controlled_landing_transport as subject  # noqa: E402
import high_level_timing as timing  # noqa: E402
import serve_reference_capabilities as capability_bridge  # noqa: E402
import takeoff_command  # noqa: E402
import teacher_run_authorization as teacher  # noqa: E402
import test_physical_controlled_landing_transport as landing_test  # noqa: E402
import test_physical_setpoint_hl_transport as base  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def canonical_ast(takeoff_height_m: float) -> str:
    return takeoff_command._canonical_json(
        {
            "program": [
                {"height_m": takeoff_height_m, "kind": "takeoff"},
                {"kind": "land"},
            ],
            "semantics": "webeeblocks-ast-v1",
            "version": 1,
        }
    )


class TestHostBoundDynamicTransport(subject.TrustedDynamicControlledLandingTransport):
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
            raise subject.DynamicControlledLandingTransportError(
                "integrated current-program re-assertion failed"
            ) from exc
        if type(evidence) is not capability_bridge.CurrentProgramPreflightEvidence:
            raise subject.DynamicControlledLandingTransportError(
                "invalid current-program evidence"
            )
        if evidence.execution_authority is not False:
            raise subject.DynamicControlledLandingTransportError(
                "current-program evidence became authority"
            )
        if (
            evidence.profile_id != binding.profile_id
            or evidence.ast_binding != binding.ast_binding
            or evidence.connection_epoch != binding.connection_epoch
        ):
            raise subject.DynamicControlledLandingTransportError(
                "current-program binding mismatch"
            )
        return binding


def make_fixture(label: str, *, takeoff_height_m: float = 0.8, reply_status: int | None = 0):
    cf = base.FakeCrazyflie(reply_status=reply_status)
    fixture = base.Fixture(label, cf)
    binding = teacher.PhysicalRunBinding(
        profile_id="activity-dynamic-landing",
        ast_binding=canonical_ast(takeoff_height_m),
        connection_epoch=fixture.epoch(),
    )
    authorizer = teacher.TrustedTeacherAuthorizer()
    authorization = authorizer.authorize_run(binding, lambda _binding: True)
    fixture.binding = binding
    fixture.current_binding = binding
    fixture.authorization = authorization
    fixture.kwargs["teacher_authorization"] = authorization
    transport = TestHostBoundDynamicTransport(
        bridge=fixture.bridge,
        connection_epoch_reader=fixture.epoch,
        **fixture.kwargs,
    )
    return fixture, transport


def unpack_last_land(fixture):
    require(fixture.cf.send_calls, "dynamic landing must emit one terminal packet")
    data = bytes(fixture.cf.send_calls[-1][0][0].data)
    return struct.unpack("<BBf?f?f", data)


def test_initial_altitude_is_derived_only_from_exact_teacher_ast() -> None:
    fixture, transport = make_fixture("dynamic-root", takeoff_height_m=0.8)
    try:
        require(
            transport.initial_nominal_altitude_m == 0.8,
            "dynamic landing root did not derive exact teacher-bound takeoff height",
        )
        require(
            transport.nominal_altitude_m == 0.8,
            "runtime nominal altitude did not start at exact preflight-proven takeoff",
        )
    finally:
        fixture.close()


def test_vertical_completion_advances_runtime_nominal_altitude() -> None:
    fixture, transport = make_fixture("dynamic-altitude")
    try:
        result = transport.send_vertical_move(
            direction="up",
            distance_m=0.3,
            timing_policy=timing.HighLevelTimingPolicy(),
        )
        require(result.accepted is True, "accepted dynamic vertical effect required")
        require(
            isclose(transport.nominal_altitude_m, 1.1, rel_tol=0, abs_tol=1e-9),
            "accepted vertical effect did not advance host-owned nominal altitude",
        )
    finally:
        fixture.close()


def test_rejected_or_out_of_bounds_vertical_does_not_advance_state() -> None:
    fixture, transport = make_fixture("dynamic-reject", reply_status=7)
    try:
        result = transport.send_vertical_move(
            direction="up",
            distance_m=0.3,
            timing_policy=timing.HighLevelTimingPolicy(),
        )
        require(result.accepted is False, "nonzero firmware status must reject vertical effect")
        require(
            transport.nominal_altitude_m == 0.8,
            "rejected vertical effect changed host-owned nominal altitude",
        )
    finally:
        fixture.close()

    fixture, transport = make_fixture("dynamic-bound", takeoff_height_m=1.4)
    try:
        try:
            transport.send_vertical_move(
                direction="up",
                distance_m=0.2,
                timing_policy=timing.HighLevelTimingPolicy(),
            )
        except subject.DynamicControlledLandingTransportError as exc:
            require("0.2-1.5" in str(exc), "runtime altitude defense failed for wrong reason")
        else:
            raise AssertionError("runtime vertical effect escaped preflight-equivalent altitude bound")
        require(not fixture.cf.send_calls, "out-of-bounds runtime vertical request emitted a packet")
        require(transport.nominal_altitude_m == 1.4, "rejected runtime bound changed nominal altitude")
    finally:
        fixture.close()


def test_terminal_landing_uses_completed_dynamic_path_altitude() -> None:
    fixture, transport = make_fixture("dynamic-landing")
    try:
        vertical = transport.send_vertical_move(
            direction="up",
            distance_m=0.3,
            timing_policy=timing.HighLevelTimingPolicy(),
        )
        require(vertical.accepted is True, "dynamic vertical prefix must complete")
        require(isclose(transport.nominal_altitude_m, 1.1, abs_tol=1e-9), "dynamic prefix altitude")

        landing_test.queue_pre_land(
            fixture,
            completion=base.state(
                is_flying=False,
                hl_control_active=False,
                hl_traj_finished=True,
            ),
        )
        result = transport.send_controlled_landing()
        require(result.accepted is True, "dynamic terminal landing acknowledgement")
        command, group, descent, relative, yaw, current_yaw, velocity = unpack_last_land(fixture)
        require((command, group) == (10, 0), "dynamic terminal landing command/header changed")
        require(
            isclose(descent, 1.1, rel_tol=0, abs_tol=1e-6) and relative is True,
            "terminal descent did not derive from definitively completed selected vertical path",
        )
        require(yaw == 0.0 and current_yaw is True, "dynamic landing must preserve current yaw")
        require(isclose(velocity, 0.5, abs_tol=1e-6), "dynamic landing safe velocity changed")
        require(
            fixture.domain.phase == base.execution.INACTIVE,
            "dynamic landing must still require fresh controlled-landing completion",
        )
    finally:
        fixture.close()


def main() -> int:
    test_initial_altitude_is_derived_only_from_exact_teacher_ast()
    test_vertical_completion_advances_runtime_nominal_altitude()
    test_rejected_or_out_of_bounds_vertical_does_not_advance_state()
    test_terminal_landing_uses_completed_dynamic_path_altitude()
    print(
        "PASS dynamic controlled landing: exact teacher AST owns initial Z, selected vertical "
        "completion owns runtime Z, terminal command-10 uses completed runtime altitude"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

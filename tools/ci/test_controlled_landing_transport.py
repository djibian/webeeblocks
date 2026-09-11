#!/usr/bin/env python3
from __future__ import annotations

import json
from math import isclose
from pathlib import Path
from types import SimpleNamespace
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / "tools" / "ci"
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(CI))
sys.path.insert(0, str(PHYSICAL))

import controlled_landing_transport as landing_transport  # noqa: E402
import landing_completion  # noqa: E402
import physical_execution_domain as execution  # noqa: E402
import teacher_run_authorization as teacher  # noqa: E402
import test_physical_setpoint_hl_transport as base  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except Exception as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError(f"expected failure containing {pattern!r}")


def canonical(height_m: float = 0.8) -> str:
    return json.dumps(
        {
            "program": [
                {"height_m": height_m, "kind": "takeoff"},
                {"kind": "land"},
            ],
            "semantics": "webeeblocks-ast-v1",
            "version": 1,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


class HostBoundLandingTransport(landing_transport.TrustedControlledLandingTransport):
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
                "integrated current-program re-assertion failed"
            ) from exc
        if type(evidence) is not base.capability_bridge.CurrentProgramPreflightEvidence:
            raise landing_transport.ControlledLandingTransportError(
                "invalid current-program evidence"
            )
        if (
            evidence.execution_authority is not False
            or evidence.profile_id != binding.profile_id
            or evidence.ast_binding != binding.ast_binding
            or evidence.connection_epoch != binding.connection_epoch
        ):
            raise landing_transport.ControlledLandingTransportError(
                "current-program binding mismatch"
            )
        return binding


class CompletionStub:
    def __init__(self, epoch: str, *, error: Exception | None = None) -> None:
        self.bound_connection_epoch = epoch
        self.error = error
        self.capture_calls = 0
        self.await_calls = 0
        self.baseline = landing_completion.PreLandingFlightEvidence(epoch, 0)

    def capture_pre_land_flight(self, *, timeout_seconds: float = 0.2):
        del timeout_seconds
        self.capture_calls += 1
        return self.baseline

    def await_completion(self, baseline, **kwargs):
        del kwargs
        self.await_calls += 1
        require(baseline is self.baseline, "landing completion must consume exact baseline")
        if self.error is not None:
            raise self.error
        return landing_completion.LandingCompletionEvidence(
            connection_epoch=self.bound_connection_epoch,
            observations=1,
            supervisor_state=SimpleNamespace(
                blocking_fault=False,
                is_flying=False,
                hl_control_active=False,
                hl_traj_finished=True,
            ),
        )


def make_transport(label: str, cf: base.FakeCrazyflie, *, completion_error=None):
    fixture = base.Fixture(label, cf)
    binding = teacher.PhysicalRunBinding(
        profile_id="activity-1",
        ast_binding=canonical(),
        connection_epoch=fixture.epoch(),
    )
    authorizer = teacher.TrustedTeacherAuthorizer()
    authorization = authorizer.authorize_run(binding, lambda exact: exact == binding)
    fixture.current_binding = binding
    kwargs = dict(fixture.kwargs)
    kwargs["teacher_authorization"] = authorization
    transport = HostBoundLandingTransport(
        bridge=fixture.bridge,
        connection_epoch_reader=fixture.epoch,
        **kwargs,
    )
    completion = CompletionStub(fixture.epoch(), error=completion_error)
    transport._landing_observer = completion
    return fixture, transport, completion


def unpack_landing(cf: base.FakeCrazyflie):
    require(len(cf.send_calls) == 1, "terminal landing must emit exactly one packet")
    data = bytes(cf.send_calls[0][0][0].data)
    return struct.unpack("<BBf?f?f", data)


landing_transport._DEFAULT_REPLY_TIMEOUT_SECONDS = 0.01


def test_accepted_exact_ast_landing_completes_inactive() -> None:
    cf = base.FakeCrazyflie(reply_status=0)
    fixture, transport, completion = make_transport("landing-accepted", cf)
    try:
        result = transport.send_controlled_landing()
        require(result.accepted is True, "zero firmware status must be accepted")
        require(fixture.domain.phase == execution.INACTIVE, "fresh #264 completion must establish inactive")
        require(completion.capture_calls == 1, "one pre-land flight baseline is required")
        require(completion.await_calls == 1, "positive acknowledgement must require landing completion")
        command, group, height, relative, yaw, current_yaw, velocity = unpack_landing(cf)
        require(command == 10 and group == 0, "only pinned command-10 single-Crazyflie landing is allowed")
        require(isclose(height, 0.8, rel_tol=0, abs_tol=1e-6), "landing descent must derive exact takeoff height")
        require(relative is True, "landing command must use relative downward distance")
        require(isclose(yaw, 0.0, rel_tol=0, abs_tol=1e-9) and current_yaw is True, "landing must preserve current yaw")
        require(isclose(velocity, 0.5, rel_tol=0, abs_tol=1e-6), "landing velocity must be explicit pinned safe default")
        try:
            transport.send_controlled_landing(height_m=0.2)
        except TypeError:
            pass
        else:
            raise AssertionError("caller-selected landing semantics unexpectedly exist")
    finally:
        fixture.close()


def test_definitive_rejection_restores_flying_without_completion() -> None:
    cf = base.FakeCrazyflie(reply_status=7)
    fixture, transport, completion = make_transport("landing-rejected", cf)
    try:
        result = transport.send_controlled_landing()
        require(result.accepted is False and result.status == 7, "non-zero firmware status must be definitive rejection")
        require(fixture.domain.phase == execution.FLYING, "definitive rejection must restore prior flying phase")
        require(completion.capture_calls == 1, "fresh pre-land evidence remains required before emission")
        require(completion.await_calls == 0, "rejected landing must not consume completion authority")
        require(len(cf.send_calls) == 1, "rejected landing must not be retried")
    finally:
        fixture.close()


def test_acknowledgement_ambiguity_poisoned_without_retry() -> None:
    cf = base.FakeCrazyflie(reply_status=None)
    fixture, transport, completion = make_transport("landing-timeout", cf)
    try:
        expect_error(transport.send_controlled_landing, "acknowledgement timeout")
        require(fixture.domain.phase == execution.RECOVERY_REQUIRED, "ambiguous emitted landing must require recovery")
        require(fixture.ack.poisoned is True, "ambiguous landing acknowledgement must poison epoch freshness")
        require(completion.await_calls == 0, "unknown acknowledgement cannot enter completion")
        require(len(cf.send_calls) == 1, "ambiguous landing must never retry")
    finally:
        fixture.close()


def test_completion_uncertainty_requires_recovery() -> None:
    cf = base.FakeCrazyflie(reply_status=0)
    fixture, transport, completion = make_transport(
        "landing-completion-uncertain",
        cf,
        completion_error=landing_completion.LandingCompletionError("completion unavailable"),
    )
    try:
        expect_error(transport.send_controlled_landing, "completion unavailable")
        require(completion.await_calls == 1, "accepted landing must consume completion observer")
        require(fixture.domain.phase == execution.RECOVERY_REQUIRED, "uncertain accepted landing completion must require recovery")
        require(len(cf.send_calls) == 1, "completion uncertainty must not retry physical landing")
    finally:
        fixture.close()


def main() -> int:
    test_accepted_exact_ast_landing_completes_inactive()
    test_definitive_rejection_restores_flying_without_completion()
    test_acknowledgement_ambiguity_poisoned_without_retry()
    test_completion_uncertainty_requires_recovery()
    print(
        "PASS controlled terminal landing derives command 10 from the exact program, "
        "sends once after callback registration, distinguishes rejection/ambiguity, "
        "and requires fresh completion before inactive"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

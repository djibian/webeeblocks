#!/usr/bin/env python3
from __future__ import annotations

import inspect
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(PHYSICAL))

import physical_execution_domain as execution  # noqa: E402
import physical_program_sequence as sequence  # noqa: E402
import serve_reference_capabilities as capability_bridge  # noqa: E402
import teacher_run_authorization as teacher  # noqa: E402
import terminal_landing_transport as landing_transport  # noqa: E402

# Reuse the exact fake radio/session/supervisor seams already exercised by the
# integrated #276 transport contract. Importing this test module does not execute
# its main() because of its normal __main__ guard.
import test_physical_setpoint_hl_transport as base  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def canonical(program: list[dict[str, object]]) -> str:
    return json.dumps(
        {
            "program": program,
            "semantics": "webeeblocks-ast-v1",
            "version": 1,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def expect_error(callable_, pattern: str) -> Exception:
    try:
        callable_()
    except Exception as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return exc
    raise AssertionError(f"expected error containing {pattern!r}")


class HostBoundTerminalTransport(landing_transport.TrustedTerminalLandingTransport):
    """Test analogue of physical_run_activation's lexical landing subclass."""

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
            raise landing_transport.TerminalLandingTransportError(
                "integrated #278/#249 current-program re-assertion failed"
            ) from exc
        if type(evidence) is not capability_bridge.CurrentProgramPreflightEvidence:
            raise landing_transport.TerminalLandingTransportError(
                "invalid current-program evidence"
            )
        if evidence.execution_authority is not False:
            raise landing_transport.TerminalLandingTransportError(
                "current-program evidence became authority"
            )
        if (
            evidence.profile_id != binding.profile_id
            or evidence.ast_binding != binding.ast_binding
            or evidence.connection_epoch != binding.connection_epoch
        ):
            raise landing_transport.TerminalLandingTransportError(
                "current-program binding mismatch"
            )
        return binding


def simple_ast() -> str:
    return canonical(
        [
            {"kind": "takeoff", "height_m": 0.8},
            {"kind": "land"},
        ]
    )


def prepare(label: str, *, ast_binding: str | None = None, reply_status: int | None = 0):
    ast = ast_binding or simple_ast()
    cf = base.FakeCrazyflie(reply_status=reply_status)
    fixture = base.Fixture(label, cf)
    binding = teacher.PhysicalRunBinding(
        profile_id="activity-1",
        ast_binding=ast,
        connection_epoch=fixture.epoch(),
    )
    authorization = teacher.TrustedTeacherAuthorizer().authorize_run(
        binding,
        lambda _binding: True,
    )
    fixture.current_binding = binding
    kwargs = dict(fixture.kwargs)
    kwargs["teacher_authorization"] = authorization
    program_sequence = sequence.PhysicalProgramSequence(ast)
    transport = HostBoundTerminalTransport(
        bridge=fixture.bridge,
        program_sequence=program_sequence,
        **kwargs,
    )
    return fixture, program_sequence, transport


def queue_landing_success(fixture: base.Fixture) -> None:
    fixture.supervisor_reads.clear()
    fixture.supervisor_reads.extend(
        [
            base.state(is_flying=True, hl_control_active=True, hl_traj_finished=True),
            base.state(is_flying=True, hl_control_active=True, hl_traj_finished=True),
            base.state(is_flying=False, hl_control_active=False, hl_traj_finished=True),
        ]
    )


def unpack_land(cf: base.FakeCrazyflie):
    require(len(cf.send_calls) == 1, "terminal landing must emit exactly one packet")
    packet = cf.send_calls[0][0][0]
    return struct.unpack("<BBf?f?f", bytes(packet.data))


def test_exact_claim_emits_command_10_then_requires_completion() -> None:
    fixture, program, transport = prepare("land-ok")
    try:
        claim = program.reserve_terminal_landing()
        queue_landing_success(fixture)
        result = transport.send_terminal_landing(claim)
        require(result.accepted, "zero firmware result must accept exact terminal landing")
        command, group, descent, relative, yaw_value, current_yaw, velocity = unpack_land(
            fixture.cf
        )
        require((command, group) == (10, 0), "exact firmware command-10 header required")
        require(abs(descent - 0.8) < 1e-6, "landing distance must come from exact takeoff")
        require(relative is True, "landing distance must use firmware relative semantics")
        require(abs(yaw_value) < 1e-9 and current_yaw is True, "landing must preserve yaw")
        require(abs(velocity - 0.5) < 1e-6, "landing must use pinned safe velocity")
        require(
            fixture.domain.phase == execution.INACTIVE,
            "acknowledgement alone is insufficient; #264 completion must make domain inactive",
        )
        require(
            program.landing_for_claim(claim).index == 1,
            "transport must preserve the exact pending sequence claim for host completion",
        )
        program.complete_landing(claim)
        require(program.completed, "host may complete exact sequence only after causal landing")
    finally:
        fixture.close()


def test_no_terminal_claim_or_caller_landing_parameters_can_emit() -> None:
    fixture, program, transport = prepare("land-claim")
    try:
        expect_error(
            lambda: transport.send_terminal_landing(object()),
            "terminal landing claim",
        )
        require(not fixture.cf.send_calls, "forged landing claim must fail before effect")

        claim = program.reserve_terminal_landing()
        try:
            transport.send_terminal_landing(claim, height_m=0.1)
        except TypeError:
            pass
        else:
            raise AssertionError("caller-selected landing height unexpectedly entered API")
        require(not fixture.cf.send_calls, "caller semantic substitution must not emit")
        require(
            list(inspect.signature(transport.send_terminal_landing).parameters) == ["claim"],
            "terminal landing effect surface must expose only the opaque exact claim",
        )
        expect_error(
            lambda: transport.send_turn(angle_deg=10, timing_policy=object()),
            "cannot emit ordinary",
        )
        require(not fixture.cf.send_calls, "terminal-only transport must reject motion surface")
    finally:
        fixture.close()


def test_current_program_change_blocks_before_landing_effect() -> None:
    fixture, program, transport = prepare("land-binding")
    try:
        claim = program.reserve_terminal_landing()
        fixture.current_binding = teacher.PhysicalRunBinding(
            profile_id="activity-1",
            ast_binding=canonical(
                [
                    {"kind": "takeoff", "height_m": 0.9},
                    {"kind": "land"},
                ]
            ),
            connection_epoch=fixture.epoch(),
        )
        expect_error(
            lambda: transport.send_terminal_landing(claim),
            "current-program re-assertion",
        )
        require(not fixture.cf.send_calls, "changed browser program must prevent landing")
        require(fixture.domain.phase == execution.FLYING, "pre-effect failure remains flying")
    finally:
        fixture.close()


def test_definitive_rejection_preserves_exact_landing_for_retry() -> None:
    fixture, program, transport = prepare("land-reject", reply_status=17)
    try:
        claim = program.reserve_terminal_landing()
        fixture.supervisor_reads.clear()
        fixture.supervisor_reads.extend(
            [
                base.state(is_flying=True, hl_control_active=True, hl_traj_finished=True),
                base.state(is_flying=True, hl_control_active=True, hl_traj_finished=True),
            ]
        )
        result = transport.send_terminal_landing(claim)
        require(not result.accepted, "non-zero firmware status must be definitive rejection")
        require(len(fixture.cf.send_calls) == 1, "rejected landing still has exactly one send")
        require(fixture.domain.phase == execution.FLYING, "definitive rejection restores flying")
        require(program.landing_for_claim(claim).index == 1, "rejection must not advance sequence")
        program.release_unemitted(claim)
        retry = program.reserve_terminal_landing()
        require(program.landing_for_claim(retry).index == 1, "same exact landing remains next")
    finally:
        fixture.close()


def test_completion_uncertainty_forces_recovery_and_no_retry() -> None:
    fixture, program, transport = prepare("land-timeout")
    old_total = landing_transport._COMPLETION_TIMEOUT_SECONDS
    old_read = landing_transport._COMPLETION_READ_TIMEOUT_SECONDS
    old_poll = landing_transport._COMPLETION_POLL_SECONDS
    try:
        claim = program.reserve_terminal_landing()
        fixture.supervisor_reads.clear()
        fixture.supervisor_reads.extend(
            [
                base.state(is_flying=True, hl_control_active=True, hl_traj_finished=True),
                base.state(is_flying=True, hl_control_active=True, hl_traj_finished=True),
            ]
        )
        landing_transport._COMPLETION_TIMEOUT_SECONDS = 0.01
        landing_transport._COMPLETION_READ_TIMEOUT_SECONDS = 0.002
        landing_transport._COMPLETION_POLL_SECONDS = 0.001
        expect_error(
            lambda: transport.send_terminal_landing(claim),
            "timed out",
        )
        require(len(fixture.cf.send_calls) == 1, "ambiguous completion must never resend landing")
        require(
            fixture.domain.phase == execution.RECOVERY_REQUIRED,
            "accepted landing without #264 completion must force recovery",
        )
        require(program.landing_for_claim(claim).index == 1, "uncertain landing cannot advance sequence")
    finally:
        landing_transport._COMPLETION_TIMEOUT_SECONDS = old_total
        landing_transport._COMPLETION_READ_TIMEOUT_SECONDS = old_read
        landing_transport._COMPLETION_POLL_SECONDS = old_poll
        fixture.close()


def main() -> int:
    test_exact_claim_emits_command_10_then_requires_completion()
    test_no_terminal_claim_or_caller_landing_parameters_can_emit()
    test_current_program_change_blocks_before_landing_effect()
    test_definitive_rejection_preserves_exact_landing_for_retry()
    test_completion_uncertainty_forces_recovery_and_no_retry()
    print(
        "PASS trusted terminal landing is exact-program-bound, one-shot, "
        "completion-gated and fail-closed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

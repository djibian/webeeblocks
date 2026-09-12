#!/usr/bin/env python3
"""Trusted host adapter for one production causal physical run activation.

The running #283 host supplies the already host-validated profile/canonical-AST
binding, its one live reset-aware #278 bridge, the distinct launcher-installed
teacher socket and the shared #273 execution domain. The generic takeoff
lifecycle remains in ``production_takeoff_run``. The exact canonical AST is
validated against the integrated sequencing boundary before any reset or flight
effect; after exact takeoff has causally completed, the same sequence owns each
bounded horizontal/vertical move, turn, bottom Color LED effect, no-effect
wait/set_speed state and the one terminal controlled landing.

Importing this module performs no physical effect.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import socket
from time import monotonic, sleep

from color_led_transport import (
    ColorLedTransportError,
    TrustedBottomColorLedTransport,
)
from controlled_landing_transport import (
    ControlledLandingTransportError,
    TrustedControlledLandingTransport,
)
from high_level_timing import HighLevelTimingPolicy
from physical_execution_domain import FLYING, INACTIVE, PhysicalExecutionDomain
from physical_program_sequence import PhysicalProgramSequence, PhysicalProgramSequenceError
from post_reset_teacher_decision import PostResetTeacherDecisionChannel
from powered_session_authority import (
    TrustedPoweredSessionFactory,
    make_cflib_stm_deck_power_cycle,
)
from production_takeoff_run import ProductionTakeoffRunController
from serve_reference_capabilities import CurrentProgramPreflightEvidence
from supervisor_state import FreshSupervisorStateReader
from takeoff_transport import TakeoffTransportError, TrustedTakeoffTransport
from teacher_run_authorization import PhysicalRunBinding, TrustedTeacherAuthorizer
from yaw_observer import FreshYawObserver

_WAIT_SLICE_SECONDS = 0.05


class PhysicalRunActivationError(RuntimeError):
    """Fail-closed error for trusted production run activation composition."""


@dataclass(frozen=True, slots=True)
class _NoEffectStepResult:
    """Internal success marker for an exact program step that emitted no command."""

    accepted: bool = True
    emitted: bool = False


def _monotonic_value(clock) -> float:
    try:
        value = float(clock())
    except Exception as exc:
        raise PhysicalRunActivationError("physical wait monotonic clock is unavailable") from exc
    if not isfinite(value):
        raise PhysicalRunActivationError("physical wait monotonic clock is invalid")
    return value


def _require_exact_epoch(
    connection_epoch_reader,
    bound_epoch: str,
    *,
    context: str,
) -> None:
    try:
        current = connection_epoch_reader()
    except Exception as exc:
        raise PhysicalRunActivationError(context + " connection epoch is unavailable") from exc
    if current != bound_epoch:
        raise PhysicalRunActivationError("connection epoch changed during " + context)


def _execute_exact_wait(
    seconds: float,
    watchdog_guard: object,
    connection_epoch_reader,
    bound_epoch: str,
    *,
    clock=monotonic,
    sleeper=sleep,
) -> None:
    """Consume host time only; emit no Crazyflie command and mint no authority."""
    if not isinstance(seconds, float) or not isfinite(seconds) or seconds <= 0:
        raise PhysicalRunActivationError("exact physical wait duration is invalid")
    assert_live = getattr(watchdog_guard, "assert_live", None)
    if not callable(assert_live):
        raise PhysicalRunActivationError("physical wait requires live watchdog guard")
    if not callable(connection_epoch_reader) or not isinstance(bound_epoch, str) or not bound_epoch:
        raise PhysicalRunActivationError("physical wait requires exact connection epoch")
    if not callable(clock) or not callable(sleeper):
        raise PhysicalRunActivationError("physical wait timing primitives are unavailable")

    assert_live()
    _require_exact_epoch(
        connection_epoch_reader,
        bound_epoch,
        context="exact physical wait",
    )
    started = _monotonic_value(clock)
    deadline = started + seconds
    now = started

    while now < deadline:
        assert_live()
        _require_exact_epoch(
            connection_epoch_reader,
            bound_epoch,
            context="exact physical wait",
        )
        delay = min(_WAIT_SLICE_SECONDS, deadline - now)
        try:
            sleeper(delay)
        except Exception as exc:
            raise PhysicalRunActivationError("physical wait sleeper failed") from exc
        later = _monotonic_value(clock)
        if later <= now:
            raise PhysicalRunActivationError("physical wait monotonic clock did not advance")
        now = later

    assert_live()
    _require_exact_epoch(
        connection_epoch_reader,
        bound_epoch,
        context="exact physical wait",
    )


def _live_crazyflie(session: object) -> object:
    """Return the raw live cflib Crazyflie only inside the trusted host TCB."""
    scf = getattr(session, "_scf", None)
    if scf is None:
        raise PhysicalRunActivationError("trusted host has no live Crazyflie session")
    is_link_open = getattr(scf, "is_link_open", None)
    if not callable(is_link_open):
        raise PhysicalRunActivationError("trusted host link state is unavailable")
    try:
        live = is_link_open()
    except Exception as exc:
        raise PhysicalRunActivationError("trusted host link state is unavailable") from exc
    if live is not True:
        raise PhysicalRunActivationError("trusted host Crazyflie link is not live")
    crazyflie = getattr(scf, "cf", None)
    if crazyflie is None:
        raise PhysicalRunActivationError("trusted host Crazyflie object is unavailable")
    return crazyflie


def _assert_current_program(
    bridge: object,
    binding: PhysicalRunBinding,
    *,
    timeout_seconds: float,
) -> CurrentProgramPreflightEvidence:
    try:
        evidence = bridge.assert_current_program(
            profile_id=binding.profile_id,
            ast_binding=binding.ast_binding,
            connection_epoch=binding.connection_epoch,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        raise PhysicalRunActivationError(
            "fresh integrated #278/#249 current-program assertion failed"
        ) from exc
    if type(evidence) is not CurrentProgramPreflightEvidence:
        raise PhysicalRunActivationError("current-program evidence type is invalid")
    if evidence.execution_authority is not False:
        raise PhysicalRunActivationError(
            "current-program evidence crossed the non-authority boundary"
        )
    if (
        evidence.profile_id != binding.profile_id
        or evidence.ast_binding != binding.ast_binding
        or evidence.connection_epoch != binding.connection_epoch
    ):
        raise PhysicalRunActivationError(
            "current-program evidence does not match the host-owned binding"
        )
    if not isinstance(evidence.challenge_id, str) or not evidence.challenge_id.strip():
        raise PhysicalRunActivationError("current-program challenge provenance is unavailable")
    return evidence


def _require_flight_inactive(reader: FreshSupervisorStateReader) -> bool:
    try:
        state = reader.read(timeout_seconds=0.2)
    except Exception as exc:
        raise PhysicalRunActivationError(
            "fresh pre-reset supervisor state is unavailable"
        ) from exc
    values = (
        getattr(state, "blocking_fault", None),
        getattr(state, "is_flying", None),
        getattr(state, "hl_control_active", None),
    )
    if any(not isinstance(value, bool) for value in values):
        raise PhysicalRunActivationError("pre-reset supervisor state is malformed")
    blocking_fault, is_flying, high_level_active = values
    if blocking_fault:
        raise PhysicalRunActivationError("blocking supervisor fault prevents trusted reset")
    if is_flying or high_level_active:
        raise PhysicalRunActivationError(
            "STM+deck reset requires fresh physical flight-inactive evidence"
        )
    return True


def activate_validated_run(
    *,
    uri: str,
    session: object,
    bridge: object,
    teacher_socket: socket.socket,
    staged_binding: PhysicalRunBinding,
    execution_domain: PhysicalExecutionDomain,
    assertion_timeout_seconds: float = 1.0,
):
    """Activate one exact host-validated run and return its trusted controller.

    ``execute_next_inflight()`` on the returned process-local object accepts no
    semantic parameters. It reserves only the next exact top-level horizontal or
    vertical move, turn, bottom Color LED effect, no-effect wait/set_speed state
    or terminal land from the post-reset #267 binding and keeps every positive
    provenance/effect path lexical to this adapter's host-owned bridge.
    """
    if not isinstance(uri, str) or not uri.startswith("radio://"):
        raise PhysicalRunActivationError("physical activation requires explicit radio:// URI")
    if type(staged_binding) is not PhysicalRunBinding:
        raise PhysicalRunActivationError("exact host-staged PhysicalRunBinding is required")
    if type(execution_domain) is not PhysicalExecutionDomain:
        raise PhysicalRunActivationError("exact process-wide #273 execution domain is required")
    if not isinstance(teacher_socket, socket.socket):
        raise PhysicalRunActivationError("distinct trusted teacher socket is required")
    if assertion_timeout_seconds <= 0:
        raise PhysicalRunActivationError("current-program assertion timeout must be positive")

    try:
        sequence = PhysicalProgramSequence(staged_binding.ast_binding)
    except PhysicalProgramSequenceError as exc:
        raise PhysicalRunActivationError(
            "teacher-bound physical program cannot enter exact sequencing"
        ) from exc

    begin_replacement = getattr(bridge, "begin_post_reset_replacement", None)
    install_replacement = getattr(bridge, "install_post_reset_session", None)
    if not callable(begin_replacement) or not callable(install_replacement):
        raise PhysicalRunActivationError(
            "trusted activation requires the integrated fail-closed post-reset bridge"
        )

    previous_epoch = staged_binding.connection_epoch
    try:
        current_epoch = session.read_connection_epoch()
    except Exception as exc:
        raise PhysicalRunActivationError("pre-reset connection epoch is unavailable") from exc
    if current_epoch != previous_epoch:
        raise PhysicalRunActivationError("staged run belongs to a stale pre-reset epoch")

    _assert_current_program(
        bridge,
        staged_binding,
        timeout_seconds=assertion_timeout_seconds,
    )
    pre_reset_cf = _live_crazyflie(session)
    pre_reset_reader = FreshSupervisorStateReader(
        pre_reset_cf,
        session.read_connection_epoch,
    )

    def require_flight_known_inactive() -> bool:
        return _require_flight_inactive(pre_reset_reader)

    def invalidate_prior_evidence() -> None:
        begin_replacement(previous_epoch)
        session.close()

    def open_post_reset_session() -> object:
        session.open()
        try:
            installed_epoch = install_replacement(session)
            live_epoch = session.read_connection_epoch()
            if installed_epoch != live_epoch or live_epoch == previous_epoch:
                raise PhysicalRunActivationError(
                    "post-reset bridge was not rebound to the genuinely new live epoch"
                )
            return _live_crazyflie(session)
        except Exception:
            try:
                session.close()
            except Exception:
                pass
            raise

    def close_post_reset_session(crazyflie: object) -> None:
        if crazyflie is not _live_crazyflie(session):
            raise PhysicalRunActivationError(
                "post-reset cleanup is not bound to the live Crazyflie"
            )
        session.close()

    def read_connection_epoch(crazyflie: object) -> str:
        if crazyflie is not _live_crazyflie(session):
            raise PhysicalRunActivationError(
                "post-reset epoch read is not bound to the live Crazyflie"
            )
        return session.read_connection_epoch()

    def read_capabilities(crazyflie: object):
        if crazyflie is not _live_crazyflie(session):
            raise PhysicalRunActivationError(
                "post-reset capability read is not bound to the live Crazyflie"
            )
        return session.read_capabilities()

    def assert_bound_preflight(crazyflie: object, epoch: str) -> bool:
        if crazyflie is not _live_crazyflie(session):
            raise PhysicalRunActivationError(
                "post-reset preflight is not bound to the live Crazyflie"
            )
        binding = PhysicalRunBinding(
            profile_id=staged_binding.profile_id,
            ast_binding=staged_binding.ast_binding,
            connection_epoch=epoch,
        )
        _assert_current_program(
            bridge,
            binding,
            timeout_seconds=assertion_timeout_seconds,
        )
        return True

    def read_fresh_supervisor(crazyflie: object, epoch: str):
        if crazyflie is not _live_crazyflie(session):
            raise PhysicalRunActivationError(
                "post-reset supervisor read is not bound to the live Crazyflie"
            )
        if session.read_connection_epoch() != epoch:
            raise PhysicalRunActivationError(
                "post-reset supervisor read belongs to another connection epoch"
            )
        reader = FreshSupervisorStateReader(
            crazyflie,
            session.read_connection_epoch,
        )
        return reader.read(timeout_seconds=0.2)

    powered_factory = TrustedPoweredSessionFactory(
        require_flight_known_inactive=require_flight_known_inactive,
        invalidate_prior_evidence=invalidate_prior_evidence,
        stm_deck_power_cycle=make_cflib_stm_deck_power_cycle(uri),
        open_post_reset_session=open_post_reset_session,
        close_post_reset_session=close_post_reset_session,
        read_connection_epoch=read_connection_epoch,
        read_capabilities=read_capabilities,
        assert_bound_preflight=assert_bound_preflight,
        read_fresh_supervisor=read_fresh_supervisor,
    )
    authorizer = TrustedTeacherAuthorizer()
    decision_channel = PostResetTeacherDecisionChannel(
        teacher_socket,
        session.read_connection_epoch,
    )

    class _HostBoundInitialFlightTransport(TrustedTakeoffTransport):
        def _read_current_binding(self) -> PhysicalRunBinding:
            binding = self.teacher_binding
            try:
                _assert_current_program(
                    bridge,
                    binding,
                    timeout_seconds=assertion_timeout_seconds,
                )
            except PhysicalRunActivationError as exc:
                raise TakeoffTransportError(str(exc)) from exc
            return binding

    def host_bound_transport_factory(**kwargs) -> TrustedTakeoffTransport:
        return _HostBoundInitialFlightTransport(**kwargs)

    controller = ProductionTakeoffRunController(
        powered_session_factory=powered_factory,
        teacher_channel=decision_channel,
        teacher_authorizer=authorizer,
        connection_epoch_reader=session.read_connection_epoch,
        host_bound_transport_factory=host_bound_transport_factory,
        execution_domain=execution_domain,
    )
    try:
        controller.start(
            profile_id=staged_binding.profile_id,
            ast_binding=staged_binding.ast_binding,
            previous_connection_epoch=previous_epoch,
        )
    finally:
        decision_channel.close()

    active_run = controller.active_run
    if active_run is None:
        try:
            controller.shutdown()
        finally:
            raise PhysicalRunActivationError(
                "causal takeoff completed without an active physical run bundle"
            )
    if sequence.ast_binding != active_run.teacher_authorization.binding.ast_binding:
        try:
            controller.shutdown()
        finally:
            raise PhysicalRunActivationError(
                "post-takeoff teacher run no longer matches the exact sequenced AST"
            )

    class _HostBoundInflightTransport(TrustedControlledLandingTransport):
        def _read_current_binding(self) -> PhysicalRunBinding:
            binding = self.teacher_binding
            try:
                _assert_current_program(
                    bridge,
                    binding,
                    timeout_seconds=assertion_timeout_seconds,
                )
            except PhysicalRunActivationError as exc:
                raise ControlledLandingTransportError(str(exc)) from exc
            return binding

    class _HostBoundColorLedTransport(TrustedBottomColorLedTransport):
        def _read_current_binding(self) -> PhysicalRunBinding:
            binding = self.teacher_binding
            try:
                _assert_current_program(
                    bridge,
                    binding,
                    timeout_seconds=assertion_timeout_seconds,
                )
            except PhysicalRunActivationError as exc:
                raise ColorLedTransportError(str(exc)) from exc
            return binding

    timing_policy = HighLevelTimingPolicy()

    class _ActivatedRunController:
        __slots__ = ("_yaw_reader", "_transport", "_color_transport")

        def __init__(self) -> None:
            self._yaw_reader = None
            self._transport = None
            self._color_transport = None

        @property
        def active_run(self):
            return controller.active_run

        def _ensure_transport(self):
            if self._transport is not None:
                return self._transport
            transport = _HostBoundInflightTransport(
                crazyflie=active_run.crazyflie,
                execution_domain=active_run.execution_domain,
                acknowledgement_domain=active_run.acknowledgement_domain,
                safelink_guard=active_run.safelink_guard,
                teacher_authorization=active_run.teacher_authorization,
                powered_session=active_run.powered_session,
                watchdog_guard=active_run.watchdog_guard,
                supervisor_reader=active_run.supervisor_reader,
                connection_epoch_reader=session.read_connection_epoch,
            )
            if transport.bound_connection_epoch != session.read_connection_epoch():
                raise PhysicalRunActivationError(
                    "physical effect transport is not bound to the exact active host epoch"
                )
            self._transport = transport
            return transport

        def _ensure_color_transport(self):
            if self._color_transport is not None:
                return self._color_transport
            transport = _HostBoundColorLedTransport(
                crazyflie=active_run.crazyflie,
                execution_domain=active_run.execution_domain,
                safelink_guard=active_run.safelink_guard,
                teacher_authorization=active_run.teacher_authorization,
                powered_session=active_run.powered_session,
                watchdog_guard=active_run.watchdog_guard,
                connection_epoch_reader=session.read_connection_epoch,
            )
            if transport.bound_connection_epoch != session.read_connection_epoch():
                raise PhysicalRunActivationError(
                    "Color LED effect transport is not bound to the exact active host epoch"
                )
            self._color_transport = transport
            return transport

        def _ensure_yaw_reader(self):
            if self._yaw_reader is not None:
                return self._yaw_reader
            reader = FreshYawObserver(
                active_run.crazyflie,
                session.read_connection_epoch,
            )
            reader.open()
            self._yaw_reader = reader
            return reader

        def _release_or_poison_sequence(self, claim: object, reason: str) -> None:
            if active_run.execution_domain.phase == FLYING:
                sequence.release_unemitted(claim)
            else:
                sequence.mark_ambiguous(claim, reason)

        def _execute_wait(self):
            claim = sequence.reserve_next_wait()
            wait_step = sequence.wait_for_claim(claim)
            binding = active_run.teacher_authorization.binding
            try:
                if active_run.execution_domain.phase != FLYING:
                    raise PhysicalRunActivationError(
                        "exact wait requires causally established flying state"
                    )
                _assert_current_program(
                    bridge,
                    binding,
                    timeout_seconds=assertion_timeout_seconds,
                )
                _execute_exact_wait(
                    wait_step.seconds,
                    active_run.watchdog_guard,
                    session.read_connection_epoch,
                    active_run.powered_session.connection_epoch,
                )
                if active_run.execution_domain.phase != FLYING:
                    raise PhysicalRunActivationError(
                        "physical state changed during no-effect exact wait"
                    )
                _assert_current_program(
                    bridge,
                    binding,
                    timeout_seconds=assertion_timeout_seconds,
                )
            except Exception:
                sequence.fail_wait(
                    claim,
                    "exact wait did not complete under the live trusted run binding",
                )
                raise
            sequence.complete_wait(claim)
            return _NoEffectStepResult()

        def _execute_speed(self):
            claim = sequence.reserve_next_speed()
            speed_step = sequence.speed_for_claim(claim)
            binding = active_run.teacher_authorization.binding
            assert_live = getattr(active_run.watchdog_guard, "assert_live", None)
            try:
                if active_run.execution_domain.phase != FLYING:
                    raise PhysicalRunActivationError(
                        "exact set_speed requires causally established flying state"
                    )
                if not callable(assert_live):
                    raise PhysicalRunActivationError(
                        "exact set_speed requires live watchdog guard"
                    )
                assert_live()
                _require_exact_epoch(
                    session.read_connection_epoch,
                    active_run.powered_session.connection_epoch,
                    context="exact physical set_speed",
                )
                _assert_current_program(
                    bridge,
                    binding,
                    timeout_seconds=assertion_timeout_seconds,
                )

                # This is host-local run state only. It emits no command and the
                # same policy object is later consumed by exact horizontal moves.
                timing_policy.set_horizontal_speed(speed_step.speed_m_s)

                if active_run.execution_domain.phase != FLYING:
                    raise PhysicalRunActivationError(
                        "physical state changed during no-effect exact set_speed"
                    )
                assert_live()
                _require_exact_epoch(
                    session.read_connection_epoch,
                    active_run.powered_session.connection_epoch,
                    context="exact physical set_speed",
                )
                _assert_current_program(
                    bridge,
                    binding,
                    timeout_seconds=assertion_timeout_seconds,
                )
            except Exception:
                sequence.fail_speed(
                    claim,
                    "exact set_speed did not complete under the live trusted run binding",
                )
                raise
            sequence.complete_speed(claim)
            return _NoEffectStepResult()

        def _execute_light(self):
            claim = sequence.reserve_next_light()
            light_step = sequence.light_for_claim(claim)
            try:
                result = self._ensure_color_transport().send_color(
                    color=light_step.color
                )
            except Exception:
                self._release_or_poison_sequence(
                    claim,
                    "bottom Color LED effect outcome is not definitively retryable",
                )
                raise

            accepted = getattr(result, "accepted", None)
            if accepted is True:
                if active_run.execution_domain.phase != FLYING:
                    sequence.mark_ambiguous(
                        claim,
                        "accepted bottom Color LED effect did not causally return to flying",
                    )
                    raise PhysicalRunActivationError(
                        "accepted bottom Color LED completion is not causally established"
                    )
                sequence.complete_light(claim)
            elif accepted is False:
                if active_run.execution_domain.phase != FLYING:
                    sequence.mark_ambiguous(
                        claim,
                        "rejected bottom Color LED effect did not restore the flying phase",
                    )
                    raise PhysicalRunActivationError(
                        "definitive bottom Color LED rejection did not restore physical state"
                    )
                sequence.release_unemitted(claim)
            else:
                sequence.mark_ambiguous(
                    claim,
                    "trusted bottom Color LED transport returned an indeterminate result",
                )
                raise PhysicalRunActivationError(
                    "trusted bottom Color LED transport returned no definitive acknowledgement"
                )
            return result

        def execute_next_inflight(self):
            """Advance one exact AST step; accepts no caller semantic data."""
            step_kind = sequence.next_step_kind
            if step_kind == "wait":
                return self._execute_wait()
            if step_kind == "set_speed":
                return self._execute_speed()
            if step_kind == "set_light":
                return self._execute_light()

            terminal_landing = step_kind == "land"
            if terminal_landing:
                claim = sequence.reserve_terminal_landing()
                sequence.landing_for_claim(claim)
                motion = None
            else:
                claim = sequence.reserve_next_motion()
                motion = sequence.motion_for_claim(claim)

            try:
                transport = self._ensure_transport()
                if terminal_landing:
                    result = transport.send_controlled_landing()
                elif motion is not None and motion.kind == "move":
                    result = transport.send_horizontal_move(
                        direction=motion.direction,
                        distance_m=motion.distance_m,
                        yaw_reader=self._ensure_yaw_reader(),
                        timing_policy=timing_policy,
                    )
                elif motion is not None and motion.kind == "vertical":
                    result = transport.send_vertical_move(
                        direction=motion.direction,
                        distance_m=motion.distance_m,
                        timing_policy=timing_policy,
                    )
                elif motion is not None and motion.kind == "turn":
                    result = transport.send_turn(
                        angle_deg=motion.angle_deg,
                        timing_policy=timing_policy,
                    )
                else:
                    raise PhysicalRunActivationError(
                        "reserved physical statement is outside the bounded effect slice"
                    )
            except Exception:
                self._release_or_poison_sequence(
                    claim,
                    "physical effect outcome is not definitively retryable",
                )
                raise

            accepted = getattr(result, "accepted", None)
            if accepted is True:
                if terminal_landing:
                    if active_run.execution_domain.phase != INACTIVE:
                        sequence.mark_ambiguous(
                            claim,
                            "accepted terminal landing did not causally establish inactive",
                        )
                        raise PhysicalRunActivationError(
                            "accepted terminal landing completion is not causally established"
                        )
                    sequence.complete_landing(claim)
                else:
                    if active_run.execution_domain.phase != FLYING:
                        sequence.mark_ambiguous(
                            claim,
                            "accepted in-flight effect did not causally return to flying",
                        )
                        raise PhysicalRunActivationError(
                            "accepted in-flight effect completion is not causally established"
                        )
                    sequence.complete_motion(claim)
            elif accepted is False:
                if active_run.execution_domain.phase != FLYING:
                    sequence.mark_ambiguous(
                        claim,
                        "rejected physical effect did not restore the flying phase",
                    )
                    raise PhysicalRunActivationError(
                        "definitive physical rejection did not restore physical state"
                    )
                sequence.release_unemitted(claim)
            else:
                sequence.mark_ambiguous(
                    claim,
                    "trusted physical transport returned an indeterminate result",
                )
                raise PhysicalRunActivationError(
                    "trusted physical transport returned no definitive acknowledgement"
                )
            return result

        def shutdown(self) -> None:
            yaw_error = None
            if self._yaw_reader is not None:
                try:
                    self._yaw_reader.close()
                except Exception as exc:
                    yaw_error = exc
            controller.shutdown()
            if yaw_error is not None:
                raise PhysicalRunActivationError(
                    "could not close in-flight yaw observer cleanly"
                ) from yaw_error

    return _ActivatedRunController()

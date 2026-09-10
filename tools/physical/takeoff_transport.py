#!/usr/bin/env python3
"""Trusted one-shot physical takeoff effect consumer for the host TCB.

This module composes the already-integrated physical authority/safety domains
around one exact-bound command-9 request derived from the teacher-authorized
canonical AST. It does not expose a raw packet or caller-supplied height API.
The production physical host must instantiate it only with its co-located live
Crazyflie/session objects and fresh current-program assertion path.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from time import monotonic

from high_level_ack import HighLevelAckDomain, HighLevelAckError
from physical_execution_domain import (
    INACTIVE,
    FLYING,
    PhysicalExecutionDomain,
    PhysicalExecutionDomainError,
)
from powered_session_authority import EstablishedPoweredSession
from safelink_precondition import SafeLinkPrecondition
from supervisor_state import FreshSupervisorStateReader
from teacher_run_authorization import TeacherRunAuthorization
from takeoff_command import BoundTakeoffCommand, derive_bound_takeoff_command
from watchdog_liveness import EmergencyWatchdogLivenessGuard


class TakeoffTransportError(RuntimeError):
    """Fail-closed trusted takeoff transport error."""


@dataclass(frozen=True)
class TakeoffResult:
    accepted: bool
    status: int


class TrustedTakeoffTransport:
    """One exact-run takeoff consumer bound to trusted host-local authorities."""

    def __init__(
        self,
        *,
        crazyflie: object,
        execution_domain: PhysicalExecutionDomain,
        acknowledgement_domain: HighLevelAckDomain,
        safelink_guard: SafeLinkPrecondition,
        teacher_authorization: TeacherRunAuthorization,
        powered_session: EstablishedPoweredSession,
        watchdog_guard: EmergencyWatchdogLivenessGuard,
        supervisor_reader: FreshSupervisorStateReader,
        assert_current_program,
    ) -> None:
        if type(execution_domain) is not PhysicalExecutionDomain:
            raise TakeoffTransportError("exact physical execution domain is required")
        if type(acknowledgement_domain) is not HighLevelAckDomain:
            raise TakeoffTransportError("exact HighLevel acknowledgement domain is required")
        if type(safelink_guard) is not SafeLinkPrecondition:
            raise TakeoffTransportError("exact SafeLink precondition is required")
        if type(teacher_authorization) is not TeacherRunAuthorization:
            raise TakeoffTransportError("exact teacher run authorization is required")
        if type(powered_session) is not EstablishedPoweredSession:
            raise TakeoffTransportError("exact established powered session is required")
        if type(watchdog_guard) is not EmergencyWatchdogLivenessGuard:
            raise TakeoffTransportError("exact emergency watchdog guard is required")
        if type(supervisor_reader) is not FreshSupervisorStateReader:
            raise TakeoffTransportError("exact fresh supervisor reader is required")
        if not callable(assert_current_program):
            raise TakeoffTransportError("trusted current-program assertion is required")
        if powered_session.session is not crazyflie:
            raise TakeoffTransportError("powered session is not bound to exact Crazyflie")
        binding = teacher_authorization.binding
        if powered_session.connection_epoch != binding.connection_epoch:
            raise TakeoffTransportError("powered session epoch differs from authorized run")
        if acknowledgement_domain.bound_connection_epoch != binding.connection_epoch:
            raise TakeoffTransportError("acknowledgement domain epoch differs from authorized run")
        if safelink_guard.bound_connection_epoch != binding.connection_epoch:
            raise TakeoffTransportError("SafeLink epoch differs from authorized run")
        if supervisor_reader.bound_connection_epoch != binding.connection_epoch:
            raise TakeoffTransportError("supervisor reader epoch differs from authorized run")
        if supervisor_reader.bound_crazyflie is not crazyflie:
            raise TakeoffTransportError("supervisor reader is not bound to exact Crazyflie")
        if watchdog_guard.bound_connection_epoch != binding.connection_epoch:
            raise TakeoffTransportError("watchdog epoch differs from authorized run")
        if watchdog_guard.powered_session_identity != powered_session.watchdog_authority.identity:
            raise TakeoffTransportError("watchdog is not bound to established powered session")

        self._cf = crazyflie
        self._execution_domain = execution_domain
        self._ack_domain = acknowledgement_domain
        self._safelink = safelink_guard
        self._teacher = teacher_authorization
        self._powered = powered_session
        self._watchdog = watchdog_guard
        self._supervisor = supervisor_reader
        self._assert_current_program = assert_current_program
        self._binding = binding

    def _assert_mutable_authority(self) -> None:
        binding = self._binding
        self._teacher.assert_effect_binding(
            profile_id=binding.profile_id,
            ast_binding=binding.ast_binding,
            connection_epoch=binding.connection_epoch,
        )
        if self._powered.connection_epoch != binding.connection_epoch:
            raise TakeoffTransportError("powered session epoch changed")
        if self._powered.session is not self._cf:
            raise TakeoffTransportError("powered session Crazyflie identity changed")
        if self._powered.watchdog_authority.state != "active":
            raise TakeoffTransportError("powered-session watchdog authority is not active")
        self._watchdog.assert_live()

    def _assert_current_binding(self) -> None:
        binding = self._binding
        evidence = self._assert_current_program(
            profile_id=binding.profile_id,
            ast_binding=binding.ast_binding,
            connection_epoch=binding.connection_epoch,
        )
        if (
            getattr(evidence, "profile_id", None) != binding.profile_id
            or getattr(evidence, "ast_binding", None) != binding.ast_binding
            or getattr(evidence, "connection_epoch", None) != binding.connection_epoch
            or getattr(evidence, "execution_authority", None) is not False
        ):
            raise TakeoffTransportError("fresh current-program evidence does not match run")

    def _fresh_pre_takeoff_state(self) -> object:
        try:
            state = self._supervisor.read(timeout_seconds=0.25)
        except Exception as exc:
            raise TakeoffTransportError("fresh pre-takeoff supervisor state unavailable") from exc
        if getattr(state, "blocking_fault", None) is not False:
            raise TakeoffTransportError("blocking supervisor fault prevents takeoff")
        if getattr(state, "can_fly", None) is not True:
            raise TakeoffTransportError("supervisor does not permit flight")
        if getattr(state, "is_flying", None) is not False:
            raise TakeoffTransportError("takeoff requires fresh not-flying state")
        if getattr(state, "hl_control_active", None) is True:
            raise TakeoffTransportError("conflicting high-level control is already active")
        return state

    def _fresh_completion_state(self) -> object:
        try:
            return self._supervisor.read(timeout_seconds=0.25)
        except Exception as exc:
            raise TakeoffTransportError("fresh takeoff completion state unavailable") from exc

    def _prove_takeoff_complete(self) -> bool:
        saw_flying = False
        deadline = monotonic() + 5.0
        while monotonic() < deadline:
            self._assert_mutable_authority()
            state = self._fresh_completion_state()
            if getattr(state, "blocking_fault", None) is not False:
                raise TakeoffTransportError("blocking fault during takeoff completion")
            if getattr(state, "is_flying", None) is not True:
                continue
            if getattr(state, "hl_control_active", None) is not True:
                raise TakeoffTransportError("high-level control missing during takeoff")
            saw_flying = True
            if getattr(state, "hl_traj_finished", None) is True:
                return saw_flying
        raise TakeoffTransportError("takeoff completion remained ambiguous")

    def send_from_authorized_ast(self, *, acknowledgement_timeout_seconds: float = 1.0) -> TakeoffResult:
        if self._execution_domain.phase != INACTIVE:
            raise TakeoffTransportError("takeoff requires inactive physical execution phase")
        command: BoundTakeoffCommand = derive_bound_takeoff_command(self._binding.ast_binding)
        self._assert_mutable_authority()

        def immediate_precondition() -> None:
            if self._execution_domain.phase != INACTIVE:
                raise TakeoffTransportError("takeoff execution phase changed")
            self._assert_current_binding()
            self._assert_mutable_authority()
            self._fresh_pre_takeoff_state()
            self._assert_mutable_authority()
            self._safelink.assert_live()

        packet = self._build_packet(command.request)
        reply = Event()
        reply_data: dict[str, bytes] = {}

        def callback(response) -> None:
            try:
                data = bytes(response.data)
            except Exception:
                return
            if data[:3] == command.request[:3]:
                reply_data["data"] = data
                reply.set()

        try:
            with self._execution_domain.effect_transaction(immediate_precondition) as effect:
                with self._ack_domain.transaction(command.request) as ack:
                    self._cf.add_port_callback(packet.port, callback)
                    try:
                        effect.mark_emitted()
                        ack.mark_emitted()
                        self._cf.send_packet(packet)
                        if not reply.wait(acknowledgement_timeout_seconds):
                            ack.fail_ambiguous("takeoff acknowledgement timed out")
                        result = ack.resolve_reply(reply_data["data"])
                        if not result.accepted:
                            effect.mark_definitive_rejection()
                            return TakeoffResult(False, result.status)
                        permit = effect.mark_accepted()
                    finally:
                        self._cf.remove_port_callback(packet.port, callback)
        except (HighLevelAckError, PhysicalExecutionDomainError, TakeoffTransportError):
            raise
        except Exception as exc:
            raise TakeoffTransportError("takeoff effect failed or is ambiguous") from exc

        try:
            self._execution_domain.complete_accepted_effect(
                permit,
                FLYING,
                self._prove_takeoff_complete,
            )
        except Exception as exc:
            raise TakeoffTransportError("takeoff completion was not positively established") from exc
        return TakeoffResult(True, 0)

    def _build_packet(self, request: bytes):
        try:
            from cflib.crtp.crtpstack import CRTPPacket, CRTPPort
        except ImportError as exc:
            raise TakeoffTransportError("cflib CRTP support unavailable") from exc
        packet = CRTPPacket()
        packet.set_header(CRTPPort.SETPOINT_HL, 0)
        packet.data = request
        return packet

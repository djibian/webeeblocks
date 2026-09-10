#!/usr/bin/env python3
"""Trusted causal takeoff effect core for the physical-host TCB.

The importable core deliberately has no current-program bridge, responder token,
provenance object, raw-packet or caller-height constructor surface.  Its
``_read_current_binding`` hook fails closed.  The trusted #283 physical-host
composition must provide the positive lexical override that performs one fresh
#278/#249 assertion on the exact teacher-authorized profile / canonical AST /
connection epoch immediately before the physical effect.

The only command semantics consumed here are the pure #287 command-9 bytes
produced by :mod:`takeoff_command` from the exact #267 canonical AST binding.
The effect composes the exact #266 powered session, #262 watchdog, #257 fresh
supervisor state, #272 SafeLink, #271 acknowledgement freshness and process-wide
#273 execution lifecycle.  A positive firmware acknowledgement is not enough to
claim flight: the exact #279 completion permit is consumed only after causally
fresh supervisor evidence establishes flight under high-level control and then
a finished takeoff trajectory.  Ambiguity remains fail closed.
"""

from __future__ import annotations

import math
from threading import Event, Lock
from time import monotonic, sleep
from typing import Callable

import high_level_ack
import physical_execution_domain
import powered_session_authority
import safelink_precondition
import supervisor_state
import teacher_run_authorization
import takeoff_command
import watchdog_liveness

_SETPOINT_HL_PORT = 0x08
_DEFAULT_REPLY_TIMEOUT_SECONDS = 0.2
_COMPLETION_READ_TIMEOUT_SECONDS = 0.2
_COMPLETION_POLL_SECONDS = 0.05
_COMPLETION_TIMEOUT_SECONDS = 5.0
_WAIT_SLICE_SECONDS = 0.01


class TakeoffTransportError(RuntimeError):
    """Fail-closed trusted takeoff transport error."""


def _require_callable(value: object, name: str) -> Callable:
    if not callable(value):
        raise TakeoffTransportError(f"{name} must be callable")
    return value


def _positive_timeout(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TakeoffTransportError(f"{name} must be positive")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0.0:
        raise TakeoffTransportError(f"{name} must be positive")
    return parsed


def _default_packet_factory(request: bytes) -> object:
    try:
        from cflib.crtp.crtpstack import CRTPPacket, CRTPPort
    except Exception as exc:
        raise TakeoffTransportError("pinned cflib CRTP packet types are unavailable") from exc
    if getattr(CRTPPort, "SETPOINT_HL", None) != _SETPOINT_HL_PORT:
        raise TakeoffTransportError("cflib SETPOINT_HL port does not match pinned contract")
    packet = CRTPPacket()
    packet.port = CRTPPort.SETPOINT_HL
    packet.data = request
    return packet


class TrustedTakeoffTransport:
    """One exact-run takeoff effect core, completed only by host-local provenance."""

    def __init__(
        self,
        *,
        crazyflie: object,
        execution_domain: physical_execution_domain.PhysicalExecutionDomain,
        acknowledgement_domain: high_level_ack.HighLevelAckDomain,
        safelink_guard: safelink_precondition.LiveSafeLinkPrecondition,
        teacher_authorization: teacher_run_authorization.TeacherRunAuthorization,
        powered_session: powered_session_authority.EstablishedPoweredSession,
        watchdog_guard: watchdog_liveness.EmergencyWatchdogLivenessGuard,
        supervisor_reader: supervisor_state.FreshSupervisorStateReader,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if crazyflie is None:
            raise TakeoffTransportError("exact live Crazyflie object is required")
        if type(execution_domain) is not physical_execution_domain.PhysicalExecutionDomain:
            raise TakeoffTransportError("exact process-wide PhysicalExecutionDomain is required")
        if type(acknowledgement_domain) is not high_level_ack.HighLevelAckDomain:
            raise TakeoffTransportError("exact HighLevelAckDomain is required")
        if type(safelink_guard) is not safelink_precondition.LiveSafeLinkPrecondition:
            raise TakeoffTransportError("exact LiveSafeLinkPrecondition is required")
        if type(teacher_authorization) is not teacher_run_authorization.TeacherRunAuthorization:
            raise TakeoffTransportError("exact #267 TeacherRunAuthorization receipt is required")
        if type(powered_session) is not powered_session_authority.EstablishedPoweredSession:
            raise TakeoffTransportError("exact #266 EstablishedPoweredSession is required")
        if (
            type(powered_session.watchdog_authority)
            is not powered_session_authority.EphemeralPoweredSessionWatchdogAuthority
        ):
            raise TakeoffTransportError("powered session lacks the #266-minted watchdog authority")
        if type(watchdog_guard) is not watchdog_liveness.EmergencyWatchdogLivenessGuard:
            raise TakeoffTransportError("exact active #262 watchdog guard is required")
        if type(supervisor_reader) is not supervisor_state.FreshSupervisorStateReader:
            raise TakeoffTransportError("exact #257 FreshSupervisorStateReader is required")

        epoch = acknowledgement_domain.bound_connection_epoch
        if not isinstance(epoch, str) or not epoch.strip() or epoch != epoch.strip():
            raise TakeoffTransportError("HighLevel acknowledgement epoch is invalid")
        if safelink_guard.bound_crazyflie is not crazyflie:
            raise TakeoffTransportError("SafeLink precondition is not bound to exact Crazyflie")
        if safelink_guard.bound_connection_epoch != epoch:
            raise TakeoffTransportError("SafeLink belongs to a different connection epoch")
        if teacher_authorization.binding.connection_epoch != epoch:
            raise TakeoffTransportError("teacher authorization belongs to another epoch")
        if powered_session.connection_epoch != epoch:
            raise TakeoffTransportError("powered session belongs to another epoch")
        if powered_session.session is not crazyflie:
            raise TakeoffTransportError("powered session is not bound to exact Crazyflie")
        if watchdog_guard.bound_connection_epoch != epoch:
            raise TakeoffTransportError("watchdog belongs to another epoch")
        if watchdog_guard.bound_crazyflie is not crazyflie:
            raise TakeoffTransportError("watchdog is not bound to exact Crazyflie")
        if watchdog_guard.powered_session_identity != powered_session.watchdog_authority.identity:
            raise TakeoffTransportError("watchdog is not bound to established powered session")
        if supervisor_reader.bound_connection_epoch != epoch:
            raise TakeoffTransportError("supervisor reader belongs to another epoch")
        if supervisor_reader.bound_crazyflie is not crazyflie:
            raise TakeoffTransportError("supervisor reader is not bound to exact Crazyflie")
        if supervisor_reader.poisoned is not False:
            raise TakeoffTransportError("supervisor reader is poisoned before takeoff")

        self._cf = crazyflie
        self._execution = execution_domain
        self._ack = acknowledgement_domain
        self._safelink = safelink_guard
        self._teacher = teacher_authorization
        self._powered = powered_session
        self._watchdog = watchdog_guard
        self._supervisor = supervisor_reader
        self._clock = _require_callable(clock, "monotonic clock")
        self._bound_connection_epoch = epoch

    @property
    def bound_connection_epoch(self) -> str:
        return self._bound_connection_epoch

    @property
    def execution_domain(self) -> physical_execution_domain.PhysicalExecutionDomain:
        return self._execution

    @property
    def teacher_binding(self) -> teacher_run_authorization.PhysicalRunBinding:
        return self._teacher.binding

    def _read_current_binding(self) -> teacher_run_authorization.PhysicalRunBinding:
        raise TakeoffTransportError(
            "current-program assertion is not bound to the trusted #283 physical host"
        )

    def _assert_binding_authority(
        self,
        binding: teacher_run_authorization.PhysicalRunBinding,
    ) -> None:
        if type(binding) is not teacher_run_authorization.PhysicalRunBinding:
            raise TakeoffTransportError("exact #267 PhysicalRunBinding is required")
        self._teacher.assert_effect_binding(
            profile_id=binding.profile_id,
            ast_binding=binding.ast_binding,
            connection_epoch=binding.connection_epoch,
        )
        if binding != self._teacher.binding:
            raise TakeoffTransportError("current binding differs from teacher-authorized run")
        if binding.connection_epoch != self._bound_connection_epoch:
            raise TakeoffTransportError("current run belongs to a different connection epoch")
        if self._powered.connection_epoch != self._bound_connection_epoch:
            raise TakeoffTransportError("powered session connection epoch changed")
        if self._powered.session is not self._cf:
            raise TakeoffTransportError("powered session Crazyflie identity changed")
        if self._watchdog.powered_session_identity != self._powered.watchdog_authority.identity:
            raise TakeoffTransportError("watchdog/powered-session identity changed")
        self._watchdog.assert_live()
        if self._execution.phase != physical_execution_domain.INACTIVE:
            raise TakeoffTransportError("takeoff requires established inactive execution state")

    def _assert_current_authority(self) -> teacher_run_authorization.PhysicalRunBinding:
        binding = self._read_current_binding()
        self._assert_binding_authority(binding)
        return binding

    def _read_fresh_pre_takeoff(self) -> object:
        if self._supervisor.poisoned is not False:
            raise TakeoffTransportError("supervisor reader is poisoned before takeoff")
        try:
            state = self._supervisor.read(timeout_seconds=_COMPLETION_READ_TIMEOUT_SECONDS)
        except Exception as exc:
            raise TakeoffTransportError("fresh pre-takeoff supervisor state unavailable") from exc
        values = (
            getattr(state, "blocking_fault", None),
            getattr(state, "can_fly", None),
            getattr(state, "is_flying", None),
            getattr(state, "hl_control_active", None),
        )
        if any(not isinstance(value, bool) for value in values):
            raise TakeoffTransportError("fresh pre-takeoff supervisor state is malformed")
        blocking_fault, can_fly, is_flying, high_level_active = values
        if blocking_fault:
            raise TakeoffTransportError("blocking supervisor fault prevents takeoff")
        if not can_fly:
            raise TakeoffTransportError("supervisor does not positively permit flight")
        if is_flying:
            raise TakeoffTransportError("takeoff requires fresh not-flying state")
        if high_level_active:
            raise TakeoffTransportError("conflicting high-level control is already active")
        return state

    def _require_connection_live(self) -> None:
        method = getattr(self._cf, "is_connected", None)
        if not callable(method):
            raise TakeoffTransportError("Crazyflie live connection state is unavailable")
        try:
            connected = method()
        except Exception as exc:
            raise TakeoffTransportError("Crazyflie live connection state became unavailable") from exc
        if connected is not True:
            raise TakeoffTransportError("Crazyflie disconnected during takeoff transaction")

    def _wait_for_reply(
        self,
        event: Event,
        reply_reader: Callable[[], bytes | None],
        timeout_seconds: float,
    ) -> bytes:
        deadline = float(self._clock()) + timeout_seconds
        while True:
            if event.is_set():
                reply = reply_reader()
                if reply is None:
                    raise TakeoffTransportError("SETPOINT_HL reply event has no packet data")
                return reply
            self._require_connection_live()
            remaining = deadline - float(self._clock())
            if remaining <= 0.0:
                raise TakeoffTransportError("takeoff acknowledgement timeout")
            event.wait(min(_WAIT_SLICE_SECONDS, remaining))

    def _validate_packet(self, packet: object, request: bytes) -> None:
        if getattr(packet, "port", None) != _SETPOINT_HL_PORT:
            raise TakeoffTransportError("packet factory substituted non-SETPOINT_HL port")
        try:
            data = bytes(getattr(packet, "data"))
        except Exception as exc:
            raise TakeoffTransportError("packet factory returned unreadable data") from exc
        if data != request:
            raise TakeoffTransportError("packet factory substituted takeoff request bytes")

    def _prove_takeoff_completion(self) -> bool:
        deadline = float(self._clock()) + _COMPLETION_TIMEOUT_SECONDS
        saw_flying = False
        while True:
            remaining = deadline - float(self._clock())
            if remaining <= 0.0:
                raise TakeoffTransportError("takeoff completion timed out")
            self._teacher.assert_effect_binding(
                profile_id=self._teacher.binding.profile_id,
                ast_binding=self._teacher.binding.ast_binding,
                connection_epoch=self._teacher.binding.connection_epoch,
            )
            if self._powered.connection_epoch != self._bound_connection_epoch:
                raise TakeoffTransportError("powered session changed during takeoff completion")
            if self._powered.session is not self._cf:
                raise TakeoffTransportError("powered session Crazyflie changed during completion")
            if self._watchdog.powered_session_identity != self._powered.watchdog_authority.identity:
                raise TakeoffTransportError("watchdog identity changed during takeoff completion")
            self._watchdog.assert_live()
            if self._supervisor.poisoned is not False:
                raise TakeoffTransportError("supervisor freshness is poisoned during completion")
            try:
                state = self._supervisor.read(
                    timeout_seconds=min(_COMPLETION_READ_TIMEOUT_SECONDS, remaining)
                )
            except Exception as exc:
                raise TakeoffTransportError("fresh takeoff completion observation failed") from exc
            values = (
                getattr(state, "blocking_fault", None),
                getattr(state, "is_flying", None),
                getattr(state, "hl_control_active", None),
                getattr(state, "hl_traj_finished", None),
            )
            if any(not isinstance(value, bool) for value in values):
                raise TakeoffTransportError("fresh takeoff completion state is malformed")
            blocking_fault, is_flying, high_level_active, trajectory_finished = values
            if blocking_fault:
                raise TakeoffTransportError("blocking supervisor fault during takeoff completion")
            if is_flying:
                if not high_level_active:
                    raise TakeoffTransportError("high-level control missing after takeoff effect")
                saw_flying = True
                if trajectory_finished:
                    self._watchdog.assert_live()
                    self._teacher.assert_effect_binding(
                        profile_id=self._teacher.binding.profile_id,
                        ast_binding=self._teacher.binding.ast_binding,
                        connection_epoch=self._teacher.binding.connection_epoch,
                    )
                    return saw_flying
            elif high_level_active:
                raise TakeoffTransportError("high-level control active without established flight")
            remaining = deadline - float(self._clock())
            if remaining <= 0.0:
                raise TakeoffTransportError("takeoff completion timed out")
            sleep(min(_COMPLETION_POLL_SECONDS, remaining))

    def send_from_authorized_ast(
        self,
        *,
        reply_timeout_seconds: float = _DEFAULT_REPLY_TIMEOUT_SECONDS,
    ) -> high_level_ack.HighLevelAckResult:
        """Emit exactly one command-9 request derived from the authorized AST."""
        timeout = _positive_timeout(reply_timeout_seconds, "takeoff reply timeout")
        if self._execution.phase != physical_execution_domain.INACTIVE:
            raise TakeoffTransportError("takeoff requires established inactive execution state")

        # Derivation accepts no caller parameters and preserves the exact AST
        # binding as the sole source of the target height.
        command = takeoff_command.derive_bound_takeoff_command(
            self._teacher.binding.ast_binding
        )
        result: high_level_ack.HighLevelAckResult | None = None
        completion_permit: physical_execution_domain.AcceptedEffectCompletionPermit | None = None

        with self._execution.effect_transaction(self._assert_current_authority) as effect:
            packet = _default_packet_factory(command.request)
            self._validate_packet(packet, command.request)

            # Re-assert after packet construction so the last potentially
            # mutable source of program identity remains fresh immediately
            # before fresh supervisor/SafeLink evidence and emission.
            binding = self._assert_current_authority()
            if binding.ast_binding != command.ast_binding:
                raise TakeoffTransportError("derived takeoff no longer matches current AST binding")
            self._read_fresh_pre_takeoff()
            self._assert_binding_authority(binding)
            self._safelink.assert_ready()

            with self._ack.transaction(command.request) as acknowledgement:
                reply_event = Event()
                reply_lock = Lock()
                first_reply: list[bytes] = []

                def on_reply(reply_packet: object) -> None:
                    try:
                        data = bytes(getattr(reply_packet, "data"))
                    except Exception:
                        data = b""
                    with reply_lock:
                        if first_reply:
                            return
                        first_reply.append(data)
                        reply_event.set()

                def read_reply() -> bytes | None:
                    with reply_lock:
                        return first_reply[0] if first_reply else None

                add_callback = getattr(self._cf, "add_port_callback", None)
                remove_callback = getattr(self._cf, "remove_port_callback", None)
                send_packet = getattr(self._cf, "send_packet", None)
                if not callable(add_callback) or not callable(remove_callback) or not callable(send_packet):
                    raise TakeoffTransportError("Crazyflie SETPOINT_HL callback/send surface is unavailable")
                installed = False
                try:
                    add_callback(_SETPOINT_HL_PORT, on_reply)
                    installed = True
                    acknowledgement.mark_emitted()
                    effect.mark_emitted()
                    send_packet(packet)
                    try:
                        reply = self._wait_for_reply(reply_event, read_reply, timeout)
                    except Exception as exc:
                        acknowledgement.fail_ambiguous(str(exc))
                    result = acknowledgement.resolve_reply(reply)
                    if result.accepted:
                        completion_permit = effect.mark_accepted()
                    else:
                        effect.mark_definitive_rejection()
                finally:
                    if installed:
                        try:
                            remove_callback(_SETPOINT_HL_PORT, on_reply)
                        except Exception:
                            pass

        if result is None:
            raise TakeoffTransportError("takeoff acknowledgement result is unavailable")
        if not result.accepted:
            return result
        if completion_permit is None:
            raise TakeoffTransportError("accepted takeoff has no private completion permit")
        try:
            self._execution.complete_accepted_effect(
                completion_permit,
                physical_execution_domain.FLYING,
                self._prove_takeoff_completion,
            )
        except Exception as exc:
            raise TakeoffTransportError("takeoff completion was not positively established") from exc
        return result

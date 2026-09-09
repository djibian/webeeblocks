#!/usr/bin/env python3
"""Trusted one-shot in-flight SETPOINT_HL transport for the physical Crazyflie.

This is the first bounded module in this directory that may emit an ordinary
flight-capable CRTP packet. It deliberately exposes no browser/HTTP surface and
it cannot manufacture teacher or powered-session authority.

The transport is bound at construction time to the exact integrated authority
objects that make one physical run eligible:
- one #267 TeacherRunAuthorization receipt;
- one #266 EstablishedPoweredSession and its non-forgeable watchdog authority;
- the exact active #262 EmergencyWatchdogLivenessGuard for that powered session;
- one #272 live SafeLink precondition and one #271 acknowledgement domain on the
  same connection epoch;
- the process-wide #273 reset/effect exclusion domain.

The current slice intentionally supports only in-flight relative GO_TO_2 commands
for horizontal movement and yaw turns. It does not expose TAKEOFF_2, LAND_2,
vertical movement, STOP, trajectory, spiral, raw command bytes or a generic send
method. Horizontal geometry is derived through integrated #256 from one fresh
#260 yaw observation and duration through integrated #268. Turns use #256/#268
directly. Takeoff/landing/vertical timing policy remains a separate prerequisite.

A caller must supply a trusted non-authority current-preflight binding reader.
Its result is required to be the exact #267 PhysicalRunBinding and is rechecked
inside #273 immediately before every effect. Arbitrary authority callbacks are
not accepted.

Live SafeLink is re-checked immediately before entering #271. The SETPOINT_HL
reply callback is installed before the pessimistic effect boundary is crossed.
Exactly one plain Crazyflie.send_packet(packet) call is made, with no
expected_reply/application retry. A non-zero firmware result restores the prior
flying phase. A zero result moves #273 to awaiting-completion and returns one opaque
accepted-effect claim only to this transport. The transport consumes that claim
only after fresh #257 evidence positively observes the prior trajectory finished
while flight remains healthy.
Timeout, disconnect, malformed reply, send failure or epoch change is ambiguous
and remains fail-closed.

The physical packet is constructed internally from the already-validated local
request bytes. No caller-supplied packet object crosses the effect boundary.
"""

from __future__ import annotations

import math
import struct
from threading import Event, Lock
from time import monotonic, sleep
from typing import Callable

import high_level_ack
import high_level_semantics
import high_level_timing
import current_program_preflight
import physical_execution_domain
import powered_session_authority
import safelink_precondition
import supervisor_state
import teacher_run_authorization
import watchdog_liveness
import yaw_observer

_SETPOINT_HL_PORT = 0x08
_COMMAND_GO_TO_2 = 12
_DEFAULT_REPLY_TIMEOUT_SECONDS = 0.2
_DEFAULT_YAW_TIMEOUT_SECONDS = 0.5
_WAIT_SLICE_SECONDS = 0.01
_COMPLETION_READ_TIMEOUT_SECONDS = 0.2
_COMPLETION_POLL_SECONDS = 0.05
_GO_TO_2_SIZE = 24


class SetpointHlTransportError(RuntimeError):
    """Fail-closed trusted SETPOINT_HL transport error."""


def _require_callable(value: object, name: str) -> Callable:
    if not callable(value):
        raise SetpointHlTransportError(f"{name} must be callable")
    return value


def _positive_timeout(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SetpointHlTransportError(f"{name} must be positive")
    timeout = float(value)
    if not math.isfinite(timeout) or timeout <= 0.0:
        raise SetpointHlTransportError(f"{name} must be positive")
    return timeout


def _nonempty_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise SetpointHlTransportError(f"{name} must be a non-empty trimmed string")
    return value


def _go_to_request(target: object, duration_seconds: object) -> bytes:
    if not isinstance(target, high_level_semantics.RelativeHighLevelTarget):
        raise SetpointHlTransportError("validated #256 relative target is required")
    duration = _positive_timeout(duration_seconds, "GO_TO_2 duration")
    values = (target.x_m, target.y_m, target.z_m, target.yaw_rad, duration)
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        for value in values
    ):
        raise SetpointHlTransportError("GO_TO_2 target/duration must be finite")
    data = struct.pack(
        "<BBBBfffff",
        _COMMAND_GO_TO_2,
        0,  # group mask: one reference Crazyflie only
        1,  # relative world-frame target
        0,  # smooth seventh-order planner, not linear
        float(target.x_m),
        float(target.y_m),
        float(target.z_m),
        float(target.yaw_rad),
        duration,
    )
    _validate_request(data)
    return data


def _validate_request(value: object) -> bytes:
    if isinstance(value, bytearray):
        data = bytes(value)
    elif isinstance(value, bytes):
        data = value
    else:
        raise SetpointHlTransportError("validated SETPOINT_HL request must be bytes")
    if len(data) != _GO_TO_2_SIZE:
        raise SetpointHlTransportError("GO_TO_2 payload size does not match pinned cflib")
    command, group_mask, relative, linear, x, y, z, yaw, duration = struct.unpack(
        "<BBBBfffff", data
    )
    if command != _COMMAND_GO_TO_2:
        raise SetpointHlTransportError(
            "only validated GO_TO_2 is available on the ordinary effect surface"
        )
    if group_mask != 0 or relative != 1 or linear != 0:
        raise SetpointHlTransportError(
            "GO_TO_2 must be single-Crazyflie, relative and smooth"
        )
    if any(not math.isfinite(value) for value in (x, y, z, yaw, duration)):
        raise SetpointHlTransportError("GO_TO_2 payload contains non-finite values")
    if duration <= 0.0:
        raise SetpointHlTransportError("GO_TO_2 duration must be positive")
    return data


def _request_duration(request: bytes) -> float:
    return float(struct.unpack("<BBBBfffff", request)[-1])


def _default_packet_factory(request: bytes) -> object:
    try:
        from cflib.crtp.crtpstack import CRTPPacket, CRTPPort
    except Exception as exc:
        raise SetpointHlTransportError(
            "pinned cflib CRTP packet types are unavailable"
        ) from exc
    if getattr(CRTPPort, "SETPOINT_HL", None) != _SETPOINT_HL_PORT:
        raise SetpointHlTransportError(
            "cflib SETPOINT_HL port does not match pinned contract"
        )
    packet = CRTPPacket()
    packet.port = CRTPPort.SETPOINT_HL
    packet.data = request
    return packet


class TrustedSetpointHlTransport:
    """One exact-authority, no-retry in-flight HighLevel motion transport."""

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
        current_preflight_guard: current_program_preflight.LiveCurrentProgramPreflightGuard,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if crazyflie is None:
            raise SetpointHlTransportError("exact live Crazyflie object is required")
        if type(execution_domain) is not physical_execution_domain.PhysicalExecutionDomain:
            raise SetpointHlTransportError(
                "exact process-wide PhysicalExecutionDomain is required"
            )
        if type(acknowledgement_domain) is not high_level_ack.HighLevelAckDomain:
            raise SetpointHlTransportError(
                "exact HighLevelAckDomain is required"
            )
        if type(safelink_guard) is not safelink_precondition.LiveSafeLinkPrecondition:
            raise SetpointHlTransportError(
                "exact LiveSafeLinkPrecondition is required"
            )
        if type(teacher_authorization) is not teacher_run_authorization.TeacherRunAuthorization:
            raise SetpointHlTransportError(
                "exact #267 TeacherRunAuthorization receipt is required"
            )
        if type(powered_session) is not powered_session_authority.EstablishedPoweredSession:
            raise SetpointHlTransportError(
                "exact #266 EstablishedPoweredSession is required"
            )
        if (
            type(powered_session.watchdog_authority)
            is not powered_session_authority.EphemeralPoweredSessionWatchdogAuthority
        ):
            raise SetpointHlTransportError(
                "powered session lacks the #266-minted watchdog authority"
            )
        if type(watchdog_guard) is not watchdog_liveness.EmergencyWatchdogLivenessGuard:
            raise SetpointHlTransportError(
                "exact active #262 watchdog guard is required"
            )
        if type(supervisor_reader) is not supervisor_state.FreshSupervisorStateReader:
            raise SetpointHlTransportError(
                "exact #257 FreshSupervisorStateReader is required"
            )
        if type(current_preflight_guard) is not current_program_preflight.LiveCurrentProgramPreflightGuard:
            raise SetpointHlTransportError(
                "exact trusted #249 current-program preflight guard is required"
            )

        self._cf = crazyflie
        self._execution = execution_domain
        self._ack = acknowledgement_domain
        self._safelink = safelink_guard
        self._teacher = teacher_authorization
        self._powered_session = powered_session
        self._watchdog = watchdog_guard
        self._supervisor = supervisor_reader
        self._current_preflight = current_preflight_guard
        self._clock = _require_callable(clock, "monotonic clock")

        epoch = _nonempty_text(
            acknowledgement_domain.bound_connection_epoch,
            "HighLevel acknowledgement epoch",
        )
        if safelink_guard.bound_crazyflie is not crazyflie:
            raise SetpointHlTransportError(
                "SafeLink precondition is not bound to the exact Crazyflie"
            )
        if safelink_guard.bound_connection_epoch != epoch:
            raise SetpointHlTransportError(
                "SafeLink and acknowledgement domains are not bound to the same epoch"
            )
        if teacher_authorization.binding.connection_epoch != epoch:
            raise SetpointHlTransportError(
                "teacher run receipt belongs to a different connection epoch"
            )
        if current_preflight_guard.binding != teacher_authorization.binding:
            raise SetpointHlTransportError(
                "current-program preflight guard is not bound to the teacher-authorized run"
            )
        if powered_session.connection_epoch != epoch:
            raise SetpointHlTransportError(
                "powered session belongs to a different connection epoch"
            )
        if watchdog_guard.bound_connection_epoch != epoch:
            raise SetpointHlTransportError(
                "watchdog guard belongs to a different connection epoch"
            )
        if watchdog_guard.bound_crazyflie is not crazyflie:
            raise SetpointHlTransportError(
                "watchdog guard is not bound to the exact Crazyflie"
            )
        if (
            watchdog_guard.powered_session_identity
            != powered_session.watchdog_authority.identity
        ):
            raise SetpointHlTransportError(
                "watchdog guard is not bound to the #266 powered session"
            )
        if powered_session.session is not crazyflie:
            raise SetpointHlTransportError(
                "powered session is not bound to the exact Crazyflie object"
            )
        if supervisor_reader.bound_connection_epoch != epoch:
            raise SetpointHlTransportError(
                "fresh supervisor reader belongs to a different connection epoch"
            )
        if supervisor_reader.bound_crazyflie is not crazyflie:
            raise SetpointHlTransportError(
                "fresh supervisor reader is not bound to the exact Crazyflie"
            )
        if supervisor_reader.poisoned is not False:
            raise SetpointHlTransportError(
                "fresh supervisor reader is poisoned before physical execution"
            )
        self._bound_connection_epoch = epoch

    @property
    def bound_connection_epoch(self) -> str:
        return self._bound_connection_epoch

    @property
    def execution_domain(self) -> physical_execution_domain.PhysicalExecutionDomain:
        return self._execution

    def _read_current_binding(
        self,
    ) -> teacher_run_authorization.PhysicalRunBinding:
        try:
            evidence = self._current_preflight.assert_current()
        except Exception as exc:
            raise SetpointHlTransportError(
                "trusted #249 current-program re-assertion failed"
            ) from exc
        binding = getattr(evidence, "binding", None)
        if type(binding) is not teacher_run_authorization.PhysicalRunBinding:
            raise SetpointHlTransportError(
                "trusted #249 guard returned invalid current-program evidence"
            )
        if binding.connection_epoch != self._bound_connection_epoch:
            raise SetpointHlTransportError(
                "current preflight binding belongs to a different connection epoch"
            )
        return binding

    def _assert_binding_authority(
        self,
        binding: teacher_run_authorization.PhysicalRunBinding,
    ) -> None:
        """Re-check mutable authority without performing the slower #249 round trip."""
        self._teacher.assert_effect_binding(
            profile_id=binding.profile_id,
            ast_binding=binding.ast_binding,
            connection_epoch=binding.connection_epoch,
        )
        if self._powered_session.connection_epoch != self._bound_connection_epoch:
            raise SetpointHlTransportError(
                "powered session connection epoch changed"
            )
        if (
            self._watchdog.powered_session_identity
            != self._powered_session.watchdog_authority.identity
        ):
            raise SetpointHlTransportError(
                "watchdog/powered-session identity changed"
            )
        self._watchdog.assert_live()
        if self._execution.phase != physical_execution_domain.FLYING:
            raise SetpointHlTransportError(
                "ordinary GO_TO_2 motion requires fresh established flying state"
            )

    def _assert_current_authority(self) -> None:
        """Fresh #249 assertion followed by the exact mutable run authority."""
        binding = self._read_current_binding()
        self._assert_binding_authority(binding)

    def _read_fresh_finished_flying(self) -> object:
        """Require final fresh #257 no-fault flight with no active trajectory."""
        if self._supervisor.poisoned is not False:
            raise SetpointHlTransportError(
                "fresh supervisor reader is poisoned before physical effect"
            )
        try:
            state = self._supervisor.read(timeout_seconds=0.2)
        except Exception as exc:
            raise SetpointHlTransportError(
                "fresh supervisor safety observation failed before physical effect"
            ) from exc
        blocking_fault = getattr(state, "blocking_fault", None)
        is_flying = getattr(state, "is_flying", None)
        trajectory_finished = getattr(state, "hl_traj_finished", None)
        if (
            not isinstance(blocking_fault, bool)
            or not isinstance(is_flying, bool)
            or not isinstance(trajectory_finished, bool)
        ):
            raise SetpointHlTransportError(
                "fresh supervisor pre-effect state is malformed"
            )
        if blocking_fault:
            raise SetpointHlTransportError(
                "fresh supervisor state has a blocking fault"
            )
        if not is_flying:
            raise SetpointHlTransportError(
                "fresh supervisor state does not positively establish flight"
            )
        if not trajectory_finished:
            raise SetpointHlTransportError(
                "previous high-level trajectory is not freshly finished"
            )
        return state

    def _require_connection_live(self) -> None:
        method = getattr(self._cf, "is_connected", None)
        if not callable(method):
            raise SetpointHlTransportError(
                "Crazyflie live connection state is unavailable during acknowledgement"
            )
        try:
            connected = method()
        except Exception as exc:
            raise SetpointHlTransportError(
                "Crazyflie live connection state became unavailable"
            ) from exc
        if connected is not True:
            raise SetpointHlTransportError(
                "Crazyflie disconnected before definitive SETPOINT_HL acknowledgement"
            )

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
                    raise SetpointHlTransportError(
                        "SETPOINT_HL reply event has no packet data"
                    )
                return reply
            self._require_connection_live()
            remaining = deadline - float(self._clock())
            if remaining <= 0.0:
                raise SetpointHlTransportError("SETPOINT_HL acknowledgement timeout")
            event.wait(min(_WAIT_SLICE_SECONDS, remaining))

    def _validate_packet(self, packet: object, request: bytes) -> None:
        if getattr(packet, "port", None) != _SETPOINT_HL_PORT:
            raise SetpointHlTransportError(
                "packet factory substituted a non-SETPOINT_HL port"
            )
        try:
            packet_data = bytes(getattr(packet, "data"))
        except Exception as exc:
            raise SetpointHlTransportError(
                "packet factory returned unreadable SETPOINT_HL data"
            ) from exc
        if packet_data != request:
            raise SetpointHlTransportError(
                "packet factory substituted SETPOINT_HL request bytes"
            )

    def _force_completion_uncertainty(
        self,
        claim: physical_execution_domain.AcceptedEffectCompletionClaim,
    ) -> None:
        if self._execution.phase == physical_execution_domain.AWAITING_COMPLETION:
            try:
                self._execution.complete_accepted_effect(
                    claim,
                    physical_execution_domain.FLYING,
                    lambda: False,
                )
            except physical_execution_domain.PhysicalExecutionDomainError:
                pass

    def _await_motion_completion(
        self,
        claim: physical_execution_domain.AcceptedEffectCompletionClaim,
        planned_duration: float,
    ) -> None:
        """Consume the private accepted-effect claim only after fresh #257 proof."""
        if type(claim) is not physical_execution_domain.AcceptedEffectCompletionClaim:
            raise SetpointHlTransportError(
                "exact accepted-effect completion claim is required"
            )
        timeout = _positive_timeout(
            planned_duration + max(1.0, planned_duration * 0.5),
            "high-level motion completion timeout",
        )
        deadline = monotonic() + timeout
        try:
            while True:
                remaining = deadline - monotonic()
                if remaining <= 0.0:
                    raise SetpointHlTransportError(
                        "high-level motion completion timed out"
                    )
                if self._supervisor.poisoned is not False:
                    raise SetpointHlTransportError(
                        "fresh supervisor reader is poisoned during motion completion"
                    )
                try:
                    state = self._supervisor.read(
                        timeout_seconds=min(
                            _COMPLETION_READ_TIMEOUT_SECONDS,
                            remaining,
                        )
                    )
                except Exception as exc:
                    raise SetpointHlTransportError(
                        "fresh supervisor motion-completion observation failed"
                    ) from exc

                blocking_fault = getattr(state, "blocking_fault", None)
                is_flying = getattr(state, "is_flying", None)
                trajectory_finished = getattr(state, "hl_traj_finished", None)
                if (
                    not isinstance(blocking_fault, bool)
                    or not isinstance(is_flying, bool)
                    or not isinstance(trajectory_finished, bool)
                ):
                    raise SetpointHlTransportError(
                        "fresh supervisor motion-completion state is malformed"
                    )
                if blocking_fault:
                    raise SetpointHlTransportError(
                        "blocking supervisor fault during motion completion"
                    )
                if not is_flying:
                    raise SetpointHlTransportError(
                        "physical flight ended unexpectedly during motion completion"
                    )
                if trajectory_finished:
                    self._execution.complete_accepted_effect(
                        claim,
                        physical_execution_domain.FLYING,
                        lambda: True,
                    )
                    return

                remaining = deadline - monotonic()
                if remaining <= 0.0:
                    raise SetpointHlTransportError(
                        "high-level motion completion timed out"
                    )
                sleep(min(_COMPLETION_POLL_SECONDS, remaining))
        except Exception:
            self._force_completion_uncertainty(claim)
            raise

    def _send_go_to_once(
        self,
        request_builder: Callable[[], bytes],
        *,
        reply_timeout_seconds: float,
    ) -> high_level_ack.HighLevelAckResult:
        builder = _require_callable(request_builder, "validated GO_TO_2 builder")
        timeout = _positive_timeout(
            reply_timeout_seconds,
            "SETPOINT_HL reply timeout",
        )
        result: high_level_ack.HighLevelAckResult | None = None
        completion_claim: (
            physical_execution_domain.AcceptedEffectCompletionClaim | None
        ) = None
        planned_duration: float | None = None

        with self._execution.effect_transaction(
            self._assert_current_authority
        ) as effect:
            request = _validate_request(builder())
            planned_duration = _request_duration(request)
            packet = _default_packet_factory(request)
            self._validate_packet(packet, request)

            # The fresh host-initiated #249 round trip may block. Keep it before
            # the final #257 observation so supervisor evidence is not aged by
            # preflight. Then re-check the mutable teacher/watchdog authority
            # once more after that supervisor read, immediately before SafeLink.
            final_binding = self._read_current_binding()
            self._assert_binding_authority(final_binding)
            self._read_fresh_finished_flying()
            self._assert_binding_authority(final_binding)
            self._safelink.assert_ready()

            with self._ack.transaction(request) as acknowledgement:
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
                if (
                    not callable(add_callback)
                    or not callable(remove_callback)
                    or not callable(send_packet)
                ):
                    raise SetpointHlTransportError(
                        "Crazyflie SETPOINT_HL callback/send surface is unavailable"
                    )

                callback_installed = False
                try:
                    add_callback(_SETPOINT_HL_PORT, on_reply)
                    callback_installed = True

                    acknowledgement.mark_emitted()
                    effect.mark_emitted()

                    # One positional argument only: never cflib expected_reply.
                    send_packet(packet)

                    try:
                        reply = self._wait_for_reply(
                            reply_event,
                            read_reply,
                            timeout,
                        )
                    except Exception as exc:
                        acknowledgement.fail_ambiguous(str(exc))

                    result = acknowledgement.resolve_reply(reply)
                    if result.accepted:
                        # The opaque claim never crosses this transport surface.
                        # An external lambda alone therefore cannot restore
                        # effect eligibility after this accepted command.
                        completion_claim = effect.mark_accepted()
                    else:
                        effect.mark_definitive_rejection()
                finally:
                    if callback_installed:
                        try:
                            remove_callback(_SETPOINT_HL_PORT, on_reply)
                        except Exception:
                            pass

        if result is None or planned_duration is None:
            raise SetpointHlTransportError(
                "SETPOINT_HL acknowledgement result is unavailable"
            )
        if result.accepted:
            if completion_claim is None:
                raise SetpointHlTransportError(
                    "accepted SETPOINT_HL effect has no private completion claim"
                )
            self._await_motion_completion(
                completion_claim,
                planned_duration,
            )
        return result

    def send_horizontal_move(
        self,
        *,
        direction: str,
        distance_m: object,
        yaw_reader: yaw_observer.FreshYawObserver,
        timing_policy: high_level_timing.HighLevelTimingPolicy,
        yaw_timeout_seconds: float = _DEFAULT_YAW_TIMEOUT_SECONDS,
        reply_timeout_seconds: float = _DEFAULT_REPLY_TIMEOUT_SECONDS,
    ) -> high_level_ack.HighLevelAckResult:
        """Send one #256/#260/#268 horizontal relative GO_TO_2 command."""
        if type(yaw_reader) is not yaw_observer.FreshYawObserver:
            raise SetpointHlTransportError(
                "exact #260 FreshYawObserver is required for horizontal movement"
            )
        if yaw_reader.bound_crazyflie is not self._cf:
            raise SetpointHlTransportError(
                "yaw observer is not bound to the exact Crazyflie"
            )
        if yaw_reader.bound_connection_epoch != self._bound_connection_epoch:
            raise SetpointHlTransportError(
                "yaw observer is not open on the exact connection epoch"
            )
        if not yaw_reader.is_open:
            raise SetpointHlTransportError(
                "yaw observer must be open before horizontal physical movement"
            )
        if type(timing_policy) is not high_level_timing.HighLevelTimingPolicy:
            raise SetpointHlTransportError(
                "exact #268 HighLevelTimingPolicy is required"
            )
        yaw_timeout = _positive_timeout(yaw_timeout_seconds, "fresh yaw timeout")

        def build() -> bytes:
            observation = yaw_reader.read(timeout_seconds=yaw_timeout)
            if observation.connection_epoch != self._bound_connection_epoch:
                raise SetpointHlTransportError(
                    "fresh yaw observation belongs to another connection epoch"
                )
            target = high_level_semantics.body_relative_move(
                direction,
                distance_m,
                observation.yaw_rad,
            )
            duration = timing_policy.horizontal_move_duration(distance_m)
            return _go_to_request(target, duration)

        return self._send_go_to_once(
            build,
            reply_timeout_seconds=reply_timeout_seconds,
        )

    def send_turn(
        self,
        *,
        angle_deg: object,
        timing_policy: high_level_timing.HighLevelTimingPolicy,
        reply_timeout_seconds: float = _DEFAULT_REPLY_TIMEOUT_SECONDS,
    ) -> high_level_ack.HighLevelAckResult:
        """Send one #256/#268 relative yaw GO_TO_2 command."""
        if type(timing_policy) is not high_level_timing.HighLevelTimingPolicy:
            raise SetpointHlTransportError(
                "exact #268 HighLevelTimingPolicy is required"
            )

        def build() -> bytes:
            target = high_level_semantics.relative_turn(angle_deg)
            duration = timing_policy.turn_duration(angle_deg)
            return _go_to_request(target, duration)

        return self._send_go_to_once(
            build,
            reply_timeout_seconds=reply_timeout_seconds,
        )


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
flying phase. A zero result moves #273 only to awaiting-completion; fresh #257
completion evidence must establish flying again before another motion effect.
Timeout, disconnect, malformed reply, send failure or epoch change is ambiguous
and remains fail-closed.

packet_factory exists only as a deterministic test seam. The returned packet is
revalidated byte-for-byte and for exact SETPOINT_HL port before the effect
boundary, so it cannot substitute another physical command.
"""

from __future__ import annotations

import math
import struct
from threading import Event, Lock
from time import monotonic
from typing import Callable

import high_level_ack
import high_level_semantics
import high_level_timing
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
        safelink_precondition: safelink_precondition.LiveSafeLinkPrecondition,
        teacher_authorization: teacher_run_authorization.TeacherRunAuthorization,
        powered_session: powered_session_authority.EstablishedPoweredSession,
        watchdog_guard: watchdog_liveness.EmergencyWatchdogLivenessGuard,
        supervisor_reader: supervisor_state.FreshSupervisorStateReader,
        current_preflight_binding_reader: Callable[
            [], teacher_run_authorization.PhysicalRunBinding
        ],
        packet_factory: Callable[[bytes], object] | None = None,
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
        if type(safelink_precondition) is not safelink_precondition_module_type():
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

        self._cf = crazyflie
        self._execution = execution_domain
        self._ack = acknowledgement_domain
        self._safelink = safelink_precondition
        self._teacher = teacher_authorization
        self._powered_session = powered_session
        self._watchdog = watchdog_guard
        self._supervisor = supervisor_reader
        self._current_preflight_binding_reader = _require_callable(
            current_preflight_binding_reader,
            "current exact preflight binding reader",
        )
        self._packet_factory = _require_callable(
            packet_factory or _default_packet_factory,
            "SETPOINT_HL packet factory",
        )
        self._clock = _require_callable(clock, "monotonic clock")

        epoch = _nonempty_text(
            acknowledgement_domain.bound_connection_epoch,
            "HighLevel acknowledgement epoch",
        )
        if safelink_precondition.bound_crazyflie is not crazyflie:
            raise SetpointHlTransportError(
                "SafeLink precondition is not bound to the exact Crazyflie"
            )
        if safelink_precondition.bound_connection_epoch != epoch:
            raise SetpointHlTransportError(
                "SafeLink and acknowledgement domains are not bound to the same epoch"
            )
        if teacher_authorization.binding.connection_epoch != epoch:
            raise SetpointHlTransportError(
                "teacher run receipt belongs to a different connection epoch"
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
            binding = self._current_preflight_binding_reader()
        except Exception as exc:
            raise SetpointHlTransportError(
                "current exact preflight binding is unavailable"
            ) from exc
        if type(binding) is not teacher_run_authorization.PhysicalRunBinding:
            raise SetpointHlTransportError(
                "current preflight reader did not return PhysicalRunBinding"
            )
        if binding.connection_epoch != self._bound_connection_epoch:
            raise SetpointHlTransportError(
                "current preflight binding belongs to a different connection epoch"
            )
        return binding

    def _assert_current_authority(self) -> None:
        """Re-establish mutable run authority/evidence at one effect boundary."""
        binding = self._read_current_binding()
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

    def _read_fresh_flying(self) -> object:
        """Require one fresh same-epoch #257 non-fault flying observation."""
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
        if getattr(state, "blocking_fault", None) is not False:
            raise SetpointHlTransportError(
                "fresh supervisor state has a blocking or unknown fault"
            )
        if getattr(state, "is_flying", None) is not True:
            raise SetpointHlTransportError(
                "fresh supervisor state does not positively establish flight"
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

        with self._execution.effect_transaction(
            self._assert_current_authority
        ) as effect:
            request = _validate_request(builder())
            # Test seam / cflib packet construction is completed and verified
            # before the final fresh safety/authority observations.
            packet = self._packet_factory(request)
            self._validate_packet(packet, request)

            # Request construction may block for fresh yaw. Re-establish fresh
            # supervisor flight safety first, then mutable teacher/watchdog
            # authority, immediately before SafeLink/#271/emission.
            self._read_fresh_flying()
            self._assert_current_authority()
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
                        effect.mark_accepted()
                    else:
                        effect.mark_definitive_rejection()
                    return result
                finally:
                    if callback_installed:
                        try:
                            remove_callback(_SETPOINT_HL_PORT, on_reply)
                        except Exception:
                            pass

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


def safelink_precondition_module_type():
    """Late helper avoids shadowing the constructor argument name in isinstance checks."""
    return safelink_precondition.LiveSafeLinkPrecondition

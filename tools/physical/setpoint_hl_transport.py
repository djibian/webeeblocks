#!/usr/bin/env python3
"""Trusted one-shot SETPOINT_HL effect transport for the physical Crazyflie host.

This is the first bounded module in this directory that may emit an ordinary
flight-capable CRTP packet. It deliberately does not expose a browser/HTTP
surface and it does not build student semantics itself.

One send is eligible only inside the process-wide PhysicalExecutionDomain after
the caller-supplied exact preflight, teacher-run, powered-session/watchdog and
action-specific assertions succeed. The request builder then runs under the
same exclusion so fresh yaw/geometry/timing evidence may be consumed without a
reset race. Live SafeLink is re-checked after request construction and
immediately before the HighLevelAckDomain transaction.

The firmware reply callback is installed before the effect boundary is crossed.
The packet is sent exactly once with plain Crazyflie.send_packet(packet): this
module never supplies cflib expected_reply and therefore cannot activate its
application-level auto-retry machinery. A timeout, disconnect, malformed reply,
send exception or epoch change leaves the physical execution domain
recovery-required and poisons acknowledgement freshness for the old epoch.
A definitive non-zero firmware result restores the exact prior execution phase.
A zero result moves the execution domain only to awaiting-completion; the caller
must separately establish fresh #257/#264 completion before another effect or
reset is eligible.

Two-byte STOP/group-mask requests are intentionally outside this transport
because HighLevelAckDomain requires the firmware's three-byte surviving reply
prefix. Emergency/motor-cut STOP remains a separately justified exceptional
path.
"""

from __future__ import annotations

import math
from threading import Event, Lock
from time import monotonic
from typing import Callable, Iterable

import high_level_ack as high_level_ack
import physical_execution_domain as physical_execution
import safelink_precondition as safelink

_SETPOINT_HL_PORT = 0x08
_DEFAULT_REPLY_TIMEOUT_SECONDS = 0.2
_WAIT_SLICE_SECONDS = 0.01
_ALLOWED_REQUEST_SIZES = {7: 15, 8: 15, 12: 24}


class SetpointHlTransportError(RuntimeError):
    """Fail-closed local error for the trusted SETPOINT_HL effect transport."""


def _require_callable(value: object, name: str) -> Callable:
    if not callable(value):
        raise SetpointHlTransportError(f"{name} must be callable")
    return value


def _positive_timeout(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SetpointHlTransportError("SETPOINT_HL reply timeout must be positive")
    timeout = float(value)
    if not math.isfinite(timeout) or timeout <= 0.0:
        raise SetpointHlTransportError("SETPOINT_HL reply timeout must be positive")
    return timeout


def _request_bytes(value: object) -> bytes:
    if isinstance(value, bytearray):
        data = bytes(value)
    elif isinstance(value, bytes):
        data = value
    else:
        raise SetpointHlTransportError("SETPOINT_HL request builder must return bytes")
    if len(data) < 3:
        raise SetpointHlTransportError(
            "SETPOINT_HL ordinary effect request requires a three-byte reply prefix"
        )
    if len(data) > 30:
        raise SetpointHlTransportError("SETPOINT_HL request exceeds CRTP data capacity")
    command = data[0]
    expected_size = _ALLOWED_REQUEST_SIZES.get(command)
    if expected_size is None:
        raise SetpointHlTransportError(
            "SETPOINT_HL command is outside the ordinary WebeeBlocks motion surface"
        )
    if len(data) != expected_size:
        raise SetpointHlTransportError(
            "SETPOINT_HL command payload size does not match pinned cflib format"
        )
    if data[1] != 0:
        raise SetpointHlTransportError(
            "SETPOINT_HL ordinary WebeeBlocks motion requires group mask zero"
        )
    return data


def _default_packet_factory(request: bytes) -> object:
    """Build the pinned cflib CRTP packet lazily on the physical host."""
    try:
        from cflib.crtp.crtpstack import CRTPPacket, CRTPPort
    except Exception as exc:
        raise SetpointHlTransportError(
            "pinned cflib CRTP packet types are unavailable"
        ) from exc
    if getattr(CRTPPort, "SETPOINT_HL", None) != _SETPOINT_HL_PORT:
        raise SetpointHlTransportError("cflib SETPOINT_HL port does not match pinned contract")
    packet = CRTPPacket()
    packet.port = CRTPPort.SETPOINT_HL
    packet.data = request
    return packet


class TrustedSetpointHlTransport:
    """Compose one acknowledged physical SETPOINT_HL send under trusted exclusion."""

    def __init__(
        self,
        *,
        crazyflie: object,
        execution_domain: physical_execution.PhysicalExecutionDomain,
        acknowledgement_domain: high_level_ack.HighLevelAckDomain,
        safelink_precondition: safelink.LiveSafeLinkPrecondition,
        packet_factory: Callable[[bytes], object] | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if crazyflie is None:
            raise SetpointHlTransportError("exact live Crazyflie object is required")
        if not isinstance(execution_domain, physical_execution.PhysicalExecutionDomain):
            raise SetpointHlTransportError(
                "trusted process-wide PhysicalExecutionDomain is required"
            )
        if not isinstance(acknowledgement_domain, high_level_ack.HighLevelAckDomain):
            raise SetpointHlTransportError(
                "HighLevelAckDomain is required for physical acknowledgement freshness"
            )
        if not isinstance(safelink_precondition, safelink.LiveSafeLinkPrecondition):
            raise SetpointHlTransportError(
                "LiveSafeLinkPrecondition is required before physical emission"
            )
        if safelink_precondition.bound_crazyflie is not crazyflie:
            raise SetpointHlTransportError(
                "SafeLink precondition is not bound to the exact Crazyflie"
            )
        if (
            safelink_precondition.bound_connection_epoch
            != acknowledgement_domain.bound_connection_epoch
        ):
            raise SetpointHlTransportError(
                "SafeLink and acknowledgement domains are not bound to the same epoch"
            )
        self._cf = crazyflie
        self._execution = execution_domain
        self._ack = acknowledgement_domain
        self._safelink = safelink_precondition
        self._packet_factory = _require_callable(
            packet_factory or _default_packet_factory,
            "SETPOINT_HL packet factory",
        )
        self._clock = _require_callable(clock, "monotonic clock")

    @property
    def bound_connection_epoch(self) -> str:
        return self._ack.bound_connection_epoch

    @property
    def execution_domain(self) -> physical_execution.PhysicalExecutionDomain:
        return self._execution

    def _require_connection_live(self) -> None:
        method = getattr(self._cf, "is_connected", None)
        if not callable(method):
            raise SetpointHlTransportError(
                "Crazyflie live connection state is unavailable during acknowledgement wait"
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
        deadline = self._clock() + timeout_seconds
        while True:
            if event.is_set():
                reply = reply_reader()
                if reply is None:
                    raise SetpointHlTransportError(
                        "SETPOINT_HL reply event has no packet data"
                    )
                return reply
            self._require_connection_live()
            remaining = deadline - self._clock()
            if remaining <= 0.0:
                raise SetpointHlTransportError(
                    "SETPOINT_HL acknowledgement timeout"
                )
            event.wait(min(_WAIT_SLICE_SECONDS, remaining))

    def send_once(
        self,
        *,
        request_builder: Callable[[], object],
        exact_preflight_assertion: Callable[[], object],
        teacher_binding_assertion: Callable[[], object],
        powered_session_assertion: Callable[[], object],
        watchdog_liveness_assertion: Callable[[], object],
        action_preconditions: Iterable[Callable[[], object]] = (),
        reply_timeout_seconds: float = _DEFAULT_REPLY_TIMEOUT_SECONDS,
    ) -> high_level_ack.HighLevelAckResult:
        """Emit exactly one ordinary SETPOINT_HL request and require its exact reply.

        The four mandatory assertions and every action-specific assertion execute
        after the process-wide reset/effect exclusion is held. request_builder
        then runs under that same exclusion; callers may use it to consume fresh
        yaw/geometry/timing evidence. SafeLink is re-checked after the request has
        been fully built and immediately before acknowledgement serialization.

        A positive return value is acknowledgement only. Callers must separately
        invoke execution_domain.complete_accepted_effect(...) with fresh
        supervisor/landing evidence before issuing another effect or reset.
        """
        builder = _require_callable(request_builder, "SETPOINT_HL request builder")
        checks = [
            _require_callable(exact_preflight_assertion, "exact preflight assertion"),
            _require_callable(teacher_binding_assertion, "teacher-run binding assertion"),
            _require_callable(powered_session_assertion, "powered-session assertion"),
            _require_callable(
                watchdog_liveness_assertion,
                "watchdog-liveness assertion",
            ),
        ]
        try:
            extra_checks = tuple(action_preconditions)
        except Exception as exc:
            raise SetpointHlTransportError(
                "action-specific physical preconditions must be iterable"
            ) from exc
        checks.extend(
            _require_callable(check, "action-specific physical precondition")
            for check in extra_checks
        )
        timeout = _positive_timeout(reply_timeout_seconds)

        with self._execution.effect_transaction(*checks) as effect:
            request = _request_bytes(builder())

            # This must remain immediately adjacent to acknowledgement
            # serialization: no other trusted precondition may be inserted
            # between the live radio duplicate-suppression proof and #271.
            self._safelink.assert_ready()

            with self._ack.transaction(request) as acknowledgement:
                packet = self._packet_factory(request)

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
                if not callable(add_callback) or not callable(remove_callback):
                    raise SetpointHlTransportError(
                        "Crazyflie SETPOINT_HL reply callback surface is unavailable"
                    )

                callback_installed = False
                try:
                    add_callback(_SETPOINT_HL_PORT, on_reply)
                    callback_installed = True

                    # Both state machines cross their pessimistic boundary before
                    # the single caller-side physical send. No send occurs before
                    # these two calls have succeeded.
                    acknowledgement.mark_emitted()
                    effect.mark_emitted()

                    # Deliberately one positional argument only: cflib's
                    # expected-reply auto-resend path is never activated here.
                    self._cf.send_packet(packet)

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
                            # Callback cleanup cannot change the already-sent
                            # physical effect outcome. The callback itself is
                            # one-shot and ignores all packets after its first.
                            pass

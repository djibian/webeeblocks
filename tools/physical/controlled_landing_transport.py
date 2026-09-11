#!/usr/bin/env python3
"""Trusted controlled terminal LAND_2 effect for the physical Crazyflie.

This module extends the integrated #276 host-local SETPOINT_HL trust root with
one fixed-policy terminal landing primitive for #304. It exposes no altitude,
duration, yaw, raw-byte or retry surface: the only command is pinned cflib
``COMMAND_LAND_2`` to absolute 0.0 m over 2.0 s while preserving current yaw.

Authority remains the exact #276 composition. Fresh current-program provenance,
teacher binding, powered session, watchdog, supervisor state, SafeLink and
acknowledgement freshness are checked at the effect boundary. Positive firmware
acknowledgement is not completion: the private #279 permit is consumed only
after the integrated #264 observer establishes a later same-epoch finished,
non-flying, high-level-inactive state. Importing this module performs no effect.
"""

from __future__ import annotations

import struct
from threading import Event, Lock
from typing import Callable

import high_level_ack
import landing_completion
import physical_execution_domain
import setpoint_hl_transport

_COMMAND_LAND_2 = 8
_LAND_GROUP_MASK = 0
_LAND_ABSOLUTE_HEIGHT_M = 0.0
_LAND_TARGET_YAW_RAD = 0.0
_LAND_USE_CURRENT_YAW = True
_LAND_DURATION_SECONDS = 2.0
_LAND_PACKET = struct.Struct("<BBff?f")
_DEFAULT_REPLY_TIMEOUT_SECONDS = 0.2
_LANDING_COMPLETION_TIMEOUT_SECONDS = 8.0


class ControlledLandingTransportError(setpoint_hl_transport.SetpointHlTransportError):
    """Fail-closed trusted controlled-landing transport error."""


def _landing_request() -> bytes:
    return _LAND_PACKET.pack(
        _COMMAND_LAND_2,
        _LAND_GROUP_MASK,
        _LAND_ABSOLUTE_HEIGHT_M,
        _LAND_TARGET_YAW_RAD,
        _LAND_USE_CURRENT_YAW,
        _LAND_DURATION_SECONDS,
    )


def _validate_landing_request(value: object) -> bytes:
    if isinstance(value, bytearray):
        data = bytes(value)
    elif isinstance(value, bytes):
        data = value
    else:
        raise ControlledLandingTransportError("validated LAND_2 request must be bytes")
    if len(data) != _LAND_PACKET.size:
        raise ControlledLandingTransportError("LAND_2 payload size does not match pinned cflib")
    command, group_mask, height, yaw, use_current_yaw, duration = _LAND_PACKET.unpack(data)
    if command != _COMMAND_LAND_2 or group_mask != _LAND_GROUP_MASK:
        raise ControlledLandingTransportError("only the fixed single-Crazyflie LAND_2 policy is available")
    if (
        height != _LAND_ABSOLUTE_HEIGHT_M
        or yaw != _LAND_TARGET_YAW_RAD
        or use_current_yaw is not _LAND_USE_CURRENT_YAW
        or duration != _LAND_DURATION_SECONDS
    ):
        raise ControlledLandingTransportError("LAND_2 request differs from trusted host landing policy")
    return data


class TrustedControlledLandingTransport(setpoint_hl_transport.TrustedSetpointHlTransport):
    """#276 transport plus one host-policy terminal LAND_2 effect."""

    def __init__(
        self,
        *,
        connection_epoch_reader: Callable[[], str],
        **kwargs,
    ) -> None:
        if not callable(connection_epoch_reader):
            raise ControlledLandingTransportError(
                "live connection epoch reader is required for controlled landing"
            )
        super().__init__(**kwargs)
        self._landing_observer = landing_completion.ControlledLandingCompletionObserver(
            self._supervisor,
            connection_epoch_reader,
        )
        if self._landing_observer.bound_connection_epoch != self.bound_connection_epoch:
            raise ControlledLandingTransportError(
                "landing completion observer belongs to a different connection epoch"
            )

    def _force_landing_completion_uncertainty(
        self,
        permit: physical_execution_domain.AcceptedEffectCompletionPermit,
    ) -> None:
        if self.execution_domain.phase == physical_execution_domain.AWAITING_COMPLETION:
            try:
                self.execution_domain.complete_accepted_effect(
                    permit,
                    physical_execution_domain.INACTIVE,
                    lambda: False,
                )
            except physical_execution_domain.PhysicalExecutionDomainError:
                pass

    def _await_landing_completion(
        self,
        permit: physical_execution_domain.AcceptedEffectCompletionPermit,
        baseline: landing_completion.PreLandingFlightEvidence,
    ) -> None:
        if type(permit) is not physical_execution_domain.AcceptedEffectCompletionPermit:
            raise ControlledLandingTransportError(
                "exact accepted-effect completion permit is required for landing"
            )
        try:
            self._watchdog.assert_live()
            evidence = self._landing_observer.await_completion(
                baseline,
                total_timeout_seconds=_LANDING_COMPLETION_TIMEOUT_SECONDS,
            )
            self._watchdog.assert_live()

            def prove_completion() -> bool:
                self._watchdog.assert_live()
                state = evidence.supervisor_state
                return (
                    evidence.connection_epoch == self.bound_connection_epoch
                    and getattr(state, "blocking_fault", None) is False
                    and getattr(state, "is_flying", None) is False
                    and getattr(state, "hl_control_active", None) is False
                    and getattr(state, "hl_traj_finished", None) is True
                )

            self.execution_domain.complete_accepted_effect(
                permit,
                physical_execution_domain.INACTIVE,
                prove_completion,
            )
        except Exception:
            self._force_landing_completion_uncertainty(permit)
            raise

    def send_controlled_landing(self) -> high_level_ack.HighLevelAckResult:
        """Emit the fixed host-policy terminal landing exactly once."""
        request = _validate_landing_request(_landing_request())
        result: high_level_ack.HighLevelAckResult | None = None
        completion_permit: physical_execution_domain.AcceptedEffectCompletionPermit | None = None
        baseline: landing_completion.PreLandingFlightEvidence | None = None

        with self.execution_domain.effect_transaction(self._assert_current_authority) as effect:
            packet = setpoint_hl_transport._default_packet_factory(request)
            self._validate_packet(packet, request)

            # Preserve #276 ordering: fresh host-owned current-program assertion,
            # fresh finished-flight state, another authority check, then SafeLink.
            final_binding = self._read_current_binding()
            self._assert_binding_authority(final_binding)
            self._read_fresh_finished_flying()
            baseline = self._landing_observer.capture_pre_land_flight()
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
                if not callable(add_callback) or not callable(remove_callback) or not callable(send_packet):
                    raise ControlledLandingTransportError(
                        "Crazyflie SETPOINT_HL callback/send surface is unavailable"
                    )
                callback_installed = False
                try:
                    add_callback(setpoint_hl_transport._SETPOINT_HL_PORT, on_reply)
                    callback_installed = True
                    acknowledgement.mark_emitted()
                    effect.mark_emitted()
                    send_packet(packet)
                    try:
                        reply = self._wait_for_reply(
                            reply_event,
                            read_reply,
                            _DEFAULT_REPLY_TIMEOUT_SECONDS,
                        )
                    except Exception as exc:
                        acknowledgement.fail_ambiguous(str(exc))
                    result = acknowledgement.resolve_reply(reply)
                    if result.accepted:
                        completion_permit = effect.mark_accepted()
                    else:
                        effect.mark_definitive_rejection()
                finally:
                    if callback_installed:
                        try:
                            remove_callback(setpoint_hl_transport._SETPOINT_HL_PORT, on_reply)
                        except Exception:
                            pass

        if result is None:
            raise ControlledLandingTransportError("LAND_2 acknowledgement result is unavailable")
        if result.accepted:
            if completion_permit is None or baseline is None:
                raise ControlledLandingTransportError(
                    "accepted LAND_2 effect lacks private completion state"
                )
            self._await_landing_completion(completion_permit, baseline)
        return result

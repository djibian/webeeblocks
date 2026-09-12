#!/usr/bin/env python3
"""Trusted controlled landing for shared-interpreter dynamic physical programs.

The integrated static physical sequence can derive terminal descent from the whole
flat AST before takeoff. A dynamic program cannot: the exact branch/repeat path is
selected later by the existing shared Runtime interpreter from fresh sensor data.
This transport therefore retains one host-local nominal world-Z value and advances
it only after a definitively accepted vertical effect. Terminal landing uses that
completed runtime state while preserving the existing teacher/current-program,
powered-session, watchdog, supervisor, SafeLink, acknowledgement and fresh
completion authority chain.

No independent initial-altitude input exists. The transport derives its initial
nominal altitude from the exact teacher-bound canonical AST through the integrated
conservative dynamic preflight. This makes the runtime landing root the same
preflight-proven takeoff height used by the bound dynamic backend; a later host
composition can reject any disagreement before the shared interpreter progresses.
"""

from __future__ import annotations

from math import isfinite
import struct
from threading import Event, Lock

import controlled_landing_transport
import high_level_ack
import high_level_semantics
import high_level_timing
import landing_command
import physical_dynamic_preflight
import physical_execution_domain
import physical_program_sequence
import setpoint_hl_transport

_LAND_PACKET = struct.Struct("<BBf?f?f")


class DynamicControlledLandingTransportError(
    controlled_landing_transport.ControlledLandingTransportError
):
    """Fail-closed error for dynamic host-owned terminal-altitude composition."""


def _nominal_altitude(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DynamicControlledLandingTransportError(
            "dynamic nominal altitude must be finite"
        )
    parsed = float(value)
    if (
        not isfinite(parsed)
        or parsed < physical_program_sequence.MIN_NOMINAL_ALTITUDE_M
        or parsed > physical_program_sequence.MAX_NOMINAL_ALTITUDE_M
    ):
        raise DynamicControlledLandingTransportError(
            "dynamic nominal altitude violates established 0.2-1.5 m bounds"
        )
    return parsed


class TrustedDynamicControlledLandingTransport(
    controlled_landing_transport.TrustedControlledLandingTransport
):
    """Existing trusted effect transport plus runtime-selected nominal altitude."""

    def __init__(self, **kwargs) -> None:
        authorization = kwargs.get("teacher_authorization")
        binding = getattr(authorization, "binding", None)
        ast_binding = getattr(binding, "ast_binding", None)
        try:
            safety = physical_dynamic_preflight.validate_bound_dynamic_program(ast_binding)
        except physical_dynamic_preflight.DynamicPhysicalPreflightError as exc:
            raise DynamicControlledLandingTransportError(
                "exact dynamic preflight cannot establish initial landing altitude"
            ) from exc
        if safety.ast_binding != ast_binding:
            raise DynamicControlledLandingTransportError(
                "dynamic landing preflight changed the exact teacher-bound AST"
            )
        initial = _nominal_altitude(safety.initial_altitude_m)
        self._initial_nominal_altitude_m = initial
        self._nominal_altitude_m = initial
        super().__init__(**kwargs)

    @property
    def initial_nominal_altitude_m(self) -> float:
        """Exact teacher-AST/preflight-derived root for runtime altitude state."""
        return self._initial_nominal_altitude_m

    @property
    def nominal_altitude_m(self) -> float:
        return self._nominal_altitude_m

    def send_vertical_move(
        self,
        *,
        direction: str,
        distance_m: object,
        timing_policy: high_level_timing.HighLevelTimingPolicy,
        reply_timeout_seconds: float = setpoint_hl_transport._DEFAULT_REPLY_TIMEOUT_SECONDS,
    ) -> high_level_ack.HighLevelAckResult:
        """Advance host-local nominal Z only after definitive vertical completion."""
        try:
            target = high_level_semantics.vertical_move(direction, distance_m)
        except (TypeError, ValueError, high_level_semantics.HighLevelSemanticError) as exc:
            raise DynamicControlledLandingTransportError(
                "dynamic vertical move violates integrated semantics"
            ) from exc
        next_altitude = _nominal_altitude(self._nominal_altitude_m + target.z_m)
        result = super().send_vertical_move(
            direction=direction,
            distance_m=distance_m,
            timing_policy=timing_policy,
            reply_timeout_seconds=reply_timeout_seconds,
        )
        if getattr(result, "accepted", None) is True:
            self._nominal_altitude_m = next_altitude
        return result

    def _dynamic_landing_request(self) -> bytes:
        descent_m = _nominal_altitude(self._nominal_altitude_m)
        return _LAND_PACKET.pack(
            landing_command.LAND_WITH_VELOCITY_COMMAND,
            landing_command.LAND_GROUP_MASK,
            descent_m,
            True,
            0.0,
            True,
            landing_command.LAND_VELOCITY_M_S,
        )

    def send_controlled_landing(
        self,
        *,
        reply_timeout_seconds: float = controlled_landing_transport._DEFAULT_REPLY_TIMEOUT_SECONDS,
    ) -> high_level_ack.HighLevelAckResult:
        """Land from the definitively completed interpreter-selected nominal Z."""
        timeout = setpoint_hl_transport._positive_timeout(
            reply_timeout_seconds,
            "SETPOINT_HL landing reply timeout",
        )
        result: high_level_ack.HighLevelAckResult | None = None
        completion_permit: physical_execution_domain.AcceptedEffectCompletionPermit | None = None
        baseline = None

        with self.execution_domain.effect_transaction(self._assert_current_authority) as effect:
            initial_binding = self._read_current_binding()
            self._assert_binding_authority(initial_binding)
            request = self._dynamic_landing_request()
            packet = setpoint_hl_transport._default_packet_factory(request)
            self._validate_packet(packet, request)

            self._read_fresh_finished_flying()
            baseline = self._landing_observer.capture_pre_land_flight()
            final_binding = self._read_current_binding()
            self._assert_binding_authority(final_binding)
            if final_binding != initial_binding:
                raise DynamicControlledLandingTransportError(
                    "current physical program changed during dynamic landing preparation"
                )
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
                    raise DynamicControlledLandingTransportError(
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
                        reply = self._wait_for_reply(reply_event, read_reply, timeout)
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
                            remove_callback(
                                setpoint_hl_transport._SETPOINT_HL_PORT,
                                on_reply,
                            )
                        except Exception:
                            pass

        if result is None:
            raise DynamicControlledLandingTransportError(
                "dynamic controlled landing acknowledgement result is unavailable"
            )
        if result.accepted:
            if completion_permit is None or baseline is None:
                raise DynamicControlledLandingTransportError(
                    "accepted dynamic landing lacks private completion state"
                )
            self._await_landing_completion(completion_permit, baseline)
        return result

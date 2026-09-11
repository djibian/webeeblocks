#!/usr/bin/env python3
"""Trusted exactly-once terminal landing effect for the physical Crazyflie.

This module completes the bounded #304 effect core on top of the integrated #276
SETPOINT_HL trust root.  It emits only the pure command-10 request produced by
:mod:`landing_command` from the exact teacher-bound canonical AST.  No caller
height, velocity, yaw, raw packet, retry control, program index or authority
object is accepted by the landing method.

The normal landing path preserves the existing current-program/teacher/session/
watchdog/supervisor/SafeLink/acknowledgement/exclusion authorities.  Positive
firmware acknowledgement is not completion: the private #279 permit is consumed
only after #264 establishes a later fresh same-epoch finished, non-flying,
high-level-inactive state.  Ambiguous send/ack/completion outcome fails closed
and requires recovery rather than manufacturing an application retry.

Importing this module performs no physical effect.
"""

from __future__ import annotations

from threading import Event, Lock
from typing import Callable

import high_level_ack
import landing_command
import landing_completion
import physical_execution_domain
import setpoint_hl_transport

_DEFAULT_REPLY_TIMEOUT_SECONDS = 0.2
_LANDING_COMPLETION_TIMEOUT_SECONDS = 8.0


class ControlledLandingTransportError(setpoint_hl_transport.SetpointHlTransportError):
    """Fail-closed trusted controlled-landing transport error."""


def _require_callable(value: object, name: str) -> Callable:
    if not callable(value):
        raise ControlledLandingTransportError(f"{name} must be callable")
    return value


class TrustedControlledLandingTransport(setpoint_hl_transport.TrustedSetpointHlTransport):
    """#276 trusted transport plus one exact terminal command-10 effect."""

    def __init__(
        self,
        *,
        connection_epoch_reader: Callable[[], str],
        **kwargs,
    ) -> None:
        self._connection_epoch_reader = _require_callable(
            connection_epoch_reader,
            "live connection epoch reader",
        )
        super().__init__(**kwargs)
        self._landing_observer = landing_completion.ControlledLandingCompletionObserver(
            self._supervisor,
            self._connection_epoch_reader,
        )
        if self._landing_observer.bound_connection_epoch != self.bound_connection_epoch:
            raise ControlledLandingTransportError(
                "landing completion observer belongs to a different connection epoch"
            )

    @staticmethod
    def _validate_landing_packet(packet: object, request: bytes) -> None:
        if getattr(packet, "port", None) != setpoint_hl_transport._SETPOINT_HL_PORT:
            raise ControlledLandingTransportError(
                "packet factory substituted a non-SETPOINT_HL landing port"
            )
        try:
            packet_data = bytes(getattr(packet, "data"))
        except Exception as exc:
            raise ControlledLandingTransportError(
                "packet factory returned unreadable landing data"
            ) from exc
        if packet_data != request:
            raise ControlledLandingTransportError(
                "packet factory substituted the exact bound landing request"
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
        """Emit the exact teacher-bound terminal landing once, with no parameters."""
        try:
            bound = landing_command.derive_bound_landing_command(
                self.teacher_binding.ast_binding
            )
        except landing_command.LandingCommandError as exc:
            raise ControlledLandingTransportError(
                "exact teacher-bound landing request is unavailable"
            ) from exc

        request = bound.request
        result: high_level_ack.HighLevelAckResult | None = None
        completion_permit: physical_execution_domain.AcceptedEffectCompletionPermit | None = None
        baseline: landing_completion.PreLandingFlightEvidence | None = None

        with self.execution_domain.effect_transaction(self._assert_current_authority) as effect:
            if bound.ast_binding != self.teacher_binding.ast_binding:
                raise ControlledLandingTransportError(
                    "derived landing no longer matches the exact teacher-bound AST"
                )
            packet = setpoint_hl_transport._default_packet_factory(request)
            self._validate_landing_packet(packet, request)

            # Preserve #276's immediate authority topology around the effect:
            # fresh host-owned provenance, fresh finished-flight evidence,
            # one #264 pre-land baseline, rechecked authority, then SafeLink.
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
                if (
                    not callable(add_callback)
                    or not callable(remove_callback)
                    or not callable(send_packet)
                ):
                    raise ControlledLandingTransportError(
                        "Crazyflie SETPOINT_HL callback/send surface is unavailable"
                    )

                callback_installed = False
                try:
                    add_callback(setpoint_hl_transport._SETPOINT_HL_PORT, on_reply)
                    callback_installed = True
                    acknowledgement.mark_emitted()
                    effect.mark_emitted()
                    # Deliberately exactly one plain send: no expected_reply,
                    # retry or alternate application-level landing path exists.
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
                            remove_callback(
                                setpoint_hl_transport._SETPOINT_HL_PORT,
                                on_reply,
                            )
                        except Exception:
                            pass

        if result is None:
            raise ControlledLandingTransportError(
                "landing acknowledgement result is unavailable"
            )
        if result.accepted:
            if completion_permit is None or baseline is None:
                raise ControlledLandingTransportError(
                    "accepted landing lacks private completion state"
                )
            self._await_landing_completion(completion_permit, baseline)
        return result

#!/usr/bin/env python3
"""Trusted exactly-once terminal landing effect for the physical Crazyflie.

This module composes the pure exact-AST command-10 semantics from
``landing_command`` with the already integrated #276 physical-host trust root.
It adds no caller-selected landing height, velocity, yaw, raw packet, retry or
alternate authority surface.

A landing request is derived only from the exact teacher-bound canonical AST.
Fresh host-local current-program provenance, teacher binding, powered-session and
watchdog state, supervisor flight state, SafeLink and acknowledgement freshness
are rechecked at the effect boundary. The callback is installed before one plain
``Crazyflie.send_packet`` call. Positive acknowledgement is not completion: the
private #279 permit is consumed only after #264 observes a later same-epoch
finished, non-flying, high-level-inactive state. Any ambiguous post-emission or
completion outcome remains fail closed and requires recovery.
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
    """Fail-closed trusted terminal-landing transport error."""


class TrustedControlledLandingTransport(setpoint_hl_transport.TrustedSetpointHlTransport):
    """The #276 effect core extended with one exact terminal landing primitive."""

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

    def _force_completion_uncertainty(
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
            self._force_completion_uncertainty(permit)
            raise

    def send_controlled_landing(
        self,
        *,
        reply_timeout_seconds: float = _DEFAULT_REPLY_TIMEOUT_SECONDS,
    ) -> high_level_ack.HighLevelAckResult:
        """Emit the exact AST-derived command-10 landing once and prove completion."""
        timeout = setpoint_hl_transport._positive_timeout(
            reply_timeout_seconds,
            "SETPOINT_HL landing reply timeout",
        )
        result: high_level_ack.HighLevelAckResult | None = None
        completion_permit: physical_execution_domain.AcceptedEffectCompletionPermit | None = None
        baseline: landing_completion.PreLandingFlightEvidence | None = None

        with self.execution_domain.effect_transaction(self._assert_current_authority) as effect:
            # Bind the pure command to a fresh host-owned current-program read,
            # not merely to the earlier immutable teacher receipt.  The effect
            # transaction has already performed its own authority reconstruction;
            # this explicit binding is retained so a later final read can prove
            # that no program change occurred while fresh supervisor evidence was
            # being acquired.
            initial_binding = self._read_current_binding()
            self._assert_binding_authority(initial_binding)
            try:
                bound_command = landing_command.derive_bound_landing_command(
                    initial_binding.ast_binding
                )
            except landing_command.LandingCommandError as exc:
                raise ControlledLandingTransportError(str(exc)) from exc
            if bound_command.ast_binding != initial_binding.ast_binding:
                raise ControlledLandingTransportError(
                    "derived landing command differs from current-program provenance"
                )
            request = bytes(bound_command.request)
            packet = setpoint_hl_transport._default_packet_factory(request)
            self._validate_packet(packet, request)

            # Fresh supervisor reads may block.  Reconstruct current-program
            # provenance again afterwards, immediately before the SafeLink/ack
            # effect boundary, so a workspace/program change during those reads
            # cannot inherit the earlier authority.
            self._read_fresh_finished_flying()
            baseline = self._landing_observer.capture_pre_land_flight()
            final_binding = self._read_current_binding()
            self._assert_binding_authority(final_binding)
            if final_binding != initial_binding:
                raise ControlledLandingTransportError(
                    "current physical program changed during landing preparation"
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
            raise ControlledLandingTransportError(
                "controlled landing acknowledgement result is unavailable"
            )
        if result.accepted:
            if completion_permit is None or baseline is None:
                raise ControlledLandingTransportError(
                    "accepted controlled landing lacks private completion state"
                )
            self._await_landing_completion(completion_permit, baseline)
        return result

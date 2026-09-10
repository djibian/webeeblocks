#!/usr/bin/env python3
"""Production-shaped trusted-host takeoff lifecycle for one physical run.

This module is the causal composition missing after the bounded #289 takeoff
core. It performs no work when imported. A trusted host supplies the already
constructed #266 reset factory, the distinct post-reset #290 teacher channel,
and a host-local transport factory whose only positive current-program path is
the lexical #278/#249 bridge closure in ``serve_physical_host.py``.

The order is intentionally fixed and fail closed:

    #273 reset exclusion -> #266 new powered session -> #290/#267 exact teacher
    decision on that new epoch -> #257/#262 watchdog -> #272/#271 domains ->
    host-bound #289 command-9 transport -> causal #273 ``flying`` completion.

The ordinary caller cannot provide any object in that authority chain. It may
only stage the non-authority profile/AST intent before this controller is called.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import high_level_ack
import physical_execution_domain
import post_reset_teacher_decision
import powered_session_authority
import safelink_precondition
import supervisor_state
import takeoff_transport
import teacher_run_authorization
import watchdog_liveness


class ProductionTakeoffRunError(RuntimeError):
    """Fail-closed error for the production trusted-host takeoff lifecycle."""


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ProductionTakeoffRunError(f"{name} must be non-empty trimmed text")
    return value


def _require_callable(value: object, name: str) -> Callable:
    if not callable(value):
        raise ProductionTakeoffRunError(f"{name} must be callable")
    return value


@dataclass(frozen=True, slots=True)
class ActivePhysicalTakeoffRun:
    """Process-local authority bundle retained only inside the trusted host."""

    crazyflie: object
    execution_domain: physical_execution_domain.PhysicalExecutionDomain
    acknowledgement_domain: high_level_ack.HighLevelAckDomain
    safelink_guard: safelink_precondition.LiveSafeLinkPrecondition
    teacher_authorization: teacher_run_authorization.TeacherRunAuthorization
    powered_session: powered_session_authority.EstablishedPoweredSession
    watchdog_guard: watchdog_liveness.EmergencyWatchdogLivenessGuard
    supervisor_reader: supervisor_state.FreshSupervisorStateReader


class ProductionTakeoffRunController:
    """One-shot production lifecycle from reset recovery to causal flight."""

    def __init__(
        self,
        *,
        powered_session_factory: powered_session_authority.TrustedPoweredSessionFactory,
        teacher_channel: post_reset_teacher_decision.PostResetTeacherDecisionChannel,
        teacher_authorizer: teacher_run_authorization.TrustedTeacherAuthorizer,
        connection_epoch_reader: Callable[[], str],
        host_bound_transport_factory: Callable[..., object],
        execution_domain: physical_execution_domain.PhysicalExecutionDomain | None = None,
    ) -> None:
        if type(powered_session_factory) is not powered_session_authority.TrustedPoweredSessionFactory:
            raise ProductionTakeoffRunError("exact #266 TrustedPoweredSessionFactory is required")
        if type(teacher_channel) is not post_reset_teacher_decision.PostResetTeacherDecisionChannel:
            raise ProductionTakeoffRunError("exact #290 post-reset teacher channel is required")
        if type(teacher_authorizer) is not teacher_run_authorization.TrustedTeacherAuthorizer:
            raise ProductionTakeoffRunError("exact #267 TrustedTeacherAuthorizer is required")
        if execution_domain is None:
            execution_domain = physical_execution_domain.PhysicalExecutionDomain()
        if type(execution_domain) is not physical_execution_domain.PhysicalExecutionDomain:
            raise ProductionTakeoffRunError("exact process-wide #273 execution domain is required")

        self._powered_factory = powered_session_factory
        self._teacher_channel = teacher_channel
        self._teacher_authorizer = teacher_authorizer
        self._epoch_reader = _require_callable(connection_epoch_reader, "connection epoch reader")
        self._transport_factory = _require_callable(
            host_bound_transport_factory,
            "host-bound takeoff transport factory",
        )
        self._execution = execution_domain
        self._used = False
        self._active: ActivePhysicalTakeoffRun | None = None

    @property
    def active_run(self) -> ActivePhysicalTakeoffRun | None:
        return self._active

    @property
    def execution_domain(self) -> physical_execution_domain.PhysicalExecutionDomain:
        return self._execution

    def _read_epoch(self) -> str:
        try:
            value = self._epoch_reader()
        except Exception as exc:
            raise ProductionTakeoffRunError("live host connection epoch is unavailable") from exc
        return _text(value, "live host connection epoch")

    def start(
        self,
        *,
        profile_id: str,
        ast_binding: str,
        previous_connection_epoch: str,
    ) -> ActivePhysicalTakeoffRun:
        """Establish one exact run and reach ``flying`` only through real domains."""
        if self._used:
            raise ProductionTakeoffRunError("production takeoff controller is one-shot")
        self._used = True

        profile = _text(profile_id, "profileId")
        ast = _text(ast_binding, "astBinding")
        previous_epoch = _text(previous_connection_epoch, "previous connection epoch")
        if self._read_epoch() != previous_epoch:
            raise ProductionTakeoffRunError(
                "staged run no longer matches the live pre-reset connection epoch"
            )

        receipt: teacher_run_authorization.TeacherRunAuthorization | None = None
        watchdog: watchdog_liveness.EmergencyWatchdogLivenessGuard | None = None
        try:
            established = self._execution.run_reset_establishment(
                lambda: self._powered_factory.establish(
                    previous_connection_epoch=previous_epoch,
                )
            )
            if type(established) is not powered_session_authority.EstablishedPoweredSession:
                raise ProductionTakeoffRunError("#266 returned an invalid established powered session")
            if self._execution.phase != physical_execution_domain.INACTIVE:
                raise ProductionTakeoffRunError("#266 did not establish the shared inactive phase")
            if self._read_epoch() != established.connection_epoch:
                raise ProductionTakeoffRunError("post-reset powered session is not the live host epoch")
            if established.connection_epoch == previous_epoch:
                raise ProductionTakeoffRunError("post-reset run reused the pre-reset epoch")

            binding = teacher_run_authorization.PhysicalRunBinding(
                profile_id=profile,
                ast_binding=ast,
                connection_epoch=established.connection_epoch,
            )
            receipt = self._teacher_channel.receive_authorization_for_binding(
                self._teacher_authorizer,
                binding,
            )
            if type(receipt) is not teacher_run_authorization.TeacherRunAuthorization:
                raise ProductionTakeoffRunError("post-reset teacher decision minted no exact receipt")
            receipt.assert_effect_binding(
                profile_id=profile,
                ast_binding=ast,
                connection_epoch=established.connection_epoch,
            )

            crazyflie = established.session
            supervisor = supervisor_state.FreshSupervisorStateReader(
                crazyflie,
                self._epoch_reader,
            )
            watchdog = watchdog_liveness.EmergencyWatchdogLivenessGuard(
                crazyflie,
                self._epoch_reader,
                supervisor,
                established.watchdog_authority,
            )
            watchdog.activate()
            watchdog.assert_live()

            acknowledgement = high_level_ack.HighLevelAckDomain(self._epoch_reader)
            safelink = safelink_precondition.LiveSafeLinkPrecondition(
                crazyflie,
                self._epoch_reader,
            )
            transport = self._transport_factory(
                crazyflie=crazyflie,
                execution_domain=self._execution,
                acknowledgement_domain=acknowledgement,
                safelink_guard=safelink,
                teacher_authorization=receipt,
                powered_session=established,
                watchdog_guard=watchdog,
                supervisor_reader=supervisor,
            )
            if not isinstance(transport, takeoff_transport.TrustedTakeoffTransport):
                raise ProductionTakeoffRunError(
                    "host-bound factory returned no trusted #289 takeoff transport"
                )
            if transport.bound_connection_epoch != established.connection_epoch:
                raise ProductionTakeoffRunError("takeoff transport is not bound to post-reset epoch")
            if transport.teacher_binding != binding:
                raise ProductionTakeoffRunError("takeoff transport lost exact teacher run binding")

            result = transport.send_from_authorized_ast()
            if type(result) is not high_level_ack.HighLevelAckResult or result.accepted is not True:
                raise ProductionTakeoffRunError("takeoff was not positively acknowledged")
            if self._execution.phase != physical_execution_domain.FLYING:
                raise ProductionTakeoffRunError("causal takeoff did not establish shared flying phase")
            watchdog.assert_live()
            receipt.assert_effect_binding(
                profile_id=profile,
                ast_binding=ast,
                connection_epoch=established.connection_epoch,
            )

            active = ActivePhysicalTakeoffRun(
                crazyflie=crazyflie,
                execution_domain=self._execution,
                acknowledgement_domain=acknowledgement,
                safelink_guard=safelink,
                teacher_authorization=receipt,
                powered_session=established,
                watchdog_guard=watchdog,
                supervisor_reader=supervisor,
            )
            self._active = active
            return active
        except Exception as exc:
            if watchdog is not None and watchdog.active:
                try:
                    watchdog.stop_for_terminal_reboot()
                except Exception:
                    pass
            if receipt is not None and receipt.active:
                try:
                    self._teacher_authorizer.close_run(
                        receipt,
                        "production takeoff activation failed",
                    )
                except Exception:
                    receipt.invalidate("production takeoff activation failed")
            if isinstance(exc, ProductionTakeoffRunError):
                raise
            raise ProductionTakeoffRunError(
                "production takeoff lifecycle failed closed"
            ) from exc

    def shutdown(self) -> None:
        """Terminate process-local run authorities during trusted host teardown."""
        active = self._active
        self._active = None
        if active is None:
            return
        if active.watchdog_guard.active:
            try:
                active.watchdog_guard.stop_for_terminal_reboot()
            except Exception:
                pass
        if active.teacher_authorization.active:
            try:
                self._teacher_authorizer.close_run(
                    active.teacher_authorization,
                    "physical host shutting down",
                )
            except Exception:
                active.teacher_authorization.invalidate("physical host shutting down")

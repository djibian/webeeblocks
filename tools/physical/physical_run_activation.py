#!/usr/bin/env python3
"""Trusted #287 host adapter for one production causal takeoff activation.

This module is not a caller protocol. The running #283 physical host supplies the
already host-validated profile/canonical-AST binding, its one live read-only
session/bridge, the distinct launcher-installed teacher socket and the shared
#273 execution domain. The generic production lifecycle lives in
``production_takeoff_run``; this adapter supplies only the host-local seams that
must remain lexical to the trusted process:

- reuse the same ``ReadOnlyCapabilitySession`` object behind the existing #278
  bridge while closing/reopening its underlying cflib link across #266 reset;
- unwrap the raw post-reset Crazyflie object only inside the trusted host TCB;
- perform every positive #278/#249 current-program assertion through the same
  host-owned bridge;
- construct #290 and the host-bound #289 transport without exposing those
  authorities to ordinary caller/browser IPC.

The ordinary caller never supplies reset safety, the new connection epoch,
teacher authority, provenance, a Crazyflie object, command bytes or takeoff
height. Importing this module performs no physical effect.
"""

from __future__ import annotations

import socket

from physical_execution_domain import PhysicalExecutionDomain
from post_reset_teacher_decision import PostResetTeacherDecisionChannel
from powered_session_authority import (
    TrustedPoweredSessionFactory,
    make_cflib_stm_deck_power_cycle,
)
from production_takeoff_run import ProductionTakeoffRunController
from serve_reference_capabilities import CurrentProgramPreflightEvidence
from supervisor_state import FreshSupervisorStateReader
from takeoff_transport import TakeoffTransportError, TrustedTakeoffTransport
from teacher_run_authorization import PhysicalRunBinding, TrustedTeacherAuthorizer


class PhysicalRunActivationError(RuntimeError):
    """Fail-closed error for trusted production run activation composition."""


def _live_crazyflie(session: object) -> object:
    """Return the raw live cflib Crazyflie only inside the trusted host TCB.

    ``ReadOnlyCapabilitySession`` intentionally exposes no public effect surface.
    Python object privacy is not the #280 security boundary; process separation
    is. Trusted composition may unwrap its own live ``SyncCrazyflie`` while the
    raw object remains entirely absent from caller/browser IPC.
    """
    scf = getattr(session, "_scf", None)
    if scf is None:
        raise PhysicalRunActivationError("trusted host has no live Crazyflie session")
    is_link_open = getattr(scf, "is_link_open", None)
    if not callable(is_link_open):
        raise PhysicalRunActivationError("trusted host link state is unavailable")
    try:
        live = is_link_open()
    except Exception as exc:
        raise PhysicalRunActivationError("trusted host link state is unavailable") from exc
    if live is not True:
        raise PhysicalRunActivationError("trusted host Crazyflie link is not live")
    crazyflie = getattr(scf, "cf", None)
    if crazyflie is None:
        raise PhysicalRunActivationError("trusted host Crazyflie object is unavailable")
    return crazyflie


def _assert_current_program(
    bridge: object,
    binding: PhysicalRunBinding,
    *,
    timeout_seconds: float,
) -> CurrentProgramPreflightEvidence:
    try:
        evidence = bridge.assert_current_program(
            profile_id=binding.profile_id,
            ast_binding=binding.ast_binding,
            connection_epoch=binding.connection_epoch,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        raise PhysicalRunActivationError(
            "fresh integrated #278/#249 current-program assertion failed"
        ) from exc
    if type(evidence) is not CurrentProgramPreflightEvidence:
        raise PhysicalRunActivationError("current-program evidence type is invalid")
    if evidence.execution_authority is not False:
        raise PhysicalRunActivationError(
            "current-program evidence crossed the non-authority boundary"
        )
    if (
        evidence.profile_id != binding.profile_id
        or evidence.ast_binding != binding.ast_binding
        or evidence.connection_epoch != binding.connection_epoch
    ):
        raise PhysicalRunActivationError(
            "current-program evidence does not match the host-owned binding"
        )
    if not isinstance(evidence.challenge_id, str) or not evidence.challenge_id.strip():
        raise PhysicalRunActivationError("current-program challenge provenance is unavailable")
    return evidence


def _require_flight_inactive(reader: FreshSupervisorStateReader) -> bool:
    try:
        state = reader.read(timeout_seconds=0.2)
    except Exception as exc:
        raise PhysicalRunActivationError(
            "fresh pre-reset supervisor state is unavailable"
        ) from exc
    values = (
        getattr(state, "blocking_fault", None),
        getattr(state, "is_flying", None),
        getattr(state, "hl_control_active", None),
    )
    if any(not isinstance(value, bool) for value in values):
        raise PhysicalRunActivationError("pre-reset supervisor state is malformed")
    blocking_fault, is_flying, high_level_active = values
    if blocking_fault:
        raise PhysicalRunActivationError("blocking supervisor fault prevents trusted reset")
    if is_flying or high_level_active:
        raise PhysicalRunActivationError(
            "STM+deck reset requires fresh physical flight-inactive evidence"
        )
    return True


def activate_validated_run(
    *,
    uri: str,
    session: object,
    bridge: object,
    teacher_socket: socket.socket,
    staged_binding: PhysicalRunBinding,
    execution_domain: PhysicalExecutionDomain,
    assertion_timeout_seconds: float = 1.0,
) -> ProductionTakeoffRunController:
    """Activate one exact host-validated run through the real production lifecycle.

    The returned controller owns the successful process-local run authorities so
    the host can terminate them deliberately during teardown. ``staged_binding``
    is non-authority data captured only after the host itself completed #278/#249
    on the pre-reset epoch.
    """
    if not isinstance(uri, str) or not uri.startswith("radio://"):
        raise PhysicalRunActivationError("physical activation requires explicit radio:// URI")
    if type(staged_binding) is not PhysicalRunBinding:
        raise PhysicalRunActivationError("exact host-staged PhysicalRunBinding is required")
    if type(execution_domain) is not PhysicalExecutionDomain:
        raise PhysicalRunActivationError("exact process-wide #273 execution domain is required")
    if not isinstance(teacher_socket, socket.socket):
        raise PhysicalRunActivationError("distinct trusted teacher socket is required")
    if assertion_timeout_seconds <= 0:
        raise PhysicalRunActivationError("current-program assertion timeout must be positive")

    previous_epoch = staged_binding.connection_epoch
    try:
        current_epoch = session.read_connection_epoch()
    except Exception as exc:
        raise PhysicalRunActivationError("pre-reset connection epoch is unavailable") from exc
    if current_epoch != previous_epoch:
        raise PhysicalRunActivationError("staged run belongs to a stale pre-reset epoch")

    # Reconstruct current-program truth immediately before preparing the reset.
    _assert_current_program(
        bridge,
        staged_binding,
        timeout_seconds=assertion_timeout_seconds,
    )
    pre_reset_cf = _live_crazyflie(session)
    pre_reset_reader = FreshSupervisorStateReader(
        pre_reset_cf,
        session.read_connection_epoch,
    )

    def require_flight_known_inactive() -> bool:
        # #266 invokes this under #273 immediately before invalidation/reset.
        return _require_flight_inactive(pre_reset_reader)

    def invalidate_prior_evidence() -> None:
        # The bridge keeps the same loopback URL/tokens and the same adapter
        # identity. Closing this adapter invalidates only the old live epoch.
        session.close()

    def open_post_reset_session() -> object:
        session.open()
        return _live_crazyflie(session)

    def close_post_reset_session(crazyflie: object) -> None:
        if crazyflie is not _live_crazyflie(session):
            raise PhysicalRunActivationError(
                "post-reset cleanup is not bound to the live Crazyflie"
            )
        session.close()

    def read_connection_epoch(crazyflie: object) -> str:
        if crazyflie is not _live_crazyflie(session):
            raise PhysicalRunActivationError(
                "post-reset epoch read is not bound to the live Crazyflie"
            )
        return session.read_connection_epoch()

    def read_capabilities(crazyflie: object):
        if crazyflie is not _live_crazyflie(session):
            raise PhysicalRunActivationError(
                "post-reset capability read is not bound to the live Crazyflie"
            )
        return session.read_capabilities()

    def assert_bound_preflight(crazyflie: object, epoch: str) -> bool:
        if crazyflie is not _live_crazyflie(session):
            raise PhysicalRunActivationError(
                "post-reset preflight is not bound to the live Crazyflie"
            )
        binding = PhysicalRunBinding(
            profile_id=staged_binding.profile_id,
            ast_binding=staged_binding.ast_binding,
            connection_epoch=epoch,
        )
        _assert_current_program(
            bridge,
            binding,
            timeout_seconds=assertion_timeout_seconds,
        )
        return True

    def read_fresh_supervisor(crazyflie: object, epoch: str):
        if crazyflie is not _live_crazyflie(session):
            raise PhysicalRunActivationError(
                "post-reset supervisor read is not bound to the live Crazyflie"
            )
        if session.read_connection_epoch() != epoch:
            raise PhysicalRunActivationError(
                "post-reset supervisor read belongs to another connection epoch"
            )
        reader = FreshSupervisorStateReader(
            crazyflie,
            session.read_connection_epoch,
        )
        return reader.read(timeout_seconds=0.2)

    powered_factory = TrustedPoweredSessionFactory(
        require_flight_known_inactive=require_flight_known_inactive,
        invalidate_prior_evidence=invalidate_prior_evidence,
        stm_deck_power_cycle=make_cflib_stm_deck_power_cycle(uri),
        open_post_reset_session=open_post_reset_session,
        close_post_reset_session=close_post_reset_session,
        read_connection_epoch=read_connection_epoch,
        read_capabilities=read_capabilities,
        assert_bound_preflight=assert_bound_preflight,
        read_fresh_supervisor=read_fresh_supervisor,
    )
    authorizer = TrustedTeacherAuthorizer()
    decision_channel = PostResetTeacherDecisionChannel(
        teacher_socket,
        session.read_connection_epoch,
    )

    class _HostBoundInitialFlightTransport(TrustedTakeoffTransport):
        """Positive current-program provenance stays lexical to this host adapter."""

        def _read_current_binding(self) -> PhysicalRunBinding:
            binding = self.teacher_binding
            try:
                _assert_current_program(
                    bridge,
                    binding,
                    timeout_seconds=assertion_timeout_seconds,
                )
            except PhysicalRunActivationError as exc:
                raise TakeoffTransportError(str(exc)) from exc
            return binding

    def host_bound_transport_factory(**kwargs) -> TrustedTakeoffTransport:
        return _HostBoundInitialFlightTransport(**kwargs)

    controller = ProductionTakeoffRunController(
        powered_session_factory=powered_factory,
        teacher_channel=decision_channel,
        teacher_authorizer=authorizer,
        connection_epoch_reader=session.read_connection_epoch,
        host_bound_transport_factory=host_bound_transport_factory,
        execution_domain=execution_domain,
    )
    try:
        controller.start(
            profile_id=staged_binding.profile_id,
            ast_binding=staged_binding.ast_binding,
            previous_connection_epoch=previous_epoch,
        )
    finally:
        # #290 is one-shot; the receipt, not the transport socket, is the durable
        # process-local authority after a successful decision.
        decision_channel.close()
    return controller

#!/usr/bin/env python3
"""Trusted #287 physical-run activation inside the #283 host TCB.

This module is not a caller protocol.  The running physical host supplies the
already host-validated profile/canonical-AST binding, its one live capability
session/bridge, the distinct launcher-installed teacher socket and the shared
#273 execution domain.  It then owns the required production ordering:

validated current program -> #266 reset establishment -> post-reset #267 teacher
receipt -> #262 watchdog activation -> causal command-9 effect -> #273 flying.

The ordinary caller never supplies reset safety, the new connection epoch,
teacher authority, provenance, a Crazyflie object, command bytes or takeoff
height.  Fresh #278/#249 assertions remain host-initiated before reset proof,
after reconnect and immediately before the effect.  This file introduces no
student-facing protocol and does not execute anything on import.
"""

from __future__ import annotations

from dataclasses import dataclass
import socket

from high_level_ack import HighLevelAckDomain, HighLevelAckResult
from physical_execution_domain import FLYING, PhysicalExecutionDomain
from post_reset_teacher_decision import PostResetTeacherDecisionChannel
from powered_session_authority import (
    EstablishedPoweredSession,
    TrustedPoweredSessionFactory,
    make_cflib_stm_deck_power_cycle,
)
from safelink_precondition import LiveSafeLinkPrecondition
from serve_reference_capabilities import CurrentProgramPreflightEvidence
from supervisor_state import FreshSupervisorStateReader
from takeoff_transport import TakeoffTransportError, TrustedTakeoffTransport
from teacher_run_authorization import (
    PhysicalRunBinding,
    TeacherRunAuthorization,
    TrustedTeacherAuthorizer,
)
from watchdog_liveness import EmergencyWatchdogLivenessGuard


class PhysicalRunActivationError(RuntimeError):
    """Fail-closed error for trusted production run activation."""


@dataclass(frozen=True)
class ActivePhysicalRun:
    """Process-local authorities retained after causal entry into flight."""

    powered_session: EstablishedPoweredSession
    teacher_authorization: TeacherRunAuthorization
    watchdog_guard: EmergencyWatchdogLivenessGuard
    supervisor_reader: FreshSupervisorStateReader
    safelink_guard: LiveSafeLinkPrecondition
    acknowledgement_domain: HighLevelAckDomain
    initial_effect_result: HighLevelAckResult


def _live_crazyflie(session: object) -> object:
    """Read the raw live cflib object only inside the trusted host TCB.

    ReadOnlyCapabilitySession intentionally exposes no public effect surface.
    Python object privacy is not the #280 security boundary; process separation
    is.  The trusted host may therefore unwrap its own live SyncCrazyflie while
    still keeping that object entirely off caller/browser IPC.
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
    cf = getattr(scf, "cf", None)
    if cf is None:
        raise PhysicalRunActivationError("trusted host Crazyflie object is unavailable")
    return cf


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
) -> ActivePhysicalRun:
    """Causally activate one host-validated run and return live in-flight state.

    ``staged_binding`` is non-authority current-program data captured only after
    the running host itself completed #278/#249 on the pre-reset epoch.  The
    distinct trusted run-control channel decides *when* this function is called;
    no field from that trigger selects any collaborator or run data.
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

    # Reconstruct current-program truth again immediately before any reset work.
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

    post_reset: dict[str, object] = {}

    def require_flight_known_inactive() -> bool:
        # #266 calls this under the same #273 reset exclusion immediately before
        # invalidation and the physical power-cycle attempt.
        return _require_flight_inactive(pre_reset_reader)

    def invalidate_prior_evidence() -> None:
        # Closing the exact session invalidates the old random connection epoch.
        # The bridge server deliberately survives and remains bound to this same
        # session object so the browser endpoint/token need not be replaced.
        session.close()

    def open_post_reset_session() -> object:
        session.open()
        cf = _live_crazyflie(session)
        post_reset["crazyflie"] = cf
        return cf

    def close_post_reset_session(_crazyflie: object) -> None:
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
        state = reader.read(timeout_seconds=0.2)
        post_reset["supervisor_reader"] = reader
        return state

    reset_factory = TrustedPoweredSessionFactory(
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

    established = execution_domain.run_reset_establishment(
        lambda: reset_factory.establish(previous_connection_epoch=previous_epoch)
    )
    if type(established) is not EstablishedPoweredSession:
        raise PhysicalRunActivationError("#266 did not return an exact powered session")
    if established.session is not post_reset.get("crazyflie"):
        raise PhysicalRunActivationError("#266 powered session changed Crazyflie identity")
    if established.connection_epoch != session.read_connection_epoch():
        raise PhysicalRunActivationError("#266 powered session is not on the live host epoch")

    post_binding = PhysicalRunBinding(
        profile_id=staged_binding.profile_id,
        ast_binding=staged_binding.ast_binding,
        connection_epoch=established.connection_epoch,
    )
    authorizer = TrustedTeacherAuthorizer()
    receipt: TeacherRunAuthorization | None = None
    decision_channel = PostResetTeacherDecisionChannel(
        teacher_socket,
        session.read_connection_epoch,
    )
    try:
        receipt = decision_channel.receive_authorization_for_binding(
            authorizer,
            post_binding,
        )
    finally:
        decision_channel.close()

    try:
        supervisor_reader = post_reset.get("supervisor_reader")
        if type(supervisor_reader) is not FreshSupervisorStateReader:
            raise PhysicalRunActivationError(
                "#266 fresh post-reset supervisor reader was not retained"
            )
        cf = established.session
        watchdog = EmergencyWatchdogLivenessGuard(
            cf,
            session.read_connection_epoch,
            supervisor_reader,
            established.watchdog_authority,
        )
        watchdog.activate(supervisor_timeout_seconds=0.2)
        safelink = LiveSafeLinkPrecondition(cf, session.read_connection_epoch)
        acknowledgements = HighLevelAckDomain(session.read_connection_epoch)

        class _HostBoundInitialFlightTransport(TrustedTakeoffTransport):
            """Positive #249 provenance stays lexical to this trusted activation."""

            def _read_current_binding(self) -> PhysicalRunBinding:
                binding = self.teacher_binding
                _assert_current_program(
                    bridge,
                    binding,
                    timeout_seconds=assertion_timeout_seconds,
                )
                return binding

        transport = _HostBoundInitialFlightTransport(
            crazyflie=cf,
            execution_domain=execution_domain,
            acknowledgement_domain=acknowledgements,
            safelink_guard=safelink,
            teacher_authorization=receipt,
            powered_session=established,
            watchdog_guard=watchdog,
            supervisor_reader=supervisor_reader,
        )
        result = transport.send_from_authorized_ast()
        if result.accepted is not True:
            raise PhysicalRunActivationError(
                f"initial physical command was definitively rejected with status {result.status}"
            )
        if execution_domain.phase != FLYING:
            raise PhysicalRunActivationError(
                "accepted initial physical command did not causally establish flying"
            )
        return ActivePhysicalRun(
            powered_session=established,
            teacher_authorization=receipt,
            watchdog_guard=watchdog,
            supervisor_reader=supervisor_reader,
            safelink_guard=safelink,
            acknowledgement_domain=acknowledgements,
            initial_effect_result=result,
        )
    except Exception:
        if receipt is not None and receipt.active:
            try:
                authorizer.close_run(receipt, "physical run activation failed closed")
            except Exception:
                receipt.invalidate("physical run activation failed closed")
        raise

#!/usr/bin/env python3
"""Production trusted-host activation for one dynamic physical Runtime v2 program.

This composition reuses the existing reset/teacher/watchdog/causal-takeoff chain,
then gives the exact teacher-bound AST to the shared Runtime interpreter through
``BoundDynamicPhysicalRun``.  Ordinary caller IPC supplies no direction, branch,
expression value, cursor or action parameter.

Deterministic shared-language and conservative dynamic-physical validation happen
before reset or takeoff.  The one real takeoff remains owned by
``ProductionTakeoffRunController``; the interpreter's takeoff callback is only a
verification inside ``TrustedDynamicPhysicalBackend``.  Any failure after that
causal takeoff terminates the powered-session/watchdog authority through the
existing controller shutdown path rather than permitting ordinary continuation.

Importing this module performs no physical effect.
"""

from __future__ import annotations

import socket

from color_led_transport import ColorLedTransportError, TrustedBottomColorLedTransport
from dynamic_controlled_landing_transport import (
    DynamicControlledLandingTransportError,
    TrustedDynamicControlledLandingTransport,
)
from dynamic_physical_backend import TrustedDynamicPhysicalBackend
from dynamic_physical_run import BoundDynamicPhysicalRun, DynamicPhysicalRunError
from high_level_timing import HighLevelTimingPolicy
from physical_execution_domain import PhysicalExecutionDomain
from physical_run_activation import (
    PhysicalRunActivationError,
    _assert_current_program,
    _execute_exact_wait,
    _live_crazyflie,
    _require_flight_inactive,
)
from post_reset_teacher_decision import PostResetTeacherDecisionChannel
from powered_session_authority import (
    TrustedPoweredSessionFactory,
    make_cflib_stm_deck_power_cycle,
)
from production_takeoff_run import ProductionTakeoffRunController
from shared_interpreter_host import SharedInterpreterHostError, validate_bound_shared_program
from supervisor_state import FreshSupervisorStateReader
from takeoff_transport import TakeoffTransportError, TrustedTakeoffTransport
from teacher_run_authorization import PhysicalRunBinding, TrustedTeacherAuthorizer


class DynamicRunActivationError(PhysicalRunActivationError):
    """Fail-closed error for production shared-interpreter physical activation."""


def _terminal_shutdown(controller: ProductionTakeoffRunController) -> None:
    """Enter the existing powered-session terminal recovery path best-effort."""
    try:
        controller.shutdown()
    except Exception:
        # The trusted watchdog lifecycle records terminal uncertainty itself.
        pass


def activate_validated_dynamic_run(
    *,
    uri: str,
    session: object,
    bridge: object,
    teacher_socket: socket.socket,
    staged_binding: PhysicalRunBinding,
    execution_domain: PhysicalExecutionDomain,
    assertion_timeout_seconds: float = 1.0,
):
    """Activate and return one exact parameter-free dynamic physical run owner."""
    if not isinstance(uri, str) or not uri.startswith("radio://"):
        raise DynamicRunActivationError("dynamic physical activation requires explicit radio:// URI")
    if type(staged_binding) is not PhysicalRunBinding:
        raise DynamicRunActivationError("exact host-staged PhysicalRunBinding is required")
    if type(execution_domain) is not PhysicalExecutionDomain:
        raise DynamicRunActivationError("exact process-wide physical execution domain is required")
    if not isinstance(teacher_socket, socket.socket):
        raise DynamicRunActivationError("distinct trusted teacher socket is required")
    if assertion_timeout_seconds <= 0:
        raise DynamicRunActivationError("current-program assertion timeout must be positive")

    # This is deliberately before bridge cutover/reset/takeoff.  It invokes the
    # existing JS product validator and conservative dynamic physical envelope,
    # but no backend/effect surface.
    try:
        safety = validate_bound_shared_program(staged_binding.ast_binding)
    except Exception as exc:
        if isinstance(exc, (SharedInterpreterHostError, RuntimeError)):
            raise DynamicRunActivationError(
                "teacher-bound dynamic program failed pre-effect shared validation"
            ) from exc
        raise
    if safety.ast_binding != staged_binding.ast_binding:
        raise DynamicRunActivationError("pre-effect validation changed the exact AST binding")

    begin_replacement = getattr(bridge, "begin_post_reset_replacement", None)
    install_replacement = getattr(bridge, "install_post_reset_session", None)
    if not callable(begin_replacement) or not callable(install_replacement):
        raise DynamicRunActivationError(
            "trusted dynamic activation requires the fail-closed post-reset bridge"
        )

    previous_epoch = staged_binding.connection_epoch
    try:
        current_epoch = session.read_connection_epoch()
    except Exception as exc:
        raise DynamicRunActivationError("pre-reset connection epoch is unavailable") from exc
    if current_epoch != previous_epoch:
        raise DynamicRunActivationError("staged dynamic run belongs to a stale pre-reset epoch")

    _assert_current_program(
        bridge,
        staged_binding,
        timeout_seconds=assertion_timeout_seconds,
    )
    pre_reset_cf = _live_crazyflie(session)
    pre_reset_reader = FreshSupervisorStateReader(pre_reset_cf, session.read_connection_epoch)

    def require_flight_known_inactive() -> bool:
        return _require_flight_inactive(pre_reset_reader)

    def invalidate_prior_evidence() -> None:
        begin_replacement(previous_epoch)
        session.close()

    def open_post_reset_session() -> object:
        session.open()
        try:
            installed_epoch = install_replacement(session)
            live_epoch = session.read_connection_epoch()
            if installed_epoch != live_epoch or live_epoch == previous_epoch:
                raise DynamicRunActivationError(
                    "post-reset bridge was not rebound to the genuinely new live epoch"
                )
            return _live_crazyflie(session)
        except Exception:
            try:
                session.close()
            except Exception:
                pass
            raise

    def close_post_reset_session(crazyflie: object) -> None:
        if crazyflie is not _live_crazyflie(session):
            raise DynamicRunActivationError(
                "post-reset cleanup is not bound to the live Crazyflie"
            )
        session.close()

    def read_connection_epoch(crazyflie: object) -> str:
        if crazyflie is not _live_crazyflie(session):
            raise DynamicRunActivationError(
                "post-reset epoch read is not bound to the live Crazyflie"
            )
        return session.read_connection_epoch()

    def read_capabilities(crazyflie: object):
        if crazyflie is not _live_crazyflie(session):
            raise DynamicRunActivationError(
                "post-reset capability read is not bound to the live Crazyflie"
            )
        return session.read_capabilities()

    def assert_bound_preflight(crazyflie: object, epoch: str) -> bool:
        if crazyflie is not _live_crazyflie(session):
            raise DynamicRunActivationError(
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
            raise DynamicRunActivationError(
                "post-reset supervisor read is not bound to the live Crazyflie"
            )
        if session.read_connection_epoch() != epoch:
            raise DynamicRunActivationError(
                "post-reset supervisor read belongs to another connection epoch"
            )
        return FreshSupervisorStateReader(
            crazyflie,
            session.read_connection_epoch,
        ).read(timeout_seconds=0.2)

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
        decision_channel.close()

    active_run = controller.active_run
    if active_run is None:
        _terminal_shutdown(controller)
        raise DynamicRunActivationError(
            "causal takeoff completed without an active dynamic physical run bundle"
        )
    binding = active_run.teacher_authorization.binding
    if (
        binding.profile_id != staged_binding.profile_id
        or binding.ast_binding != staged_binding.ast_binding
        or binding.connection_epoch != active_run.powered_session.connection_epoch
    ):
        _terminal_shutdown(controller)
        raise DynamicRunActivationError(
            "post-takeoff teacher run no longer matches the exact dynamic AST"
        )

    class _HostBoundDynamicInflightTransport(TrustedDynamicControlledLandingTransport):
        def _read_current_binding(self) -> PhysicalRunBinding:
            current = self.teacher_binding
            try:
                _assert_current_program(
                    bridge,
                    current,
                    timeout_seconds=assertion_timeout_seconds,
                )
            except PhysicalRunActivationError as exc:
                raise DynamicControlledLandingTransportError(str(exc)) from exc
            return current

    class _HostBoundColorLedTransport(TrustedBottomColorLedTransport):
        def _read_current_binding(self) -> PhysicalRunBinding:
            current = self.teacher_binding
            try:
                _assert_current_program(
                    bridge,
                    current,
                    timeout_seconds=assertion_timeout_seconds,
                )
            except PhysicalRunActivationError as exc:
                raise ColorLedTransportError(str(exc)) from exc
            return current

    def assert_current_program() -> object:
        return _assert_current_program(
            bridge,
            binding,
            timeout_seconds=assertion_timeout_seconds,
        )

    def execute_wait(seconds: float) -> None:
        _execute_exact_wait(
            seconds,
            active_run.watchdog_guard,
            session.read_connection_epoch,
            active_run.powered_session.connection_epoch,
        )

    try:
        inflight_transport = _HostBoundDynamicInflightTransport(
            crazyflie=active_run.crazyflie,
            execution_domain=active_run.execution_domain,
            acknowledgement_domain=active_run.acknowledgement_domain,
            safelink_guard=active_run.safelink_guard,
            teacher_authorization=active_run.teacher_authorization,
            powered_session=active_run.powered_session,
            watchdog_guard=active_run.watchdog_guard,
            supervisor_reader=active_run.supervisor_reader,
            connection_epoch_reader=session.read_connection_epoch,
        )
        color_transport = _HostBoundColorLedTransport(
            crazyflie=active_run.crazyflie,
            execution_domain=active_run.execution_domain,
            safelink_guard=active_run.safelink_guard,
            teacher_authorization=active_run.teacher_authorization,
            powered_session=active_run.powered_session,
            watchdog_guard=active_run.watchdog_guard,
            connection_epoch_reader=session.read_connection_epoch,
        )
        live_epoch = session.read_connection_epoch()
        if (
            inflight_transport.bound_connection_epoch != live_epoch
            or color_transport.bound_connection_epoch != live_epoch
        ):
            raise DynamicRunActivationError(
                "dynamic physical consumers are not bound to the exact active host epoch"
            )
        backend = TrustedDynamicPhysicalBackend(
            ast_binding=staged_binding.ast_binding,
            active_run=active_run,
            connection_epoch_reader=session.read_connection_epoch,
            assert_current_program=assert_current_program,
            inflight_transport=inflight_transport,
            color_transport=color_transport,
            timing_policy=HighLevelTimingPolicy(),
            execute_wait=execute_wait,
        )
        dynamic_run = BoundDynamicPhysicalRun(backend)
    except Exception as exc:
        _terminal_shutdown(controller)
        if isinstance(exc, DynamicRunActivationError):
            raise
        raise DynamicRunActivationError(
            "post-takeoff dynamic physical composition failed closed"
        ) from exc

    class _ActivatedDynamicRunController:
        __slots__ = ("_run", "_executed", "_closed", "_terminal")

        def __init__(self) -> None:
            self._run = dynamic_run
            self._executed = False
            self._closed = False
            self._terminal = False

        @property
        def active_run(self):
            return controller.active_run

        def execute_next_inflight(self):
            """Execute the whole exact interpreter-owned dynamic program once."""
            if self._executed:
                raise DynamicRunActivationError("dynamic physical program is one-shot")
            if self._terminal:
                raise DynamicRunActivationError("dynamic physical program is terminal")
            self._executed = True
            try:
                result = self._run.execute()
                self._run.close()
                self._closed = True
                return result
            except Exception as exc:
                self._terminal = True
                if not self._closed:
                    try:
                        self._run.close()
                    except Exception:
                        pass
                    self._closed = True
                _terminal_shutdown(controller)
                raise DynamicRunActivationError(
                    "post-takeoff dynamic physical execution failed closed into terminal recovery"
                ) from exc

        def shutdown(self) -> None:
            close_error = None
            if not self._closed:
                try:
                    self._run.close()
                except Exception as exc:
                    close_error = exc
                self._closed = True
            _terminal_shutdown(controller)
            if close_error is not None:
                raise DynamicRunActivationError(
                    "dynamic physical observer teardown is uncertain"
                ) from close_error

    return _ActivatedDynamicRunController()

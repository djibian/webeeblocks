#!/usr/bin/env python3
"""Trusted exactly-once terminal HighLevel landing effect composition.

This module extends the integrated #276 SETPOINT_HL trust root for the one exact
terminal ``land`` already reserved by :class:`PhysicalProgramSequence`. It does
not expose caller-selected landing height, velocity, yaw, raw bytes, provenance
or authority. The request is derived solely from the exact teacher-bound
canonical AST through ``landing_command``.

The effect boundary preserves the integrated #267/#266/#262/#257/#272/#271/#273
authorities and fresh #278/#249 current-program assertion supplied by the trusted
host subclass. A positive firmware acknowledgement is not completion: the same
accepted-effect permit remains pending until #264 observes a later same-epoch
finished, non-flying, high-level-inactive supervisor state. Any post-emission
uncertainty fails closed and creates no application retry path.
"""

from __future__ import annotations

from threading import Event, Lock

import landing_command
import landing_completion
import physical_execution_domain
import physical_program_sequence
import setpoint_hl_transport

_SETPOINT_HL_PORT = 0x08
_ACK_TIMEOUT_SECONDS = 0.2
_PRE_LAND_READ_TIMEOUT_SECONDS = 0.2
_COMPLETION_TIMEOUT_SECONDS = 8.0
_COMPLETION_READ_TIMEOUT_SECONDS = 0.2
_COMPLETION_POLL_SECONDS = 0.05


class TerminalLandingTransportError(RuntimeError):
    """Fail-closed trusted terminal-landing transport error."""


class TrustedTerminalLandingTransport(setpoint_hl_transport.TrustedSetpointHlTransport):
    """Terminal-only extension of the existing trusted SETPOINT_HL effect core."""

    def __init__(self, *, program_sequence: object, **kwargs) -> None:
        if type(program_sequence) is not physical_program_sequence.PhysicalProgramSequence:
            raise TerminalLandingTransportError(
                "exact trusted physical-program sequence is required for landing"
            )
        super().__init__(**kwargs)
        if program_sequence.ast_binding != self.teacher_binding.ast_binding:
            raise TerminalLandingTransportError(
                "landing sequence does not match the exact teacher-authorized AST"
            )
        self._program_sequence = program_sequence

    def send_horizontal_move(self, *args, **kwargs):
        raise TerminalLandingTransportError(
            "terminal landing transport cannot emit ordinary in-flight motion"
        )

    def send_turn(self, *args, **kwargs):
        raise TerminalLandingTransportError(
            "terminal landing transport cannot emit ordinary in-flight motion"
        )

    def _assert_exact_landing_claim(self, claim: object) -> None:
        try:
            landing = self._program_sequence.landing_for_claim(claim)
        except physical_program_sequence.PhysicalProgramSequenceError as exc:
            raise TerminalLandingTransportError(
                "exact pending terminal landing claim is required"
            ) from exc
        if landing.index != self._program_sequence.next_index:
            raise TerminalLandingTransportError(
                "terminal landing claim no longer matches the exact program cursor"
            )

    def _bound_landing_request(self) -> bytes:
        binding = self._read_current_binding()
        self._assert_binding_authority(binding)
        if binding.ast_binding != self._program_sequence.ast_binding:
            raise TerminalLandingTransportError(
                "fresh current program no longer matches the landing sequence"
            )
        try:
            command = landing_command.derive_bound_landing_command(binding.ast_binding)
        except landing_command.LandingCommandError as exc:
            raise TerminalLandingTransportError(
                "exact teacher-bound terminal landing request is unavailable"
            ) from exc
        if command.ast_binding != binding.ast_binding:
            raise TerminalLandingTransportError(
                "derived terminal landing request lost exact AST provenance"
            )
        return command.request

    def _landing_observer(self) -> landing_completion.ControlledLandingCompletionObserver:
        epoch_reader = getattr(self._supervisor, "_read_epoch", None)
        if not callable(epoch_reader):
            raise TerminalLandingTransportError(
                "fresh supervisor epoch reader is unavailable for landing completion"
            )
        try:
            observer = landing_completion.ControlledLandingCompletionObserver(
                self._supervisor,
                epoch_reader,
            )
        except landing_completion.LandingCompletionError as exc:
            raise TerminalLandingTransportError(
                "controlled landing completion observer is unavailable"
            ) from exc
        if observer.bound_connection_epoch != self.bound_connection_epoch:
            raise TerminalLandingTransportError(
                "landing completion observer belongs to another connection epoch"
            )
        return observer

    def send_terminal_landing(self, claim: object):
        """Emit and causally complete the one exact pending terminal landing.

        ``claim`` is the opaque host-local object returned by
        ``PhysicalProgramSequence.reserve_terminal_landing()``. It carries no
        caller-selected semantics. The method performs exactly one physical send
        after installing the acknowledgement callback and never retries.
        """
        self._assert_exact_landing_claim(claim)
        request = self._bound_landing_request()
        packet = setpoint_hl_transport._default_packet_factory(request)
        self._validate_packet(packet, request)
        observer = self._landing_observer()

        result = None
        completion_permit = None
        baseline = None

        with self._execution.effect_transaction(
            self._assert_current_authority,
            lambda: self._assert_exact_landing_claim(claim),
        ) as effect:
            # Final fresh provenance and exact claim checks occur inside the
            # process-wide reset/effect exclusion immediately before the effect.
            final_binding = self._read_current_binding()
            self._assert_binding_authority(final_binding)
            if final_binding.ast_binding != self._program_sequence.ast_binding:
                raise TerminalLandingTransportError(
                    "fresh landing provenance no longer matches the exact program"
                )
            self._assert_exact_landing_claim(claim)

            try:
                baseline = observer.capture_pre_land_flight(
                    timeout_seconds=_PRE_LAND_READ_TIMEOUT_SECONDS
                )
            except landing_completion.LandingCompletionError as exc:
                raise TerminalLandingTransportError(
                    "fresh pre-land physical-flight evidence is unavailable"
                ) from exc

            # Recheck all effect authority after the asynchronous supervisor read.
            self._assert_current_authority()
            self._assert_exact_landing_claim(claim)
            self._safelink.assert_ready()
            self._watchdog.assert_live()

            reply_ready = Event()
            reply_lock = Lock()
            reply_data: dict[str, object] = {}

            with self._ack.transaction(request) as acknowledgement:
                def high_level_callback(reply_packet: object) -> None:
                    try:
                        data = bytes(reply_packet.data)
                    except Exception:
                        data = b""
                    with reply_lock:
                        if reply_ready.is_set():
                            return
                        if len(data) >= 3 and data[:3] == acknowledgement.request_prefix:
                            reply_data["data"] = data
                            reply_ready.set()

                self._cf.add_port_callback(_SETPOINT_HL_PORT, high_level_callback)
                try:
                    # The two domains cross their effect boundary immediately
                    # before the one plain cflib send. No expected-reply/retry
                    # transport option is used.
                    acknowledgement.mark_emitted()
                    effect.mark_emitted()
                    try:
                        self._cf.send_packet(packet)
                    except Exception as exc:
                        raise TerminalLandingTransportError(
                            "terminal landing send outcome is ambiguous"
                        ) from exc

                    try:
                        reply = self._wait_for_reply(
                            reply_ready,
                            reply_lock,
                            reply_data,
                            _ACK_TIMEOUT_SECONDS,
                        )
                    except Exception as exc:
                        acknowledgement.fail_ambiguous(exc)
                        raise AssertionError("unreachable")

                    result = acknowledgement.resolve_reply(reply)
                    if result.accepted:
                        completion_permit = effect.mark_accepted()
                    else:
                        effect.mark_definitive_rejection()
                finally:
                    self._cf.remove_port_callback(_SETPOINT_HL_PORT, high_level_callback)

        if result is None:
            raise TerminalLandingTransportError(
                "terminal landing acknowledgement result is unavailable"
            )
        if not result.accepted:
            return result
        if completion_permit is None or baseline is None:
            raise TerminalLandingTransportError(
                "accepted terminal landing has no completion authority/evidence"
            )

        try:
            # The independent watchdog service remains active throughout #264's
            # completion wait. Requiring it both before and after observation
            # prevents a completed program from being accepted after watchdog
            # liveness became terminal during the landing interval.
            self._watchdog.assert_live()
            completion = observer.await_completion(
                baseline,
                total_timeout_seconds=_COMPLETION_TIMEOUT_SECONDS,
                per_read_timeout_seconds=_COMPLETION_READ_TIMEOUT_SECONDS,
                poll_interval_seconds=_COMPLETION_POLL_SECONDS,
            )
            self._watchdog.assert_live()
            if completion.connection_epoch != self.bound_connection_epoch:
                raise TerminalLandingTransportError(
                    "landing completion evidence belongs to another connection epoch"
                )
            state = completion.supervisor_state
            if (
                getattr(state, "blocking_fault", None) is not False
                or getattr(state, "is_flying", None) is not False
                or getattr(state, "hl_control_active", None) is not False
                or getattr(state, "hl_traj_finished", None) is not True
            ):
                raise TerminalLandingTransportError(
                    "landing completion evidence does not establish trusted inactivity"
                )

            self._execution.complete_accepted_effect(
                completion_permit,
                physical_execution_domain.INACTIVE,
                lambda: True,
            )
        except Exception:
            if self._execution.phase == physical_execution_domain.AWAITING_COMPLETION:
                self._force_completion_uncertainty(completion_permit)
            raise

        if self._execution.phase != physical_execution_domain.INACTIVE:
            raise TerminalLandingTransportError(
                "causal terminal landing did not leave physical execution inactive"
            )
        return result

#!/usr/bin/env python3
"""Trusted physical-host composition root for current-program provenance.

This executable is the #280 authority boundary. Importing this file creates no
session, bridge, responder, teacher channel or physical effect object. When run
by trusted production composition it alone owns the live Crazyflie capability
session and the integrated #278 bridge/responder relationship.

The ordinary caller/UI is outside this process. Its IPC messages are untrusted
run-context validation requests only; a positive reply is diagnostic/non-authority
data and must never be accepted later as an effect capability. A distinct
launcher-installed teacher socket may independently approve one exact #267 run;
that receipt remains process-local and is never returned on caller/browser IPC.
The #276 transport belongs *inside this same process* so fresh #249 and all
identity-sensitive #257/#260/#262/#266/#267/#271/#272/#273 objects share the one
live Crazyflie/session/connection epoch.

Browser bootstrap is a distinct one-way composition channel. Its responder
credential is written there once and never returned on ordinary caller IPC. The
teacher decision socket is distinct from both channels and is consumed by its own
one-shot trusted control path; ordinary caller data cannot trigger, select,
replace or write that decision path. The host-local #276 transport type closes
directly over the same bridge; no bridge-to-effect handle, binder, client or
caller-selectable provenance input is exported. A trusted run activation may
construct the bounded in-flight effect surface only after the exact run-scoped
safety/authority objects already exist on that same live epoch. This executable
emits no flight, arming, setpoint or reset command merely by starting or
validating a run context.
"""

if __name__ == "__main__":

    def _run_physical_host() -> None:
        import argparse
        import json
        import os
        from pathlib import Path
        import socket
        import sys
        from threading import Thread

        physical = Path(__file__).resolve().parent
        if str(physical) not in sys.path:
            sys.path.insert(0, str(physical))

        from high_level_timing import HighLevelTimingPolicy
        from probe_reference_hardware import ReadOnlyCapabilitySession
        from serve_reference_capabilities import (
            CapabilityBridgeError,
            CurrentProgramPreflightEvidence,
            ReadOnlyCapabilityHttpBridge,
        )
        from setpoint_hl_transport import (
            SetpointHlTransportError,
            TrustedSetpointHlTransport,
        )
        from teacher_decision_channel import (
            TeacherDecisionChannelError,
            TrustedTeacherDecisionChannel,
        )
        from teacher_run_authorization import TrustedTeacherAuthorizer
        from yaw_observer import FreshYawObserver

        max_message_bytes = 8192
        assertion_timeout_seconds = 1.0

        parser = argparse.ArgumentParser(
            description="WebeeBlocks trusted physical-host composition root"
        )
        parser.add_argument("--uri", required=True, help="explicit radio:// Crazyradio URI")
        parser.add_argument(
            "--caller-fd",
            required=True,
            type=int,
            help="trusted-launcher-installed ordinary caller IPC socket handle",
        )
        parser.add_argument(
            "--browser-config-fd",
            required=True,
            type=int,
            help="distinct one-way browser bootstrap descriptor",
        )
        parser.add_argument(
            "--teacher-fd",
            type=int,
            default=None,
            help="distinct launcher-installed trusted teacher decision socket handle",
        )
        args = parser.parse_args()

        if not args.uri.startswith("radio://"):
            raise SystemExit("physical host requires explicit radio:// URI")
        if args.caller_fd < 3 or args.browser_config_fd < 3:
            raise SystemExit("physical host channels must be inherited non-stdio handles")
        if args.caller_fd == args.browser_config_fd:
            raise SystemExit("caller and browser bootstrap channels must be distinct")
        if args.teacher_fd is not None:
            if args.teacher_fd < 3:
                raise SystemExit(
                    "teacher decision channel must be an inherited non-stdio handle"
                )
            if args.teacher_fd in {args.caller_fd, args.browser_config_fd}:
                raise SystemExit(
                    "teacher decision channel must be distinct from caller/browser channels"
                )

        caller_socket = socket.socket(fileno=args.caller_fd)
        caller_reader = caller_socket.makefile("r", encoding="utf-8", newline="\n")
        caller_writer = caller_socket.makefile("w", encoding="utf-8", newline="\n")
        teacher_socket = (
            None if args.teacher_fd is None else socket.socket(fileno=args.teacher_fd)
        )

        with ReadOnlyCapabilitySession(args.uri) as session:
            bridge = ReadOnlyCapabilityHttpBridge(session)

            class _HostBoundSetpointHlTransport(TrustedSetpointHlTransport):
                """#276 effect transport whose provenance source is lexical to this host."""

                def _read_current_binding(self):
                    binding = self.teacher_binding
                    try:
                        evidence = bridge.assert_current_program(
                            profile_id=binding.profile_id,
                            ast_binding=binding.ast_binding,
                            connection_epoch=binding.connection_epoch,
                            timeout_seconds=assertion_timeout_seconds,
                        )
                    except Exception as exc:
                        raise SetpointHlTransportError(
                            "integrated #278/#249 current-program re-assertion failed"
                        ) from exc
                    if type(evidence) is not CurrentProgramPreflightEvidence:
                        raise SetpointHlTransportError(
                            "integrated #278 bridge returned invalid current-program evidence"
                        )
                    if evidence.execution_authority is not False:
                        raise SetpointHlTransportError(
                            "current-program evidence crossed the non-authority boundary"
                        )
                    if (
                        evidence.profile_id != binding.profile_id
                        or evidence.ast_binding != binding.ast_binding
                        or evidence.connection_epoch != binding.connection_epoch
                    ):
                        raise SetpointHlTransportError(
                            "current-program evidence does not match the teacher-authorized run"
                        )
                    if (
                        not isinstance(evidence.challenge_id, str)
                        or not evidence.challenge_id.strip()
                    ):
                        raise SetpointHlTransportError(
                            "current-program challenge provenance is unavailable"
                        )
                    return binding

            def _compose_inflight_setpoint_transport(
                *,
                crazyflie,
                execution_domain,
                acknowledgement_domain,
                safelink_guard,
                teacher_authorization,
                powered_session,
                watchdog_guard,
                supervisor_reader,
            ):
                """Compose #276 only from safety objects already local to this TCB.

                The current-program bridge is intentionally not an argument. The
                trusted lifecycle/teacher path calls this local closure after it
                has established the exact same-epoch #266/#267/#262/#257/#272/
                #271/#273 objects. Ordinary caller IPC cannot invoke or replace
                this composition path.
                """
                effect_transport = _HostBoundSetpointHlTransport(
                    crazyflie=crazyflie,
                    execution_domain=execution_domain,
                    acknowledgement_domain=acknowledgement_domain,
                    safelink_guard=safelink_guard,
                    teacher_authorization=teacher_authorization,
                    powered_session=powered_session,
                    watchdog_guard=watchdog_guard,
                    supervisor_reader=supervisor_reader,
                )
                if effect_transport.bound_connection_epoch != session.read_connection_epoch():
                    raise SetpointHlTransportError(
                        "co-located effect transport is not bound to the live host epoch"
                    )
                return effect_transport

            class _ActiveInflightRun:
                """Host-local run surface holding authorities outside ordinary IPC."""

                __slots__ = ("_transport", "_yaw_reader", "_timing_policy")

                def __init__(self, transport, yaw_reader, timing_policy) -> None:
                    self._transport = transport
                    self._yaw_reader = yaw_reader
                    self._timing_policy = timing_policy

                def execute(self, request):
                    if not isinstance(request, dict):
                        raise SetpointHlTransportError(
                            "physical motion request must be a bounded semantic object"
                        )
                    motion = request.get("motion")
                    if motion == "turn":
                        if set(request) != {"motion", "angleDeg"}:
                            raise SetpointHlTransportError(
                                "turn request contains unsupported fields"
                            )
                        return self._transport.send_turn(
                            angle_deg=request["angleDeg"],
                            timing_policy=self._timing_policy,
                        )
                    if motion == "horizontal":
                        if set(request) != {"motion", "direction", "distanceM"}:
                            raise SetpointHlTransportError(
                                "horizontal request contains unsupported fields"
                            )
                        return self._transport.send_horizontal_move(
                            direction=request["direction"],
                            distance_m=request["distanceM"],
                            yaw_reader=self._yaw_reader,
                            timing_policy=self._timing_policy,
                        )
                    raise SetpointHlTransportError(
                        "unsupported ordinary physical motion request"
                    )

            def _activate_inflight_run(
                *,
                crazyflie,
                execution_domain,
                acknowledgement_domain,
                safelink_guard,
                teacher_authorization,
                powered_session,
                watchdog_guard,
                supervisor_reader,
                yaw_reader,
                timing_policy,
            ):
                """Create one usable effect surface only from trusted run-scoped objects."""
                if type(yaw_reader) is not FreshYawObserver:
                    raise SetpointHlTransportError(
                        "exact #260 FreshYawObserver is required for active physical run"
                    )
                if type(timing_policy) is not HighLevelTimingPolicy:
                    raise SetpointHlTransportError(
                        "exact #268 HighLevelTimingPolicy is required for active physical run"
                    )
                if yaw_reader.bound_crazyflie is not crazyflie:
                    raise SetpointHlTransportError(
                        "active-run yaw observer is not bound to the exact Crazyflie"
                    )
                if yaw_reader.bound_connection_epoch != session.read_connection_epoch():
                    raise SetpointHlTransportError(
                        "active-run yaw observer is not bound to the live host epoch"
                    )
                if not yaw_reader.is_open:
                    raise SetpointHlTransportError(
                        "active-run yaw observer must already be open"
                    )
                effect_transport = _compose_inflight_setpoint_transport(
                    crazyflie=crazyflie,
                    execution_domain=execution_domain,
                    acknowledgement_domain=acknowledgement_domain,
                    safelink_guard=safelink_guard,
                    teacher_authorization=teacher_authorization,
                    powered_session=powered_session,
                    watchdog_guard=watchdog_guard,
                    supervisor_reader=supervisor_reader,
                )
                return _ActiveInflightRun(
                    effect_transport,
                    yaw_reader,
                    timing_policy,
                )

            bridge_thread = Thread(target=bridge.serve_forever, daemon=True)
            bridge_thread.start()
            host, port = bridge.address

            teacher_authorizer = TrustedTeacherAuthorizer()
            teacher_channel = (
                None
                if teacher_socket is None
                else TrustedTeacherDecisionChannel(
                    teacher_socket,
                    session.read_connection_epoch,
                )
            )
            teacher_state = {
                "authorization": None,
                "error": None,
            }
            teacher_thread = None

            def run_teacher_decision_channel() -> None:
                if teacher_channel is None:
                    return
                try:
                    receipt = teacher_channel.receive_authorization(teacher_authorizer)
                except TeacherDecisionChannelError as exc:
                    teacher_state["error"] = str(exc)
                    return
                teacher_state["authorization"] = receipt

            # Trusted composition routes this descriptor only to the production
            # browser #249 responder. It never crosses the caller IPC channel.
            with os.fdopen(
                args.browser_config_fd,
                "w",
                encoding="utf-8",
                closefd=True,
            ) as browser_config:
                browser_config.write(
                    json.dumps(
                        {
                            "baseUrl": f"http://{host}:{port}",
                            "token": bridge.token,
                            "preflightResponderToken": bridge.preflight_responder_token,
                            "executionAuthority": False,
                        },
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                    + "\n"
                )
                browser_config.flush()

            # The teacher protocol is independent from ordinary caller requests.
            # It may remain idle until the trusted launcher/teacher writes its
            # one-run request, and it never serializes the resulting #267 receipt.
            if teacher_channel is not None:
                teacher_thread = Thread(
                    target=run_teacher_decision_channel,
                    daemon=True,
                )
                teacher_thread.start()

            try:
                for line in caller_reader:
                    if len(line.encode("utf-8")) > max_message_bytes:
                        break
                    try:
                        request = json.loads(line)
                    except (UnicodeError, json.JSONDecodeError):
                        break
                    if not isinstance(request, dict):
                        break
                    if request.get("op") != "validate-run-context":
                        break

                    request_id = request.get("requestId")
                    profile_id = request.get("profileId")
                    ast_binding = request.get("astBinding")
                    connection_epoch = request.get("connectionEpoch")
                    if any(
                        not isinstance(value, str)
                        or not value.strip()
                        or value != value.strip()
                        for value in (
                            request_id,
                            profile_id,
                            ast_binding,
                            connection_epoch,
                        )
                    ):
                        break

                    try:
                        # This evidence stays inside the trusted physical host.
                        # Future #276 composition must consume it here immediately
                        # before the effect; the co-located transport above uses
                        # this exact lexical bridge rather than caller provenance.
                        # Caller replies are never accepted as provenance.
                        evidence = bridge.assert_current_program(
                            profile_id=profile_id,
                            ast_binding=ast_binding,
                            connection_epoch=connection_epoch,
                            timeout_seconds=assertion_timeout_seconds,
                        )
                        if (
                            evidence.execution_authority is not False
                            or evidence.profile_id != profile_id
                            or evidence.ast_binding != ast_binding
                            or evidence.connection_epoch != connection_epoch
                        ):
                            raise CapabilityBridgeError(
                                "current-program evidence does not match requested run"
                            )
                    except CapabilityBridgeError as exc:
                        response = {
                            "requestId": request_id,
                            "ok": False,
                            "error": str(exc),
                            "executionAuthority": False,
                        }
                    else:
                        response = {
                            "requestId": request_id,
                            "ok": True,
                            "executionAuthority": False,
                        }

                    try:
                        caller_writer.write(
                            json.dumps(
                                response,
                                separators=(",", ":"),
                                sort_keys=True,
                            )
                            + "\n"
                        )
                        caller_writer.flush()
                    except OSError:
                        break
            finally:
                bridge.shutdown()
                bridge_thread.join(timeout=1.0)

                # Closing the trusted channel first unblocks an idle one-shot
                # teacher worker; no late decision can survive host teardown.
                if teacher_channel is not None:
                    teacher_channel.close()
                elif teacher_socket is not None:
                    try:
                        teacher_socket.close()
                    except OSError:
                        pass
                if teacher_thread is not None:
                    teacher_thread.join(timeout=1.0)

                receipt = teacher_state["authorization"]
                _teacher_channel_error = teacher_state["error"]
                if receipt is not None:
                    try:
                        teacher_authorizer.close_run(
                            receipt,
                            "physical host shutting down",
                        )
                    except Exception:
                        pass
                # Keep the local error value deliberately non-observable to caller
                # IPC while retaining it for a future co-located trusted lifecycle.
                del _teacher_channel_error

                try:
                    caller_reader.close()
                    caller_writer.close()
                    caller_socket.close()
                except OSError:
                    pass

    _run_physical_host()

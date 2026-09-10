#!/usr/bin/env python3
"""Trusted physical-host composition root for current-program provenance.

This executable is the #280 authority boundary. Importing this file creates no
session, bridge, responder, teacher channel or physical effect object. When run
by trusted production composition it alone owns the live Crazyflie capability
session and the integrated #278 bridge/responder relationship.

The ordinary caller/UI is outside this process. Run-context validation requests
remain diagnostic/non-authority. After the distinct launcher-installed teacher
capability has established one exact #293 run, ordinary IPC may also request a
parameter-free ``execute-next-inflight`` step. That request carries no motion
semantics or authority: ``activate_validated_run()`` derives the next eligible
move/turn from the exact #267 canonical AST and keeps the #276 effect/provenance
objects inside the trusted process. A positive reply is still non-authority data.

Browser bootstrap is a distinct one-way composition channel. Its responder
credential is written there once and never returned on ordinary caller IPC. The
teacher socket is distinct from both channels and is consumed only inside the
one-shot production activation path; ordinary caller data cannot supply, replace
or write that trusted decision channel. The #276 transport belongs inside this
same process so fresh #249 and all identity-sensitive #257/#260/#262/#266/#267/
#271/#272/#273 objects share the one live Crazyflie/session/connection epoch.
Starting the host, validating a run without the trusted teacher capability, or
requesting an in-flight step before successful activation remains effect-free.
"""

if __name__ == "__main__":

    def _run_physical_host() -> None:
        import argparse
        import json
        import os
        from pathlib import Path
        import socket
        import sys
        from threading import Event, Lock, Thread

        physical = Path(__file__).resolve().parent
        if str(physical) not in sys.path:
            sys.path.insert(0, str(physical))

        from physical_execution_domain import PhysicalExecutionDomain
        from physical_run_activation import activate_validated_run
        from post_reset_capability_bridge import PostResetCapabilityHttpBridge
        from probe_reference_hardware import ReadOnlyCapabilitySession
        from serve_reference_capabilities import CapabilityBridgeError
        from teacher_run_authorization import PhysicalRunBinding

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
            help=(
                "distinct launcher-installed teacher capability; its presence enables "
                "one post-reset host-first #290 decision for a freshly validated candidate"
            ),
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
            bridge = PostResetCapabilityHttpBridge(session)
            bridge_thread = Thread(target=bridge.serve_forever, daemon=True)
            bridge_thread.start()
            host, port = bridge.address

            execution_domain = PhysicalExecutionDomain()
            lifecycle_lock = Lock()
            staged_ready = Event()
            host_stopping = Event()
            staged_state = {"binding": None}
            activation_state = {
                "started": False,
                "active_run": None,
                "error": None,
            }
            activation_thread = None

            def run_trusted_activation() -> None:
                if teacher_socket is None:
                    return
                try:
                    while not staged_ready.wait(0.05):
                        if host_stopping.is_set():
                            return
                    if host_stopping.is_set():
                        return

                    with lifecycle_lock:
                        binding = staged_state["binding"]
                        if type(binding) is not PhysicalRunBinding:
                            raise RuntimeError(
                                "trusted teacher capability has no exact host-validated candidate"
                            )
                        activation_state["active_run"] = activate_validated_run(
                            uri=args.uri,
                            session=session,
                            bridge=bridge,
                            teacher_socket=teacher_socket,
                            staged_binding=binding,
                            execution_domain=execution_domain,
                            assertion_timeout_seconds=assertion_timeout_seconds,
                        )
                except Exception as exc:
                    activation_state["error"] = str(exc)

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

            if teacher_socket is not None:
                activation_thread = Thread(
                    target=run_trusted_activation,
                    daemon=True,
                )
                activation_thread.start()

            def write_response(response: dict[str, object]) -> bool:
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
                    return True
                except OSError:
                    return False

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

                    operation = request.get("op")
                    if operation == "execute-next-inflight":
                        request_id = request.get("requestId")
                        if (
                            not isinstance(request_id, str)
                            or not request_id.strip()
                            or request_id != request_id.strip()
                        ):
                            break
                        if set(request) != {"op", "requestId"}:
                            response = {
                                "requestId": request_id,
                                "ok": False,
                                "error": (
                                    "in-flight execution accepts no caller-selected "
                                    "motion semantics"
                                ),
                                "executionAuthority": False,
                            }
                        else:
                            try:
                                with lifecycle_lock:
                                    active_controller = activation_state["active_run"]
                                    if active_controller is None:
                                        raise RuntimeError(
                                            "authorized in-flight execution is unavailable"
                                        )
                                    result = active_controller.execute_next_inflight()
                                    if getattr(result, "accepted", None) is not True:
                                        raise RuntimeError(
                                            "authorized in-flight effect was rejected"
                                        )
                            except Exception:
                                response = {
                                    "requestId": request_id,
                                    "ok": False,
                                    "error": "authorized in-flight execution failed closed",
                                    "executionAuthority": False,
                                }
                            else:
                                response = {
                                    "requestId": request_id,
                                    "ok": True,
                                    "executionAuthority": False,
                                }
                        if not write_response(response):
                            break
                        continue

                    if operation != "validate-run-context":
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
                        with lifecycle_lock:
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

                            if (
                                teacher_socket is not None
                                and not activation_state["started"]
                            ):
                                staged_state["binding"] = PhysicalRunBinding(
                                    profile_id=profile_id,
                                    ast_binding=ast_binding,
                                    connection_epoch=connection_epoch,
                                )
                                activation_state["started"] = True
                                staged_ready.set()
                    except CapabilityBridgeError as exc:
                        response = {
                            "requestId": request_id,
                            "ok": False,
                            "error": str(exc),
                            "executionAuthority": False,
                        }
                    except Exception as exc:
                        response = {
                            "requestId": request_id,
                            "ok": False,
                            "error": "run context validation failed closed: " + str(exc),
                            "executionAuthority": False,
                        }
                    else:
                        response = {
                            "requestId": request_id,
                            "ok": True,
                            "executionAuthority": False,
                        }

                    if not write_response(response):
                        break
            finally:
                host_stopping.set()
                staged_ready.set()

                if activation_thread is not None:
                    activation_thread.join()

                active_controller = activation_state["active_run"]
                _activation_error = activation_state["error"]
                if active_controller is not None:
                    try:
                        active_controller.shutdown()
                    except Exception:
                        pass

                bridge.shutdown()
                bridge_thread.join(timeout=1.0)

                if teacher_socket is not None:
                    try:
                        teacher_socket.close()
                    except OSError:
                        pass

                del _activation_error

                try:
                    caller_reader.close()
                    caller_writer.close()
                    caller_socket.close()
                except OSError:
                    pass

    _run_physical_host()

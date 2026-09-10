#!/usr/bin/env python3
"""Trusted physical-host composition root for current-program provenance.

This executable is the #280 authority boundary. Importing this file creates no
session, bridge, responder, mint/bind API or physical effect object. When run by
trusted production composition it alone owns the live Crazyflie capability
session and the integrated #278 bridge/responder relationship.

The ordinary caller/UI is outside this process. Its IPC messages are untrusted
run-context requests only; a positive reply is diagnostic/non-authority data and
must never be accepted later as an effect capability. The future #276 transport
belongs *inside this same process* so the fresh #249 assertion and all
identity-sensitive #257/#260/#262/#266/#267/#271/#272/#273 objects share the
one live Crazyflie/session/connection epoch.

Browser bootstrap is a distinct one-way composition channel. The responder
credential is written there once and is never returned on the ordinary caller
channel. Live bridge/session/responder state remains local to the running host
composition instead of being installed as attributes on the process' importable
``__main__`` module. This executable emits no flight, arming, setpoint or reset
command.
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

        from probe_reference_hardware import ReadOnlyCapabilitySession
        from serve_reference_capabilities import (
            CapabilityBridgeError,
            ReadOnlyCapabilityHttpBridge,
        )

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
        args = parser.parse_args()

        if not args.uri.startswith("radio://"):
            raise SystemExit("physical host requires explicit radio:// URI")
        if args.caller_fd < 3 or args.browser_config_fd < 3:
            raise SystemExit("physical host channels must be inherited non-stdio handles")
        if args.caller_fd == args.browser_config_fd:
            raise SystemExit("caller and browser bootstrap channels must be distinct")

        caller_socket = socket.socket(fileno=args.caller_fd)
        caller_reader = caller_socket.makefile("r", encoding="utf-8", newline="\n")
        caller_writer = caller_socket.makefile("w", encoding="utf-8", newline="\n")

        with ReadOnlyCapabilitySession(args.uri) as session:
            bridge = ReadOnlyCapabilityHttpBridge(session)
            bridge_thread = Thread(target=bridge.serve_forever, daemon=True)
            bridge_thread.start()
            host, port = bridge.address

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
                        # before the effect; caller replies are never provenance.
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
                try:
                    caller_reader.close()
                    caller_writer.close()
                    caller_socket.close()
                except OSError:
                    pass

    _run_physical_host()

#!/usr/bin/env python3
"""Trusted #280 current-program authority process.

This executable is the authority side of the selected production process split.
It alone owns the live Crazyflie capability session, integrated #278 bridge,
host-created challenge state and browser responder credential.

Trusted production composition gives the separate effect worker only a one-way
request-send capability and a one-way response-receive capability. This host
receives the matching request-read and response-write handles. Browser bootstrap
uses a third, distinct one-way channel. No bridge/session/responder object or
credential crosses to the effect worker.

A positive response remains non-authority data. It is useful only as the fresh
current-program prerequisite consumed inside the separately composed #276 effect
worker together with its independent teacher/safety/effect preconditions.

Importing this file creates no session, bridge, responder, requester, binder,
mint API or physical effect object. This prerequisite emits no movement, arming,
setpoint or reset command.
"""

if __name__ == "__main__":

    def _run_physical_host() -> None:
        import argparse
        import json
        import os
        from pathlib import Path
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
            description="WebeeBlocks trusted current-program authority process"
        )
        parser.add_argument("--uri", required=True, help="explicit radio:// Crazyradio URI")
        parser.add_argument(
            "--request-fd",
            required=True,
            type=int,
            help="trusted-launcher-installed effect request read handle",
        )
        parser.add_argument(
            "--response-fd",
            required=True,
            type=int,
            help="trusted-launcher-installed effect response write handle",
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
        handles = (args.request_fd, args.response_fd, args.browser_config_fd)
        if any(fd < 3 for fd in handles):
            raise SystemExit("physical host channels must be inherited non-stdio handles")
        if len(set(handles)) != len(handles):
            raise SystemExit("physical host channels must be distinct")

        request_reader = os.fdopen(
            args.request_fd,
            "r",
            encoding="utf-8",
            newline="\n",
            closefd=True,
        )
        response_writer = os.fdopen(
            args.response_fd,
            "w",
            encoding="utf-8",
            newline="\n",
            closefd=True,
        )

        with ReadOnlyCapabilitySession(args.uri) as session:
            bridge = ReadOnlyCapabilityHttpBridge(session)
            bridge_thread = Thread(target=bridge.serve_forever, daemon=True)
            bridge_thread.start()
            host, port = bridge.address

            # Trusted composition routes this descriptor only toward the
            # production browser #249 responder. It never crosses either effect
            # IPC capability.
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
                for line in request_reader:
                    if len(line.encode("utf-8")) > max_message_bytes:
                        break
                    try:
                        request = json.loads(line)
                    except (UnicodeError, json.JSONDecodeError):
                        break
                    if not isinstance(request, dict):
                        break
                    if request.get("op") != "assert-current-program":
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
                            "profileId": evidence.profile_id,
                            "astBinding": evidence.ast_binding,
                            "connectionEpoch": evidence.connection_epoch,
                            "challengeId": evidence.challenge_id,
                            "executionAuthority": False,
                        }

                    try:
                        response_writer.write(
                            json.dumps(
                                response,
                                separators=(",", ":"),
                                sort_keys=True,
                            )
                            + "\n"
                        )
                        response_writer.flush()
                    except OSError:
                        break
            finally:
                bridge.shutdown()
                bridge_thread.join(timeout=1.0)
                try:
                    request_reader.close()
                    response_writer.close()
                except OSError:
                    pass

    _run_physical_host()

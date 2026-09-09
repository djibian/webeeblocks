#!/usr/bin/env python3
"""Trusted physical-host current-program authority composition.

This executable is intentionally not an importable bridge/session factory.
Production launch gives it two distinct inherited OS socket capabilities:

- a browser-bootstrap channel used once to deliver the integrated #278 browser
  base URL and responder credential;
- a caller-request channel that can ask only for a fresh exact current-program
  assertion.

The process itself owns the live ReadOnlyCapabilitySession, the #278 bridge,
host-created challenge state and browser responder credential. The caller
channel accepts no bridge/session/socket/token substitution fields. A later
#276 integration must instantiate the physical effect transport inside this same
trusted host process so the exact live Crazyflie/session and all process-local
safety domains remain co-located with this #249 assertion gate.
"""

if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path
    import socket
    import sys
    from threading import Thread

    PHYSICAL = Path(__file__).resolve().parent
    if str(PHYSICAL) not in sys.path:
        sys.path.insert(0, str(PHYSICAL))

    from probe_reference_hardware import ReadOnlyCapabilitySession
    from serve_reference_capabilities import (
        CapabilityBridgeError,
        ReadOnlyCapabilityHttpBridge,
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", required=True)
    parser.add_argument("--caller-fd", required=True, type=int)
    parser.add_argument("--browser-config-fd", required=True, type=int)
    args = parser.parse_args()

    if not args.uri.startswith("radio://"):
        raise SystemExit("current-program authority requires explicit radio:// URI")
    if args.caller_fd < 0 or args.browser_config_fd < 0:
        raise SystemExit("authority channels require inherited descriptors")
    if args.caller_fd == args.browser_config_fd:
        raise SystemExit("caller and browser authority channels must be distinct")

    caller_socket = socket.socket(fileno=args.caller_fd)
    browser_socket = socket.socket(fileno=args.browser_config_fd)
    caller_reader = caller_socket.makefile("r", encoding="utf-8", newline="\n")
    caller_writer = caller_socket.makefile("w", encoding="utf-8", newline="\n")
    browser_writer = browser_socket.makefile("w", encoding="utf-8", newline="\n")

    with ReadOnlyCapabilitySession(args.uri) as session:
        bridge = ReadOnlyCapabilityHttpBridge(session)
        http_thread = Thread(target=bridge.serve_forever, daemon=True)
        http_thread.start()
        host, port = bridge.address

        browser_writer.write(
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
        browser_writer.flush()
        browser_writer.close()
        browser_socket.close()

        allowed_fields = {
            "op",
            "requestId",
            "profileId",
            "astBinding",
            "connectionEpoch",
        }
        try:
            for line in caller_reader:
                request_id = None
                response = None
                try:
                    if len(line.encode("utf-8")) > 8192:
                        raise ValueError("caller request exceeds protocol limit")
                    request = json.loads(line)
                    if not isinstance(request, dict):
                        raise ValueError("caller request must be a JSON object")
                    request_id = request.get("requestId")
                    if (
                        not isinstance(request_id, str)
                        or not request_id.strip()
                        or request_id != request_id.strip()
                    ):
                        raise ValueError("requestId must be a non-empty trimmed string")
                    unexpected = sorted(set(request) - allowed_fields)
                    if unexpected:
                        raise ValueError(
                            "caller request contains forbidden authority fields: "
                            + ",".join(unexpected)
                        )
                    if request.get("op") != "assert-current-program":
                        raise ValueError("unsupported current-program authority operation")
                    profile_id = request.get("profileId")
                    ast_binding = request.get("astBinding")
                    connection_epoch = request.get("connectionEpoch")
                    for value, name in (
                        (profile_id, "profileId"),
                        (ast_binding, "astBinding"),
                        (connection_epoch, "connectionEpoch"),
                    ):
                        if (
                            not isinstance(value, str)
                            or not value.strip()
                            or value != value.strip()
                        ):
                            raise ValueError(name + " must be a non-empty trimmed string")

                    try:
                        evidence = bridge.assert_current_program(
                            profile_id=profile_id,
                            ast_binding=ast_binding,
                            connection_epoch=connection_epoch,
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
                            "challengeId": evidence.challenge_id,
                            "profileId": evidence.profile_id,
                            "astBinding": evidence.ast_binding,
                            "connectionEpoch": evidence.connection_epoch,
                            "executionAuthority": False,
                        }
                except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
                    response = {
                        "requestId": request_id,
                        "ok": False,
                        "error": str(exc),
                        "executionAuthority": False,
                    }

                caller_writer.write(
                    json.dumps(
                        response,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                    + "\n"
                )
                caller_writer.flush()
        finally:
            bridge.shutdown()
            http_thread.join(timeout=1.0)
            caller_reader.close()
            caller_writer.close()
            caller_socket.close()

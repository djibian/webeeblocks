#!/usr/bin/env python3
"""Standalone production current-program provenance authority.

This file is intentionally an executable composition boundary, not an importable
bridge/session factory. Trusted launch composition gives it two disjoint OS
capabilities:

* an effect RPC socket FD, inherited only by the physical effect side;
* a one-shot browser bootstrap FD, used only to deliver the #278 base URL and
  responder credential to the production #249 browser runtime.

The effect RPC never exposes bridge/session objects, responder credentials,
challenge-answer operations or mint/bind operations. No physical command exists
in this process.
"""

if __name__ == "__main__":
    import argparse
    import json
    import os
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
    parser.add_argument("--effect-fd", required=True, type=int)
    parser.add_argument("--browser-config-fd", required=True, type=int)
    args = parser.parse_args()

    if not args.uri.startswith("radio://"):
        raise SystemExit("current-program authority requires explicit radio:// URI")
    if args.effect_fd < 3 or args.browser_config_fd < 3:
        raise SystemExit("authority channels must be inherited non-stdio descriptors")
    if args.effect_fd == args.browser_config_fd:
        raise SystemExit("effect and browser authority channels must be distinct")

    effect_socket = socket.socket(fileno=args.effect_fd)
    effect_reader = effect_socket.makefile("r", encoding="utf-8", newline="\n")
    effect_writer = effect_socket.makefile("w", encoding="utf-8", newline="\n")

    with ReadOnlyCapabilitySession(args.uri) as session:
        bridge = ReadOnlyCapabilityHttpBridge(session)
        http_thread = Thread(target=bridge.serve_forever, daemon=True)
        http_thread.start()
        host, port = bridge.address

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
            for line in effect_reader:
                if len(line.encode("utf-8")) > 8192:
                    break
                try:
                    request = json.loads(line)
                    if not isinstance(request, dict):
                        break
                    if request.get("op") != "assert-current-program":
                        break
                    request_id = request.get("requestId")
                    profile_id = request.get("profileId")
                    ast_binding = request.get("astBinding")
                    connection_epoch = request.get("connectionEpoch")
                    if (
                        not isinstance(request_id, str)
                        or not request_id.strip()
                        or not isinstance(profile_id, str)
                        or not profile_id.strip()
                        or not isinstance(ast_binding, str)
                        or not ast_binding.strip()
                        or not isinstance(connection_epoch, str)
                        or not connection_epoch.strip()
                    ):
                        break

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
                    effect_writer.write(
                        json.dumps(
                            response,
                            separators=(",", ":"),
                            sort_keys=True,
                        )
                        + "\n"
                    )
                    effect_writer.flush()
                except (OSError, UnicodeError, json.JSONDecodeError):
                    break
        finally:
            bridge.shutdown()
            http_thread.join(timeout=1.0)
            try:
                effect_reader.close()
                effect_writer.close()
                effect_socket.close()
            except OSError:
                pass

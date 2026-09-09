#!/usr/bin/env python3
from __future__ import annotations

import json
import multiprocessing
from pathlib import Path
import runpy
import socket
import sys
from threading import Thread
import types
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
AUTHORITY = PHYSICAL / "serve_current_program_authority.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def http_request(
    url: str,
    token: str,
    *,
    method: str = "GET",
    payload: object | None = None,
) -> tuple[int, object]:
    data = None
    headers = {"Authorization": "Bearer " + token}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, method=method, headers=headers, data=data)
    try:
        with urlopen(req, timeout=2) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def authority_child(caller_socket: socket.socket, browser_socket: socket.socket) -> None:
    class ProbeError(RuntimeError):
        pass

    class FakeSession:
        def __init__(self, uri: str) -> None:
            if not uri.startswith("radio://"):
                raise ProbeError("explicit radio URI required")
            self.epoch = "authority-process-epoch"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read_connection_epoch(self) -> str:
            return self.epoch

        def read_capabilities(self) -> dict[str, object]:
            return {
                "connected": True,
                "executionAuthority": False,
            }

    fake_probe = types.ModuleType("probe_reference_hardware")
    fake_probe.ProbeError = ProbeError
    fake_probe.ReadOnlyCapabilitySession = FakeSession
    sys.modules["probe_reference_hardware"] = fake_probe

    if str(PHYSICAL) not in sys.path:
        sys.path.insert(0, str(PHYSICAL))

    caller_fd = caller_socket.detach()
    browser_fd = browser_socket.detach()
    old_argv = sys.argv
    sys.argv = [
        str(AUTHORITY),
        "--uri",
        "radio://0/80/2M/E7E7E7E7E7",
        "--caller-fd",
        str(caller_fd),
        "--browser-config-fd",
        str(browser_fd),
    ]
    try:
        runpy.run_path(str(AUTHORITY), run_name="__main__")
    finally:
        sys.argv = old_argv


def main() -> int:
    ctx = multiprocessing.get_context("spawn")
    caller_parent, caller_child = socket.socketpair()
    browser_parent, browser_child = socket.socketpair()
    process = ctx.Process(
        target=authority_child,
        args=(caller_child, browser_child),
    )
    process.start()
    caller_child.close()
    browser_child.close()

    caller_reader = caller_parent.makefile("r", encoding="utf-8", newline="\n")
    caller_writer = caller_parent.makefile("w", encoding="utf-8", newline="\n")
    browser_reader = browser_parent.makefile("r", encoding="utf-8", newline="\n")

    bootstrap = json.loads(browser_reader.readline())
    require(
        bootstrap["executionAuthority"] is False,
        "browser bootstrap remains non-authority",
    )
    responder_token = bootstrap["preflightResponderToken"]
    require(
        isinstance(responder_token, str) and responder_token,
        "trusted browser channel receives responder credential",
    )
    base_url = bootstrap["baseUrl"]
    browser_reader.close()
    browser_parent.close()

    # The ordinary caller channel may name only the expected binding. It cannot
    # substitute its own bridge/session/responder/token into trusted composition.
    caller_writer.write(
        json.dumps(
            {
                "op": "assert-current-program",
                "requestId": "substitution",
                "profileId": "activity-1",
                "astBinding": "ast-1",
                "connectionEpoch": "authority-process-epoch",
                "bridge": "caller-selected",
                "preflightResponderToken": "caller-token",
            },
            separators=(",", ":"),
        )
        + "\n"
    )
    caller_writer.flush()
    denied = json.loads(caller_reader.readline())
    require(denied["ok"] is False, "authority substitution must fail closed")
    require(
        "forbidden authority fields" in denied["error"],
        "rejection identifies forbidden authority input",
    )
    require(
        "caller-token" not in json.dumps(denied)
        and responder_token not in json.dumps(denied),
        "caller reply never reflects responder credentials",
    )

    # Positive request is blocked inside the separate trusted host until the
    # integrated #278 browser responder settles the host-created challenge.
    caller_writer.write(
        json.dumps(
            {
                "op": "assert-current-program",
                "requestId": "fresh-1",
                "profileId": "activity-1",
                "astBinding": "ast-1",
                "connectionEpoch": "authority-process-epoch",
            },
            separators=(",", ":"),
        )
        + "\n"
    )
    caller_writer.flush()

    status, challenge = http_request(
        base_url + "/v1/preflight-challenge",
        responder_token,
    )
    require(status == 200, "production #278 responder can claim host challenge")
    challenge_id = challenge["challengeId"]
    require(isinstance(challenge_id, str) and challenge_id, "fresh challenge required")

    status, response = http_request(
        base_url + "/v1/preflight-assertion",
        responder_token,
        method="POST",
        payload={
            "challengeId": challenge_id,
            "ok": True,
            "profileId": "activity-1",
            "astBinding": "ast-1",
            "connectionEpoch": "authority-process-epoch",
            "executionAuthority": False,
        },
    )
    require(status == 200 and response["accepted"] is True, "browser response settles")

    accepted = json.loads(caller_reader.readline())
    require(accepted["ok"] is True, "fresh production assertion succeeds")
    require(accepted["requestId"] == "fresh-1", "correlation preserved")
    require(accepted["challengeId"] == challenge_id, "challenge provenance preserved")
    require(accepted["executionAuthority"] is False, "caller response is non-authority")
    require(
        responder_token not in json.dumps(accepted),
        "caller never receives responder token",
    )

    # Changed browser binding remains fail-closed.
    caller_writer.write(
        json.dumps(
            {
                "op": "assert-current-program",
                "requestId": "mismatch",
                "profileId": "activity-1",
                "astBinding": "ast-1",
                "connectionEpoch": "authority-process-epoch",
            },
            separators=(",", ":"),
        )
        + "\n"
    )
    caller_writer.flush()
    status, challenge = http_request(
        base_url + "/v1/preflight-challenge",
        responder_token,
    )
    require(status == 200, "second challenge exists")
    status, mismatch = http_request(
        base_url + "/v1/preflight-assertion",
        responder_token,
        method="POST",
        payload={
            "challengeId": challenge["challengeId"],
            "ok": True,
            "profileId": "activity-1",
            "astBinding": "other-ast",
            "connectionEpoch": "authority-process-epoch",
            "executionAuthority": False,
        },
    )
    require(status == 409, "mismatched browser assertion is rejected")
    negative = json.loads(caller_reader.readline())
    require(
        negative["ok"] is False and "does not match" in negative["error"],
        "authority host propagates mismatch as non-authorizing result",
    )

    # Production script exports no importable Python client/binder/mint class.
    source = AUTHORITY.read_text(encoding="utf-8")
    require(
        "CurrentProgramProvenanceClient" not in source
        and "_bind_effect_current_program_bridge" not in source
        and "CurrentProgramEffectPreflightHandle" not in source,
        "production boundary exports no caller-selected provenance wrapper",
    )
    require(
        "ReadOnlyCapabilitySession(args.uri)" in source
        and "ReadOnlyCapabilityHttpBridge(session)" in source,
        "trusted host owns one exact session/bridge composition",
    )

    caller_writer.close()
    caller_reader.close()
    caller_parent.close()
    process.join(timeout=3)
    require(not process.is_alive(), "authority process exits on caller EOF")
    require(process.exitcode == 0, "authority process exits cleanly")

    print(
        "PASS trusted host process owns #278 responder/session while caller can "
        "request but cannot substitute current-program provenance"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(PHYSICAL))
BRIDGE_PATH = PHYSICAL / "serve_reference_capabilities.py"
spec = importlib.util.spec_from_file_location("serve_reference_capabilities", BRIDGE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load capability HTTP bridge")
bridge_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge_module)


class FakeSession:
    def __init__(self) -> None:
        self.epoch = "connection-one"
        self.capability_reads = 0
        self.epoch_reads = 0

    def read_connection_epoch(self) -> str:
        self.epoch_reads += 1
        return self.epoch

    def read_capabilities(self) -> dict[str, object]:
        self.capability_reads += 1
        return {
            "transport": "crazyradio",
            "connected": True,
            "executionAuthority": False,
            "identity": {
                "family": "crazyflie",
                "model": "crazyflie-2.1",
                "modelEvidence": "verified",
            },
            "hardware": ["flow-deck-v2"],
            "capabilities": {
                "actions": ["takeoff", "move", "land"],
                "rangeDirections": [],
                "moveDirections": ["forward"],
                "verticalDirections": [],
            },
        }


def request(
    url: str,
    token: str | None = None,
    method: str = "GET",
    payload: object | None = None,
) -> tuple[int, object | None, object]:
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, method=method, headers=headers, data=data)
    try:
        with urlopen(req, timeout=2) as response:
            raw = response.read()
            payload = json.loads(raw.decode("utf-8")) if raw else None
            return response.status, payload, response.headers
    except HTTPError as exc:
        raw = exc.read()
        payload = json.loads(raw.decode("utf-8")) if raw else None
        return exc.code, payload, exc.headers



def start_host_assertion(
    bridge,
    *,
    profile_id: str = "activity-1",
    ast_binding: str = "ast-1",
    connection_epoch: str = "connection-one",
    timeout_seconds: float = 0.5,
):
    outcome: dict[str, object] = {}

    def run() -> None:
        try:
            outcome["evidence"] = bridge.assert_current_program(
                profile_id=profile_id,
                ast_binding=ast_binding,
                connection_epoch=connection_epoch,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            outcome["error"] = exc

    thread = Thread(target=run, daemon=True)
    thread.start()
    return thread, outcome


def complete_host_assertion(
    base: str,
    token: str,
    *,
    profile_id: str = "activity-1",
    ast_binding: str = "ast-1",
    connection_epoch: str = "connection-one",
):
    status, challenge, _ = request(base + "/v1/preflight-challenge", token)
    assert status == 200
    assert challenge["executionAuthority"] is False
    challenge_id = challenge["challengeId"]
    assert isinstance(challenge_id, str) and challenge_id
    status, response, _ = request(
        base + "/v1/preflight-assertion",
        token,
        method="POST",
        payload={
            "challengeId": challenge_id,
            "ok": True,
            "profileId": profile_id,
            "astBinding": ast_binding,
            "connectionEpoch": connection_epoch,
            "executionAuthority": False,
        },
    )
    return status, response, challenge_id


def main() -> int:
    fake = FakeSession()
    token = "test-bridge-token"
    bridge = bridge_module.ReadOnlyCapabilityHttpBridge(fake, token=token)
    host, port = bridge.address
    thread = Thread(target=bridge.serve_forever, daemon=True)
    thread.start()
    base = f"http://{host}:{port}"
    try:
        status, payload, headers = request(base + "/v1/connection-epoch", token)
        assert status == 200 and payload == {"connectionEpoch": "connection-one"}
        assert headers["Access-Control-Allow-Origin"] == "*"
        assert headers["Cache-Control"] == "no-store"

        status, payload, _ = request(base + "/v1/capabilities", token)
        assert status == 200
        assert payload["executionAuthority"] is False
        assert payload["hardware"] == ["flow-deck-v2"]
        assert fake.epoch_reads == 1 and fake.capability_reads == 1

        status, payload, cors = request(base + "/v1/capabilities", method="OPTIONS")
        assert status == 204 and payload is None
        assert cors["Access-Control-Allow-Origin"] == "*"
        assert cors["Access-Control-Allow-Methods"] == "GET, POST, OPTIONS"
        assert "Authorization" in cors["Access-Control-Allow-Headers"]
        assert "Content-Type" in cors["Access-Control-Allow-Headers"]
        assert fake.epoch_reads == 1 and fake.capability_reads == 1, "CORS preflight must not touch live session"

        status, payload, _ = request(base + "/v1/capabilities")
        assert status == 401 and payload == {"error": "unauthorized"}
        assert fake.capability_reads == 1, "unauthorized read must not touch the live session"

        status, payload, _ = request(base + "/v1/connection-epoch", token, method="POST")
        assert status == 405 and payload == {"error": "read-only bridge"}
        assert fake.epoch_reads == 1, "effect-shaped methods must never reach the live session"

        # Only the trusted host can create a fresh current-program challenge.
        thread, outcome = start_host_assertion(bridge)
        status, response, challenge_id = complete_host_assertion(base, token)
        assert status == 200 and response["accepted"] is True
        assert response["executionAuthority"] is False
        thread.join(timeout=2)
        assert not thread.is_alive() and "error" not in outcome
        evidence = outcome["evidence"]
        assert evidence.profile_id == "activity-1"
        assert evidence.ast_binding == "ast-1"
        assert evidence.connection_epoch == "connection-one"
        assert evidence.challenge_id == challenge_id
        assert evidence.execution_authority is False

        # The exact challenge is one-shot; replay/late responses are rejected.
        status, replay, _ = request(
            base + "/v1/preflight-assertion",
            token,
            method="POST",
            payload={
                "challengeId": challenge_id,
                "ok": True,
                "profileId": "activity-1",
                "astBinding": "ast-1",
                "connectionEpoch": "connection-one",
                "executionAuthority": False,
            },
        )
        assert status == 409 and "stale" in replay["error"]

        # A same-challenge profile/AST mismatch settles the host request fail-closed.
        thread, outcome = start_host_assertion(bridge)
        status, challenge, _ = request(base + "/v1/preflight-challenge", token)
        mismatch_id = challenge["challengeId"]
        status, mismatch, _ = request(
            base + "/v1/preflight-assertion",
            token,
            method="POST",
            payload={
                "challengeId": mismatch_id,
                "ok": True,
                "profileId": "wrong-activity",
                "astBinding": "ast-1",
                "connectionEpoch": "connection-one",
                "executionAuthority": False,
            },
        )
        assert status == 409 and "does not match" in mismatch["error"]
        thread.join(timeout=2)
        assert isinstance(outcome.get("error"), bridge_module.CapabilityBridgeError)
        assert "does not match" in str(outcome["error"])

        # Reconnect after challenge creation but before host acceptance is stale.
        fake.epoch = "connection-one"
        thread, outcome = start_host_assertion(bridge)
        status, challenge, _ = request(base + "/v1/preflight-challenge", token)
        epoch_id = challenge["challengeId"]
        fake.epoch = "connection-two"
        status, response, _ = request(
            base + "/v1/preflight-assertion",
            token,
            method="POST",
            payload={
                "challengeId": epoch_id,
                "ok": True,
                "profileId": "activity-1",
                "astBinding": "ast-1",
                "connectionEpoch": "connection-one",
                "executionAuthority": False,
            },
        )
        assert status == 200
        thread.join(timeout=2)
        assert isinstance(outcome.get("error"), bridge_module.CapabilityBridgeError)
        assert "changed during" in str(outcome["error"])

        # A host timeout invalidates the challenge; a later response cannot revive it.
        fake.epoch = "connection-one"
        thread, outcome = start_host_assertion(bridge, timeout_seconds=0.03)
        status, challenge, _ = request(base + "/v1/preflight-challenge", token)
        timeout_id = challenge["challengeId"]
        thread.join(timeout=2)
        assert isinstance(outcome.get("error"), bridge_module.CapabilityBridgeError)
        assert "timed out" in str(outcome["error"])
        status, late, _ = request(
            base + "/v1/preflight-assertion",
            token,
            method="POST",
            payload={
                "challengeId": timeout_id,
                "ok": True,
                "profileId": "activity-1",
                "astBinding": "ast-1",
                "connectionEpoch": "connection-one",
                "executionAuthority": False,
            },
        )
        assert status == 409 and "stale" in late["error"]

        # Browser responses cannot create a challenge on their own.
        status, unsolicited, _ = request(
            base + "/v1/preflight-assertion",
            token,
            method="POST",
            payload={
                "challengeId": "fabricated-challenge",
                "ok": True,
                "profileId": "activity-1",
                "astBinding": "ast-1",
                "connectionEpoch": "connection-one",
                "executionAuthority": False,
            },
        )
        assert status == 409 and "unknown" in unsolicited["error"]

        # Exact evidence cannot be constructed by an arbitrary binding source.
        try:
            bridge_module.CurrentProgramPreflightEvidence(
                profile_id="activity-1",
                ast_binding="ast-1",
                connection_epoch="connection-one",
                challenge_id="fabricated",
                _mint_key=object(),
            )
        except bridge_module.CapabilityBridgeError as exc:
            assert "trusted host bridge" in str(exc)
        else:
            raise AssertionError("fabricated current-program evidence must fail closed")

        fake.epoch = "connection-two"
        status, payload, _ = request(base + "/v1/connection-epoch", token)
        assert status == 200 and payload == {"connectionEpoch": "connection-two"}
    finally:
        bridge.shutdown()
        thread.join(timeout=2)

    for forbidden_host in ("0.0.0.0", "::1"):
        try:
            bridge_module.ReadOnlyCapabilityHttpBridge(fake, host=forbidden_host)
        except bridge_module.CapabilityBridgeError as exc:
            assert "loopback" in str(exc)
        else:
            raise AssertionError(f"unsupported bind {forbidden_host} must fail closed")

    forbidden = (
        "takeoff", "land", "move", "vertical", "turn", "set_light", "arm",
        "disarm", "setpoint", "send_setpoint", "thrust",
    )
    for name in forbidden:
        assert not hasattr(bridge, name), f"HTTP bridge exposes authority method: {name}"

    print("PASS loopback capability bridge provides fresh host-initiated #249 handoff with no physical authority")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

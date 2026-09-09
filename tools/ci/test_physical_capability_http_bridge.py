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


def request_json(url: str, token: str | None = None, method: str = "GET") -> tuple[int, object]:
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}
    request = Request(url, method=method, headers=headers)
    try:
        with urlopen(request, timeout=2) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def main() -> int:
    fake = FakeSession()
    token = "test-bridge-token"
    bridge = bridge_module.ReadOnlyCapabilityHttpBridge(fake, token=token)
    host, port = bridge.address
    thread = Thread(target=bridge.serve_forever, daemon=True)
    thread.start()
    base = f"http://{host}:{port}"
    try:
        status, payload = request_json(base + "/v1/connection-epoch", token)
        assert status == 200 and payload == {"connectionEpoch": "connection-one"}
        status, payload = request_json(base + "/v1/capabilities", token)
        assert status == 200
        assert payload["executionAuthority"] is False
        assert payload["hardware"] == ["flow-deck-v2"]
        assert fake.epoch_reads == 1 and fake.capability_reads == 1

        status, payload = request_json(base + "/v1/capabilities")
        assert status == 401 and payload == {"error": "unauthorized"}
        assert fake.capability_reads == 1, "unauthorized read must not touch the live session"

        status, payload = request_json(base + "/v1/connection-epoch", token, method="POST")
        assert status == 405 and payload == {"error": "read-only bridge"}
        assert fake.epoch_reads == 1, "effect-shaped methods must never reach the live session"

        fake.epoch = "connection-two"
        status, payload = request_json(base + "/v1/connection-epoch", token)
        assert status == 200 and payload == {"connectionEpoch": "connection-two"}
    finally:
        bridge.shutdown()
        thread.join(timeout=2)

    try:
        bridge_module.ReadOnlyCapabilityHttpBridge(fake, host="0.0.0.0")
    except bridge_module.CapabilityBridgeError as exc:
        assert "loopback" in str(exc)
    else:
        raise AssertionError("non-loopback bind must fail closed")

    forbidden = (
        "takeoff", "land", "move", "vertical", "turn", "set_light", "arm",
        "disarm", "setpoint", "send_setpoint", "thrust",
    )
    for name in forbidden:
        assert not hasattr(bridge, name), f"HTTP bridge exposes authority method: {name}"

    print("PASS loopback capability bridge exposes authenticated reads only and no physical authority")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
if str(PHYSICAL) not in sys.path:
    sys.path.insert(0, str(PHYSICAL))

import post_reset_capability_bridge as rebind  # noqa: E402


class FakeSession:
    def __init__(self, epoch: str, label: str) -> None:
        self.epoch = epoch
        self.label = label

    def read_connection_epoch(self) -> str:
        return self.epoch

    def read_capabilities(self) -> dict[str, object]:
        return {
            "connected": True,
            "executionAuthority": False,
            "identity": {"model": "crazyflie-2.1", "modelEvidence": "verified"},
            "evidence": {"label": self.label},
        }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def request(url: str, token: str) -> tuple[int, object]:
    req = Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(req, timeout=1.0) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def expect_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except rebind.CapabilityBridgeError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError("expected CapabilityBridgeError containing " + repr(pattern))


def main() -> int:
    before = FakeSession("epoch-before", "before")
    after = FakeSession("epoch-after", "after")
    bridge = rebind.PostResetCapabilityHttpBridge(
        before,
        token="capability-token",
        preflight_responder_token="responder-token",
    )
    host, port = bridge.address
    base = f"http://{host}:{port}"
    worker = Thread(target=bridge.serve_forever, daemon=True)
    worker.start()
    try:
        original_address = bridge.address
        original_token = bridge.token
        original_responder_token = bridge.preflight_responder_token

        status, payload = request(base + "/v1/connection-epoch", bridge.token)
        require(
            status == 200 and payload == {"connectionEpoch": "epoch-before"},
            "pre-reset epoch",
        )

        expect_error(
            lambda: bridge.begin_post_reset_replacement("wrong-epoch"),
            "does not match replacement epoch",
        )
        require(
            not bridge.post_reset_replacement_pending,
            "wrong old epoch cannot invalidate bridge",
        )

        bridge.begin_post_reset_replacement("epoch-before")
        require(
            bridge.post_reset_replacement_pending,
            "replacement becomes fail-closed pending",
        )
        status, payload = request(base + "/v1/connection-epoch", bridge.token)
        require(
            status == 409 and "replacement" in payload["error"],
            "reads fail during replacement",
        )
        expect_error(
            lambda: bridge.assert_current_program(
                profile_id="activity-1",
                ast_binding="ast-1",
                connection_epoch="epoch-before",
                timeout_seconds=0.05,
            ),
            "replacement",
        )

        same_epoch = FakeSession("epoch-before", "forged-same")
        expect_error(
            lambda: bridge.install_post_reset_session(same_epoch),
            "reused the previous connection epoch",
        )
        require(
            bridge.post_reset_replacement_pending,
            "same epoch cannot reopen bridge",
        )

        installed = bridge.install_post_reset_session(after)
        require(installed == "epoch-after", "new exact epoch returned")
        require(
            not bridge.post_reset_replacement_pending,
            "new epoch completes replacement",
        )
        require(
            bridge.address == original_address,
            "loopback address stays stable across reset",
        )
        require(
            bridge.token == original_token,
            "capability bearer stays stable across reset",
        )
        require(
            bridge.preflight_responder_token == original_responder_token,
            "trusted #249 responder bearer stays stable across reset",
        )
        status, payload = request(base + "/v1/connection-epoch", bridge.token)
        require(
            status == 200 and payload == {"connectionEpoch": "epoch-after"},
            "post-reset epoch visible",
        )
        status, payload = request(base + "/v1/capabilities", bridge.token)
        require(
            status == 200 and payload["evidence"]["label"] == "after",
            "new read-only view installed",
        )
        require(
            payload["executionAuthority"] is False,
            "replacement never creates authority",
        )

        expect_error(
            lambda: bridge.install_post_reset_session(
                FakeSession("epoch-third", "third")
            ),
            "was not started",
        )

        for forbidden in (
            "takeoff",
            "land",
            "move",
            "send_packet",
            "stm_power_cycle",
            "authorize_run",
        ):
            require(
                not hasattr(bridge, forbidden),
                "rebind bridge exposes effect: " + forbidden,
            )
    finally:
        bridge.shutdown()
        worker.join(timeout=1.0)

    print(
        "PASS post-reset capability bridge preserves trusted loopback identity "
        "while stale epochs fail closed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

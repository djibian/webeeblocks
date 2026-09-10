#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys
from threading import Event, Thread
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


class BlockingFirstEpochSession(FakeSession):
    def __init__(self, epoch: str, label: str) -> None:
        super().__init__(epoch, label)
        self.first_read_started = Event()
        self.release_first_read = Event()
        self._read_count = 0

    def read_connection_epoch(self) -> str:
        self._read_count += 1
        if self._read_count == 1:
            self.first_read_started.set()
            if not self.release_first_read.wait(1.0):
                raise RuntimeError("test did not release first epoch read")
        return super().read_connection_epoch()


class BlockingCapabilitySession(FakeSession):
    def __init__(self, epoch: str, label: str) -> None:
        super().__init__(epoch, label)
        self.capability_read_started = Event()
        self.release_capability_read = Event()

    def read_capabilities(self) -> dict[str, object]:
        self.capability_read_started.set()
        if not self.release_capability_read.wait(1.0):
            raise RuntimeError("test did not release capability read")
        return super().read_capabilities()


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


def test_direct_session_assignment_cannot_bypass_replacement() -> None:
    before = FakeSession("epoch-before-direct", "before-direct")
    bridge = rebind.PostResetCapabilityHttpBridge(
        before,
        token="direct-capability-token",
        preflight_responder_token="direct-responder-token",
    )
    host, port = bridge.address
    base = f"http://{host}:{port}"
    worker = Thread(target=bridge.serve_forever, daemon=True)
    worker.start()
    try:
        for replacement in (
            FakeSession("epoch-before-direct", "same-epoch-direct"),
            FakeSession("epoch-different-direct", "different-epoch-direct"),
        ):
            expect_error(
                lambda replacement=replacement: setattr(bridge, "session", replacement),
                "explicit post-reset protocol",
            )
            require(
                not bridge.post_reset_replacement_pending,
                "rejected direct assignment cannot start replacement",
            )
            status, payload = request(base + "/v1/connection-epoch", bridge.token)
            require(
                status == 200
                and payload == {"connectionEpoch": "epoch-before-direct"},
                "rejected direct assignment cannot change observable epoch",
            )
            status, payload = request(base + "/v1/capabilities", bridge.token)
            require(
                status == 200 and payload["evidence"]["label"] == "before-direct",
                "rejected direct assignment cannot change capability view",
            )
    finally:
        bridge.shutdown()
        worker.join(timeout=1.0)
        require(not worker.is_alive(), "direct-assignment bridge worker did not stop")


def test_capability_http_read_is_drained_before_replacement_begin() -> None:
    before = BlockingCapabilitySession("epoch-http-race", "http-race")
    bridge = rebind.PostResetCapabilityHttpBridge(
        before,
        token="http-race-capability-token",
        preflight_responder_token="http-race-responder-token",
    )
    host, port = bridge.address
    base = f"http://{host}:{port}"
    worker = Thread(target=bridge.serve_forever, daemon=True)
    worker.start()
    read_outcome: dict[str, object] = {}
    replacement_outcome: dict[str, object] = {}

    def read_capabilities() -> None:
        try:
            read_outcome["result"] = request(base + "/v1/capabilities", bridge.token)
        except Exception as exc:
            read_outcome["error"] = exc

    def begin_replacement() -> None:
        try:
            bridge.begin_post_reset_replacement("epoch-http-race")
            replacement_outcome["started"] = True
        except Exception as exc:
            replacement_outcome["error"] = exc

    reader = Thread(target=read_capabilities, daemon=True)
    reader.start()
    require(
        before.capability_read_started.wait(1.0),
        "HTTP capability read did not enter the old session",
    )

    replacement = Thread(target=begin_replacement, daemon=True)
    replacement.start()
    replacement.join(timeout=0.02)
    require(
        replacement.is_alive(),
        "replacement begin returned while an admitted old capability read was still blocked",
    )

    before.release_capability_read.set()
    reader.join(timeout=1.0)
    replacement.join(timeout=1.0)
    require(not reader.is_alive(), "old capability read did not settle")
    require(not replacement.is_alive(), "replacement begin did not settle after draining read")
    require("error" not in read_outcome, "admitted old capability read must settle normally")
    status, payload = read_outcome["result"]
    require(
        status == 200 and payload["evidence"]["label"] == "http-race",
        "the admitted pre-cutover capability response must complete before the cutover returns",
    )
    require(
        replacement_outcome.get("started") is True and "error" not in replacement_outcome,
        "replacement must begin only after the admitted old read has drained",
    )

    status, payload = request(base + "/v1/capabilities", bridge.token)
    require(
        status == 409 and "replacement" in payload["error"],
        "new capability reads must fail closed after replacement begins",
    )

    bridge.shutdown()
    worker.join(timeout=1.0)
    require(not worker.is_alive(), "capability-race bridge worker did not stop")


def test_assertion_admission_cannot_race_replacement() -> None:
    """Force the old pre-read/pending-registration race and prove it is closed."""
    before = BlockingFirstEpochSession("epoch-race", "race")
    bridge = rebind.PostResetCapabilityHttpBridge(
        before,
        token="race-capability-token",
        preflight_responder_token="race-responder-token",
    )
    worker = Thread(target=bridge.serve_forever, daemon=True)
    worker.start()
    assertion_outcome: dict[str, object] = {}
    replacement_outcome: dict[str, object] = {}

    def assert_current() -> None:
        try:
            assertion_outcome["evidence"] = bridge.assert_current_program(
                profile_id="activity-race",
                ast_binding="ast-race",
                connection_epoch="epoch-race",
                timeout_seconds=0.5,
            )
        except Exception as exc:
            assertion_outcome["error"] = exc

    def begin_replacement() -> None:
        try:
            bridge.begin_post_reset_replacement("epoch-race")
            replacement_outcome["started"] = True
        except Exception as exc:
            replacement_outcome["error"] = exc

    assertion = Thread(target=assert_current, daemon=True)
    assertion.start()
    require(
        before.first_read_started.wait(1.0),
        "current-program assertion did not reach its first epoch read",
    )

    replacement = Thread(target=begin_replacement, daemon=True)
    replacement.start()
    replacement.join(timeout=0.02)
    require(
        replacement.is_alive(),
        "replacement crossed the assertion pre-read/pending-registration window",
    )

    before.release_first_read.set()
    replacement.join(timeout=1.0)
    require(not replacement.is_alive(), "replacement attempt did not settle")
    error = replacement_outcome.get("error")
    require(
        isinstance(error, rebind.CapabilityBridgeError)
        and "during current-program assertion" in str(error),
        "replacement must reject once the admitted assertion publishes its pending challenge",
    )
    require(
        "started" not in replacement_outcome,
        "replacement must not invalidate the bridge across an admitted assertion",
    )

    challenge_id = bridge._claim_current_program_challenge(timeout_seconds=0.2)
    require(isinstance(challenge_id, str) and challenge_id, "race assertion challenge")
    bridge._submit_current_program_assertion(
        {
            "challengeId": challenge_id,
            "ok": True,
            "profileId": "activity-race",
            "astBinding": "ast-race",
            "connectionEpoch": "epoch-race",
            "executionAuthority": False,
        }
    )
    assertion.join(timeout=1.0)
    require(not assertion.is_alive(), "current-program assertion did not settle")
    require("error" not in assertion_outcome, "admitted assertion must complete normally")
    evidence = assertion_outcome.get("evidence")
    require(
        getattr(evidence, "connection_epoch", None) == "epoch-race",
        "completed assertion remains bound to the unchanged pre-reset epoch",
    )
    require(
        not bridge.post_reset_replacement_pending,
        "failed concurrent replacement cannot leave a replacement marker",
    )
    bridge.shutdown()
    worker.join(timeout=1.0)
    require(not worker.is_alive(), "assertion-race bridge worker did not stop")


def main() -> int:
    test_direct_session_assignment_cannot_bypass_replacement()
    test_capability_http_read_is_drained_before_replacement_begin()
    test_assertion_admission_cannot_race_replacement()

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
        require(not worker.is_alive(), "main bridge worker did not stop")

    print(
        "PASS post-reset capability bridge preserves trusted loopback identity "
        "while stale epochs and assertion/replacement races fail closed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

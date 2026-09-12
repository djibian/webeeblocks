#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import socket
import sys
from threading import Thread

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
CI = ROOT / "tools" / "ci"
sys.path.insert(0, str(PHYSICAL))
sys.path.insert(0, str(CI))

import high_level_ack  # noqa: E402
import physical_execution_domain  # noqa: E402
import physical_run_activation as activation  # noqa: E402
import post_reset_capability_bridge  # noqa: E402
import powered_session_authority  # noqa: E402
import probe_reference_hardware  # noqa: E402
import safelink_precondition  # noqa: E402
import supervisor_state  # noqa: E402
import takeoff_transport  # noqa: E402
import teacher_run_authorization  # noqa: E402
import watchdog_liveness  # noqa: E402
import test_physical_host_activation as base  # noqa: E402

HOST = base.HOST
EVENTS = base.EVENTS
_ORIGINAL_CLOSE_RUN = teacher_run_authorization.TrustedTeacherAuthorizer.close_run


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class RealDomainFakeTransport(base.FakeTransportBase):
    """No-hardware effect seam that exercises the real #273 transaction."""

    def send_from_authorized_ast(self) -> base.FakeAckResult:
        binding_box: dict[str, object] = {}

        def fresh_current_program() -> None:
            binding = self._read_current_binding()
            require(binding == self.teacher_binding, "fresh provenance exact teacher binding")
            binding_box["binding"] = binding

        require(
            type(self.execution_domain) is physical_execution_domain.PhysicalExecutionDomain,
            "actual host must use the real process-wide #273 domain",
        )
        require(
            self.execution_domain.phase == physical_execution_domain.INACTIVE,
            "effect must start only after real #273 reset establishment",
        )
        with self.execution_domain.effect_transaction(fresh_current_program) as transaction:
            require(
                binding_box.get("binding") == self.teacher_binding,
                "effect transaction lost exact teacher/current-program binding",
            )
            EVENTS.append(("transport-send", self.bound_connection_epoch))
            transaction.mark_emitted()
            permit = transaction.mark_accepted()

        self.execution_domain.complete_accepted_effect(
            permit,
            physical_execution_domain.FLYING,
            lambda: True,
        )
        require(
            self.execution_domain.phase == physical_execution_domain.FLYING,
            "real #273 completion did not establish flying",
        )
        return base.FakeAckResult()


def _observed_close_run(self, receipt, reason: str) -> None:
    EVENTS.append(("teacher-close", reason))
    _ORIGINAL_CLOSE_RUN(self, receipt, reason)


def install_hardware_fakes() -> None:
    """Keep real #273/#290/#267; fake only hardware and deterministic effect seams."""
    probe_reference_hardware.ReadOnlyCapabilitySession = base.FakeSession
    post_reset_capability_bridge.PostResetCapabilityHttpBridge = base.FakeBridge
    powered_session_authority.TrustedPoweredSessionFactory = base.FakePoweredFactory
    powered_session_authority.EstablishedPoweredSession = base.FakePoweredSession
    supervisor_state.FreshSupervisorStateReader = base.FakeSupervisorReader
    watchdog_liveness.EmergencyWatchdogLivenessGuard = base.FakeWatchdog
    high_level_ack.HighLevelAckResult = base.FakeAckResult
    high_level_ack.HighLevelAckDomain = base.FakeAckDomain
    safelink_precondition.LiveSafeLinkPrecondition = base.FakeSafeLink
    takeoff_transport.TrustedTakeoffTransport = RealDomainFakeTransport

    activation.TrustedPoweredSessionFactory = base.FakePoweredFactory
    activation.FreshSupervisorStateReader = base.FakeSupervisorReader
    activation.TrustedTakeoffTransport = RealDomainFakeTransport
    activation.CurrentProgramPreflightEvidence = base.FakeEvidence
    activation.make_cflib_stm_deck_power_cycle = (
        lambda _uri: lambda: EVENTS.append("power-cycle")
    )

    teacher_run_authorization.TrustedTeacherAuthorizer.close_run = _observed_close_run


def _teacher_peer(
    peer: socket.socket,
    mode: str,
    result: dict[str, object],
) -> None:
    try:
        with peer.makefile("r", encoding="utf-8", newline="\n") as reader:
            line = reader.readline()
        if not line:
            raise AssertionError("trusted teacher peer received no post-reset proposal")
        proposal = json.loads(line)
        result["proposal"] = proposal
        require(
            proposal.get("op") == "teacher-run-binding-proposal",
            "real #290 host-first proposal required",
        )
        require(
            proposal.get("executionAuthority") is False,
            "teacher proposal must remain non-authority data",
        )
        EVENTS.append(("teacher-proposal", proposal.get("connectionEpoch")))

        response = {
            "op": "teacher-run-decision-result",
            "requestId": proposal["requestId"],
            "challengeId": proposal["challengeId"],
            "profileId": proposal["profileId"],
            "astBinding": proposal["astBinding"],
            "connectionEpoch": proposal["connectionEpoch"],
            "approved": True,
            "executionAuthority": False,
        }
        if mode == "mismatch":
            response["connectionEpoch"] = "stale-epoch"
        elif mode != "approve":
            raise AssertionError("unsupported teacher test mode")

        peer.sendall(
            (json.dumps(response, separators=(",", ":"), sort_keys=True) + "\n").encode(
                "utf-8"
            )
        )
        peer.shutdown(socket.SHUT_WR)
        EVENTS.append(("teacher-reply", response["connectionEpoch"]))
    except BaseException as exc:
        result["error"] = exc


def run_host(*, teacher_mode: str | None) -> dict[str, object]:
    caller_host, caller_peer = socket.socketpair()
    browser_read, browser_write = os.pipe()
    teacher_peer = None
    teacher_worker = None
    teacher_result: dict[str, object] = {}
    teacher_fd = None

    if teacher_mode is not None:
        teacher_host, teacher_peer = socket.socketpair()
        teacher_fd = teacher_host.detach()
        teacher_worker = Thread(
            target=_teacher_peer,
            args=(teacher_peer, teacher_mode, teacher_result),
            daemon=True,
        )
        teacher_worker.start()

    argv = [
        str(HOST),
        "--uri",
        "radio://0/80/2M/E7E7E7E7E7",
        "--caller-fd",
        str(caller_host.detach()),
        "--browser-config-fd",
        str(browser_write),
    ]
    if teacher_fd is not None:
        argv += ["--teacher-fd", str(teacher_fd)]

    outcome: dict[str, object] = {}
    old_argv = sys.argv[:]

    def target() -> None:
        sys.argv = argv
        try:
            runpy.run_path(str(HOST), run_name="__main__")
        except Exception as exc:
            outcome["error"] = exc
        finally:
            sys.argv = old_argv

    worker = Thread(target=target, daemon=True)
    worker.start()

    with os.fdopen(browser_read, "r", encoding="utf-8") as stream:
        bootstrap = json.loads(stream.readline())
    require(bootstrap["executionAuthority"] is False, "browser bootstrap non-authority")
    require(bootstrap["token"] == "capability-token", "stable read-only bridge token")
    require(
        bootstrap["preflightResponderToken"] == "responder-token",
        "stable browser responder token",
    )

    request = {
        "op": "validate-run-context",
        "requestId": "request-1",
        "profileId": "activity-1",
        "astBinding": base.canonical_ast(),
        "connectionEpoch": "epoch-before",
    }
    caller_peer.sendall(
        (json.dumps(request, separators=(",", ":")) + "\n").encode("utf-8")
    )
    with caller_peer.makefile("r", encoding="utf-8") as reader:
        response = json.loads(reader.readline())
    require(
        response
        == {
            "executionAuthority": False,
            "ok": True,
            "requestId": "request-1",
        },
        "caller reply must remain diagnostic/non-authority",
    )

    # Teacher-enabled cases must let the host's activation worker consume the
    # staged binding and complete the one-shot proposal/decision exchange before
    # caller EOF can trigger host teardown. This is a causal test synchronization
    # point, not a delay: a missing proposal still fails the existing bounded join.
    if teacher_worker is not None:
        teacher_worker.join(timeout=1.0)
        require(not teacher_worker.is_alive(), "teacher peer did not finish one-shot exchange")
        require(
            "error" not in teacher_result,
            "teacher peer failed: " + repr(teacher_result.get("error")),
        )

    caller_peer.shutdown(socket.SHUT_WR)

    worker.join(timeout=3.0)
    require(not worker.is_alive(), "actual production host runner did not terminate")
    require(
        "error" not in outcome,
        "actual production host runner failed: " + repr(outcome.get("error")),
    )

    caller_peer.close()
    if teacher_peer is not None:
        teacher_peer.close()
    return {"bootstrap": bootstrap, "teacher": teacher_result}


def test_mismatched_real_teacher_reply_cannot_reach_effect() -> None:
    EVENTS.clear()
    install_hardware_fakes()
    result = run_host(teacher_mode="mismatch")

    proposal = result["teacher"].get("proposal")
    require(isinstance(proposal, dict), "real #290 proposal did not reach teacher peer")
    require(
        proposal["connectionEpoch"] == "epoch-after",
        "teacher proposal must use the rotated post-reset epoch",
    )
    require(
        ("bridge-install", "epoch-after") in EVENTS,
        "bridge replacement must complete before teacher proposal",
    )
    require(
        not any(
            isinstance(event, tuple) and event[0] == "transport-send"
            for event in EVENTS
        ),
        "mismatched teacher reply reached effect emission",
    )
    require(
        "watchdog-activate" not in EVENTS,
        "mismatched teacher reply reached watchdog/effect activation",
    )
    require(
        physical_execution_domain.PhysicalExecutionDomain().phase
        == physical_execution_domain.INACTIVE,
        "failed teacher decision must leave real #273 inactive after proven reset",
    )


def test_real_teacher_and_execution_authority_reach_causal_effect() -> None:
    EVENTS.clear()
    install_hardware_fakes()
    result = run_host(teacher_mode="approve")

    proposal = result["teacher"].get("proposal")
    require(isinstance(proposal, dict), "trusted teacher proposal missing")
    require(proposal["profileId"] == "activity-1", "teacher proposal profile changed")
    require(
        proposal["astBinding"] == base.canonical_ast(),
        "teacher proposal canonical AST changed",
    )
    require(
        proposal["connectionEpoch"] == "epoch-after",
        "teacher proposal must use rotated epoch",
    )

    required = [
        ("session-open", "epoch-before"),
        ("current-program", "epoch-before"),
        ("bridge-begin", "epoch-before"),
        ("session-close", "epoch-before"),
        "power-cycle",
        ("session-open", "epoch-after"),
        ("bridge-install", "epoch-after"),
        ("current-program", "epoch-after"),
        ("teacher-proposal", "epoch-after"),
        "watchdog-activate",
        ("transport-send", "epoch-after"),
    ]
    positions = []
    for event in required:
        require(event in EVENTS, "missing actual-host event: " + repr(event))
        positions.append(EVENTS.index(event))
    require(positions == sorted(positions), "actual-host causal ordering changed")

    send_index = EVENTS.index(("transport-send", "epoch-after"))
    post_reset_preflights = [
        index
        for index, event in enumerate(EVENTS[:send_index])
        if event == ("current-program", "epoch-after")
    ]
    require(
        len(post_reset_preflights) >= 2 and post_reset_preflights[-1] < send_index,
        "fresh host-local #278/#249 must run again immediately before emission",
    )
    require(
        physical_execution_domain.PhysicalExecutionDomain().phase
        == physical_execution_domain.FLYING,
        "real #273 domain did not record causal flying completion",
    )
    require("watchdog-stop" in EVENTS, "host teardown did not stop watchdog")
    require(
        any(
            isinstance(event, tuple) and event[0] == "teacher-close"
            for event in EVENTS
        ),
        "host teardown did not close the real #267 teacher receipt",
    )


def test_no_teacher_capability_remains_effect_free() -> None:
    EVENTS.clear()
    install_hardware_fakes()
    run_host(teacher_mode=None)
    require("power-cycle" not in EVENTS, "caller-only validation triggered reset")
    require("watchdog-activate" not in EVENTS, "caller-only validation activated watchdog")
    require(
        not any(
            isinstance(event, tuple) and event[0] == "transport-send"
            for event in EVENTS
        ),
        "caller-only validation emitted an effect",
    )


def main() -> int:
    # Keep the real process-wide domain reusable across these deterministic cases:
    # failed teacher binding leaves INACTIVE, then the positive case reaches FLYING.
    test_mismatched_real_teacher_reply_cannot_reach_effect()
    test_real_teacher_and_execution_authority_reach_causal_effect()
    test_no_teacher_capability_remains_effect_free()
    print(
        "PASS actual host authority path: real #273 + real #290/#267 socket authority, "
        "fresh post-reset provenance and causal effect; mismatch/caller-only fail closed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / "tools" / "ci"
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(CI))
sys.path.insert(0, str(PHYSICAL))

import physical_execution_domain  # noqa: E402
import test_physical_host_inflight_sequence as host  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def light_ast() -> str:
    return json.dumps(
        {
            "program": [
                {"height_m": 0.8, "kind": "takeoff"},
                {"color": "red", "kind": "set_light"},
                {"color": "off", "kind": "set_light"},
                {"kind": "land"},
            ],
            "semantics": "webeeblocks-ast-v1",
            "version": 1,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


class FakeColorTransport:
    def __init__(
        self,
        *,
        crazyflie: object,
        execution_domain: object,
        safelink_guard: object,
        teacher_authorization: object,
        powered_session: object,
        watchdog_guard: object,
        connection_epoch_reader,
    ) -> None:
        del safelink_guard
        require(powered_session.session is crazyflie, "Color LED uses exact powered session")
        require(
            execution_domain.phase == physical_execution_domain.FLYING,
            "Color LED transport is created only after causal takeoff",
        )
        require(
            connection_epoch_reader() == powered_session.connection_epoch,
            "Color LED transport binds exact active epoch",
        )
        self.teacher_binding = teacher_authorization.binding
        self.bound_connection_epoch = powered_session.connection_epoch
        self.execution_domain = execution_domain
        self._crazyflie = crazyflie
        self._watchdog = watchdog_guard

    def _read_current_binding(self):
        raise AssertionError("host-local Color LED provenance override is required")

    def send_color(self, *, color):
        require(color in {"off", "red", "green", "blue", "yellow", "white"}, "bounded palette")
        require(self._watchdog.active, "same-session watchdog remains live")
        binding = self._read_current_binding()
        require(binding == self.teacher_binding, "fresh #249 matches exact light run")
        require(
            self.execution_domain.phase == physical_execution_domain.FLYING,
            "Color LED effect starts only from established flying",
        )
        host.base.EVENTS.append(("inflight-light", color, binding.connection_epoch))
        return SimpleNamespace(accepted=True, status=0, color=color)


def install_fakes() -> None:
    host.install_fakes()
    host.base.activation.TrustedBottomColorLedTransport = FakeColorTransport


def run_with_color_substitution(*, steps: int):
    original = host.send_line

    def send_line_with_color(sock, payload):
        outgoing = dict(payload)
        if outgoing.get("requestId") == "substitute-1":
            outgoing.update(
                {
                    "color": "blue",
                    "wrgb8888": 0x000000FF,
                    "parameter": "colorLedBot.wrgb8888",
                    "paramId": 0x1234,
                    "completion": True,
                }
            )
        original(sock, outgoing)

    host.send_line = send_line_with_color
    try:
        return host.run_host_sequence(light_ast(), steps=steps)
    finally:
        host.send_line = original


def test_actual_host_consumes_exact_light_program_parameter_free() -> None:
    host.base.EVENTS.clear()
    install_fakes()
    replies = run_with_color_substitution(steps=3)

    require(replies[0]["ok"] is True, "run-context validation remains diagnostic")
    require(replies[1]["ok"] is False, "caller-selected Color LED fields must be rejected")
    require(replies[1]["executionAuthority"] is False, "rejected Color LED substitution mints no authority")
    require(replies[2] == {"executionAuthority": False, "ok": True, "requestId": "step-1"}, "exact red effect executes")
    require(replies[3] == {"executionAuthority": False, "ok": True, "requestId": "step-2"}, "exact off effect executes")
    require(replies[4] == {"executionAuthority": False, "ok": True, "requestId": "step-3"}, "terminal landing follows light effects")

    light_events = [
        event
        for event in host.base.EVENTS
        if isinstance(event, tuple) and event[0] == "inflight-light"
    ]
    land_events = [
        event
        for event in host.base.EVENTS
        if isinstance(event, tuple) and event[0] == "terminal-land"
    ]
    require(
        light_events == [
            ("inflight-light", "red", "epoch-after"),
            ("inflight-light", "off", "epoch-after"),
        ],
        "host must derive both light colors only from the exact canonical AST",
    )
    require(
        land_events == [("terminal-land", "epoch-after")],
        "terminal landing follows exact completed light effects once",
    )
    require(
        not any(
            isinstance(event, tuple) and event[0] == "yaw-open"
            for event in host.base.EVENTS
        ),
        "light-only program must not manufacture a yaw-observer dependency",
    )
    takeoff_index = host.base.EVENTS.index(("transport-send", "epoch-after"))
    red_index = host.base.EVENTS.index(light_events[0])
    off_index = host.base.EVENTS.index(light_events[1])
    land_index = host.base.EVENTS.index(land_events[0])
    require(
        takeoff_index < red_index < off_index < land_index,
        "takeoff, exact light effects and terminal landing preserve canonical order",
    )
    current_program_events = [
        event
        for event in host.base.EVENTS
        if event == ("current-program", "epoch-after")
    ]
    require(
        len(current_program_events) >= 4,
        "each Color LED effect and later landing re-establish current-program provenance",
    )


def test_rejected_light_effect_remains_exact_next_step() -> None:
    host.base.EVENTS.clear()
    install_fakes()
    original = FakeColorTransport.send_color
    attempts = {"count": 0}

    def reject_once(self, *, color):
        attempts["count"] += 1
        if attempts["count"] == 1:
            binding = self._read_current_binding()
            host.base.EVENTS.append(
                ("inflight-light-rejected", color, binding.connection_epoch)
            )
            return SimpleNamespace(accepted=False, status=22, color=color)
        return original(self, color=color)

    FakeColorTransport.send_color = reject_once
    try:
        replies = host.run_host_sequence(light_ast(), steps=4)
    finally:
        FakeColorTransport.send_color = original

    require(replies[2]["ok"] is False, "definitive light rejection is surfaced fail-closed")
    require(replies[3]["ok"] is True, "next parameter-free request retries the same exact light")
    require(replies[4]["ok"] is True and replies[5]["ok"] is True, "off and landing follow accepted red")
    rejected = [
        event
        for event in host.base.EVENTS
        if isinstance(event, tuple) and event[0] == "inflight-light-rejected"
    ]
    accepted = [
        event
        for event in host.base.EVENTS
        if isinstance(event, tuple) and event[0] == "inflight-light"
    ]
    require(
        rejected == [("inflight-light-rejected", "red", "epoch-after")],
        "rejection must be the exact first red effect",
    )
    require(
        [event[1] for event in accepted] == ["red", "off"],
        "rejected red effect cannot be skipped or replaced",
    )


def test_ambiguous_light_effect_makes_host_sequence_terminal() -> None:
    host.base.EVENTS.clear()
    install_fakes()
    original = FakeColorTransport.send_color
    attempts = {"count": 0}

    def ambiguous(self, *, color):
        attempts["count"] += 1
        binding = self._read_current_binding()
        host.base.EVENTS.append(
            ("inflight-light-ambiguous", color, binding.connection_epoch)
        )
        # Drive the exact process-wide lifecycle through the same emitted-but-
        # unresolved boundary as production. Leaving the transaction by
        # exception must make the domain recovery-required before the host
        # decides whether the sequence claim is retryable or terminal.
        with self.execution_domain.effect_transaction(lambda: None) as effect:
            effect.mark_emitted()
            raise RuntimeError("injected ambiguous Color LED effect")

    FakeColorTransport.send_color = ambiguous
    try:
        replies = host.run_host_sequence(light_ast(), steps=2)
    finally:
        FakeColorTransport.send_color = original

    require(
        replies[2]["ok"] is False and replies[3]["ok"] is False,
        "ambiguous light effect and every later step fail closed",
    )
    require(
        attempts["count"] == 1,
        "terminal ambiguity must not retry the same Color LED effect",
    )
    require(
        host.base.activation._ACTIVE_RUN.execution_domain.phase
        == physical_execution_domain.RECOVERY_REQUIRED,
        "emitted unresolved light must leave the exact process-wide domain recovery-required",
    )
    ambiguous_events = [
        event
        for event in host.base.EVENTS
        if isinstance(event, tuple) and event[0] == "inflight-light-ambiguous"
    ]
    require(
        ambiguous_events == [("inflight-light-ambiguous", "red", "epoch-after")],
        "exactly one ambiguous red effect must reach the transport boundary",
    )
    require(
        not any(
            isinstance(event, tuple) and event[0] == "terminal-land"
            for event in host.base.EVENTS
        ),
        "ambiguous light effect cannot advance into landing",
    )


def main() -> int:
    test_actual_host_consumes_exact_light_program_parameter_free()
    test_rejected_light_effect_remains_exact_next_step()
    test_ambiguous_light_effect_makes_host_sequence_terminal()
    print(
        "PASS actual physical host bottom Color LED sequencing: exact teacher-bound colors execute parameter-free in order, "
        "caller-selected color/value/parameter/id/completion fields are rejected, and rejected or ambiguous effects cannot skip the sequence"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

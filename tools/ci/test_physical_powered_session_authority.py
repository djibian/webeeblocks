#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
sys.path.insert(0, str(PHYSICAL))

import powered_session_authority as authority
import watchdog_liveness as watchdog


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except authority.PoweredSessionAuthorityError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError(
        f"expected PoweredSessionAuthorityError containing {pattern!r}"
    )


def descriptor(
    *,
    connected: bool = True,
    execution_authority: bool = False,
    model: str | None = "crazyflie-2.1",
    model_evidence: str = "verified",
    self_test: bool = True,
    protocol: int = 12,
):
    return {
        "connected": connected,
        "executionAuthority": execution_authority,
        "identity": {
            "family": "crazyflie",
            "model": model,
            "modelEvidence": model_evidence,
        },
        "evidence": {
            "systemSelfTestPassed": self_test,
            "protocolVersion": protocol,
        },
    }


class Fixture:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.safe = True
        self.epoch = "epoch-after-reset"
        self.capabilities = descriptor()
        self.preflight_ok = True
        self.supervisor = SimpleNamespace(blocking_fault=False)
        self.reset_error: Exception | None = None
        self.open_error: Exception | None = None
        self.preflight_error: Exception | None = None
        self.supervisor_error: Exception | None = None
        self.close_error: Exception | None = None
        self.session = object()

    def factory(self):
        def safe_gate():
            self.events.append("safe")
            return self.safe

        def invalidate():
            self.events.append("invalidate")

        def reset():
            self.events.append("reset")
            if self.reset_error is not None:
                raise self.reset_error

        def open_session():
            self.events.append("open")
            if self.open_error is not None:
                raise self.open_error
            return self.session

        def close_session(session):
            require(session is self.session, "cleanup exact session")
            self.events.append("close")
            if self.close_error is not None:
                raise self.close_error

        def read_epoch(session):
            require(session is self.session, "epoch exact session")
            self.events.append("epoch")
            return self.epoch

        def read_capabilities(session):
            require(session is self.session, "capabilities exact session")
            self.events.append("capabilities")
            return self.capabilities

        def assert_preflight(session, epoch):
            require(session is self.session, "preflight exact session")
            require(epoch == self.epoch, "preflight exact epoch")
            self.events.append("preflight")
            if self.preflight_error is not None:
                raise self.preflight_error
            return self.preflight_ok

        def fresh_supervisor(session, epoch):
            require(session is self.session, "supervisor exact session")
            require(epoch == self.epoch, "supervisor exact epoch")
            self.events.append("supervisor")
            if self.supervisor_error is not None:
                raise self.supervisor_error
            return self.supervisor

        def identity():
            self.events.append("identity")
            return "powered-session-1"

        return authority.TrustedPoweredSessionFactory(
            require_flight_known_inactive=safe_gate,
            invalidate_prior_evidence=invalidate,
            stm_deck_power_cycle=reset,
            open_post_reset_session=open_session,
            close_post_reset_session=close_session,
            read_connection_epoch=read_epoch,
            read_capabilities=read_capabilities,
            assert_bound_preflight=assert_preflight,
            read_fresh_supervisor=fresh_supervisor,
            identity_factory=identity,
        )


def test_direct_construction_cannot_mint_fresh_authority() -> None:
    expect_error(
        lambda: authority.EphemeralPoweredSessionWatchdogAuthority("forged"),
        "only be minted after trusted reset proof",
    )
    require(
        not hasattr(authority.EphemeralPoweredSessionWatchdogAuthority, "restore"),
        "authority must expose no restore API",
    )
    require(
        not hasattr(authority.EphemeralPoweredSessionWatchdogAuthority, "from_identity"),
        "serialized identity must not mint authority",
    )


def test_factory_establishes_exact_reset_postconditions_before_minting() -> None:
    f = Fixture()
    established = f.factory().establish(previous_connection_epoch="epoch-before")
    require(established.session is f.session, "factory returns exact live session")
    require(established.connection_epoch == f.epoch, "factory returns exact new epoch")
    lifecycle = established.watchdog_authority
    require(
        isinstance(lifecycle, watchdog.PoweredSessionWatchdogAuthority),
        "concrete lifecycle satisfies #262 authority contract",
    )
    require(lifecycle.identity == "powered-session-1", "trusted identity")
    require(lifecycle.state == "new", "factory mints only fresh new state")
    lifecycle.require_fresh_reset_proof()
    require(
        f.events == [
            "safe",
            "invalidate",
            "reset",
            "open",
            "epoch",
            "capabilities",
            "preflight",
            "supervisor",
            "identity",
        ],
        f"unexpected establishment order: {f.events}",
    )


def test_authority_reset_proof_is_one_shot_and_terminal_is_latching() -> None:
    lifecycle = Fixture().factory().establish().watchdog_authority
    lifecycle.begin_activation()
    require(lifecycle.state == "activating", "activation atomically consumes freshness")
    expect_error(
        lifecycle.require_fresh_reset_proof,
        "fresh STM+deck reset proof is unavailable",
    )
    lifecycle.mark_active()
    require(lifecycle.state == "active", "active follows activating only")
    lifecycle.mark_terminal("lost watchdog certainty")
    require(lifecycle.state == "terminal", "terminal state")
    require(
        lifecycle.terminal_reason == "lost watchdog certainty",
        "first terminal reason durable in lifecycle",
    )
    lifecycle.mark_terminal("later reason")
    require(
        lifecycle.terminal_reason == "lost watchdog certainty",
        "terminal transition is idempotent and never recovers",
    )
    expect_error(
        lifecycle.require_fresh_reset_proof,
        "fresh STM+deck reset proof is unavailable",
    )


def test_unsafe_or_unknown_flight_state_prevents_reset_effect() -> None:
    f = Fixture()
    f.safe = False
    expect_error(
        f.factory().establish,
        "physical flight to be explicitly known inactive",
    )
    require(f.events == ["safe"], "unsafe state emits no invalidation or reset")


def test_prior_evidence_is_invalidated_before_ambiguous_reset() -> None:
    f = Fixture()
    f.reset_error = RuntimeError("radio ambiguity")
    expect_error(
        f.factory().establish,
        "power-cycle transaction failed or is ambiguous",
    )
    require(
        f.events == ["safe", "invalidate", "reset"],
        "ambiguous reset cannot leave old evidence reusable or open a new session",
    )


def test_transport_success_alone_never_mints_authority() -> None:
    cases = [
        ("same epoch", lambda f: setattr(f, "epoch", "epoch-before"),
         "reused the previous connection epoch"),
        ("wrong model", lambda f: setattr(f, "capabilities", descriptor(model=None)),
         "exact Crazyflie 2.1 identity is unproven"),
        ("failed self test", lambda f: setattr(f, "capabilities", descriptor(self_test=False)),
         "self-test did not pass"),
        ("old protocol", lambda f: setattr(f, "capabilities", descriptor(protocol=11)),
         "protocol is too old"),
        ("preflight false", lambda f: setattr(f, "preflight_ok", False),
         "preflight was not positively established"),
        ("supervisor fault", lambda f: setattr(
            f, "supervisor", SimpleNamespace(blocking_fault=True)
         ), "supervisor safety state is unavailable or blocking"),
    ]
    for label, mutate, message in cases:
        f = Fixture()
        mutate(f)
        expect_error(
            lambda f=f: f.factory().establish(
                previous_connection_epoch="epoch-before"
            ),
            message,
        )
        require("identity" not in f.events, f"{label}: authority identity minted too early")
        require(f.events[-1] == "close", f"{label}: failed post-reset session must close")


def test_callback_failures_fail_closed_and_cleanup_new_session() -> None:
    f = Fixture()
    f.preflight_error = RuntimeError("binding unavailable")
    expect_error(
        f.factory().establish,
        "preflight was not re-established",
    )
    require(f.events[-1] == "close", "failed preflight closes post-reset session")

    f = Fixture()
    f.supervisor_error = RuntimeError("freshness timeout")
    expect_error(
        f.factory().establish,
        "supervisor safety observation failed",
    )
    require(f.events[-1] == "close", "failed supervisor read closes post-reset session")


def test_explicit_cflib_power_cycle_helper_is_lazy_and_uri_bound() -> None:
    calls: list[object] = []

    class FakePowerSwitch:
        def __init__(self, uri: str) -> None:
            calls.append(("construct", uri))

        def stm_power_cycle(self) -> None:
            calls.append("cycle")

    reset = authority.make_cflib_stm_deck_power_cycle(
        "radio://0/80/2M/E7E7E7E7E7",
        power_switch_factory=FakePowerSwitch,
    )
    require(calls == [], "helper construction must not power-cycle hardware")
    reset()
    require(
        calls == [
            ("construct", "radio://0/80/2M/E7E7E7E7E7"),
            "cycle",
        ],
        "explicit reset delegates once to cflib PowerSwitch STM+deck cycle",
    )
    expect_error(
        lambda: authority.make_cflib_stm_deck_power_cycle("usb://not-radio"),
        "explicit Crazyradio radio:// URI",
    )


def main() -> int:
    test_direct_construction_cannot_mint_fresh_authority()
    test_factory_establishes_exact_reset_postconditions_before_minting()
    test_authority_reset_proof_is_one_shot_and_terminal_is_latching()
    test_unsafe_or_unknown_flight_state_prevents_reset_effect()
    test_prior_evidence_is_invalidated_before_ambiguous_reset()
    test_transport_success_alone_never_mints_authority()
    test_callback_failures_fail_closed_and_cleanup_new_session()
    test_explicit_cflib_power_cycle_helper_is_lazy_and_uri_bound()
    print(
        "PASS trusted powered-session authority requires explicit reset plus fresh postconditions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

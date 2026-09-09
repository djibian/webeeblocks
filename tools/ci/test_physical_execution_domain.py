#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from threading import Event, Thread
import sys

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "physical" / "physical_execution_domain.py"
sys.path.insert(0, str(MODULE_PATH.parent))
import physical_execution_domain as domain  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except domain.PhysicalExecutionDomainError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError(
        f"expected PhysicalExecutionDomainError containing {pattern!r}"
    )


def reset_ok(
    execution: domain.PhysicalExecutionDomain,
    token: object | None = None,
):
    marker = token if token is not None else object()
    result = execution.run_reset_establishment(lambda: marker)
    require(result is marker, "reset wrapper must preserve established-session result")
    require(
        execution.phase == domain.INACTIVE,
        "successful #266 reset establishes inactive",
    )
    return marker


def test_new_process_requires_reset_establishment() -> None:
    execution = domain.PhysicalExecutionDomain()
    require(
        execution.phase == domain.RECOVERY_REQUIRED,
        "fresh process must not infer reusable run authority",
    )
    expect_error(
        lambda: execution.effect_transaction(lambda: None).__enter__(),
        "not eligible",
    )
    reset_ok(execution)


def test_reset_failure_is_fail_closed() -> None:
    execution = domain.PhysicalExecutionDomain()

    def fail():
        raise RuntimeError("ambiguous reset")

    expect_error(
        lambda: execution.run_reset_establishment(fail),
        "failed or is ambiguous",
    )
    require(
        execution.phase == domain.RECOVERY_REQUIRED,
        "failed reset must not mint effect eligibility",
    )
    expect_error(
        lambda: execution.run_reset_establishment(lambda: None),
        "returned no established session",
    )
    require(
        execution.phase == domain.RECOVERY_REQUIRED,
        "empty reset result fails closed",
    )


def test_preconditions_run_inside_exclusion_and_pre_effect_failure_is_neutral() -> None:
    execution = domain.PhysicalExecutionDomain()
    reset_ok(execution)
    calls: list[str] = []

    def first():
        calls.append("first")
        require(
            execution.phase == domain.INACTIVE,
            "precondition sees stable prior phase",
        )

    def fail():
        calls.append("fail")
        raise RuntimeError("teacher binding mismatch")

    transaction = execution.effect_transaction(
        first,
        fail,
        lambda: calls.append("late"),
    )
    try:
        with transaction:
            raise AssertionError("failing precondition must prevent effect body")
    except RuntimeError as exc:
        require(
            "teacher binding mismatch" in str(exc),
            "original assertion failure preserved",
        )
    require(calls == ["first", "fail"], "preconditions stop at first failure")
    require(
        execution.phase == domain.INACTIVE,
        "pre-effect failure preserves prior phase",
    )


def test_unresolved_emission_requires_recovery() -> None:
    execution = domain.PhysicalExecutionDomain()
    reset_ok(execution)
    with execution.effect_transaction(lambda: None) as effect:
        effect.mark_emitted()
        require(
            execution.phase == domain.EFFECT_UNRESOLVED,
            "emission immediately blocks reset and later effects",
        )
    require(
        execution.phase == domain.RECOVERY_REQUIRED,
        "unresolved emitted outcome becomes recovery-required",
    )
    expect_error(
        lambda: execution.effect_transaction(lambda: None).__enter__(),
        "not eligible",
    )
    reset_ok(execution)


def test_definitive_rejection_restores_exact_prior_phase() -> None:
    execution = domain.PhysicalExecutionDomain()
    reset_ok(execution)
    with execution.effect_transaction(lambda: None) as effect:
        effect.mark_emitted()
        effect.mark_definitive_rejection()
    require(
        execution.phase == domain.INACTIVE,
        "rejected takeoff preserves inactive",
    )

    with execution.effect_transaction(lambda: None) as effect:
        effect.mark_emitted()
        takeoff_permit = effect.mark_accepted()
    execution.complete_accepted_effect(
        takeoff_permit,
        domain.FLYING,
        lambda: True,
    )
    require(
        execution.phase == domain.FLYING,
        "accepted takeoff completion establishes flying",
    )

    with execution.effect_transaction(lambda: None) as effect:
        effect.mark_emitted()
        effect.mark_definitive_rejection()
    require(
        execution.phase == domain.FLYING,
        "rejected in-flight command preserves flying",
    )

    # Keep the process-wide fixture in a stable non-flying phase for the next
    # independent regression without bypassing the public lifecycle.
    with execution.effect_transaction(lambda: None) as landing:
        landing.mark_emitted()
        landing_permit = landing.mark_accepted()
    execution.complete_accepted_effect(
        landing_permit,
        domain.INACTIVE,
        lambda: True,
    )


def test_positive_ack_requires_fresh_completion_before_next_transition() -> None:
    execution = domain.PhysicalExecutionDomain()
    reset_ok(execution)
    with execution.effect_transaction(lambda: None) as effect:
        effect.mark_emitted()
        permit = effect.mark_accepted()

    require(
        execution.phase == domain.AWAITING_COMPLETION,
        "positive acknowledgement alone is not completion evidence",
    )
    expect_error(
        lambda: execution.effect_transaction(lambda: None).__enter__(),
        "not eligible",
    )
    expect_error(
        lambda: execution.run_reset_establishment(lambda: object()),
        "blocked",
    )
    execution.complete_accepted_effect(
        permit,
        domain.FLYING,
        lambda: True,
    )
    require(
        execution.phase == domain.FLYING,
        "fresh trajectory completion can establish flying",
    )
    expect_error(
        lambda: execution.run_reset_establishment(lambda: object()),
        "blocked",
    )

    with execution.effect_transaction(lambda: None) as landing:
        landing.mark_emitted()
        landing_permit = landing.mark_accepted()
    execution.complete_accepted_effect(
        landing_permit,
        domain.INACTIVE,
        lambda: True,
    )
    require(
        execution.phase == domain.INACTIVE,
        "fresh #264 landing completion can establish inactive",
    )
    reset_ok(execution)


def test_completion_requires_exact_pending_effect_permit() -> None:
    execution = domain.PhysicalExecutionDomain()
    reset_ok(execution)
    with execution.effect_transaction(lambda: None) as effect:
        effect.mark_emitted()
        permit = effect.mark_accepted()

    # This is the exact old bypass: arbitrary proof with no provenance for the
    # accepted effect must not restore ordinary motion eligibility.
    expect_error(
        lambda: execution.complete_accepted_effect(
            object(),
            domain.FLYING,
            lambda: True,
        ),
        "completion permit",
    )
    require(
        execution.phase == domain.AWAITING_COMPLETION,
        "forged completion leaves the real accepted effect pending",
    )

    execution.complete_accepted_effect(
        permit,
        domain.FLYING,
        lambda: True,
    )
    require(
        execution.phase == domain.FLYING,
        "exact accepted-effect permit can be paired with trusted fresh proof",
    )

    with execution.effect_transaction(lambda: None) as second:
        second.mark_emitted()
        current_permit = second.mark_accepted()

    expect_error(
        lambda: execution.complete_accepted_effect(
            permit,
            domain.FLYING,
            lambda: True,
        ),
        "does not match",
    )
    require(
        execution.phase == domain.AWAITING_COMPLETION,
        "consumed stale permit cannot complete a newer effect",
    )
    execution.complete_accepted_effect(
        current_permit,
        domain.FLYING,
        lambda: True,
    )

    with execution.effect_transaction(lambda: None) as landing:
        landing.mark_emitted()
        landing_permit = landing.mark_accepted()
    execution.complete_accepted_effect(
        landing_permit,
        domain.INACTIVE,
        lambda: True,
    )


def test_completion_uncertainty_forces_recovery() -> None:
    execution = domain.PhysicalExecutionDomain()
    reset_ok(execution)
    with execution.effect_transaction(lambda: None) as effect:
        effect.mark_emitted()
        permit = effect.mark_accepted()
    expect_error(
        lambda: execution.complete_accepted_effect(
            permit,
            domain.FLYING,
            lambda: False,
        ),
        "not positively established",
    )
    require(
        execution.phase == domain.RECOVERY_REQUIRED,
        "negative completion proof cannot preserve ordinary run authority",
    )
    reset_ok(execution)

    with execution.effect_transaction(lambda: None) as effect:
        effect.mark_emitted()
        permit = effect.mark_accepted()

    def fail_proof():
        raise RuntimeError("fresh supervisor poisoned")

    expect_error(
        lambda: execution.complete_accepted_effect(
            permit,
            domain.INACTIVE,
            fail_proof,
        ),
        "failed or is ambiguous",
    )
    require(
        execution.phase == domain.RECOVERY_REQUIRED,
        "ambiguous completion requires recovery",
    )
    reset_ok(execution)


def test_reset_and_effect_boundary_are_mutually_exclusive() -> None:
    execution = domain.PhysicalExecutionDomain()
    reset_ok(execution)
    reset_entered = Event()
    release_reset = Event()
    effect_entered = Event()
    failures: list[BaseException] = []

    def held_reset():
        try:
            def establish():
                reset_entered.set()
                require(
                    release_reset.wait(1.0),
                    "test reset release signal",
                )
                return object()

            execution.run_reset_establishment(establish)
        except BaseException as exc:
            failures.append(exc)

    def effect_attempt():
        try:
            with execution.effect_transaction(lambda: None):
                effect_entered.set()
        except BaseException as exc:
            failures.append(exc)

    reset_thread = Thread(target=held_reset)
    reset_thread.start()
    require(
        reset_entered.wait(1.0),
        "reset transaction entered exclusion",
    )
    effect_thread = Thread(target=effect_attempt)
    effect_thread.start()
    require(
        not effect_entered.wait(0.05),
        "effect must not enter while reset establishment owns exclusion",
    )
    release_reset.set()
    reset_thread.join(1.0)
    effect_thread.join(1.0)
    require(
        not reset_thread.is_alive() and not effect_thread.is_alive(),
        "threads completed",
    )
    require(not failures, f"concurrency fixture failed: {failures!r}")
    require(
        effect_entered.is_set(),
        "effect may enter only after reset exclusion releases",
    )


def test_independent_handles_share_process_wide_exclusion() -> None:
    effect_execution = domain.PhysicalExecutionDomain()
    reset_execution = domain.PhysicalExecutionDomain()
    reset_ok(effect_execution)
    effect_entered = Event()
    release_effect = Event()
    reset_entered = Event()
    failures: list[BaseException] = []

    def held_effect():
        try:
            with effect_execution.effect_transaction(lambda: None):
                effect_entered.set()
                require(
                    release_effect.wait(1.0),
                    "test effect release signal",
                )
        except BaseException as exc:
            failures.append(exc)

    def reset_attempt():
        try:
            def establish():
                reset_entered.set()
                return object()

            reset_execution.run_reset_establishment(establish)
        except BaseException as exc:
            failures.append(exc)

    effect_thread = Thread(target=held_effect)
    effect_thread.start()
    require(
        effect_entered.wait(1.0),
        "effect transaction entered process-wide exclusion",
    )
    reset_thread = Thread(target=reset_attempt)
    reset_thread.start()
    require(
        not reset_entered.wait(0.05),
        "independent reset handle must not enter while another handle owns effect exclusion",
    )
    release_effect.set()
    effect_thread.join(1.0)
    reset_thread.join(1.0)
    require(
        not effect_thread.is_alive() and not reset_thread.is_alive(),
        "independent-handle threads completed",
    )
    require(not failures, f"independent-handle concurrency fixture failed: {failures!r}")
    require(
        reset_entered.is_set(),
        "reset may enter only after the independent effect handle releases exclusion",
    )
    require(
        effect_execution.phase == domain.INACTIVE
        and reset_execution.phase == domain.INACTIVE,
        "all handles must observe one shared stable process phase",
    )


def test_no_physical_effect_or_browser_surface() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "import cflib",
        "CRTPPacket",
        "HighLevelCommander(",
        ".send_packet(",
        "add_port_callback(",
        "expected_" + "reply",
        "send_arming_request",
        "send_emergency_stop",
        "http.server",
    ):
        require(
            forbidden not in source,
            "execution exclusion contains physical/browser effect surface: "
            + forbidden,
        )


def main() -> int:
    test_new_process_requires_reset_establishment()
    test_reset_failure_is_fail_closed()
    test_preconditions_run_inside_exclusion_and_pre_effect_failure_is_neutral()
    test_unresolved_emission_requires_recovery()
    test_definitive_rejection_restores_exact_prior_phase()
    test_positive_ack_requires_fresh_completion_before_next_transition()
    test_completion_requires_exact_pending_effect_permit()
    test_completion_uncertainty_forces_recovery()
    test_reset_and_effect_boundary_are_mutually_exclusive()
    test_independent_handles_share_process_wide_exclusion()
    test_no_physical_effect_or_browser_surface()
    print(
        "PASS trusted physical reset/effect exclusion is process-local, fail-closed "
        "and emits no physical effect"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

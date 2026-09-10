#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "physical" / "teacher_run_authorization.py"
spec = importlib.util.spec_from_file_location(
    "webeeblocks_teacher_run_authorization",
    MODULE_PATH,
)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load teacher run authorization")
auth = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = auth
spec.loader.exec_module(auth)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except auth.TeacherRunAuthorizationError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError(
        f"expected TeacherRunAuthorizationError containing {pattern!r}"
    )


def binding(
    epoch: str = "epoch-a",
    ast: str = "ast-123",
    profile: str = "activity-1",
):
    return auth.PhysicalRunBinding(
        profile_id=profile,
        ast_binding=ast,
        connection_epoch=epoch,
    )


def test_exact_binding_authorizes_one_run() -> None:
    gate = auth.TrustedTeacherAuthorizer()
    seen = []

    def approve(exact):
        seen.append(exact)
        return True

    exact = binding()
    receipt = gate.authorize_run(exact, approve)
    require(seen == [exact], "teacher decision sees exact proposed run binding")
    require(receipt.active, "approved run is active")
    require(gate.has_active_run, "host gate exposes active-run state")
    require(receipt.binding == exact, "receipt preserves exact binding")
    require(
        isinstance(receipt.run_id, str) and len(receipt.run_id) >= 20,
        "run id is opaque",
    )

    for _ in range(3):
        receipt.assert_effect_binding(
            profile_id=exact.profile_id,
            ast_binding=exact.ast_binding,
            connection_epoch=exact.connection_epoch,
        )
    require(
        receipt.active,
        "multiple exact effect-boundary checks preserve one run authority",
    )


def test_denial_non_boolean_and_decision_failure_fail_closed() -> None:
    for decision in (
        lambda _b: False,
        lambda _b: None,
        lambda _b: 1,
        lambda _b: "yes",
    ):
        gate = auth.TrustedTeacherAuthorizer()
        expect_error(
            lambda d=decision, g=gate: g.authorize_run(binding(), d),
            "did not explicitly authorize",
        )
        require(
            not gate.has_active_run,
            "failed decision creates no run authority",
        )

    gate = auth.TrustedTeacherAuthorizer()

    def broken(_binding):
        raise RuntimeError("UI channel failed")

    expect_error(
        lambda: gate.authorize_run(binding(), broken),
        "teacher decision failed",
    )
    require(not gate.has_active_run, "decision exception creates no authority")


def test_changed_binding_invalidates_permanently() -> None:
    for field, kwargs in (
        (
            "profile",
            {
                "profile_id": "activity-2",
                "ast_binding": "ast-123",
                "connection_epoch": "epoch-a",
            },
        ),
        (
            "ast",
            {
                "profile_id": "activity-1",
                "ast_binding": "ast-456",
                "connection_epoch": "epoch-a",
            },
        ),
        (
            "epoch",
            {
                "profile_id": "activity-1",
                "ast_binding": "ast-123",
                "connection_epoch": "epoch-b",
            },
        ),
    ):
        gate = auth.TrustedTeacherAuthorizer()
        receipt = gate.authorize_run(binding(), lambda _b: True)
        expect_error(
            lambda kw=kwargs, r=receipt: r.assert_effect_binding(**kw),
            "binding changed",
        )
        require(not receipt.active, f"{field} mismatch invalidates run")
        require(
            receipt.invalid_reason == "physical run binding changed",
            "mismatch reason is durable in receipt",
        )
        expect_error(
            lambda r=receipt: r.assert_effect_binding(
                profile_id="activity-1",
                ast_binding="ast-123",
                connection_epoch="epoch-a",
            ),
            "unavailable",
        )


def test_one_active_run_and_explicit_close() -> None:
    gate = auth.TrustedTeacherAuthorizer()
    first = gate.authorize_run(binding(), lambda _b: True)
    expect_error(
        lambda: gate.authorize_run(
            binding(epoch="epoch-b"),
            lambda _b: True,
        ),
        "already active",
    )
    gate.close_run(first, "physical run completed")
    require(
        not first.active and not gate.has_active_run,
        "close consumes run authority",
    )

    second = gate.authorize_run(
        binding(epoch="epoch-b"),
        lambda _b: True,
    )
    require(second.run_id != first.run_id, "new run requires a distinct receipt")
    expect_error(
        lambda: gate.close_run(first, "stale close"),
        "does not belong",
    )
    gate.close_run(second, "physical run cancelled")


def test_receipt_cannot_be_minted_or_restored_from_serialized_identity() -> None:
    exact = binding()
    expect_error(
        lambda: auth.TeacherRunAuthorization(
            exact,
            "forged",
            _mint_key=object(),
        ),
        "may only be minted",
    )
    source = MODULE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "def restore",
        "def import_authorization",
        "from_json",
        "requests.",
        "http.server",
        "HighLevelCommander",
        "send_setpoint",
        "send_arming_request",
        "send_emergency_stop",
        "stm_power_cycle",
    ):
        require(
            forbidden not in source,
            f"teacher gate contains forbidden authority surface: {forbidden}",
        )


def test_binding_validation() -> None:
    for kwargs in (
        {
            "profile_id": "",
            "ast_binding": "a",
            "connection_epoch": "e",
        },
        {
            "profile_id": "p",
            "ast_binding": " ",
            "connection_epoch": "e",
        },
        {
            "profile_id": "p",
            "ast_binding": "a",
            "connection_epoch": " e ",
        },
    ):
        expect_error(
            lambda kw=kwargs: auth.PhysicalRunBinding(**kw),
            "physical run",
        )


def _run_contract(path: str, marker: str, failure: str) -> None:
    result = subprocess.run(
        [sys.executable, path],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise AssertionError(failure)
    require(marker in result.stdout, marker + " PASS marker")


def test_trusted_teacher_decision_channel_contract() -> None:
    _run_contract(
        "tools/ci/test_teacher_decision_channel.py",
        "PASS trusted teacher decision channel",
        "trusted teacher decision channel regression failed",
    )


def test_post_reset_teacher_binding_contract() -> None:
    _run_contract(
        "tools/ci/test_post_reset_teacher_decision.py",
        "PASS post-reset teacher binding bootstrap",
        "post-reset teacher binding regression failed",
    )


def test_post_reset_capability_bridge_contract() -> None:
    _run_contract(
        "tools/ci/test_post_reset_capability_bridge.py",
        "PASS post-reset capability bridge",
        "post-reset capability bridge regression failed",
    )


def main() -> int:
    test_exact_binding_authorizes_one_run()
    test_denial_non_boolean_and_decision_failure_fail_closed()
    test_changed_binding_invalidates_permanently()
    test_one_active_run_and_explicit_close()
    test_receipt_cannot_be_minted_or_restored_from_serialized_identity()
    test_binding_validation()
    test_trusted_teacher_decision_channel_contract()
    test_post_reset_teacher_binding_contract()
    test_post_reset_capability_bridge_contract()
    print(
        "PASS host-only teacher run authorization: one explicit decision binds one exact "
        "profile/AST/epoch run and every effect boundary re-checks it"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
import copy
import json
import unittest

from recovery_contract import (
    apply_canonical_recovery,
    evaluate_recovery,
    validate_recovery_state,
)


def base_state():
    return {
        "schema_version": 1,
        "current_wip": "#84-G3",
        "stage": "CI_RUNNING",
        "issue": "#84",
        "pull_request": "#93",
        "pr_status": "draft",
        "head_sha": "head",
        "expected_role": "Engineering",
        "required_checks": ["governance-recovery-contract"],
        "engineering_handoff": {"status": "NONE", "head_sha": None},
        "verification_verdict": {"status": "PENDING", "head_sha": None},
        "ci_state": {"status": "PENDING", "summary": "PENDING"},
        "human_gate": {"status": "NONE", "issue": None},
        "parallel_human_gates": [],
        "blocked_reason": None,
        "failure_class": "NONE",
        "retry_count": 0,
        "last_progress_at": "2026-08-27T16:30:00Z",
        "authority": {"state": "GRANTED", "scope": "#84-G3_ONLY"},
        "contradictions": [],
        "recovery": {
            "incident_signature": None,
            "incident_head_sha": None,
            "window_started_at": None,
            "retry_target": None,
            "cause_established": False,
            "executor_status": "AVAILABLE",
        },
    }


def incident_state(failure_class="TRANSIENT", retry_count=0, **recovery_overrides):
    state = base_state()
    state["failure_class"] = failure_class
    state["retry_count"] = retry_count
    recovery = {
        "incident_signature": "sig:example",
        "incident_head_sha": state["head_sha"],
        "window_started_at": "2026-08-27T12:00:00Z",
        "retry_target": "CI_JOB:33087069466:98569506439",
        "cause_established": False,
        "executor_status": "AVAILABLE",
    }
    recovery.update(recovery_overrides)
    state["recovery"] = recovery
    return state


def canonical_body(**overrides):
    values = {
        "current_wip": "#84-G3",
        "wip_kind": "GOVERNANCE",
        "stage": "CI_RUNNING",
        "failure_class": "NONE",
        "retry_count": "0",
        "expected_role": "Engineering",
        "human_gate": "false",
        "active_issue": "#84",
        "active_pr": "#93",
        "pr_status": "DRAFT",
        "active_head_sha": "head",
        "base_branch": "webots-ci",
        "base_sha": "base",
        "authority": "EXPLICIT_USER",
        "authority_scope": "#84-G3_ONLY",
        "authority_state": "GRANTED",
        "focused_run": "PENDING",
        "focused_run_result": "PENDING",
        "exact_head_ci": "PENDING",
        "engineering_handoff": "NONE",
        "verification_verdict": "PENDING",
        "blocked_reason": "NONE",
        "recovery_incident_signature": "NONE",
        "recovery_incident_head_sha": "NONE",
        "retry_window_started_at": "NONE",
        "retry_target": "NONE",
        "cause_established": "false",
        "executor_status": "AVAILABLE",
    }
    values.update(overrides)
    lines = "\n".join(f"{key}={value}" for key, value in values.items())
    return f"""# State

## État machine canonique

```text
{lines}
```
"""


class RecoveryContractTests(unittest.TestCase):
    NOW = "2026-08-27T16:00:00Z"

    def test_no_failure_is_no_action_and_clean_recovery_state(self):
        state = base_state()
        self.assertEqual(validate_recovery_state(state), [])
        decision = evaluate_recovery(state, self.NOW)
        self.assertEqual(decision.action, "NO_ACTION")
        self.assertFalse(decision.retry_allowed)
        self.assertFalse(decision.blocks_independent_wip)

    def test_unknown_failure_class_fails_closed(self):
        state = base_state()
        state["failure_class"] = "MAYBE"
        with self.assertRaisesRegex(ValueError, "INVALID_FAILURE_CLASS"):
            evaluate_recovery(state, self.NOW)

    def test_retry_count_must_be_non_negative_integer(self):
        for value in (-1, True, "1"):
            state = base_state()
            state["retry_count"] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "INVALID_RETRY_COUNT"):
                evaluate_recovery(state, self.NOW)

    def test_transient_retries_only_specific_causal_target_within_budget(self):
        for retry_count in (0, 1):
            state = incident_state("TRANSIENT", retry_count=retry_count)
            decision = evaluate_recovery(state, self.NOW)
            self.assertEqual(decision.action, "RETRY_CAUSAL_TARGET")
            self.assertTrue(decision.retry_allowed)
            self.assertEqual(decision.retry_target, "CI_JOB:33087069466:98569506439")

    def test_harness_oracle_can_retry_exact_role_target_within_budget(self):
        state = incident_state(
            "HARNESS_ORACLE",
            retry_count=1,
            retry_target="ROLE:Engineering",
        )
        decision = evaluate_recovery(state, self.NOW)
        self.assertEqual(decision.action, "RETRY_CAUSAL_TARGET")
        self.assertEqual(decision.retry_target, "ROLE:Engineering")

    def test_blind_ci_retry_target_is_forbidden(self):
        for target in ("CI_ALL", "CI_JOB", "workflow:all", "", None):
            state = incident_state("TRANSIENT", retry_target=target)
            with self.subTest(target=target), self.assertRaisesRegex(
                ValueError, "BLIND_OR_INVALID_RETRY_TARGET"
            ):
                evaluate_recovery(state, self.NOW)

    def test_retry_budget_exhaustion_routes_to_lab_with_explicit_blocker(self):
        state = incident_state("TRANSIENT", retry_count=2)
        decision = evaluate_recovery(state, self.NOW)
        self.assertEqual(decision.action, "BLOCK_RETRY_BUDGET_EXHAUSTED")
        self.assertEqual(decision.next_role, "Lab")
        self.assertEqual(decision.blocker_reason, "RETRY_BUDGET_EXHAUSTED")
        self.assertFalse(decision.retry_allowed)

    def test_retry_window_expiry_routes_to_lab_instead_of_resetting_silently(self):
        state = incident_state(
            "HARNESS_ORACLE",
            retry_count=1,
            window_started_at="2026-08-27T08:00:00Z",
        )
        decision = evaluate_recovery(state, self.NOW)
        self.assertEqual(decision.action, "BLOCK_RETRY_WINDOW_EXPIRED")
        self.assertEqual(decision.next_role, "Lab")
        self.assertEqual(decision.blocker_reason, "RETRY_WINDOW_EXPIRED")

    def test_stale_incident_head_cannot_be_retried(self):
        state = incident_state("TRANSIENT", incident_head_sha="old-head")
        with self.assertRaisesRegex(ValueError, "STALE_RECOVERY_INCIDENT_HEAD"):
            evaluate_recovery(state, self.NOW)

    def test_product_routes_engineering_only_when_cause_is_established(self):
        established = incident_state(
            "PRODUCT",
            retry_target=None,
            window_started_at=None,
            cause_established=True,
        )
        uncertain = copy.deepcopy(established)
        uncertain["recovery"]["cause_established"] = False

        self.assertEqual(evaluate_recovery(established, self.NOW).action, "ROUTE_ENGINEERING")
        decision = evaluate_recovery(uncertain, self.NOW)
        self.assertEqual(decision.action, "ROUTE_LAB")
        self.assertEqual(decision.next_role, "Lab")
        self.assertEqual(decision.blocker_reason, "PRODUCT_CAUSE_UNCERTAIN")

    def test_human_gate_waits_without_blocking_independent_wip_or_retrying(self):
        state = incident_state(
            "HUMAN_GATE",
            retry_target=None,
            window_started_at=None,
        )
        decision = evaluate_recovery(state, self.NOW)
        self.assertEqual(decision.action, "WAIT_HUMAN_GATE")
        self.assertIsNone(decision.next_role)
        self.assertFalse(decision.retry_allowed)
        self.assertFalse(decision.blocks_independent_wip)

    def test_authority_fails_closed_without_automatic_retry(self):
        state = incident_state(
            "AUTHORITY",
            retry_target=None,
            window_started_at=None,
        )
        decision = evaluate_recovery(state, self.NOW)
        self.assertEqual(decision.action, "BLOCK_AUTHORITY")
        self.assertEqual(decision.next_role, "Lead")
        self.assertEqual(decision.blocker_reason, "AUTHORITY_REQUIRED")
        self.assertFalse(decision.retry_allowed)

    def test_platform_executor_unavailable_models_agent_capacity_failure(self):
        state = incident_state(
            "PLATFORM",
            retry_target=None,
            window_started_at=None,
            executor_status="UNAVAILABLE",
        )
        decision = evaluate_recovery(state, self.NOW)
        self.assertEqual(decision.action, "BLOCK_PLATFORM")
        self.assertEqual(decision.next_role, "Lead")
        self.assertEqual(decision.blocker_reason, "PLATFORM_EXECUTOR_UNAVAILABLE")
        self.assertFalse(decision.retry_allowed)

    def test_non_retryable_classes_cannot_smuggle_retry_target(self):
        for failure_class in ("PRODUCT", "HUMAN_GATE", "AUTHORITY", "PLATFORM"):
            state = incident_state(
                failure_class,
                retry_target="CI_JOB:1:2",
                window_started_at=None,
            )
            with self.subTest(failure_class=failure_class), self.assertRaisesRegex(
                ValueError, "RETRY_TARGET_ON_NON_RETRYABLE_FAILURE"
            ):
                evaluate_recovery(state, self.NOW)

    def test_no_failure_cannot_keep_stale_retry_metadata(self):
        state = base_state()
        state["retry_count"] = 1
        state["recovery"]["incident_signature"] = "sig:stale"
        problems = validate_recovery_state(state)
        self.assertIn("RETRY_COUNT_WITHOUT_FAILURE", problems)
        self.assertIn("RECOVERY_METADATA_WITHOUT_FAILURE", problems)

    def test_live_canonical_recovery_fields_are_machine_readable(self):
        state = apply_canonical_recovery(base_state(), canonical_body())
        self.assertEqual(state["retry_count"], 0)
        self.assertEqual(
            state["recovery"],
            {
                "incident_signature": None,
                "incident_head_sha": None,
                "window_started_at": None,
                "retry_target": None,
                "cause_established": False,
                "executor_status": "AVAILABLE",
            },
        )
        self.assertEqual(evaluate_recovery(state, self.NOW).action, "NO_ACTION")

    def test_live_platform_incident_is_not_silently_retried(self):
        raw_state = base_state()
        raw_state["failure_class"] = "PLATFORM"
        state = apply_canonical_recovery(
            raw_state,
            canonical_body(
                failure_class="PLATFORM",
                recovery_incident_signature="agent-capacity-exhausted",
                recovery_incident_head_sha="head",
                executor_status="UNAVAILABLE",
            ),
        )
        decision = evaluate_recovery(state, self.NOW)
        self.assertEqual(decision.action, "BLOCK_PLATFORM")
        self.assertEqual(decision.blocker_reason, "PLATFORM_EXECUTOR_UNAVAILABLE")
        self.assertFalse(decision.retry_allowed)

    def test_live_canonical_recovery_fields_are_required(self):
        body = canonical_body().replace("retry_target=NONE\n", "")
        with self.assertRaisesRegex(ValueError, "CANONICAL_RECOVERY_FIELDS_MISSING:retry_target"):
            apply_canonical_recovery(base_state(), body)

    def test_live_failure_class_mismatch_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "CANONICAL_FAILURE_CLASS_CONTRADICTION"):
            apply_canonical_recovery(
                base_state(),
                canonical_body(failure_class="PLATFORM"),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)

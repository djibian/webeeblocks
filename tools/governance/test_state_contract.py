#!/usr/bin/env python3
import copy
import json
import unittest
from pathlib import Path

from render_state import render, render_from_canonical
from state_contract import Observation, evaluate, validate_shape

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = ROOT / "governance" / "state.template.json"


def canonical_body(**overrides):
    values = {
        "current_wip": "#84-G1",
        "wip_kind": "GOVERNANCE",
        "stage": "VERIFICATION_READY",
        "failure_class": "NONE",
        "expected_role": "Verification",
        "human_gate": "false",
        "active_issue": "#84",
        "active_pr": "#89",
        "pr_status": "DRAFT",
        "active_head_sha": "current-head",
        "base_branch": "webots-ci",
        "base_sha": "base-head",
        "authority": "EXPLICIT_USER",
        "authority_scope": "#84-G1_ONLY",
        "authority_state": "GRANTED",
        "focused_run": "123",
        "focused_run_result": "SUCCESS",
        "exact_head_ci": "24_OF_24_SUCCESS",
        "engineering_handoff": "FINAL@current-head",
        "verification_verdict": "PENDING_INDEPENDENT",
        "blocked_reason": "NONE",
        "parallel_human_gate": "#71-D1",
        "parallel_human_gate_state": "PENDING",
    }
    values.update(overrides)
    lines = "\n".join(f"{key}={value}" for key, value in values.items())
    return f"""# State

## État machine canonique

```text
{lines}
```
"""


class GovernanceStateContractTests(unittest.TestCase):
    def setUp(self):
        template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
        self.template = template
        self.state = render(template, {
            "pull_request": "#89",
            "head_sha": "current-head",
            "pr_status": "draft",
            "last_progress_at": "2026-08-27T08:09:00Z",
        })

    def obs(self, **overrides):
        values = dict(
            pr_number=self.state.get("pull_request"),
            pr_head_sha=self.state.get("head_sha"),
            pr_status=self.state.get("pr_status"),
            ci_green=False,
            engineering_executed=False,
            progress_made=False,
            mutation_possible=True,
        )
        values.update(overrides)
        return Observation(**values)

    def test_generated_state_has_required_contract_and_exact_head(self):
        self.assertEqual(validate_shape(self.state), [])
        self.assertEqual(self.state["pull_request"], "#89")
        self.assertEqual(self.state["head_sha"], "current-head")
        self.assertEqual(self.state["pr_status"], "draft")

    def test_live_render_uses_canonical_stage_role_handoff_verdict_and_ci(self):
        state = render_from_canonical(
            self.template,
            {
                "pull_request": "#89",
                "head_sha": "current-head",
                "pr_status": "draft",
                "last_progress_at": "2026-08-27T12:38:24Z",
            },
            canonical_body(),
        )
        self.assertEqual(state["stage"], "VERIFICATION_READY")
        self.assertEqual(state["expected_role"], "Verification")
        self.assertEqual(
            state["engineering_handoff"],
            {"status": "FINAL", "head_sha": "current-head"},
        )
        self.assertEqual(
            state["verification_verdict"],
            {"status": "PENDING", "head_sha": None},
        )
        self.assertEqual(
            state["ci_state"],
            {"status": "GREEN", "summary": "24_OF_24_SUCCESS"},
        )
        self.assertIsNone(state["blocked_reason"])
        self.assertEqual(validate_shape(state), [])

    def test_canonical_blocked_reason_is_required_and_propagated(self):
        missing = canonical_body().replace("blocked_reason=NONE\n", "")
        with self.assertRaisesRegex(ValueError, "CANONICAL_FIELDS_MISSING:blocked_reason"):
            render_from_canonical(
                self.template,
                {
                    "pull_request": "#89",
                    "head_sha": "current-head",
                    "pr_status": "draft",
                    "last_progress_at": "2026-08-27T12:38:24Z",
                },
                missing,
            )

        state = render_from_canonical(
            self.template,
            {
                "pull_request": "#89",
                "head_sha": "current-head",
                "pr_status": "draft",
                "last_progress_at": "2026-08-27T12:38:24Z",
            },
            canonical_body(blocked_reason="READY_TRANSITION_UNAVAILABLE"),
        )
        self.assertEqual(state["blocked_reason"], "READY_TRANSITION_UNAVAILABLE")

    def test_live_render_fails_closed_when_canonical_head_is_stale(self):
        with self.assertRaisesRegex(ValueError, "CANONICAL_GITHUB_HEAD_CONTRADICTION"):
            render_from_canonical(
                self.template,
                {
                    "pull_request": "#89",
                    "head_sha": "current-head",
                    "pr_status": "draft",
                    "last_progress_at": "2026-08-27T12:38:24Z",
                },
                canonical_body(active_head_sha="old-head"),
            )

    def test_live_canonical_go_green_draft_exposes_pr88_transition(self):
        state = render_from_canonical(
            self.template,
            {
                "pull_request": "#89",
                "head_sha": "current-head",
                "pr_status": "draft",
                "last_progress_at": "2026-08-27T12:38:24Z",
            },
            canonical_body(
                stage="LEAD_READY",
                expected_role="Lead",
                verification_verdict="GO@current-head",
            ),
        )
        problems = evaluate(
            state,
            Observation(
                pr_number="#89",
                pr_head_sha="current-head",
                pr_status="draft",
                ci_green=True,
            ),
        )
        self.assertIn("READY_FOR_REVIEW_TRANSITION_REQUIRED", problems)

    def test_canonical_ci_mismatch_fails_closed(self):
        state = render_from_canonical(
            self.template,
            {
                "pull_request": "#89",
                "head_sha": "current-head",
                "pr_status": "draft",
                "last_progress_at": "2026-08-27T12:38:24Z",
            },
            canonical_body(exact_head_ci="PENDING", engineering_handoff="NONE"),
        )
        problems = evaluate(
            state,
            Observation(
                pr_number="#89",
                pr_head_sha="current-head",
                pr_status="draft",
                ci_green=True,
            ),
        )
        self.assertIn("CANONICAL_CI_CONTRADICTION", problems)

    def test_stale_final_engineering_handoff_after_head_change(self):
        s = copy.deepcopy(self.state)
        s["engineering_handoff"] = {"status":"FINAL", "head_sha":"old"}
        self.assertIn("STALE_ENGINEERING_HANDOFF", evaluate(s, self.obs()))

    def test_unconsumed_verification_verdict_and_stale_verdict(self):
        s = copy.deepcopy(self.state)
        s["verification_verdict"] = {"status":"GO", "head_sha":"old"}
        s["expected_role"] = "Verification"
        problems = evaluate(s, self.obs())
        self.assertIn("STALE_VERIFICATION_VERDICT", problems)
        self.assertIn("UNCONSUMED_VERIFICATION_VERDICT", problems)

    def test_unproven_is_valid_final_exact_head_non_go_verdict(self):
        s = copy.deepcopy(self.state)
        s["verification_verdict"] = {"status":"UNPROVEN", "head_sha":s["head_sha"]}
        s["engineering_handoff"] = {"status":"FINAL", "head_sha":s["head_sha"]}
        s["expected_role"] = "Verification"
        s["ci_state"] = {"status": "GREEN", "summary": "SUCCESS"}
        problems = evaluate(s, self.obs(ci_green=True, pr_status="draft"))
        self.assertNotIn("INVALID_VERIFICATION_VERDICT", problems)
        self.assertNotIn("STALE_VERIFICATION_VERDICT", problems)
        self.assertIn("UNCONSUMED_VERIFICATION_VERDICT", problems)
        self.assertNotIn("READY_FOR_REVIEW_TRANSITION_REQUIRED", problems)

        s["verification_verdict"]["head_sha"] = "old"
        self.assertIn("STALE_VERIFICATION_VERDICT", evaluate(s, self.obs()))

    def test_registry_pr_or_head_contradiction_fails_closed(self):
        problems = evaluate(self.state, self.obs(pr_number="#999", pr_head_sha="different"))
        self.assertIn("GITHUB_PR_CONTRADICTION", problems)
        self.assertIn("GITHUB_HEAD_CONTRADICTION", problems)

    def test_parallel_human_gate_is_not_global_stagnation(self):
        s = copy.deepcopy(self.state)
        s["parallel_human_gates"] = [{"issue":"#71", "status":"PENDING", "blocks_current_wip":False}]
        problems = evaluate(s, self.obs(engineering_executed=True, progress_made=True))
        self.assertNotIn("HUMAN_GATE_FALSELY_BLOCKS_CURRENT_WIP", problems)
        self.assertNotIn("LIVENESS_VIOLATION_SILENT_ENGINEERING_READY", problems)

    def test_pending_human_gate_cannot_claim_it_blocks_independent_wip(self):
        s = copy.deepcopy(self.state)
        s["parallel_human_gates"] = [{"issue":"#71", "status":"PENDING", "blocks_current_wip":True}]
        self.assertIn("HUMAN_GATE_FALSELY_BLOCKS_CURRENT_WIP", evaluate(s, self.obs()))

    def test_pr88_case_requires_ready_transition_or_explicit_blocker(self):
        s = copy.deepcopy(self.state)
        s["engineering_handoff"] = {"status":"FINAL", "head_sha":s["head_sha"]}
        s["verification_verdict"] = {"status":"GO", "head_sha":s["head_sha"]}
        s["pr_status"] = "draft"
        s["ci_state"] = {"status": "GREEN", "summary": "SUCCESS"}
        problems = evaluate(s, self.obs(pr_status="draft", ci_green=True))
        self.assertIn("READY_FOR_REVIEW_TRANSITION_REQUIRED", problems)
        s["blocked_reason"] = "mechanical transition unavailable"
        self.assertNotIn("READY_FOR_REVIEW_TRANSITION_REQUIRED", evaluate(s, self.obs(pr_status="draft", ci_green=True)))

    def test_mechanical_mutation_impossible_requires_blocker(self):
        self.assertIn("EXPLICIT_MUTATION_BLOCKER_REQUIRED", evaluate(self.state, self.obs(mutation_possible=False)))

    def test_no_silent_ready_real_pre_pr_liveness_violation(self):
        s = copy.deepcopy(self.state)
        s["stage"] = "ENGINEERING_READY"
        s["expected_role"] = "Engineering"
        s["pull_request"] = None
        s["pr_status"] = None
        s["head_sha"] = "webots-ci-base-head"
        problems = evaluate(
            s,
            self.obs(
                pr_number=None,
                pr_head_sha=None,
                pr_status=None,
                engineering_executed=True,
                progress_made=False,
            ),
        )
        self.assertIn("LIVENESS_VIOLATION_SILENT_ENGINEERING_READY", problems)
        self.assertNotIn("GITHUB_PR_CONTRADICTION", problems)
        self.assertNotIn("GITHUB_PR_STATUS_CONTRADICTION", problems)

    def test_progress_or_blocker_closes_silent_ready_violation(self):
        s = copy.deepcopy(self.state)
        s["stage"] = "ENGINEERING_READY"
        s["expected_role"] = "Engineering"
        s["pull_request"] = None
        s["pr_status"] = None
        s["head_sha"] = "webots-ci-base-head"
        common = dict(pr_number=None, pr_head_sha=None, pr_status=None, engineering_executed=True)

        progress_obs = dict(common)
        progress_obs["progress_made"] = True
        self.assertNotIn(
            "LIVENESS_VIOLATION_SILENT_ENGINEERING_READY",
            evaluate(s, self.obs(**progress_obs)),
        )

        s["blocked_reason"] = "explicit platform blocker"
        blocked_obs = dict(common)
        blocked_obs["progress_made"] = False
        self.assertNotIn(
            "LIVENESS_VIOLATION_SILENT_ENGINEERING_READY",
            evaluate(s, self.obs(**blocked_obs)),
        )

    def test_authority_is_structurally_required(self):
        s = copy.deepcopy(self.state)
        del s["authority"]
        errors = validate_shape(s)
        self.assertTrue(any(error.startswith("MISSING_FIELDS:") and "authority" in error for error in errors))

        s["authority"] = {"state": "GRANTED"}
        self.assertIn("MISSING_AUTHORITY_FIELDS:scope", validate_shape(s))

        s["authority"] = {"state": "", "scope": "#84-G1_ONLY"}
        self.assertIn("INVALID_AUTHORITY", validate_shape(s))


if __name__ == "__main__":
    unittest.main(verbosity=2)

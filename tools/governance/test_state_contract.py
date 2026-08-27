#!/usr/bin/env python3
import copy
import json
import unittest
from pathlib import Path

from state_contract import Observation, evaluate, load, validate_shape

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "governance" / "state.json"


class GovernanceStateContractTests(unittest.TestCase):
    def setUp(self):
        self.state = load(STATE_PATH)

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

    def test_versioned_state_has_required_contract(self):
        self.assertEqual(validate_shape(self.state), [])

    def test_stale_final_engineering_handoff_after_head_change(self):
        s = copy.deepcopy(self.state)
        s["engineering_handoff"] = {"status":"FINAL", "head_sha":"old"}
        problems = evaluate(s, self.obs())
        self.assertIn("STALE_ENGINEERING_HANDOFF", problems)

    def test_unconsumed_verification_verdict_and_stale_verdict(self):
        s = copy.deepcopy(self.state)
        s["verification_verdict"] = {"status":"GO", "head_sha":"old"}
        s["expected_role"] = "Verification"
        problems = evaluate(s, self.obs())
        self.assertIn("STALE_VERIFICATION_VERDICT", problems)
        self.assertIn("UNCONSUMED_VERIFICATION_VERDICT", problems)

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
        problems = evaluate(s, self.obs(pr_status="draft", ci_green=True))
        self.assertIn("READY_FOR_REVIEW_TRANSITION_REQUIRED", problems)
        s["blocked_reason"] = "mechanical transition unavailable"
        self.assertNotIn("READY_FOR_REVIEW_TRANSITION_REQUIRED", evaluate(s, self.obs(pr_status="draft", ci_green=True)))

    def test_mechanical_mutation_impossible_requires_blocker(self):
        problems = evaluate(self.state, self.obs(mutation_possible=False))
        self.assertIn("EXPLICIT_MUTATION_BLOCKER_REQUIRED", problems)

    def test_no_silent_ready_liveness_violation(self):
        problems = evaluate(self.state, self.obs(engineering_executed=True, progress_made=False))
        self.assertIn("LIVENESS_VIOLATION_SILENT_ENGINEERING_READY", problems)

    def test_progress_or_blocker_closes_silent_ready_violation(self):
        self.assertNotIn(
            "LIVENESS_VIOLATION_SILENT_ENGINEERING_READY",
            evaluate(self.state, self.obs(engineering_executed=True, progress_made=True)),
        )
        s = copy.deepcopy(self.state)
        s["blocked_reason"] = "explicit platform blocker"
        self.assertNotIn(
            "LIVENESS_VIOLATION_SILENT_ENGINEERING_READY",
            evaluate(s, self.obs(engineering_executed=True, progress_made=False)),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

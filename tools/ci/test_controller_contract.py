#!/usr/bin/env python3
"""Fail-closed static contract for V4 multi-Controller governance."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

def flat(text: str) -> str:
    return " ".join(text.split())

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.raw = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.contract = flat(self.raw)
        self.development = (ROOT / "docs" / "DEVELOPMENT.md").read_text(encoding="utf-8")
        self.notifications = (ROOT / "docs" / "CONTROLLER_NOTIFICATIONS.md").read_text(encoding="utf-8")
        self.roadmap = flat((ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8"))

    def test_five_principles(self):
        for heading in (
            "## 1 — Stateless Controllers",
            "## 2 — Optimistic Isolation",
            "## 3 — Stable Candidate",
            "## 4 — Healthy Trunk",
            "## 5 — Human Boundary",
        ):
            self.assertIn(heading, self.raw)
        self.assertIn("state of a Controller execution is never project state", self.contract)
        self.assertIn("Before every durable effect, reconstruct", self.contract)
        self.assertIn("Any information that can change a future decision", self.contract)

    def test_decision_authority_requires_trusted_provenance(self):
        self.assertIn("durable project blackboard", self.contract)
        self.assertIn("decision-authoritative only when its provenance", self.contract)
        self.assertIn("repository owner (`djibian`)", self.contract)
        self.assertIn("External comments or reviews remain evidence to inspect", self.contract)
        self.assertIn("Durability does not imply trust", self.development)
        self.assertIn("github-actions[bot]", self.notifications)

    def test_optimistic_candidate_validation_and_exact_head_integration(self):
        self.assertIn("Draft means mutable work in progress", self.contract)
        self.assertIn("Ready means the current exact HEAD is offered for validation", self.contract)
        self.assertIn("it is not a coordination lock", self.contract)
        self.assertIn("Positive decision evidence for prior HEADs cannot authorize it", self.contract)
        self.assertIn("Findings from authoritative refutations remain decision-relevant while applicable", self.contract)
        self.assertIn("Before a later candidate can receive GO", self.contract)
        self.assertIn("independent review must establish every still-applicable such finding as resolved or no longer applicable", self.contract)
        self.assertIn("observes a Ready PR and intends substantive mutation", self.contract)
        self.assertIn("Concurrent Ready/push races are tolerated", self.contract)
        self.assertIn("must never publish the required check context named `CI Gate`", self.contract)
        self.assertIn("mutated a PR cannot provide its independent review", self.contract)
        self.assertIn("may repair that PR after recording NO_GO", self.contract)
        self.assertIn("`expected_head_sha`", self.contract)
        self.assertIn("merge must fail/no-op and the Controller reconstructs current GitHub state", self.contract)

    def test_healthy_main_and_late_refutation(self):
        self.assertIn("main is the single long-lived trunk", self.contract)
        self.assertIn("ordinary integrations are suspended until restoration", self.contract)
        self.assertIn("late NO_GO on an already merged candidate", self.contract)
        self.assertIn("valid unresolved NO_GO blocks integration", self.contract)

    def test_only_test_required_notifies(self):
        self.assertIn("only notification class is TEST_REQUIRED", self.contract)
        self.assertIn("There is no human-test queue", self.contract)
        self.assertIn("A Controller never sends ntfy directly", self.contract)
        self.assertIn("unknown profiles fail closed", self.contract)
        combined = self.raw + self.development + self.notifications
        for obsolete in (
            "READY_FOR_REVIEW",
            "SESSION_LIMIT",
            "RELANCE CONTRÔLEUR",
            "Human-readiness gate",
            "Candidate evidence escalation",
            "preparatory context",
        ):
            self.assertNotIn(obsolete, combined)

    def test_termination_requires_final_reconstruction(self):
        self.assertIn("rebuild relevant engaged GitHub work one final time", self.contract)
        self.assertIn("Terminate silently only if that reconstruction exposes no useful eligible action", self.contract)
        self.assertIn("current local work is never by itself a termination condition", self.contract)

    def test_roadmap_records_w1_w2_and_findings(self):
        self.assertIn("W1 — coherence: PASS", self.roadmap)
        self.assertIn("W2 — 30-minute stability: PASS", self.roadmap)
        self.assertIn("subsequently closed", self.roadmap)
        self.assertIn("missing-`atterrir`", self.roadmap)
        self.assertIn("#129", self.roadmap)
        self.assertIn("voluntary interruption", self.roadmap)
        self.assertIn("#150", self.roadmap)
        self.assertIn("purely visual Blockly moves", self.roadmap)
        self.assertIn("#144", self.roadmap)

if __name__ == "__main__":
    unittest.main()

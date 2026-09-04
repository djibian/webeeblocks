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

    def test_exact_candidate_and_independent_review(self):
        self.assertIn("Draft means mutable work in progress", self.contract)
        self.assertIn("Ready means an exact candidate frozen for validation", self.contract)
        self.assertIn("Any new HEAD is a new candidate", self.contract)
        self.assertIn("must never publish the required check context named `CI Gate`", self.contract)
        self.assertIn("fresh CI and fresh independent review", self.contract)
        self.assertIn("mutated a PR cannot provide its independent review", self.contract)
        self.assertIn("may repair that PR after recording NO_GO", self.contract)

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

    def test_roadmap_records_w1_w2_and_findings(self):
        self.assertIn("W1 coherence: PASS", self.roadmap)
        self.assertIn("W2 stability: PASS", self.roadmap)
        self.assertIn("without atterrir", self.roadmap)
        self.assertIn("voluntarily interrupt", self.roadmap)
        self.assertIn("purely visual movement", self.roadmap)

if __name__ == "__main__":
    unittest.main()

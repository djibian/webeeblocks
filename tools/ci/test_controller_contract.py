#!/usr/bin/env python3
"""Prevent the productive-session and terminal-handoff contracts from regressing."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class ControllerContractTests(unittest.TestCase):
    def test_worker_waits_but_never_self_approves(self) -> None:
        contract = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("one continuous productive session", contract)
        self.assertIn("perform a progress checkpoint", contract)
        self.assertIn("elapsed time alone is not a reason", contract)
        self.assertIn("Stop as `BLOCKED` when about 30 minutes", contract)
        self.assertIn("same causal correction cycle repeats twice", contract)
        self.assertIn("Do not count bounded CI waiting as lack of progress", contract)
        self.assertIn("A pending `CI Gate` is not a reason to stop", contract)
        self.assertIn("five recent comparable non-cancelled gate", contract)
        self.assertIn("check about every 60 seconds", contract)
        self.assertIn("Reserve `SESSION_LIMIT` for an actual platform/runtime", contract)
        self.assertIn("never choose it solely because about 60 minutes elapsed", contract)
        self.assertIn("`READY_FOR_REVIEW`", contract)
        self.assertIn(
            "The launch that writes\na head never independently approves that head",
            contract,
        )
        self.assertNotIn("about 60 minutes maximum", contract)
        self.assertNotIn("Do not poll", contract)

    def test_terminal_handoff_is_exact_and_ci_is_silent(self) -> None:
        contract = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        development = (ROOT / "docs" / "DEVELOPMENT.md").read_text(
            encoding="utf-8"
        )
        notifications = (ROOT / "docs" / "CONTROLLER_NOTIFICATIONS.md").read_text(
            encoding="utf-8"
        )
        workflow = (
            ROOT / ".github" / "workflows" / "controller-handoff-ntfy.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("one continuous Worker", development)
        self.assertIn("one fresh\n  Reviewer-Integrator", development)
        self.assertIn("CI pending and CI completion are silent", development)
        self.assertIn(
            "CONTROLLER_HANDOFF READY_FOR_REVIEW <head-sha>", contract
        )
        self.assertIn("NO_GO <head-sha>", contract)
        self.assertIn("UNPROVEN <head-sha>", contract)
        self.assertIn(
            "A pending or settled CI and `GO` are silent", contract
        )
        self.assertIn(
            "physical test, human decision or Controller relaunch after merge uses the",
            contract,
        )
        self.assertIn(
            "stop as `HUMAN_REQUIRED` with an issue-level handoff asking Emmanuel",
            contract,
        )
        self.assertIn(
            "`COMPLETED` remains silent only when there is genuinely nothing for Emmanuel to",
            development,
        )
        self.assertNotIn(
            "A pending or settled CI, `GO` and `COMPLETED` are silent",
            contract,
        )
        for status in (
            "READY_FOR_REVIEW",
            "NO_GO",
            "UNPROVEN",
            "HUMAN_REQUIRED",
            "BLOCKED",
            "SESSION_LIMIT",
        ):
            self.assertIn(status, notifications)

        self.assertIn("issue_comment:", workflow)
        self.assertIn("pull_request_review:", workflow)
        self.assertIn("permissions: {}", workflow)
        self.assertNotIn("workflow_run:", workflow)
        self.assertNotIn("actions/checkout", workflow)
        self.assertNotIn("observes completion", development)
        self.assertNotIn("fallback when no session is active", development)
        self.assertNotIn("never waits inside", development)


if __name__ == "__main__":
    unittest.main()

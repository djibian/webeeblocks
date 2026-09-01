#!/usr/bin/env python3
"""Prevent the productive-session contract from regressing into CI handoffs."""

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

    def test_documentation_keeps_two_fresh_modes_and_ntfy_fallback(self) -> None:
        development = (ROOT / "docs" / "DEVELOPMENT.md").read_text(
            encoding="utf-8"
        )
        notifications = (ROOT / "docs" / "CONTROLLER_NOTIFICATIONS.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("one continuous Worker", development)
        self.assertIn("one fresh\n  Reviewer-Integrator", development)
        self.assertIn("fallback when no session is active", development)
        self.assertIn("polls moderately", notifications)
        self.assertNotIn("never waits inside", development)


if __name__ == "__main__":
    unittest.main()

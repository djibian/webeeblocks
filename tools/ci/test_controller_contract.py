#!/usr/bin/env python3
"""Prevent the critical-path scheduler and human-action contracts from regressing."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


def flat(text: str) -> str:
    """Normalize Markdown wrapping without weakening phrase-level assertions."""
    return " ".join(text.split())


class ControllerContractTests(unittest.TestCase):
    def test_critical_path_scheduler_preserves_review_independence_and_bounded_wip(self) -> None:
        contract_raw = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        roadmap_raw = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        development_raw = (ROOT / "docs" / "DEVELOPMENT.md").read_text(
            encoding="utf-8"
        )
        contract = flat(contract_raw)
        roadmap = flat(roadmap_raw)
        development = flat(development_raw)

        self.assertIn("Optimize the project critical path, not session duration", contract)
        self.assertIn("one active integration PR", contract)
        self.assertIn("at most one independent preparatory context", contract)
        self.assertIn("If an active PR exists, it owns the integration lane", contract)
        self.assertIn("waiting only on an external event", contract)
        self.assertIn("use the wait for one independent roadmap atom", contract)
        self.assertIn("a new Controller launch is required by independent review", contract)
        self.assertIn("Do not delay the critical path", contract)
        self.assertIn("never independently reviews, approves or merges that candidate head", contract)
        self.assertIn("A Reviewer that records `NO_GO` does not repair", contract)
        self.assertIn("A Reviewer that merges an unchanged `GO` head may", contract)
        self.assertIn("Absence of a roadmap dependency is not by itself proof", contract)
        self.assertIn("A preparatory branch becomes stale when `develop` moves", contract)
        self.assertIn("Do not create a chain of parked branches", contract)

        self.assertIn("one continuous productive session", contract)
        self.assertIn("perform a progress checkpoint", contract)
        self.assertIn("elapsed time alone is not a reason", contract)
        self.assertIn("Stop `BLOCKED` after about 30 minutes", contract)
        self.assertIn("same causal correction cycle repeats twice", contract)
        self.assertIn("A pending CI is not a reason to stop", contract)
        self.assertIn("five comparable non-cancelled gate durations", contract)
        self.assertIn("prefer checking the waiting CI at safe reserve checkpoints", contract)
        self.assertIn("Reserve `SESSION_LIMIT` for a real platform/runtime limit", contract)
        self.assertNotIn("about 60 minutes maximum", contract)
        self.assertNotIn("Do not poll", contract)

        self.assertIn("rolling operational projection", roadmap)
        self.assertIn("Protect the current integration critical path", roadmap)
        self.assertIn("Keep one active integration PR plus at most one preparatory context", roadmap)
        self.assertIn("Never invent work merely to keep a Controller session active", roadmap)
        self.assertIn("W1 — real Chrome coherence retest", roadmap)
        self.assertIn("U1 — characterize whether the current standard one-action path", roadmap)
        self.assertIn("X1 — reconstruct the current Crazyflie altitude causal path", roadmap)
        self.assertNotIn("status: DONE", roadmap_raw)
        self.assertNotIn("status: READY", roadmap_raw)

        self.assertIn("optimizes project throughput, not session length", development)
        self.assertIn("Only one integration PR toward `develop` is active", development)
        self.assertIn("At most one additional independent preparatory context", development)
        self.assertIn("If progress on the priority PR requires a fresh Controller launch", development)
        self.assertIn("instead of producing secondary busywork", development)

    def test_notifications_mean_only_test_or_relaunch_and_ci_is_silent(self) -> None:
        contract_raw = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        development_raw = (ROOT / "docs" / "DEVELOPMENT.md").read_text(
            encoding="utf-8"
        )
        notifications_raw = (ROOT / "docs" / "CONTROLLER_NOTIFICATIONS.md").read_text(
            encoding="utf-8"
        )
        workflow = (
            ROOT / ".github" / "workflows" / "controller-handoff-ntfy.yml"
        ).read_text(encoding="utf-8")
        contract = flat(contract_raw)
        development = flat(development_raw)
        notifications = flat(notifications_raw)

        self.assertIn(
            "Notifications exist only when Emmanuel must do a real test/manual evidence step or must relaunch the Controller",
            contract,
        )
        self.assertIn("CONTROLLER_HANDOFF HUMAN_REQUIRED <sha>", contract_raw)
        self.assertIn("This handoff may be non-terminal", contract)
        self.assertIn("CONTROLLER_HANDOFF READY_FOR_REVIEW <head-sha>", contract_raw)
        self.assertIn("NO_GO <head-sha>", contract_raw)
        self.assertIn("VERDICT UNPROVEN <sha>", contract_raw)
        self.assertIn("`VERDICT UNPROVEN`, pending/settled CI, `GO`, merges", contract_raw)
        self.assertIn("do not trigger ntfy", contract)

        self.assertIn("There are only two notification purposes", notifications)
        self.assertIn("**TEST**", notifications_raw)
        self.assertIn("**RELAUNCH**", notifications_raw)
        self.assertIn("may continue on one independent atom", notifications)
        self.assertIn("`VERDICT UNPROVEN <sha>`", notifications_raw)
        self.assertIn("does not match the ntfy transport grammar", notifications)
        self.assertIn("semantic migration does not require an unauthorized direct write", notifications)

        self.assertIn("CI, `GO`, merges, roadmap changes", development)
        self.assertIn("and `UNPROVEN` by itself are silent", development)
        self.assertIn("`HUMAN_REQUIRED` is reserved for a precise test", development)
        self.assertIn("Relaunch events use `READY_FOR_REVIEW`, `NO_GO`", development)

        self.assertIn("issue_comment:", workflow)
        self.assertIn("pull_request_review:", workflow)
        self.assertIn("permissions: {}", workflow)
        self.assertNotIn("workflow_run:", workflow)
        self.assertNotIn("actions/checkout", workflow)
        self.assertIn("WebeeBlocks — TEST À EFFECTUER", workflow)
        self.assertIn("WebeeBlocks — RELANCE CONTRÔLEUR", workflow)
        self.assertNotIn("UNPROVEN", workflow)
        self.assertNotIn("PREUVE À ARBITRER", workflow)


if __name__ == "__main__":
    unittest.main()

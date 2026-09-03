#!/usr/bin/env python3
"""Static fail-closed contract for UNPROVEN -> Candidate Evidence escalation."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
LISTENER = ROOT / ".github" / "workflows" / "candidate-evidence-on-unproven.yml"
CONTRACT = ROOT / "AGENTS.md"


class CandidateEvidenceTriggerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.listener = LISTENER.read_text(encoding="utf-8")
        cls.contract = CONTRACT.read_text(encoding="utf-8")

    def test_only_submitted_reviews_can_trigger(self) -> None:
        text = self.listener
        self.assertIn("  pull_request_review:\n    types: [submitted]\n", text)
        for forbidden in (
            "  pull_request_target:\n",
            "  issue_comment:\n",
            "  workflow_dispatch:\n",
            "  repository_dispatch:\n",
            "  workflow_run:\n",
            "  push:\n",
        ):
            self.assertNotIn(forbidden, text)

    def test_listener_is_read_only_and_does_not_checkout_candidate_code(self) -> None:
        text = self.listener
        self.assertIn("permissions: {}\n", text)
        self.assertIn("      pull-requests: read\n", text)
        self.assertIn("      contents: read\n", text)
        self.assertNotIn("actions: read", text)
        self.assertNotIn("actions/checkout", text)
        self.assertNotIn("secrets:", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("pull-requests: write", text)
        self.assertNotIn("issues: write", text)

    def test_event_gate_is_trusted_same_repo_develop_commented_review(self) -> None:
        text = self.listener
        for required in (
            "github.event.review.state == 'commented'",
            "github.event.review.user.login == 'djibian'",
            "github.event.pull_request.base.ref == 'develop'",
            "github.event.pull_request.head.repo.full_name == github.repository",
        ):
            self.assertIn(required, text)

    def test_canonical_unproven_and_triple_sha_binding_are_fail_closed(self) -> None:
        text = self.listener
        self.assertIn(
            'UNPROVEN_RE = re.compile(r"VERDICT UNPROVEN ([0-9a-f]{40})")',
            text,
        )
        self.assertIn("match = UNPROVEN_RE.fullmatch(line)", text)
        self.assertIn("declared_sha = match.group(1)", text)
        self.assertIn("review.get(\"commit_id\") != declared_sha", text)
        self.assertIn(
            "(live_pr.get(\"head\") or {}).get(\"sha\") != declared_sha",
            text,
        )
        self.assertIn("target_sha={declared_sha}", text)

    def test_live_pr_is_reread_and_must_still_be_open_same_repo_develop(self) -> None:
        text = self.listener
        self.assertIn('live_pr = api_get(f"/pulls/{number}")', text)
        self.assertIn('live_pr.get("state") != "open"', text)
        self.assertIn('(live_pr.get("base") or {}).get("ref") != "develop"', text)
        self.assertIn(
            '((live_pr.get("head") or {}).get("repo") or {}).get("full_name") != repository',
            text,
        )

    def test_review_history_is_paginated_and_first_unproven_is_unique(self) -> None:
        text = self.listener
        self.assertIn(
            'api_get(f"/pulls/{number}/reviews?per_page=100&page={page}")',
            text,
        )
        self.assertIn("if page > 100:", text)
        self.assertIn("current review is not uniquely present in live review history", text)
        self.assertIn("an earlier trusted UNPROVEN already exists for this PR HEAD", text)
        self.assertIn("trusted verdict history for this HEAD is contradictory", text)
        self.assertIn("item.get(\"commit_id\") != declared_sha", text)
        self.assertIn("(item.get(\"user\") or {}).get(\"login\") != TRUSTED_AUTHOR", text)

    def test_duplicate_events_are_serialized_without_cancelling_valid_work(self) -> None:
        text = self.listener
        self.assertIn(
            "group: candidate-evidence-unproven-${{ github.event.pull_request.number }}-${{ github.event.review.commit_id }}",
            text,
        )
        self.assertIn("  cancel-in-progress: false\n", text)

    def test_only_validated_sha_reaches_existing_candidate_evidence_capability(self) -> None:
        text = self.listener
        self.assertIn("    needs: validate\n", text)
        self.assertIn("    if: needs.validate.outputs.target_sha != ''\n", text)
        self.assertIn("uses: ./.github/workflows/candidate-evidence.yml", text)
        self.assertIn("target_sha: ${{ needs.validate.outputs.target_sha }}", text)
        self.assertNotIn("full:", text)
        self.assertNotIn("ci-runtime.yml", text)
        self.assertNotIn("ci-webots.yml", text)

    def test_listener_is_not_a_notification_or_command_bus(self) -> None:
        text = self.listener
        self.assertNotIn("CONTROLLER_HANDOFF", text)
        self.assertNotIn("ntfy", text.lower())
        self.assertNotIn("label", text.lower())
        self.assertNotIn("READY_FOR_REVIEW", text)
        self.assertNotIn("HUMAN_REQUIRED", text)

    def test_controller_contract_places_and_reassesses_candidate_evidence(self) -> None:
        text = self.contract
        for required in (
            "## Candidate evidence escalation",
            "Evidence is attached to the decision its failure must block",
            "Never merge a PR while",
            "never submit a second `VERDICT UNPROVEN` for the same PR HEAD",
            "authorize exactly one",
            "binding the declared SHA to `review.commit_id`",
            "not a second `CI Gate`",
            "not a required check and never a `GO` by itself",
            "Its start and completion are silent",
            "keep the productive Reviewer session alive",
            "reconstruct the live PR and exact unchanged HEAD",
            "A causal candidate defect can justify `NO_GO`",
            "apply the Human-readiness gate and use `HUMAN_REQUIRED`",
            "never edits the earlier UNPROVEN review",
        ):
            self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()

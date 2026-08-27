import json
import unittest
from pathlib import Path

from render_state import render_from_canonical
from transition_contract import (
    PullRequestObservation,
    TransitionObservation,
    evaluate_transition,
)


HEAD = "a" * 40
OTHER = "b" * 40
ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = ROOT / "governance" / "state.template.json"


def canonical_lead_body(blocked_reason="NONE"):
    values = {
        "current_wip": "#84-G2",
        "stage": "LEAD_MERGE_READY",
        "failure_class": "NONE",
        "expected_role": "Lead",
        "active_issue": "#84",
        "active_pr": "#91",
        "pr_status": "DRAFT",
        "active_head_sha": HEAD,
        "authority_scope": "#84-G2_ONLY",
        "authority_state": "GRANTED",
        "engineering_handoff": f"FINAL@{HEAD}",
        "verification_verdict": f"GO@{HEAD}",
        "exact_head_ci": "25_OF_25_SUCCESS",
        "blocked_reason": blocked_reason,
    }
    lines = "\n".join(f"{key}={value}" for key, value in values.items())
    return f"""## État machine canonique
```text
{lines}
```
"""


def live_lead_state(blocked_reason="NONE"):
    template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    return render_from_canonical(
        template,
        {
            "pull_request": "#91",
            "head_sha": HEAD,
            "pr_status": "draft",
            "last_progress_at": "2026-08-27T14:12:12Z",
        },
        canonical_lead_body(blocked_reason),
    )


def pr(number="#91", head=HEAD, ref="engineering/governance-transition-contract-g2", base="webots-ci", status="draft"):
    return PullRequestObservation(number, head, ref, base, status)


def state(**overrides):
    base = {
        "current_wip": "#84-G2",
        "stage": "ENGINEERING_IN_PROGRESS",
        "pull_request": "#91",
        "head_sha": HEAD,
        "pr_status": "draft",
        "expected_role": "Engineering",
        "engineering_handoff": {"status": "NONE", "head_sha": None},
        "verification_verdict": {"status": "PENDING", "head_sha": None},
        "ci_state": {"status": "PENDING", "summary": "PENDING"},
        "blocked_reason": None,
        "authority": {"state": "GRANTED", "scope": "#84-G2_ONLY"},
    }
    base.update(overrides)
    return base


class TransitionContractTests(unittest.TestCase):
    def obs(self, current=None, open_prs=None):
        current = pr() if current is None else current
        open_prs = [current] if open_prs is None and current is not None else (open_prs or [])
        return TransitionObservation(current, tuple(open_prs))

    def test_coherent_engineering_in_progress(self):
        self.assertEqual(evaluate_transition(state(), self.obs()), [])

    def test_more_than_one_integration_wip_fails_regardless_of_branch_prefix(self):
        second = pr(number="#92", head=OTHER, ref="feature/other")
        self.assertIn("MULTIPLE_ENGINEERING_WIP", evaluate_transition(state(), self.obs(open_prs=[pr(), second])))

    def test_main_target_requires_distinct_main_authority(self):
        main_pr = pr(base="main", ref="feature/not-engineering")
        problems = evaluate_transition(state(), self.obs(current=main_pr, open_prs=[main_pr]))
        self.assertIn("MAIN_TARGET_WITHOUT_DISTINCT_AUTHORITY", problems)
        authorized = state(authority={"state": "GRANTED", "scope": "MAIN_ONLY"})
        self.assertNotIn("MAIN_TARGET_WITHOUT_DISTINCT_AUTHORITY", evaluate_transition(authorized, self.obs(current=main_pr, open_prs=[main_pr])))

    def test_main_authority_does_not_cover_unrelated_pr(self):
        current = pr()
        unrelated = pr(number="#92", head=OTHER, ref="release/unrelated", base="main")
        authorized_current = state(authority={"state": "GRANTED", "scope": "MAIN_ONLY"})
        problems = evaluate_transition(authorized_current, self.obs(current=current, open_prs=[current, unrelated]))
        self.assertIn("MAIN_TARGET_WITHOUT_DISTINCT_AUTHORITY", problems)

    def test_verification_go_must_match_exact_head(self):
        s = state(verification_verdict={"status": "GO", "head_sha": OTHER})
        problems = evaluate_transition(s, self.obs())
        self.assertIn("VERIFICATION_GO_NOT_EXACT_HEAD", problems)
        self.assertIn("STALE_VERIFICATION_VERDICT", problems)

    def test_skipped_absent_or_ambiguous_cannot_support_lead_merge_ready(self):
        for status in ("SKIPPED", "AMBIGUOUS", "ABSENT", None):
            with self.subTest(status=status):
                s = state(
                    stage="LEAD_MERGE_READY",
                    expected_role="Lead",
                    pr_status="ready",
                    engineering_handoff={"status": "FINAL", "head_sha": HEAD},
                    verification_verdict={"status": status, "head_sha": None},
                    ci_state={"status": "GREEN", "summary": "SUCCESS"},
                )
                self.assertIn("INVALID_OR_MISSING_VERIFICATION_PRESENTED_AS_GO", evaluate_transition(s, self.obs(current=pr(status="ready"))))

    def test_registry_pr_head_and_status_contradictions_fail(self):
        observed = self.obs(current=pr(number="#99", head=OTHER, status="ready"), open_prs=[pr(number="#99", head=OTHER, status="ready")])
        problems = evaluate_transition(state(), observed)
        self.assertIn("REGISTRY_GITHUB_PR_CONTRADICTION", problems)
        self.assertIn("REGISTRY_GITHUB_HEAD_CONTRADICTION", problems)
        self.assertIn("REGISTRY_GITHUB_PR_STATUS_CONTRADICTION", problems)

    def test_engineering_final_handoff_must_reference_final_head(self):
        s = state(engineering_handoff={"status": "FINAL", "head_sha": OTHER})
        self.assertIn("ENGINEERING_HANDOFF_NOT_FINAL_HEAD", evaluate_transition(s, self.obs()))

    def test_unknown_stage_fails_closed(self):
        s = state(stage="VERIFICATON_READY", expected_role="Verification")
        self.assertIn("UNKNOWN_TRANSITION_STAGE", evaluate_transition(s, self.obs()))

    def test_expected_role_must_match_decisive_stage(self):
        s = state(stage="VERIFICATION_READY", expected_role="Engineering")
        self.assertIn("STALE_EXPECTED_ROLE_AFTER_TRANSITION", evaluate_transition(s, self.obs()))

    def test_verification_ready_requires_final_handoff_and_green_ci(self):
        s = state(stage="VERIFICATION_READY", expected_role="Verification")
        self.assertIn("HANDOFF_SKIPS_REQUIRED_STAGE", evaluate_transition(s, self.obs()))

    def test_lead_merge_ready_requires_complete_exact_head_chain(self):
        s = state(
            stage="LEAD_MERGE_READY",
            expected_role="Lead",
            pr_status="ready",
            engineering_handoff={"status": "FINAL", "head_sha": HEAD},
            verification_verdict={"status": "GO", "head_sha": HEAD},
            ci_state={"status": "GREEN", "summary": "24_OF_24_SUCCESS"},
        )
        self.assertEqual(evaluate_transition(s, self.obs(current=pr(status="ready"))), [])

    def test_final_green_go_draft_requires_ready_or_blocker(self):
        s = state(
            stage="LEAD_MERGE_READY",
            expected_role="Lead",
            engineering_handoff={"status": "FINAL", "head_sha": HEAD},
            verification_verdict={"status": "GO", "head_sha": HEAD},
            ci_state={"status": "GREEN", "summary": "24_OF_24_SUCCESS"},
        )
        self.assertIn("FINAL_GO_DRAFT_WITHOUT_BLOCKER", evaluate_transition(s, self.obs()))
        s["blocked_reason"] = "READY_TRANSITION_UNAVAILABLE"
        self.assertNotIn("FINAL_GO_DRAFT_WITHOUT_BLOCKER", evaluate_transition(s, self.obs()))

    def test_live_canonical_blocker_propagates_to_g2(self):
        s = live_lead_state("READY_TRANSITION_UNAVAILABLE")
        self.assertEqual(s["blocked_reason"], "READY_TRANSITION_UNAVAILABLE")
        self.assertNotIn(
            "FINAL_GO_DRAFT_WITHOUT_BLOCKER",
            evaluate_transition(s, self.obs()),
        )

    def test_live_canonical_no_blocker_still_requires_ready(self):
        s = live_lead_state()
        self.assertIsNone(s["blocked_reason"])
        self.assertIn(
            "FINAL_GO_DRAFT_WITHOUT_BLOCKER",
            evaluate_transition(s, self.obs()),
        )

    def test_handoff_cannot_skip_from_engineering_stage_to_final(self):
        s = state(engineering_handoff={"status": "FINAL", "head_sha": HEAD})
        self.assertIn("HANDOFF_SKIPS_REQUIRED_STAGE", evaluate_transition(s, self.obs()))

    def test_registry_declaring_pr_when_github_has_none_fails(self):
        observed = TransitionObservation(None, tuple())
        self.assertIn("REGISTRY_DECLARES_MISSING_ACTIVE_PR", evaluate_transition(state(), observed))


if __name__ == "__main__":
    unittest.main()

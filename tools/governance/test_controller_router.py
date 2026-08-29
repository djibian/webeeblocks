import copy
import unittest
from pathlib import Path

from controller_router import (
    controller_state_from_canonical,
    route_controller,
)
from transition_contract import (
    PullRequestObservation,
    TransitionObservation,
)


HEAD = "a" * 40
BASE = "b" * 40
NOW = "2026-08-28T15:00:00Z"


def canonical_body(**overrides):
    values = {
        "current_wip": "NONE",
        "stage": "NEUTRAL",
        "failure_class": "NONE",
        "retry_count": "0",
        "expected_role": "NONE",
        "active_issue": "NONE",
        "active_pr": "NONE",
        "pr_status": "NONE",
        "active_head_sha": "NONE",
        "base_branch": "webots-ci",
        "base_sha": BASE,
        "authority_scope": "NONE",
        "authority_state": "NONE",
        "exact_head_ci": "NONE",
        "engineering_handoff": "NONE",
        "verification_verdict": "NONE",
        "blocked_reason": "NONE",
        "contradictions": "NONE",
        "recovery_incident_signature": "NONE",
        "recovery_incident_head_sha": "NONE",
        "retry_window_started_at": "NONE",
        "retry_target": "NONE",
        "cause_established": "false",
        "executor_status": "AVAILABLE",
    }
    values.update({key: str(value) for key, value in overrides.items()})
    lines = "\n".join(f"{key}={value}" for key, value in values.items())
    return f"""## État machine canonique
```text
{lines}
```
"""


def pr(
    number="#95",
    head=HEAD,
    ref="engineering/governance-manual-controller-router-g4h0",
    base="webots-ci",
    status="draft",
):
    return PullRequestObservation(number, head, ref, base, status)


def observation(current=None, open_prs=None):
    pulls = [] if open_prs is None else open_prs
    return TransitionObservation(current, tuple(pulls))


def active_state(stage="ENGINEERING_IN_PROGRESS", expected_role="Engineering", **overrides):
    body_values = {
        "current_wip": "#84-G4-H0",
        "stage": stage,
        "expected_role": expected_role,
        "active_issue": "#84",
        "active_pr": "#95",
        "pr_status": "DRAFT",
        "active_head_sha": HEAD,
        "authority_scope": "#84-G4-H0_ONLY",
        "authority_state": "GRANTED",
        "exact_head_ci": "PENDING",
        "verification_verdict": "PENDING",
    }
    body_values.update(overrides)
    return controller_state_from_canonical(canonical_body(**body_values))


class ControllerRouterTests(unittest.TestCase):
    def test_current_neutral_state_routes_lead_even_when_expected_role_is_none(self):
        state = controller_state_from_canonical(canonical_body())
        route = route_controller(state, observation(), NOW)
        self.assertEqual(route.selected_role, "Lead")
        self.assertEqual(route.selected_mode, "PLAN")
        self.assertEqual(route.routing_reason, "NEUTRAL_BACKLOG_SELECTION")

    def test_neutral_state_must_not_hide_declared_wip(self):
        state = controller_state_from_canonical(canonical_body(current_wip="#78"))
        with self.assertRaisesRegex(ValueError, "NEUTRAL_CURRENT_WIP_MUST_BE_NONE"):
            route_controller(state, observation(), NOW)

    def test_neutral_state_with_open_integration_pr_fails_closed(self):
        state = controller_state_from_canonical(canonical_body())
        open_pr = pr()
        with self.assertRaisesRegex(ValueError, "NEUTRAL_WITH_OPEN_INTEGRATION_PR"):
            route_controller(state, observation(open_prs=[open_pr]), NOW)

    def test_unauthorized_main_pr_fails_before_neutral_routing(self):
        state = controller_state_from_canonical(canonical_body())
        main_pr = pr(number="#96", base="main", ref="release/unapproved")
        with self.assertRaisesRegex(ValueError, "MAIN_TARGET_WITHOUT_DISTINCT_AUTHORITY"):
            route_controller(state, observation(open_prs=[main_pr]), NOW)

    def test_multiple_integration_prs_fail_before_role_selection(self):
        state = active_state()
        first = pr()
        second = pr(number="#96", head=BASE, ref="feature/concurrent")
        with self.assertRaisesRegex(ValueError, "MULTIPLE_ENGINEERING_WIP"):
            route_controller(
                state,
                observation(current=first, open_prs=[first, second]),
                NOW,
            )

    def test_active_engineering_stage_routes_engineering(self):
        state = active_state()
        current = pr()
        route = route_controller(
            state, observation(current=current, open_prs=[current]), NOW
        )
        self.assertEqual((route.selected_role, route.selected_mode), ("Engineering", "IMPLEMENT"))

    def test_expected_role_is_a_consistency_assertion(self):
        state = active_state(stage="VERIFICATION_READY", expected_role="Engineering")
        state["engineering_handoff"] = {"status": "FINAL", "head_sha": HEAD}
        state["ci_state"] = {"status": "GREEN", "summary": "SUCCESS"}
        current = pr()
        with self.assertRaisesRegex(ValueError, "STALE_EXPECTED_ROLE_AFTER_TRANSITION"):
            route_controller(
                state, observation(current=current, open_prs=[current]), NOW
            )

    def test_verification_ready_routes_verification_on_exact_head(self):
        state = active_state(stage="VERIFICATION_READY", expected_role="Verification")
        state["engineering_handoff"] = {"status": "FINAL", "head_sha": HEAD}
        state["ci_state"] = {"status": "GREEN", "summary": "SUCCESS"}
        current = pr()
        route = route_controller(
            state, observation(current=current, open_prs=[current]), NOW
        )
        self.assertEqual((route.selected_role, route.selected_mode), ("Verification", "VERIFY"))

    def test_ci_running_does_not_poll_or_change_role(self):
        state = active_state(stage="CI_RUNNING")
        current = pr()
        route = route_controller(
            state, observation(current=current, open_prs=[current]), NOW
        )
        self.assertEqual((route.selected_role, route.selected_mode), ("Engineering", "WAIT"))
        self.assertEqual(route.routing_reason, "CI_STILL_RUNNING")

    def test_policy_encodes_canonical_ci_running_representation(self):
        policy_path = Path(__file__).resolve().parents[2] / "governance" / "controller-policy.md"
        policy = policy_path.read_text(encoding="utf-8")
        self.assertIn("`stage=CI_RUNNING`", policy)
        self.assertIn("`exact_head_ci=PENDING`", policy)
        self.assertIn("`exact_head_ci=RUNNING` is invalid", policy)

        with self.assertRaisesRegex(ValueError, "CANONICAL_CI_STATE_INVALID:RUNNING"):
            active_state(stage="CI_RUNNING", exact_head_ci="RUNNING")

    def test_completed_ci_routes_engineering_to_publish_handoff(self):
        state = active_state(stage="CI_RUNNING")
        state["ci_state"] = {"status": "GREEN", "summary": "SUCCESS"}
        current = pr()
        route = route_controller(
            state, observation(current=current, open_prs=[current]), NOW
        )
        self.assertEqual(route.selected_role, "Engineering")
        self.assertEqual(route.routing_reason, "CI_COMPLETE_HANDOFF_REQUIRED")

    def test_human_gate_waits_without_fabricating_a_role(self):
        state = active_state(
            failure_class="HUMAN_GATE",
            recovery_incident_signature="human:test",
            recovery_incident_head_sha=HEAD,
        )
        current = pr()
        route = route_controller(
            state, observation(current=current, open_prs=[current]), NOW
        )
        self.assertIsNone(route.selected_role)
        self.assertEqual((route.selected_mode, route.routing_reason), ("WAIT", "WAIT_HUMAN_GATE"))

    def test_neutral_human_gate_cannot_hide_active_integration_pr(self):
        state = controller_state_from_canonical(
            canonical_body(
                failure_class="HUMAN_GATE",
                recovery_incident_signature="human:test",
                recovery_incident_head_sha=HEAD,
                active_head_sha=HEAD,
            )
        )
        current = pr()
        with self.assertRaisesRegex(ValueError, "NEUTRAL_RECOVERY_WITH_OPEN_INTEGRATION_PR"):
            route_controller(
                state, observation(current=current, open_prs=[current]), NOW
            )

    def test_recovery_cannot_hide_registry_head_contradiction(self):
        state = active_state(
            failure_class="HUMAN_GATE",
            recovery_incident_signature="human:test",
            recovery_incident_head_sha=HEAD,
        )
        stale = pr(head=BASE)
        with self.assertRaisesRegex(ValueError, "REGISTRY_GITHUB_HEAD_CONTRADICTION"):
            route_controller(state, observation(current=stale, open_prs=[stale]), NOW)

    def test_product_failure_routes_by_causal_certainty(self):
        established = active_state(
            failure_class="PRODUCT",
            recovery_incident_signature="product:test",
            recovery_incident_head_sha=HEAD,
            cause_established="true",
        )
        uncertain = copy.deepcopy(established)
        uncertain["recovery"]["cause_established"] = False
        current = pr()
        obs = observation(current=current, open_prs=[current])
        self.assertEqual(route_controller(established, obs, NOW).selected_role, "Engineering")
        self.assertEqual(route_controller(uncertain, obs, NOW).selected_role, "Lab")

    def test_retry_target_routes_only_the_declared_role(self):
        state = active_state(
            failure_class="TRANSIENT",
            retry_count="1",
            recovery_incident_signature="ci:123:456",
            recovery_incident_head_sha=HEAD,
            retry_window_started_at="2026-08-28T14:00:00Z",
            retry_target="ROLE:Engineering",
        )
        current = pr()
        route = route_controller(
            state, observation(current=current, open_prs=[current]), NOW
        )
        self.assertEqual(route.selected_role, "Engineering")
        self.assertEqual(route.routing_reason, "RETRY_CAUSAL_TARGET")

    def test_parser_requires_all_controller_fields(self):
        body = canonical_body().replace("base_sha=" + BASE + "\n", "")
        with self.assertRaisesRegex(ValueError, "CONTROLLER_FIELDS_MISSING:base_sha"):
            controller_state_from_canonical(body)


if __name__ == "__main__":
    unittest.main(verbosity=2)

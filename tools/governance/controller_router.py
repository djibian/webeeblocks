#!/usr/bin/env python3
"""Deterministic, read-only role router for the manual WebeeBlocks controller."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from recovery_contract import evaluate_recovery
from transition_contract import (
    PullRequestObservation,
    TransitionObservation,
    evaluate_transition,
    load_observation,
)


MACHINE_BLOCK_RE = re.compile(
    r"## État machine canonique\s*```text\s*(.*?)```", re.DOTALL
)
CONTROLLER_REQUIRED = {
    "current_wip",
    "stage",
    "failure_class",
    "retry_count",
    "expected_role",
    "active_issue",
    "active_pr",
    "pr_status",
    "active_head_sha",
    "base_branch",
    "base_sha",
    "authority_scope",
    "authority_state",
    "exact_head_ci",
    "engineering_handoff",
    "verification_verdict",
    "blocked_reason",
    "contradictions",
    "recovery_incident_signature",
    "recovery_incident_head_sha",
    "retry_window_started_at",
    "retry_target",
    "cause_established",
    "executor_status",
}
ACTIVE_STAGE_ROUTES = {
    "ENGINEERING_READY": ("Engineering", "IMPLEMENT"),
    "ENGINEERING_IN_PROGRESS": ("Engineering", "IMPLEMENT"),
    "VERIFICATION_READY": ("Verification", "VERIFY"),
    "LEAD_MERGE_READY": ("Lead", "PLAN"),
}
MODE_BY_ROLE = {
    "Lead": "RECONCILE",
    "Lab": "EXPERIMENT",
    "Engineering": "IMPLEMENT",
    "Verification": "VERIFY",
}


@dataclass(frozen=True)
class ControllerRoute:
    selected_role: str | None
    selected_mode: str
    routing_reason: str


def parse_machine_block(body: str) -> dict[str, str]:
    match = MACHINE_BLOCK_RE.search(body)
    if not match:
        raise ValueError("CANONICAL_MACHINE_BLOCK_MISSING")
    values: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if line and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    missing = sorted(CONTROLLER_REQUIRED - values.keys())
    if missing:
        raise ValueError("CONTROLLER_FIELDS_MISSING:" + ",".join(missing))
    return values


def _none(raw: str) -> str | None:
    return None if raw == "NONE" else raw


def _bool(raw: str, field: str) -> bool:
    if raw == "true":
        return True
    if raw == "false":
        return False
    raise ValueError(f"CANONICAL_{field.upper()}_INVALID:{raw}")


def _retry_count(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"CANONICAL_RETRY_COUNT_INVALID:{raw}") from exc
    if value < 0 or str(value) != raw:
        raise ValueError(f"CANONICAL_RETRY_COUNT_INVALID:{raw}")
    return value


def _handoff(raw: str) -> dict[str, Any]:
    if raw in {"NONE", "PENDING"}:
        return {"status": raw, "head_sha": None}
    if raw.startswith("FINAL@") and len(raw) > len("FINAL@"):
        return {"status": "FINAL", "head_sha": raw.split("@", 1)[1]}
    raise ValueError(f"CANONICAL_ENGINEERING_HANDOFF_INVALID:{raw}")


def _verdict(raw: str) -> dict[str, Any]:
    if raw == "NONE":
        return {"status": "NONE", "head_sha": None}
    if raw in {"PENDING", "PENDING_INDEPENDENT"}:
        return {"status": "PENDING", "head_sha": None}
    for status in ("GO", "NO_GO", "UNPROVEN"):
        prefix = status + "@"
        if raw.startswith(prefix) and len(raw) > len(prefix):
            return {"status": status, "head_sha": raw.split("@", 1)[1]}
    raise ValueError(f"CANONICAL_VERIFICATION_VERDICT_INVALID:{raw}")


def _ci_state(raw: str) -> dict[str, str]:
    if raw == "NONE":
        return {"status": "NONE", "summary": raw}
    if raw == "PENDING":
        return {"status": "PENDING", "summary": raw}
    if raw == "GREEN" or raw == "SUCCESS" or raw.endswith("_SUCCESS"):
        return {"status": "GREEN", "summary": raw}
    if "FAIL" in raw or "ERROR" in raw:
        return {"status": "FAILED", "summary": raw}
    raise ValueError(f"CANONICAL_CI_STATE_INVALID:{raw}")


def controller_state_from_canonical(body: str) -> dict[str, Any]:
    """Build the minimal G1/G2/G3-compatible state, including NEUTRAL."""
    machine = parse_machine_block(body)
    pr_status = _none(machine["pr_status"])
    if pr_status is not None:
        pr_status = pr_status.lower()
        if pr_status not in {"draft", "ready"}:
            raise ValueError(f"CANONICAL_PR_STATUS_INVALID:{pr_status}")

    state = {
        "current_wip": _none(machine["current_wip"]),
        "stage": machine["stage"],
        "issue": _none(machine["active_issue"]),
        "pull_request": _none(machine["active_pr"]),
        "pr_status": pr_status,
        "head_sha": _none(machine["active_head_sha"]),
        "base_branch": machine["base_branch"],
        "base_sha": machine["base_sha"],
        "expected_role": _none(machine["expected_role"]),
        "engineering_handoff": _handoff(machine["engineering_handoff"]),
        "verification_verdict": _verdict(machine["verification_verdict"]),
        "ci_state": _ci_state(machine["exact_head_ci"]),
        "blocked_reason": _none(machine["blocked_reason"]),
        "failure_class": machine["failure_class"],
        "retry_count": _retry_count(machine["retry_count"]),
        "authority": {
            "state": machine["authority_state"],
            "scope": machine["authority_scope"],
        },
        "contradictions": []
        if machine["contradictions"] == "NONE"
        else [machine["contradictions"]],
        "recovery": {
            "incident_signature": _none(machine["recovery_incident_signature"]),
            "incident_head_sha": _none(machine["recovery_incident_head_sha"]),
            "window_started_at": _none(machine["retry_window_started_at"]),
            "retry_target": _none(machine["retry_target"]),
            "cause_established": _bool(
                machine["cause_established"], "cause_established"
            ),
            "executor_status": machine["executor_status"],
        },
    }
    return state


def _main_authorized(
    state: dict[str, Any], pr: PullRequestObservation
) -> bool:
    authority = state.get("authority") or {}
    return (
        authority.get("state") == "GRANTED"
        and authority.get("scope") == "MAIN_ONLY"
        and state.get("pull_request") == pr.number
        and state.get("head_sha") == pr.head_sha
    )


def _guard_observed_prs(
    state: dict[str, Any], observed: TransitionObservation
) -> None:
    integration_prs = [
        pr for pr in observed.open_prs if pr.base_ref == "webots-ci"
    ]
    if len(integration_prs) > 1:
        raise ValueError("MULTIPLE_ENGINEERING_WIP")
    for pr in observed.open_prs:
        if pr.base_ref == "main" and not _main_authorized(state, pr):
            raise ValueError("MAIN_TARGET_WITHOUT_DISTINCT_AUTHORITY")


def _assert_neutral(
    state: dict[str, Any], observed: TransitionObservation
) -> None:
    violations: list[str] = []
    for key in (
        "current_wip",
        "issue",
        "pull_request",
        "pr_status",
        "head_sha",
        "expected_role",
        "blocked_reason",
    ):
        if state.get(key) is not None:
            violations.append("NEUTRAL_" + key.upper() + "_MUST_BE_NONE")
    if state.get("base_branch") != "webots-ci":
        violations.append("NEUTRAL_BASE_MUST_BE_WEBOTS_CI")
    if not isinstance(state.get("base_sha"), str) or not re.fullmatch(
        r"[0-9a-f]{40}", state["base_sha"]
    ):
        violations.append("NEUTRAL_BASE_SHA_REQUIRED")
    if state.get("failure_class") != "NONE":
        violations.append("NEUTRAL_FAILURE_CLASS_MUST_BE_NONE")
    if state.get("retry_count") != 0:
        violations.append("NEUTRAL_RETRY_COUNT_MUST_BE_ZERO")
    if state.get("engineering_handoff", {}).get("status") != "NONE":
        violations.append("NEUTRAL_HANDOFF_MUST_BE_NONE")
    if state.get("verification_verdict", {}).get("status") != "NONE":
        violations.append("NEUTRAL_VERDICT_MUST_BE_NONE")
    if state.get("ci_state", {}).get("status") != "NONE":
        violations.append("NEUTRAL_CI_MUST_BE_NONE")
    if state.get("contradictions"):
        violations.append("NEUTRAL_CONTRADICTIONS_MUST_BE_EMPTY")
    authority = state.get("authority") or {}
    if authority.get("state") != "NONE" or authority.get("scope") != "NONE":
        violations.append("NEUTRAL_AUTHORITY_MUST_BE_NONE")
    recovery = state.get("recovery") or {}
    if any(
        recovery.get(key) is not None
        for key in (
            "incident_signature",
            "incident_head_sha",
            "window_started_at",
            "retry_target",
        )
    ):
        violations.append("NEUTRAL_RECOVERY_METADATA_MUST_BE_EMPTY")
    if recovery.get("cause_established") is not False:
        violations.append("NEUTRAL_CAUSE_ESTABLISHED_MUST_BE_FALSE")
    if observed.current_pr is not None:
        violations.append("NEUTRAL_CURRENT_PR_MUST_BE_NONE")
    if any(pr.base_ref == "webots-ci" for pr in observed.open_prs):
        violations.append("NEUTRAL_WITH_OPEN_INTEGRATION_PR")
    if violations:
        raise ValueError(";".join(dict.fromkeys(violations)))


def route_controller(
    state: dict[str, Any], observed: TransitionObservation, now: str
) -> ControllerRoute:
    """Select one logical role without mutating GitHub or repository state."""
    _guard_observed_prs(state, observed)

    if state.get("failure_class") != "NONE":
        if state.get("stage") == "NEUTRAL":
            if observed.current_pr is not None or any(
                pr.base_ref == "webots-ci" for pr in observed.open_prs
            ):
                raise ValueError("NEUTRAL_RECOVERY_WITH_OPEN_INTEGRATION_PR")
        else:
            problems = evaluate_transition(state, observed)
            if problems:
                raise ValueError(";".join(dict.fromkeys(problems)))
        decision = evaluate_recovery(state, now)
        if decision.next_role is None:
            return ControllerRoute(None, "WAIT", decision.action)
        return ControllerRoute(
            decision.next_role,
            MODE_BY_ROLE[decision.next_role],
            decision.action,
        )

    stage = state.get("stage")
    if stage == "NEUTRAL":
        _assert_neutral(state, observed)
        return ControllerRoute("Lead", "PLAN", "NEUTRAL_BACKLOG_SELECTION")

    problems = evaluate_transition(state, observed)
    if problems:
        raise ValueError(";".join(dict.fromkeys(problems)))

    if stage == "CI_RUNNING":
        ci_status = (state.get("ci_state") or {}).get("status")
        if ci_status == "PENDING":
            return ControllerRoute("Engineering", "WAIT", "CI_STILL_RUNNING")
        if ci_status == "GREEN":
            return ControllerRoute(
                "Engineering", "IMPLEMENT", "CI_COMPLETE_HANDOFF_REQUIRED"
            )
        if ci_status == "FAILED":
            raise ValueError("CI_FAILED_WITHOUT_FAILURE_CLASS")
        raise ValueError("CI_RUNNING_WITH_INVALID_CI_STATE")

    if stage not in ACTIVE_STAGE_ROUTES:
        raise ValueError(f"UNKNOWN_CONTROLLER_STAGE:{stage}")
    role, mode = ACTIVE_STAGE_ROUTES[stage]
    return ControllerRoute(role, mode, f"STAGE_{stage}")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-body", required=True)
    parser.add_argument("--observation", required=True)
    parser.add_argument("--now", required=True)
    args = parser.parse_args()

    state = controller_state_from_canonical(
        Path(args.canonical_body).read_text(encoding="utf-8")
    )
    observation = load_observation(args.observation)
    route = route_controller(state, observation, args.now)
    print(
        "CONTROLLER_ROUTE_OK "
        f"role={route.selected_role or 'NONE'} "
        f"mode={route.selected_mode} "
        f"reason={route.routing_reason}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

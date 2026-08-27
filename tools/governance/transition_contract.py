#!/usr/bin/env python3
"""Deterministic, read-only transition validator for WebeeBlocks governance G2."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FINAL_VERDICTS = {"GO", "NO_GO", "UNPROVEN"}
ROLE_BY_STAGE = {
    "ENGINEERING_READY": "Engineering",
    "ENGINEERING_IN_PROGRESS": "Engineering",
    "CI_RUNNING": "Engineering",
    "VERIFICATION_READY": "Verification",
    "LEAD_MERGE_READY": "Lead",
}
VALID_STAGES = set(ROLE_BY_STAGE)
READY_TRANSITION_BLOCKERS = {"READY_TRANSITION_UNAVAILABLE"}


@dataclass(frozen=True)
class PullRequestObservation:
    number: str
    head_sha: str
    head_ref: str
    base_ref: str
    status: str


@dataclass(frozen=True)
class TransitionObservation:
    current_pr: PullRequestObservation | None
    open_prs: tuple[PullRequestObservation, ...]


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _normalise_pr(raw: dict[str, Any]) -> PullRequestObservation:
    number = raw.get("number")
    if isinstance(number, int):
        number = f"#{number}"
    if not isinstance(number, str) or not number.startswith("#"):
        raise ValueError("INVALID_OBSERVED_PR_NUMBER")
    status = raw.get("status")
    if status not in {"draft", "ready"}:
        raise ValueError("INVALID_OBSERVED_PR_STATUS")
    values = {
        "head_sha": raw.get("head_sha"),
        "head_ref": raw.get("head_ref"),
        "base_ref": raw.get("base_ref"),
    }
    if not all(isinstance(value, str) and value for value in values.values()):
        raise ValueError("INVALID_OBSERVED_PR")
    return PullRequestObservation(number=number, status=status, **values)


def load_observation(path: str | Path) -> TransitionObservation:
    payload = load_json(path)
    open_raw = payload.get("open_prs")
    if not isinstance(open_raw, list):
        raise ValueError("INVALID_OPEN_PRS_OBSERVATION")
    open_prs = tuple(_normalise_pr(item) for item in open_raw)
    current_raw = payload.get("current_pr")
    current_pr = None if current_raw is None else _normalise_pr(current_raw)
    return TransitionObservation(current_pr=current_pr, open_prs=open_prs)


def _main_authorized(state: dict[str, Any], pr: PullRequestObservation) -> bool:
    authority = state.get("authority") or {}
    return (
        authority.get("state") == "GRANTED"
        and authority.get("scope") == "MAIN_ONLY"
        and state.get("pull_request") == pr.number
        and state.get("head_sha") == pr.head_sha
    )


def evaluate_transition(state: dict[str, Any], observed: TransitionObservation) -> list[str]:
    """Return explicit transition violations. Empty means transition-coherent."""
    problems: list[str] = []
    blocked_reason = state.get("blocked_reason")
    ready_transition_blocked = blocked_reason in READY_TRANSITION_BLOCKERS
    current = observed.current_pr

    # Fail closed on any concurrent integration PR, regardless of branch naming.
    # Within this repository, an open PR targeting webots-ci is conservatively
    # treated as an active Engineering/integration WIP candidate.
    integration_wips = [
        pr for pr in observed.open_prs
        if pr.base_ref == "webots-ci"
    ]
    if len(integration_wips) > 1:
        problems.append("MULTIPLE_ENGINEERING_WIP")

    for pr in observed.open_prs:
        if pr.base_ref == "main" and not _main_authorized(state, pr):
            problems.append("MAIN_TARGET_WITHOUT_DISTINCT_AUTHORITY")

    canonical_pr = state.get("pull_request")
    canonical_head = state.get("head_sha")
    canonical_status = state.get("pr_status")
    if current is not None:
        if canonical_pr != current.number:
            problems.append("REGISTRY_GITHUB_PR_CONTRADICTION")
        if canonical_head != current.head_sha:
            problems.append("REGISTRY_GITHUB_HEAD_CONTRADICTION")
        if canonical_status != current.status:
            problems.append("REGISTRY_GITHUB_PR_STATUS_CONTRADICTION")
    elif canonical_pr is not None:
        problems.append("REGISTRY_DECLARES_MISSING_ACTIVE_PR")

    handoff = state.get("engineering_handoff") or {}
    handoff_status = handoff.get("status")
    handoff_head = handoff.get("head_sha")
    verdict = state.get("verification_verdict") or {}
    verdict_status = verdict.get("status")
    verdict_head = verdict.get("head_sha")
    ci_status = (state.get("ci_state") or {}).get("status")
    stage = state.get("stage")
    expected_role = state.get("expected_role")

    if stage not in VALID_STAGES:
        problems.append("UNKNOWN_TRANSITION_STAGE")

    if handoff_status == "FINAL" and handoff_head != canonical_head:
        problems.append("ENGINEERING_HANDOFF_NOT_FINAL_HEAD")

    if verdict_status == "GO":
        if not verdict_head or verdict_head != canonical_head:
            problems.append("VERIFICATION_GO_NOT_EXACT_HEAD")
    elif verdict_status in {None, "SKIPPED", "AMBIGUOUS", "ABSENT"}:
        if stage == "LEAD_MERGE_READY":
            problems.append("INVALID_OR_MISSING_VERIFICATION_PRESENTED_AS_GO")
    elif verdict_status not in {"PENDING", "NO_GO", "UNPROVEN"}:
        problems.append("INVALID_OR_AMBIGUOUS_VERIFICATION_VERDICT")

    if verdict_status in FINAL_VERDICTS and verdict_head != canonical_head:
        problems.append("STALE_VERIFICATION_VERDICT")

    required_role = ROLE_BY_STAGE.get(stage)
    if required_role and expected_role != required_role:
        problems.append("STALE_EXPECTED_ROLE_AFTER_TRANSITION")

    # Blockers represent mechanical inability, never missing governance evidence.
    if stage in {"ENGINEERING_READY", "ENGINEERING_IN_PROGRESS", "CI_RUNNING"}:
        if handoff_status == "FINAL":
            problems.append("HANDOFF_SKIPS_REQUIRED_STAGE")

    if stage == "VERIFICATION_READY":
        if (
            handoff_status != "FINAL"
            or handoff_head != canonical_head
            or ci_status != "GREEN"
        ):
            problems.append("HANDOFF_SKIPS_REQUIRED_STAGE")
        if verdict_status not in {"PENDING", None}:
            problems.append("VERIFICATION_READY_WITH_PREEXISTING_FINAL_VERDICT")

    if stage == "LEAD_MERGE_READY":
        if (
            handoff_status != "FINAL"
            or handoff_head != canonical_head
            or ci_status != "GREEN"
            or verdict_status != "GO"
            or verdict_head != canonical_head
        ):
            problems.append("HANDOFF_SKIPS_REQUIRED_STAGE")
        # Only an explicitly recognized mechanical Draft -> Ready failure exempts
        # the mechanical Ready transition; unrelated blockers must not.
        if canonical_status == "draft" and not ready_transition_blocked:
            problems.append("FINAL_GO_DRAFT_WITHOUT_BLOCKER")

    return problems


def assert_transition_coherent(state: dict[str, Any], observed: TransitionObservation) -> None:
    problems = evaluate_transition(state, observed)
    if problems:
        raise ValueError(";".join(dict.fromkeys(problems)))


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--observation", required=True)
    args = parser.parse_args()
    state = load_json(args.state)
    observed = load_observation(args.observation)
    assert_transition_coherent(state, observed)
    print(
        "GOVERNANCE_TRANSITION_OK "
        f"wip={state.get('current_wip')} stage={state.get('stage')} "
        f"role={state.get('expected_role')} pr={state.get('pull_request')} "
        f"head={state.get('head_sha')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Deterministic, read-only validator for WebeeBlocks governance state G1."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = {
    "schema_version", "current_wip", "stage", "issue", "pull_request",
    "head_sha", "expected_role", "required_checks", "verification_verdict",
    "human_gate", "blocked_reason", "failure_class", "retry_count",
    "last_progress_at", "pr_status", "engineering_handoff",
    "parallel_human_gates", "contradictions", "authority"
}

AUTHORITY_REQUIRED_FIELDS = {"state", "scope"}
VALID_PR_STATUS = {None, "draft", "ready"}
VALID_VERDICTS = {"PENDING", "GO", "NO_GO", "UNPROVEN"}
FINAL_VERDICTS = {"GO", "NO_GO", "UNPROVEN"}


@dataclass(frozen=True)
class Observation:
    pr_number: str | None
    pr_head_sha: str | None
    pr_status: str | None
    ci_green: bool
    engineering_executed: bool = False
    progress_made: bool = False
    mutation_possible: bool = True


def load(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_shape(state: dict[str, Any]) -> list[str]:
    errors = []
    missing = sorted(REQUIRED_FIELDS - state.keys())
    if missing:
        errors.append("MISSING_FIELDS:" + ",".join(missing))
    if state.get("schema_version") != 1:
        errors.append("UNSUPPORTED_SCHEMA_VERSION")
    if state.get("pr_status") not in VALID_PR_STATUS:
        errors.append("INVALID_PR_STATUS")

    verdict = state.get("verification_verdict") or {}
    if verdict.get("status") not in VALID_VERDICTS:
        errors.append("INVALID_VERIFICATION_VERDICT")

    authority = state.get("authority")
    if not isinstance(authority, dict):
        errors.append("INVALID_AUTHORITY")
    else:
        missing_authority = sorted(AUTHORITY_REQUIRED_FIELDS - authority.keys())
        if missing_authority:
            errors.append("MISSING_AUTHORITY_FIELDS:" + ",".join(missing_authority))
        elif not all(
            isinstance(authority.get(key), str) and authority.get(key)
            for key in AUTHORITY_REQUIRED_FIELDS
        ):
            errors.append("INVALID_AUTHORITY")

    if not isinstance(state.get("required_checks"), list):
        errors.append("INVALID_REQUIRED_CHECKS")
    if not isinstance(state.get("parallel_human_gates"), list):
        errors.append("INVALID_PARALLEL_HUMAN_GATES")
    return errors


def evaluate(state: dict[str, Any], observed: Observation) -> list[str]:
    """Return explicit contradictions/required transitions. Empty means coherent."""
    problems = validate_shape(state)
    current_head = observed.pr_head_sha or state.get("head_sha")

    # Repository/PR truth outranks a stale registry snapshot.
    if state.get("pull_request") != observed.pr_number:
        problems.append("GITHUB_PR_CONTRADICTION")
    if observed.pr_head_sha and state.get("head_sha") != observed.pr_head_sha:
        problems.append("GITHUB_HEAD_CONTRADICTION")
    if observed.pr_status != state.get("pr_status"):
        problems.append("GITHUB_PR_STATUS_CONTRADICTION")

    handoff = state.get("engineering_handoff") or {}
    if handoff.get("status") == "FINAL" and handoff.get("head_sha") != current_head:
        problems.append("STALE_ENGINEERING_HANDOFF")

    verdict = state.get("verification_verdict") or {}
    if verdict.get("status") in FINAL_VERDICTS and verdict.get("head_sha") != current_head:
        problems.append("STALE_VERIFICATION_VERDICT")
    if verdict.get("status") in FINAL_VERDICTS and state.get("expected_role") == "Verification":
        problems.append("UNCONSUMED_VERIFICATION_VERDICT")

    # Human gates are independent waits, not global stagnation.
    for gate in state.get("parallel_human_gates", []):
        if gate.get("status") == "PENDING" and gate.get("blocks_current_wip") is True:
            problems.append("HUMAN_GATE_FALSELY_BLOCKS_CURRENT_WIP")

    # Real #88 incident: a verified final draft needs a mechanical transition or blocker.
    if (
        handoff.get("status") == "FINAL"
        and observed.ci_green
        and verdict.get("status") == "GO"
        and observed.pr_status == "draft"
        and not state.get("blocked_reason")
    ):
        problems.append("READY_FOR_REVIEW_TRANSITION_REQUIRED")

    # Mechanical impossibility is never represented as silence.
    if not observed.mutation_possible and not state.get("blocked_reason"):
        problems.append("EXPLICIT_MUTATION_BLOCKER_REQUIRED")

    # NO_SILENT_READY_V1.
    authority = state.get("authority")
    authority_state = authority.get("state") if isinstance(authority, dict) else None
    if (
        state.get("stage") == "ENGINEERING_READY"
        and state.get("expected_role") == "Engineering"
        and authority_state == "GRANTED"
        and observed.engineering_executed
        and not observed.progress_made
        and not state.get("blocked_reason")
    ):
        problems.append("LIVENESS_VIOLATION_SILENT_ENGINEERING_READY")

    return problems


def assert_coherent(state: dict[str, Any], observed: Observation) -> None:
    problems = evaluate(state, observed)
    if problems:
        raise ValueError(";".join(problems))

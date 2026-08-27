#!/usr/bin/env python3
"""Deterministic, read-only bounded recovery policy for WebeeBlocks governance G3."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_FAILURE_CLASSES = {
    "NONE",
    "TRANSIENT",
    "HARNESS_ORACLE",
    "PRODUCT",
    "HUMAN_GATE",
    "AUTHORITY",
    "PLATFORM",
}
RETRYABLE_FAILURE_CLASSES = {"TRANSIENT", "HARNESS_ORACLE"}
MAX_RETRIES = 2
RETRY_WINDOW_SECONDS = 6 * 60 * 60
VALID_EXECUTOR_STATUS = {"AVAILABLE", "UNAVAILABLE", "UNKNOWN"}
VALID_ROLES = {"Lead", "Lab", "Engineering", "Verification"}
CI_JOB_TARGET_RE = re.compile(r"^CI_JOB:(\d+):(\d+)$")
ROLE_TARGET_RE = re.compile(r"^ROLE:(Lead|Lab|Engineering|Verification)$")
MACHINE_BLOCK_RE = re.compile(
    r"## État machine canonique\s*```text\s*(.*?)```",
    re.DOTALL,
)
CANONICAL_RECOVERY_REQUIRED = {
    "failure_class",
    "retry_count",
    "recovery_incident_signature",
    "recovery_incident_head_sha",
    "retry_window_started_at",
    "retry_target",
    "cause_established",
    "executor_status",
}


@dataclass(frozen=True)
class RecoveryDecision:
    action: str
    next_role: str | None
    retry_allowed: bool
    blocker_reason: str | None
    blocks_independent_wip: bool
    retry_target: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_utc(raw: str) -> datetime:
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"INVALID_RECOVERY_TIMESTAMP:{raw}") from exc
    if value.tzinfo is None:
        raise ValueError(f"INVALID_RECOVERY_TIMESTAMP:{raw}")
    return value.astimezone(timezone.utc)


def _is_specific_retry_target(target: str | None) -> bool:
    if target is None:
        return False
    return bool(CI_JOB_TARGET_RE.fullmatch(target) or ROLE_TARGET_RE.fullmatch(target))


def parse_machine_block(body: str) -> dict[str, str]:
    match = MACHINE_BLOCK_RE.search(body)
    if not match:
        raise ValueError("CANONICAL_MACHINE_BLOCK_MISSING")
    values: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    missing = sorted(CANONICAL_RECOVERY_REQUIRED - values.keys())
    if missing:
        raise ValueError("CANONICAL_RECOVERY_FIELDS_MISSING:" + ",".join(missing))
    return values


def _parse_none(raw: str) -> str | None:
    return None if raw == "NONE" else raw


def _parse_bool(raw: str, field: str) -> bool:
    if raw == "true":
        return True
    if raw == "false":
        return False
    raise ValueError(f"CANONICAL_{field.upper()}_INVALID:{raw}")


def apply_canonical_recovery(state: dict[str, Any], body: str) -> dict[str, Any]:
    machine = parse_machine_block(body)
    canonical_failure = machine["failure_class"]
    if state.get("failure_class") != canonical_failure:
        raise ValueError(
            f"CANONICAL_FAILURE_CLASS_CONTRADICTION:"
            f"{canonical_failure}!={state.get('failure_class')}"
        )
    try:
        retry_count = int(machine["retry_count"])
    except ValueError as exc:
        raise ValueError(
            f"CANONICAL_RETRY_COUNT_INVALID:{machine['retry_count']}"
        ) from exc
    if retry_count < 0 or str(retry_count) != machine["retry_count"]:
        raise ValueError(f"CANONICAL_RETRY_COUNT_INVALID:{machine['retry_count']}")

    enriched = dict(state)
    enriched["retry_count"] = retry_count
    enriched["recovery"] = {
        "incident_signature": _parse_none(machine["recovery_incident_signature"]),
        "incident_head_sha": _parse_none(machine["recovery_incident_head_sha"]),
        "window_started_at": _parse_none(machine["retry_window_started_at"]),
        "retry_target": _parse_none(machine["retry_target"]),
        "cause_established": _parse_bool(machine["cause_established"], "cause_established"),
        "executor_status": machine["executor_status"],
    }
    return enriched


def validate_recovery_state(state: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    failure_class = state.get("failure_class")
    retry_count = state.get("retry_count")
    recovery = state.get("recovery")

    if failure_class not in VALID_FAILURE_CLASSES:
        problems.append("INVALID_FAILURE_CLASS")

    if not isinstance(retry_count, int) or isinstance(retry_count, bool) or retry_count < 0:
        problems.append("INVALID_RETRY_COUNT")

    if not isinstance(recovery, dict):
        problems.append("INVALID_RECOVERY_STATE")
        return problems

    required = {
        "incident_signature",
        "incident_head_sha",
        "window_started_at",
        "retry_target",
        "cause_established",
        "executor_status",
    }
    missing = sorted(required - recovery.keys())
    if missing:
        problems.append("MISSING_RECOVERY_FIELDS:" + ",".join(missing))
        return problems

    if not isinstance(recovery.get("cause_established"), bool):
        problems.append("INVALID_CAUSE_ESTABLISHED")

    if recovery.get("executor_status") not in VALID_EXECUTOR_STATUS:
        problems.append("INVALID_EXECUTOR_STATUS")

    if failure_class == "NONE":
        if retry_count != 0:
            problems.append("RETRY_COUNT_WITHOUT_FAILURE")
        if any(
            recovery.get(key) is not None
            for key in ("incident_signature", "incident_head_sha", "window_started_at", "retry_target")
        ):
            problems.append("RECOVERY_METADATA_WITHOUT_FAILURE")
        if recovery.get("cause_established") is not False:
            problems.append("CAUSE_ESTABLISHED_WITHOUT_FAILURE")
        return problems

    signature = recovery.get("incident_signature")
    incident_head = recovery.get("incident_head_sha")
    if not isinstance(signature, str) or not signature:
        problems.append("MISSING_INCIDENT_SIGNATURE")
    if not isinstance(incident_head, str) or not incident_head:
        problems.append("MISSING_INCIDENT_HEAD")
    elif incident_head != state.get("head_sha"):
        problems.append("STALE_RECOVERY_INCIDENT_HEAD")

    if failure_class in RETRYABLE_FAILURE_CLASSES:
        target = recovery.get("retry_target")
        if not _is_specific_retry_target(target):
            problems.append("BLIND_OR_INVALID_RETRY_TARGET")
        started_at = recovery.get("window_started_at")
        if not isinstance(started_at, str) or not started_at:
            problems.append("MISSING_RETRY_WINDOW_START")
        else:
            try:
                parse_utc(started_at)
            except ValueError as exc:
                problems.append(str(exc))
    elif recovery.get("retry_target") is not None:
        problems.append("RETRY_TARGET_ON_NON_RETRYABLE_FAILURE")

    return problems


def evaluate_recovery(state: dict[str, Any], now: str) -> RecoveryDecision:
    problems = validate_recovery_state(state)
    if problems:
        raise ValueError(";".join(dict.fromkeys(problems)))

    failure_class = state["failure_class"]
    retry_count = state["retry_count"]
    recovery = state["recovery"]

    if failure_class == "NONE":
        return RecoveryDecision(
            action="NO_ACTION",
            next_role=None,
            retry_allowed=False,
            blocker_reason=None,
            blocks_independent_wip=False,
        )

    if failure_class in RETRYABLE_FAILURE_CLASSES:
        now_dt = parse_utc(now)
        started_at = parse_utc(recovery["window_started_at"])
        age = (now_dt - started_at).total_seconds()
        if age < 0:
            raise ValueError("RETRY_WINDOW_STARTS_IN_FUTURE")
        if age > RETRY_WINDOW_SECONDS:
            return RecoveryDecision(
                action="BLOCK_RETRY_WINDOW_EXPIRED",
                next_role="Lab",
                retry_allowed=False,
                blocker_reason="RETRY_WINDOW_EXPIRED",
                blocks_independent_wip=True,
            )
        if retry_count >= MAX_RETRIES:
            return RecoveryDecision(
                action="BLOCK_RETRY_BUDGET_EXHAUSTED",
                next_role="Lab",
                retry_allowed=False,
                blocker_reason="RETRY_BUDGET_EXHAUSTED",
                blocks_independent_wip=True,
            )
        return RecoveryDecision(
            action="RETRY_CAUSAL_TARGET",
            next_role=state.get("expected_role"),
            retry_allowed=True,
            blocker_reason=None,
            blocks_independent_wip=False,
            retry_target=recovery["retry_target"],
        )

    if failure_class == "PRODUCT":
        if recovery["cause_established"]:
            return RecoveryDecision(
                action="ROUTE_ENGINEERING",
                next_role="Engineering",
                retry_allowed=False,
                blocker_reason=None,
                blocks_independent_wip=False,
            )
        return RecoveryDecision(
            action="ROUTE_LAB",
            next_role="Lab",
            retry_allowed=False,
            blocker_reason="PRODUCT_CAUSE_UNCERTAIN",
            blocks_independent_wip=False,
        )

    if failure_class == "HUMAN_GATE":
        return RecoveryDecision(
            action="WAIT_HUMAN_GATE",
            next_role=None,
            retry_allowed=False,
            blocker_reason=None,
            blocks_independent_wip=False,
        )

    if failure_class == "AUTHORITY":
        return RecoveryDecision(
            action="BLOCK_AUTHORITY",
            next_role="Lead",
            retry_allowed=False,
            blocker_reason="AUTHORITY_REQUIRED",
            blocks_independent_wip=True,
        )

    if failure_class == "PLATFORM":
        blocker = (
            "PLATFORM_EXECUTOR_UNAVAILABLE"
            if recovery["executor_status"] == "UNAVAILABLE"
            else "PLATFORM_UNAVAILABLE"
        )
        return RecoveryDecision(
            action="BLOCK_PLATFORM",
            next_role="Lead",
            retry_allowed=False,
            blocker_reason=blocker,
            blocks_independent_wip=True,
        )

    raise AssertionError(f"unhandled failure class: {failure_class}")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--canonical-body", required=True)
    parser.add_argument("--now", required=True)
    args = parser.parse_args()

    state = load_json(args.state)
    body = Path(args.canonical_body).read_text(encoding="utf-8")
    state = apply_canonical_recovery(state, body)
    decision = evaluate_recovery(state, args.now)
    print(
        "GOVERNANCE_RECOVERY_OK "
        f"failure_class={state.get('failure_class')} "
        f"retry_count={state.get('retry_count')} "
        f"action={decision.action} "
        f"next_role={decision.next_role or 'NONE'} "
        f"blocker={decision.blocker_reason or 'NONE'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

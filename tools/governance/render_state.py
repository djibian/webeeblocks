#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TOKENS = {
    "$PULL_REQUEST": "pull_request",
    "$PR_STATUS": "pr_status",
    "$HEAD_SHA": "head_sha",
    "$LAST_PROGRESS_AT": "last_progress_at",
}

MACHINE_BLOCK_RE = re.compile(
    r"## État machine canonique\s*```text\s*(.*?)```",
    re.DOTALL,
)

CANONICAL_REQUIRED = {
    "current_wip",
    "stage",
    "failure_class",
    "expected_role",
    "active_issue",
    "active_pr",
    "pr_status",
    "active_head_sha",
    "authority_scope",
    "authority_state",
    "engineering_handoff",
    "verification_verdict",
    "exact_head_ci",
    "blocked_reason",
}


def render(template: dict, values: dict[str, str]) -> dict:
    def walk(value):
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items()}
        if isinstance(value, list):
            return [walk(v) for v in value]
        if isinstance(value, str) and value in TOKENS:
            key = TOKENS[value]
            if key not in values or values[key] in (None, ""):
                raise ValueError(f"missing generated state value: {key}")
            return values[key]
        return value
    return walk(template)


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
    missing = sorted(CANONICAL_REQUIRED - values.keys())
    if missing:
        raise ValueError("CANONICAL_FIELDS_MISSING:" + ",".join(missing))
    return values


def parse_handoff(raw: str) -> dict:
    if raw in {"NONE", "PENDING"}:
        return {"status": raw, "head_sha": None}
    if raw.startswith("FINAL@") and len(raw) > len("FINAL@"):
        return {"status": "FINAL", "head_sha": raw.split("@", 1)[1]}
    raise ValueError(f"CANONICAL_ENGINEERING_HANDOFF_INVALID:{raw}")


def parse_verdict(raw: str) -> dict:
    if raw in {"PENDING", "PENDING_INDEPENDENT"}:
        return {"status": "PENDING", "head_sha": None}
    for status in ("GO", "NO_GO", "UNPROVEN"):
        prefix = status + "@"
        if raw.startswith(prefix) and len(raw) > len(prefix):
            return {"status": status, "head_sha": raw.split("@", 1)[1]}
    raise ValueError(f"CANONICAL_VERIFICATION_VERDICT_INVALID:{raw}")


def parse_ci(raw: str) -> dict:
    if raw == "PENDING":
        return {"status": "PENDING", "summary": raw}
    if raw.endswith("_SUCCESS") or raw == "SUCCESS":
        return {"status": "GREEN", "summary": raw}
    if "FAIL" in raw or "ERROR" in raw:
        return {"status": "FAILED", "summary": raw}
    raise ValueError(f"CANONICAL_CI_STATE_INVALID:{raw}")


def parse_blocked_reason(raw: str) -> str | None:
    if raw == "NONE":
        return None
    if raw:
        return raw
    raise ValueError(f"CANONICAL_BLOCKED_REASON_INVALID:{raw}")


def render_from_canonical(
    template: dict,
    values: dict[str, str],
    canonical_body: str,
) -> dict:
    machine = parse_machine_block(canonical_body)

    canonical_pr = machine["active_pr"]
    canonical_head = machine["active_head_sha"]
    canonical_status = machine["pr_status"].lower()

    if canonical_pr != values["pull_request"]:
        raise ValueError(
            f"CANONICAL_GITHUB_PR_CONTRADICTION:{canonical_pr}!={values['pull_request']}"
        )
    if canonical_head != values["head_sha"]:
        raise ValueError(
            f"CANONICAL_GITHUB_HEAD_CONTRADICTION:{canonical_head}!={values['head_sha']}"
        )
    if canonical_status != values["pr_status"]:
        raise ValueError(
            f"CANONICAL_GITHUB_PR_STATUS_CONTRADICTION:{canonical_status}!={values['pr_status']}"
        )

    state = render(template, values)
    state.update(
        {
            "current_wip": machine["current_wip"],
            "stage": machine["stage"],
            "issue": machine["active_issue"],
            "pull_request": canonical_pr,
            "pr_status": canonical_status,
            "head_sha": canonical_head,
            "expected_role": machine["expected_role"],
            "failure_class": machine["failure_class"],
            "engineering_handoff": parse_handoff(machine["engineering_handoff"]),
            "verification_verdict": parse_verdict(machine["verification_verdict"]),
            "ci_state": parse_ci(machine["exact_head_ci"]),
            "blocked_reason": parse_blocked_reason(machine["blocked_reason"]),
            "authority": {
                "state": machine["authority_state"],
                "scope": machine["authority_scope"],
            },
        }
    )

    if "parallel_human_gate" in machine:
        state["parallel_human_gates"] = [
            {
                "issue": machine["parallel_human_gate"],
                "status": machine.get("parallel_human_gate_state", "PENDING"),
                "blocks_current_wip": False,
            }
        ]
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--pull-request", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--pr-status", choices=("draft", "ready"), required=True)
    parser.add_argument("--last-progress-at", required=True)
    parser.add_argument("--canonical-body", required=True)
    args = parser.parse_args()

    template = json.loads(Path(args.template).read_text(encoding="utf-8"))
    canonical_body = Path(args.canonical_body).read_text(encoding="utf-8")
    state = render_from_canonical(
        template,
        {
            "pull_request": args.pull_request,
            "head_sha": args.head_sha,
            "pr_status": args.pr_status,
            "last_progress_at": args.last_progress_at,
        },
        canonical_body,
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

TOKENS = {
    "$PULL_REQUEST": "pull_request",
    "$PR_STATUS": "pr_status",
    "$HEAD_SHA": "head_sha",
    "$LAST_PROGRESS_AT": "last_progress_at",
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--pull-request", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--pr-status", choices=("draft", "ready"), required=True)
    parser.add_argument("--last-progress-at", required=True)
    args = parser.parse_args()
    template = json.loads(Path(args.template).read_text(encoding="utf-8"))
    state = render(template, {
        "pull_request": args.pull_request,
        "head_sha": args.head_sha,
        "pr_status": args.pr_status,
        "last_progress_at": args.last_progress_at,
    })
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

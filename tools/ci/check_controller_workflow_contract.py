#!/usr/bin/env python3
"""Fail closed when PR workflows bypass the native exact-head contract."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def root_event_block(source: str) -> str:
    lines = source.splitlines()
    start = next((index for index, line in enumerate(lines) if line == "on:"), None)
    if start is None:
        return ""

    body: list[str] = []
    for line in lines[start + 1 :]:
        if line and not line[0].isspace() and not line.lstrip().startswith("#"):
            break
        body.append(line)
    return "\n".join(body)


def event_body(block: str, event: str) -> str | None:
    lines = block.splitlines()
    marker = re.compile(rf"^  {re.escape(event)}:\s*$")
    next_event = re.compile(r"^  [^\s#][^:]*:")

    for index, line in enumerate(lines):
        if not marker.fullmatch(line):
            continue
        body: list[str] = []
        for candidate in lines[index + 1 :]:
            if next_event.match(candidate):
                break
            body.append(candidate)
        return "\n".join(body)
    return None


def audit(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    block = root_event_block(source)
    pull_request = event_body(block, "pull_request")
    errors: list[str] = []

    if "pull_request_target:" in block:
        errors.append("pull_request_target is forbidden on the integration branch")

    if pull_request is None:
        return errors

    explicit_types = re.search(r"(?m)^    types:\s*", pull_request)
    if explicit_types and not re.search(r"\bsynchronize\b", pull_request):
        errors.append("explicit pull_request.types omits synchronize")

    if "${{ secrets." in source:
        errors.append("pull_request workflow consumes a secret")

    if re.search(r"(?m)^\s+[A-Za-z][A-Za-z0-9_-]*:\s*write\s*$", source):
        errors.append("pull_request workflow grants a write permission")

    return errors


def main() -> int:
    failures: list[str] = []
    inspected = 0
    for path in sorted((*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml"))):
        source = path.read_text(encoding="utf-8")
        if event_body(root_event_block(source), "pull_request") is not None:
            inspected += 1
        for error in audit(path):
            failures.append(f"{path.relative_to(ROOT)}: {error}")

    if failures:
        raise SystemExit("\n".join(failures))
    if inspected == 0:
        raise SystemExit("No pull_request workflow was inspected")

    print(
        f"PASS: {inspected} pull_request workflows preserve native synchronize "
        "evidence without secrets or write permissions."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

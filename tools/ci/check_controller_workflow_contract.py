#!/usr/bin/env python3
"""Fail closed when PR workflows bypass the native exact-head contract."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def strip_yaml_comment(line: str) -> str:
    """Remove YAML comments without treating quoted hashes as comments."""
    quote: str | None = None
    escaped = False
    result: list[str] = []
    for character in line:
        if escaped:
            result.append(character)
            escaped = False
            continue
        if character == "\\" and quote == '"':
            result.append(character)
            escaped = True
            continue
        if character in {"'", '"'}:
            if quote is None:
                quote = character
            elif quote == character:
                quote = None
            result.append(character)
            continue
        if character == "#" and quote is None:
            break
        result.append(character)
    return "".join(result).rstrip()


def uncommented_lines(source: str) -> list[str]:
    return [strip_yaml_comment(line) for line in source.splitlines()]


def root_block(lines: list[str], key: str) -> tuple[str | None, list[str]]:
    marker = re.compile(rf"^{re.escape(key)}:\s*(.*?)\s*$")
    for index, line in enumerate(lines):
        match = marker.fullmatch(line)
        if not match:
            continue
        body: list[str] = []
        for candidate in lines[index + 1 :]:
            if candidate and not candidate[0].isspace():
                break
            body.append(candidate)
        return match.group(1), body
    return None, []


def event_body(on_body: list[str], event: str) -> list[str] | None:
    marker = re.compile(rf"^  {re.escape(event)}:\s*(.*?)\s*$")
    next_event = re.compile(r"^  [^\s][^:]*:")
    for index, line in enumerate(on_body):
        match = marker.fullmatch(line)
        if not match:
            continue
        if match.group(1):
            return [f"    {match.group(1)}"]
        body: list[str] = []
        for candidate in on_body[index + 1 :]:
            if next_event.match(candidate):
                break
            body.append(candidate)
        return body
    return None


def explicit_types(pull_request: list[str]) -> list[str] | None:
    marker = re.compile(r"^    types:\s*(.*?)\s*$")
    sibling = re.compile(r"^    [^\s][^:]*:")
    if sum(bool(marker.fullmatch(line)) for line in pull_request) > 1:
        raise ValueError("pull_request.types must be declared at most once")
    for index, line in enumerate(pull_request):
        match = marker.fullmatch(line)
        if not match:
            continue
        value = match.group(1)
        if value:
            if not (value.startswith("[") and value.endswith("]")):
                raise ValueError("pull_request.types must be an inline list or a YAML list")
            return [item.strip().strip("'\"") for item in value[1:-1].split(",") if item.strip()]

        values: list[str] = []
        for candidate in pull_request[index + 1 :]:
            if sibling.match(candidate):
                break
            item = re.fullmatch(r"\s{6}-\s*([^\s].*?)\s*", candidate)
            if candidate.strip() and not item:
                raise ValueError("pull_request.types contains unsupported YAML syntax")
            if item:
                values.append(item.group(1).strip().strip("'\""))
        return values
    return None


def explicit_read_only_permissions(lines: list[str]) -> bool:
    if sum(bool(re.match(r"^permissions\s*:", line)) for line in lines) != 1:
        return False
    value, body = root_block(lines, "permissions")
    if value is None or value:
        return False
    entries = [line.strip() for line in body if line.strip()]
    return entries == ["contents: read"]


def audit_source(path: Path, source: str) -> tuple[bool, list[str]]:
    lines = uncommented_lines(source)
    on_value, on_body = root_block(lines, "on")
    errors: list[str] = []

    if sum(bool(re.match(r"^on\s*:", line)) for line in lines) != 1:
        return False, ["top-level on must be declared exactly once"]
    if on_value is None:
        return False, ["top-level on mapping is missing"]
    if on_value:
        if re.search(r"\bpull_request(?:_target)?\b", on_value):
            return True, ["inline pull-request event syntax is forbidden; use an auditable mapping"]
        return False, []

    target_headers = [line for line in on_body if re.match(r"^  pull_request_target\s*:", line)]
    if target_headers:
        errors.append("pull_request_target is forbidden on the integration branch")

    request_headers = [line for line in on_body if re.match(r"^  pull_request\s*:", line)]
    if len(request_headers) > 1:
        errors.append("pull_request event must be declared at most once")
    if request_headers and request_headers[0].split(":", 1)[1].strip():
        errors.append("pull_request event must use an auditable block mapping")

    pull_request = event_body(on_body, "pull_request")
    if pull_request is None:
        return False, errors

    try:
        types = explicit_types(pull_request)
    except ValueError as error:
        errors.append(str(error))
    else:
        if types is not None and "synchronize" not in types:
            errors.append("explicit pull_request.types omits synchronize")

    if not explicit_read_only_permissions(lines):
        errors.append("pull_request workflow must declare exactly top-level contents: read")

    nested_permissions = [line for line in lines if re.match(r"^\s+permissions\s*:", line)]
    if nested_permissions:
        errors.append("job-level permissions are forbidden in pull_request workflows")

    uncommented = "\n".join(lines)
    if re.search(r"(?i)\bsecrets\b", uncommented):
        errors.append("pull_request workflow consumes or transmits a secret")

    if re.search(r"(?i)\bwrite-all\b", uncommented):
        errors.append("pull_request workflow grants write-all permission")

    return True, errors


def audit(path: Path) -> tuple[bool, list[str]]:
    return audit_source(path, path.read_text(encoding="utf-8"))


def main() -> int:
    failures: list[str] = []
    inspected = 0
    for path in sorted((*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml"))):
        is_pull_request, errors = audit(path)
        inspected += int(is_pull_request)
        failures.extend(f"{path.relative_to(ROOT)}: {error}" for error in errors)

    if failures:
        raise SystemExit("\n".join(failures))
    if inspected == 0:
        raise SystemExit("No pull_request workflow was inspected")

    print(
        f"PASS: {inspected} pull_request workflows preserve native synchronize "
        "evidence with explicit read-only authority and no secrets."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

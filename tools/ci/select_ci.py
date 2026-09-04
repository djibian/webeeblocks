#!/usr/bin/env python3
"""Conservatively select WebeeBlocks CI suites from changed paths."""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DOC_ONLY = ("*.md", "docs/**", "documentation/**", ".github/pull_request_template.md")
FORCE_FULL = (
    ".github/workflows/**",
    "tools/ci/select_ci.py",
    "tools/ci/test_select_ci.py",
    "tools/ci/check_ci_gate.py",
    "tools/ci/test_ci_gate.py",
    "tools/ci/test_workflow_contract.py",
    "tools/ci/test_repository_hygiene.py",
    "tools/ci/test_windows_release_contract.py",
    "tools/ci/test_controller_contract.py",
    "tools/build_windows_classroom_release.ps1",
    "packaging/windows/**",
    "plugins/robot_windows/blockly_v2/webots/**",
    "tools/prepare_runtime_v2.*",
    "controllers/crazyflie_runtime_v2/**",
    "worlds/crazyflie_runtime_v2*",
)
RUNTIME = (
    "plugins/robot_windows/blockly_v2/**",
    "plugins/robot_windows/blockly/webeeblocks/**",
    "tools/prepare_runtime_v2.*",
    "tools/ci/*runtime_v2*",
    "experiments/runtime-v2-student-ui/**",
)
WEBOTS = (
    "controllers/**",
    "worlds/**",
    "plugins/robot_windows/blockly/google-blockly-31ee4ea/**",
    "tools/ci/**",
    "experiments/**",
)
SHARED_RUNTIME_WEBOTS = (
    "controllers/crazyflie_runtime_v2/**",
    "worlds/crazyflie_runtime_v2*",
    "plugins/robot_windows/blockly/webeeblocks/wwi_backend.js",
)

def matches(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)

@dataclass(frozen=True)
class Selection:
    runtime: bool
    webots: bool
    full: bool
    reason: str
    paths: tuple[str, ...]

    def outputs(self) -> dict[str, str]:
        return {
            "runtime": str(self.runtime).lower(),
            "webots": str(self.webots).lower(),
            "full": str(self.full).lower(),
            "reason": self.reason,
        }

def select(paths: Iterable[str], *, force_full: bool = False) -> Selection:
    changed = tuple(sorted({path.strip() for path in paths if path.strip()}))
    if force_full:
        return Selection(True, True, True, "scheduled or manual full verification", changed)
    if not changed:
        return Selection(True, True, True, "empty or indeterminate diff", changed)
    if any(matches(path, FORCE_FULL) for path in changed):
        return Selection(True, True, True, "full-gate path changed", changed)
    runtime = False
    webots = False
    unknown: list[str] = []
    for path in changed:
        if matches(path, DOC_ONLY):
            continue
        if matches(path, SHARED_RUNTIME_WEBOTS):
            runtime = True
            webots = True
        elif matches(path, RUNTIME):
            runtime = True
        elif matches(path, WEBOTS):
            webots = True
        else:
            unknown.append(path)
    if unknown:
        return Selection(True, True, True, f"unknown/shared path: {unknown[0]}", changed)
    reason = "documentation only" if not runtime and not webots else "path-scoped suites"
    return Selection(runtime, webots, False, reason, changed)

def git_changed_paths(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", f"{base}...{head}"],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.splitlines()

def write_github_output(path: Path, selection: Selection) -> None:
    with path.open("a", encoding="utf-8") as stream:
        for key, value in selection.outputs().items():
            stream.write(f"{key}={value}\n")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--base-ref", default="")
    parser.add_argument("--draft", default="false")
    parser.add_argument("--paths-file", type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    if args.draft.lower() == "true":
        selection = Selection(False, False, False, "draft PR", ())
    else:
        force_full = args.event != "pull_request"
        if args.paths_file:
            paths = args.paths_file.read_text(encoding="utf-8").splitlines()
        elif force_full:
            paths = ()
        elif args.base and args.head:
            paths = git_changed_paths(args.base, args.head)
        else:
            paths = ()
        selection = select(paths, force_full=force_full)

    if args.github_output:
        write_github_output(args.github_output, selection)
    print(json.dumps({**selection.outputs(), "paths": selection.paths}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

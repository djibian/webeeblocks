#!/usr/bin/env python3
"""Select the bounded #70 S3 firmware build from exact changed paths."""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
from pathlib import Path
from typing import Iterable

S3_PATHS = (
    "experiments/crazyflie-ukf-surface-range/**",
    ".github/workflows/ci-webots.yml",
)


def selected(paths: Iterable[str], *, non_pr: bool = False) -> bool:
    if non_pr:
        return True
    return any(
        any(fnmatch.fnmatchcase(path, pattern) for pattern in S3_PATHS)
        for path in paths
    )


def git_changed_paths(base: str, head: str) -> list[str]:
    if not base or not head:
        raise SystemExit("exact base and head are required for PR S3 selection")
    result = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", f"{base}...{head}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--base", default="")
    parser.add_argument("--head", required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    non_pr = args.event != "pull_request"
    paths = () if non_pr else git_changed_paths(args.base, args.head)
    run = selected(paths, non_pr=non_pr)

    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as stream:
            stream.write(f"run={str(run).lower()}\n")
    print(f"S3_BUILD={str(run).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

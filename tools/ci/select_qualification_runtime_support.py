#!/usr/bin/env python3
"""Select exact physical-qualification runtime support without broad CI coupling."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = ".github/workflows/ci.yml"
START_MARKER = "# BEGIN PHYSICAL_QUALIFICATION_RUNTIME_SUPPORT"
END_MARKER = "# END PHYSICAL_QUALIFICATION_RUNTIME_SUPPORT"


def extract_support_block(text: str) -> str | None:
    if text.count(START_MARKER) != 1 or text.count(END_MARKER) != 1:
        return None
    start = text.index(START_MARKER)
    end = text.index(END_MARKER, start)
    if end <= start:
        return None
    return text[start : end + len(END_MARKER)]


def workflow_support_changed(base_text: str | None, head_text: str | None) -> bool:
    if base_text is None or head_text is None:
        return True
    base_block = extract_support_block(base_text)
    head_block = extract_support_block(head_text)
    if base_block is None or head_block is None:
        return True
    return base_block != head_block


def relevant_path(path: str) -> bool:
    if path in {
        "tools/ci/select_qualification_runtime_support.py",
        "tools/ci/test_physical_qualification_runtime_lock.py",
        "tools/ci/test_physical_qualification_package.py",
        "tools/ci/test_x3_characterization_package.py",
        "tools/prepare_runtime_v2.sh",
        "plugins/robot_windows/blockly/google-blockly-31ee4ea/blocks/crazyflie_v2.js",
        "plugins/robot_windows/blockly/google-blockly-31ee4ea/media/sprites.svg",
        "plugins/robot_windows/blockly/google-blockly-31ee4ea/media/sprites.png",
        "worlds/crazyflie_runtime_v2.wbt",
        "controllers/crazyflie_square/pid_controller.c",
        "controllers/crazyflie_square/pid_controller.h",
    }:
        return True
    return path.startswith(
        (
            "tools/physical/",
            "plugins/robot_windows/blockly_v2/",
            "plugins/robot_windows/blockly/webeeblocks/",
            "controllers/crazyflie_runtime_v2/",
        )
    )


def _git_text(ref: str, path: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout


def _changed_paths(base: str, head: str) -> tuple[str, ...]:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--no-renames", f"{base}...{head}"],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("qualification runtime scope cannot resolve exact PR diff") from exc
    return tuple(line.strip() for line in result.stdout.splitlines() if line.strip())


def should_run(event: str, base: str, head: str) -> bool:
    if event != "pull_request":
        return True
    if not base or not head:
        raise RuntimeError("qualification runtime scope requires exact pull-request base/head")
    paths = _changed_paths(base, head)
    if any(relevant_path(path) for path in paths):
        return True
    if WORKFLOW_PATH not in paths:
        return False
    return workflow_support_changed(
        _git_text(base, WORKFLOW_PATH),
        _git_text(head, WORKFLOW_PATH),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--base", default="")
    parser.add_argument("--head", default="")
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    run = should_run(args.event, args.base, args.head)
    value = "true" if run else "false"
    if args.github_output is not None:
        with args.github_output.open("a", encoding="utf-8") as stream:
            stream.write(f"run={value}\n")
    print(f"PHYSICAL_QUALIFICATION_RUNTIME={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

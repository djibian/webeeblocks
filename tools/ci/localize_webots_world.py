#!/usr/bin/env python3
"""Create an offline-equivalent Webots world from pinned R2025a URLs."""

from __future__ import annotations

import argparse
from pathlib import Path


REMOTE_PREFIX = "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/"
LOCAL_PREFIX = "webots://"


def localize(source: Path, target: Path, expected: int) -> int:
    original = source.read_text(encoding="utf-8")
    replacements = original.count(REMOTE_PREFIX)
    if replacements != expected:
        raise ValueError(
            f"expected exactly {expected} pinned Webots R2025a references in "
            f"{source}, found {replacements}"
        )

    localized = original.replace(REMOTE_PREFIX, LOCAL_PREFIX)
    if "raw.githubusercontent.com/cyberbotics/webots/" in localized:
        raise ValueError(f"a remote Cyberbotics dependency remains in {source}")
    if localized.replace(LOCAL_PREFIX, REMOTE_PREFIX) != original:
        raise ValueError(f"localizing {source} changed more than the URL prefix")

    target.write_text(localized, encoding="utf-8")
    return replacements


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--expected", type=int, required=True)
    args = parser.parse_args()

    count = localize(args.source, args.target, args.expected)
    print(
        f"PASS: localized exactly {count} Webots R2025a references in "
        f"{args.source} without changing world semantics."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

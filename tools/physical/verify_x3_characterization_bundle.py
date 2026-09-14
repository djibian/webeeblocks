#!/usr/bin/env python3
"""Verify the complete deterministic X3 characterization bundle manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

MANIFEST_NAME = "MANIFEST.json"
FORMAT = "webeeblocks-x3-characterization-manifest-v1"


class ManifestError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ManifestError("manifest path is invalid")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ManifestError(f"manifest path is unsafe: {value!r}")
    if value == MANIFEST_NAME:
        raise ManifestError("manifest must not list itself")
    return value


def load_manifest(bundle: Path) -> dict[str, tuple[int, str]]:
    manifest_path = bundle / MANIFEST_NAME
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError("bundle manifest is missing or invalid") from exc
    if not isinstance(value, dict) or set(value) != {"format", "files"}:
        raise ManifestError("bundle manifest has unsupported shape")
    if value.get("format") != FORMAT:
        raise ManifestError("bundle manifest format changed")
    rows = value.get("files")
    if not isinstance(rows, list) or not rows:
        raise ManifestError("bundle manifest file list is empty or invalid")

    expected: dict[str, tuple[int, str]] = {}
    previous = ""
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "size", "sha256"}:
            raise ManifestError("bundle manifest file entry has unsupported shape")
        relative = _safe_relative(row.get("path"))
        size = row.get("size")
        digest = row.get("sha256")
        if not isinstance(size, int) or size < 0:
            raise ManifestError(f"manifest size is invalid for {relative}")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ManifestError(f"manifest digest is invalid for {relative}")
        if relative in expected:
            raise ManifestError(f"manifest path is duplicated: {relative}")
        if previous and relative <= previous:
            raise ManifestError("manifest paths are not strictly sorted")
        expected[relative] = (size, digest)
        previous = relative
    return expected


def verify_bundle(bundle: Path) -> None:
    bundle = bundle.resolve()
    if not bundle.is_dir():
        raise ManifestError(f"bundle directory missing: {bundle}")
    expected = load_manifest(bundle)
    actual: dict[str, Path] = {}
    for path in bundle.rglob("*"):
        relative = path.relative_to(bundle).as_posix()
        if path.is_symlink():
            raise ManifestError(f"bundle symlink is not allowed: {relative}")
        if path.is_file() and relative != MANIFEST_NAME:
            actual[relative] = path

    expected_names = set(expected)
    actual_names = set(actual)
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        extra = sorted(actual_names - expected_names)
        raise ManifestError(f"bundle file set mismatch: missing={missing!r} extra={extra!r}")

    for relative in sorted(expected):
        expected_size, expected_digest = expected[relative]
        path = actual[relative]
        observed_size = path.stat().st_size
        if observed_size != expected_size:
            raise ManifestError(
                f"bundle file size mismatch: {relative}: expected {expected_size}, got {observed_size}"
            )
        observed_digest = sha256(path)
        if observed_digest != expected_digest:
            raise ManifestError(f"bundle file digest mismatch: {relative}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args(argv)
    verify_bundle(args.bundle)
    print("PASS: exact X3 characterization bundle manifest verified")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ManifestError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

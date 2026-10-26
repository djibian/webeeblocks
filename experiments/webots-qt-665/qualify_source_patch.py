#!/usr/bin/env python3
"""Offline, fail-closed source-patch prequalification for Webots R2025a (#665).

This is NOT a native Qt test, compiled-binary attestation, or CI Gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

UPSTREAM_COMMIT = "c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b"
ORIGINAL_BLOBS = {
    "src/webots/gui/WbMainWindow.hpp": "53806f899578622f9da956d06e8a2a2ab96c6a98",
    "src/webots/gui/WbMainWindow.cpp": "55e5f8afad696d43ad9be425743861cec73fad21",
    "src/webots/app/WbApplication.cpp": "65dfca226077bd0c0f97f8996d5acd04fc572e57",
}
PATCH = Path(__file__).with_name("webots-r2025a-guarded-progress-retirement.patch")


def git(directory: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(directory), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {process.stderr.strip()}")
    return process.stdout.strip()


def blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def validate(source: Path) -> dict:
    source = source.resolve(strict=True)
    if git(source, "rev-parse", "HEAD") != UPSTREAM_COMMIT:
        raise RuntimeError("Not the pinned upstream Webots R2025a commit; refusing patch check")
    patch = PATCH.read_bytes()
    names = re.findall(
        rb"^diff --git a/([^\s]+) b/([^\s]+)$", patch, re.MULTILINE
    )
    paths = sorted(ORIGINAL_BLOBS)
    if len(names) != len(paths) or sorted(a.decode() for a, b in names if a == b) != paths:
        raise RuntimeError("Unexpected or unmatched patch paths; no oracle or CI edits permitted")
    with tempfile.TemporaryDirectory(prefix="qt665-source-") as temporary:
        trial = Path(temporary)
        git(trial, "init", "-q")
        for name in paths:
            original = (source / name).read_bytes()
            actual = blob(original)
            if actual != ORIGINAL_BLOBS[name]:
                raise RuntimeError(f"Source blob mismatch: {name}: {actual}")
            destination = trial / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, destination)
        git(trial, "apply", "--check", str(PATCH.resolve()))
        git(trial, "apply", str(PATCH.resolve()))
        patched = {name: blob((trial / name).read_bytes()) for name in paths}
        cpp = (trial / "src/webots/gui/WbMainWindow.cpp").read_text()
        app = (trial / "src/webots/app/WbApplication.cpp").read_text()
        if (
            "delete mWorldLoadingProgressDialog;" in cpp
            or "mRetiredWorldLoadingProgressDialogs.append(dialog);" not in cpp
            or "dialog->deleteLater();" not in cpp
            or "runWorldLoadingProgressOperation" not in cpp
            or "dialog->hide();" not in cpp
        ):
            raise RuntimeError("Required guarded-retirement source properties absent")
        if app.count(
            "mWorldLoadingProgressDialogCreated = true;\n    emit createWorldLoadingProgressDialog();"
        ) != 2:
            raise RuntimeError("Both reentrant-creation flags must precede signal emission")
    return {
        "status": "SOURCE_PATCH_APPLIES_ONLY",
        "upstream_commit": UPSTREAM_COMMIT,
        "patch_sha256": hashlib.sha256(patch).hexdigest(),
        "original_blobs": ORIGINAL_BLOBS,
        "patched_blobs": patched,
        "upstream_compilation": "NOT_TESTED",
        "native_qt_ab": "NOT_TESTED",
        "actual_runner_binary_adoption": "NOT_TESTED",
        "canonical_ci_gate": "NOT_TESTED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--webots-tree", type=Path, required=True, help="clean upstream R2025a checkout")
    args = parser.parse_args()
    try:
        print(json.dumps(validate(args.webots_tree), indent=2, sort_keys=True))
    except (OSError, RuntimeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

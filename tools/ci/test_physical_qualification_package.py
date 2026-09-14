#!/usr/bin/env python3
"""Regression oracle for the packaged physical-qualification artifact."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "tools" / "physical" / "verify_physical_qualification_package.py"
RUNNER = ROOT / "tools" / "physical" / "run_packaged_physical_qualification.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "physical-qualification-package.yml"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_verify(bundle: Path, *, success: bool) -> None:
    result = subprocess.run(
        [sys.executable, str(VERIFIER), str(bundle), "--manifest-only"],
        text=True,
        capture_output=True,
    )
    if success and result.returncode != 0:
        raise AssertionError("package verifier unexpectedly failed\n" + result.stdout + result.stderr)
    if not success and result.returncode == 0:
        raise AssertionError("package verifier accepted a mutated package")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args(argv)
    bundle = args.bundle.resolve()

    run_verify(bundle, success=True)

    source_sha = bundle / "SOURCE_SHA"
    original = source_sha.read_bytes()
    try:
        source_sha.write_bytes(original + b"x")
        run_verify(bundle, success=False)
    finally:
        source_sha.write_bytes(original)

    extra = bundle / "unexpected-controller-or-dependency.txt"
    try:
        extra.write_text("unexpected\n", encoding="utf-8")
        run_verify(bundle, success=False)
    finally:
        extra.unlink(missing_ok=True)

    run_verify(bundle, success=True)

    manifest = (bundle / "SHA256SUMS.json").read_text(encoding="utf-8")
    require(
        manifest.count(".whl") == 7,
        "package manifest must contain exactly seven locked wheels",
    )
    require(
        '"execution_authority_packaged": false'
        in (bundle / "PROVENANCE.json").read_text(encoding="utf-8"),
        "package provenance must remain non-authority",
    )

    runner = RUNNER.read_text(encoding="utf-8")
    for required in (
        "--no-index",
        "--no-deps",
        "PYTHONNOUSERSITE=1",
        "PYTHONDONTWRITEBYTECODE=1",
        "verify_physical_qualification_package.py",
        "launch_physical_qualification.py",
        "chmod u+x",
        "WEBOTS_HOME",
        "--version",
        "R2025a",
        '--webots "$WEBOTS_BIN"',
    ):
        require(required in runner, f"offline runner missing contract: {required}")
    for forbidden in ("curl ", "wget ", "http://", "https://"):
        require(forbidden not in runner, f"offline runner must not use network: {forbidden}")

    verifier = VERIFIER.read_text(encoding="utf-8")
    require(
        'env["PYTHONDONTWRITEBYTECODE"] = "1"' in verifier,
        "effect-free package verification must not mutate manifest-covered sources with bytecode",
    )

    workflow = WORKFLOW.read_text(encoding="utf-8")
    for required in (
        "name: CI Physical qualification package",
        "qualification-package-runtime-ubuntu22-cp310-cflib-45fdb784",
        "qualification-package-inputs-r2025a-",
        "python3 tools/physical/package_physical_qualification.py",
        "python3 tools/physical/verify_physical_qualification_package.py",
        "python3 tools/ci/test_physical_qualification_package.py",
        "name: WebeeBlocks-Physical-Qualification",
        "path: ci-artifacts/physical-qualification/WebeeBlocks-Physical-Qualification/",
        "include-hidden-files: true",
    ):
        require(required in workflow, f"package workflow missing contract: {required}")
    require(
        "ci-artifacts/physical-qualification/WebeeBlocks-Physical-Qualification.zip"
        not in workflow,
        "package workflow must not create/upload a nested ZIP",
    )
    require(
        "CHECKPOINT_REQUEST" not in workflow and "TEST_REQUIRED" not in workflow,
        "machine-only package workflow must not open a human checkpoint",
    )
    require(
        workflow.count("github.event.pull_request.draft == true") >= 4,
        "network/cache priming must stay Draft/maintenance-only",
    )
    require("restore-keys:" not in workflow, "package caches must be exact-key only")

    print(
        "PASS: exact offline physical qualification package, mutation rejection and no-checkpoint workflow contract"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

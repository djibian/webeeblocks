#!/usr/bin/env python3
"""Regression oracle for the packaged physical-qualification artifact."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "tools" / "physical" / "verify_physical_qualification_package.py"
PACKAGER = ROOT / "tools" / "physical" / "package_physical_qualification.py"
RUNNER = ROOT / "tools" / "physical" / "run_packaged_physical_qualification.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
WEBOTS_IMAGE_DIGEST = "sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099"


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


def verify_static_contract() -> None:
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
    for required in (
        'env["PYTHONDONTWRITEBYTECODE"] = "1"',
        "_git_tree_oid(cflib_root).hex() != EXPECTED_CFLIB_TREE",
        "runtime.verify_isolated_imports(cflib, locked)",
    ):
        require(required in verifier, f"package verifier missing canonical read-only contract: {required}")

    packager = PACKAGER.read_text(encoding="utf-8")
    for required in (
        '"status", "--porcelain", "--untracked-files=no"',
        '"archive",',
        "EXPECTED_CFLIB_COMMIT",
        "WEBOTS_BUILD_IMAGE_DIGEST",
    ):
        require(required in packager, f"packager missing exact provenance contract: {required}")

    workflow = WORKFLOW.read_text(encoding="utf-8")
    for required in (
        "name: CI Gate",
        "# BEGIN PHYSICAL_QUALIFICATION_RUNTIME_SUPPORT",
        "qualification-runtime-ubuntu22-cp310-cflib-45fdb784",
        "qualification-package-inputs-r2025a-",
        WEBOTS_IMAGE_DIGEST,
        "python3 tools/physical/package_physical_qualification.py",
        "python3 tools/physical/verify_physical_qualification_package.py",
        "python3 tools/ci/test_physical_qualification_package.py",
        "name: WebeeBlocks-Physical-Qualification",
        "path: ci-artifacts/physical-qualification/WebeeBlocks-Physical-Qualification/",
        "include-hidden-files: true",
    ):
        require(required in workflow, f"canonical workflow missing package contract: {required}")
    require(
        "ci-artifacts/physical-qualification/WebeeBlocks-Physical-Qualification.zip"
        not in workflow,
        "package workflow must not create/upload a nested ZIP",
    )
    require(
        "CHECKPOINT_REQUEST" not in workflow and "TEST_REQUIRED" not in workflow,
        "machine-only package path must not open a human checkpoint",
    )
    require(
        workflow.count("github.event.pull_request.draft == true") >= 4,
        "network/cache priming must stay Draft/maintenance-only",
    )
    require("restore-keys:" not in workflow, "package caches must be exact-key only")


def verify_built_bundle(bundle: Path) -> None:
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
    require("/.git/" not in manifest and "/.git\"" not in manifest, "package must omit checkout Git metadata")
    require(not (bundle / "support" / "cflib-source" / ".git").exists(), "canonical cflib source must omit .git")

    provenance = (bundle / "PROVENANCE.json").read_text(encoding="utf-8")
    require(
        '"preparation_execution_authority": false' in provenance,
        "package preparation must remain non-authority",
    )
    require(
        '"execution_requires_teacher_authorization": true' in provenance,
        "packaged execution must retain teacher authorization",
    )
    require(WEBOTS_IMAGE_DIGEST in provenance, "package provenance must bind exact Webots build image")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args(argv)
    bundle = args.bundle.resolve()

    verify_static_contract()
    if bundle.is_dir():
        verify_built_bundle(bundle)
        print(
            "PASS: exact offline physical qualification package, canonical provenance, mutation rejection and no-checkpoint CI contract"
        )
    else:
        print("PASS: physical qualification package static CI contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

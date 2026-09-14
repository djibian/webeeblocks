#!/usr/bin/env python3
"""Verify one packaged offline physical-qualification artifact without effects."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys

EXPECTED_CFLIB_COMMIT = "45fdb784c9d13074c42835f3b5ac1d12133bf873"
EXPECTED_CFLIB_TREE = "a78cf78d2b4aba51a0fa2b03de0260664b523401"
EXPECTED_CFLIB_SUBTREE = "750e850390753de14019f0e1f55d4fbc44317699"
RUNTIME_TARGET = "ubuntu-22.04-python-3.10-x86_64"
MANIFEST_NAME = "SHA256SUMS.json"
PROVENANCE_NAME = "PROVENANCE.json"
SOURCE_SHA_NAME = "SOURCE_SHA"


class QualificationPackageVerificationError(RuntimeError):
    """Fail-closed packaged-artifact verification error."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QualificationPackageVerificationError(f"invalid JSON file: {path.name}") from exc
    if not isinstance(value, dict):
        raise QualificationPackageVerificationError(f"{path.name} must be a JSON object")
    return value


def verify_manifest(bundle: Path) -> dict[str, object]:
    bundle = bundle.resolve()
    manifest = _load_json(bundle / MANIFEST_NAME)
    if manifest.get("format") != "webeeblocks-physical-qualification-manifest-v1":
        raise QualificationPackageVerificationError(
            "unsupported qualification package manifest format"
        )
    files = manifest.get("files")
    if not isinstance(files, list):
        raise QualificationPackageVerificationError("manifest files must be a list")

    expected: dict[str, tuple[int, str]] = {}
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "size", "sha256"}:
            raise QualificationPackageVerificationError(
                "manifest file entry has unsupported shape"
            )
        relative = item.get("path")
        size = item.get("size")
        digest = item.get("sha256")
        if (
            not isinstance(relative, str)
            or not relative
            or relative.startswith("/")
            or ".." in Path(relative).parts
            or relative == MANIFEST_NAME
        ):
            raise QualificationPackageVerificationError("manifest contains unsafe file path")
        if relative in expected:
            raise QualificationPackageVerificationError("manifest contains duplicate file path")
        if not isinstance(size, int) or size < 0:
            raise QualificationPackageVerificationError("manifest contains invalid file size")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise QualificationPackageVerificationError("manifest contains invalid sha256")
        expected[relative] = (size, digest)

    actual = {
        path.relative_to(bundle).as_posix(): path
        for path in bundle.rglob("*")
        if path.is_file()
        and path.relative_to(bundle).as_posix() != MANIFEST_NAME
        and not path.relative_to(bundle).as_posix().startswith(".runtime/")
    }
    if set(actual) != set(expected):
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        raise QualificationPackageVerificationError(
            f"qualification package is not exact; missing={missing!r} extra={extra!r}"
        )

    for relative, path in actual.items():
        if path.is_symlink():
            raise QualificationPackageVerificationError(
                f"symlink is not allowed in package: {relative}"
            )
        expected_size, expected_digest = expected[relative]
        if path.stat().st_size != expected_size:
            raise QualificationPackageVerificationError(f"size mismatch: {relative}")
        if sha256_file(path) != expected_digest:
            raise QualificationPackageVerificationError(f"sha256 mismatch: {relative}")

    return manifest


def verify_provenance(bundle: Path) -> dict[str, object]:
    provenance = _load_json(bundle / PROVENANCE_NAME)
    required = {
        "format",
        "source_sha",
        "runtime_target",
        "cflib",
        "qualification_runtime_lock_sha256",
        "wheel_count",
        "blockly_version",
        "webots_version",
        "execution_authority_packaged",
    }
    if set(provenance) != required:
        raise QualificationPackageVerificationError(
            "qualification provenance has unsupported fields"
        )
    if provenance.get("format") != "webeeblocks-physical-qualification-provenance-v1":
        raise QualificationPackageVerificationError("unsupported qualification provenance format")
    source_sha = provenance.get("source_sha")
    if not isinstance(source_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise QualificationPackageVerificationError(
            "qualification provenance source SHA is invalid"
        )
    source_file = (bundle / SOURCE_SHA_NAME).read_text(encoding="utf-8").strip()
    if source_file != source_sha:
        raise QualificationPackageVerificationError(
            "SOURCE_SHA disagrees with qualification provenance"
        )
    if provenance.get("runtime_target") != RUNTIME_TARGET:
        raise QualificationPackageVerificationError("qualification runtime target changed")
    if (
        provenance.get("blockly_version") != "13.2.1"
        or provenance.get("webots_version") != "R2025a"
    ):
        raise QualificationPackageVerificationError(
            "prepared browser/Webots provenance changed"
        )
    if provenance.get("execution_authority_packaged") is not False:
        raise QualificationPackageVerificationError("package must not claim execution authority")
    cflib = provenance.get("cflib")
    if cflib != {
        "commit": EXPECTED_CFLIB_COMMIT,
        "tree": EXPECTED_CFLIB_TREE,
        "subtree": EXPECTED_CFLIB_SUBTREE,
    }:
        raise QualificationPackageVerificationError("cflib provenance changed")
    if provenance.get("wheel_count") != 7:
        raise QualificationPackageVerificationError(
            "qualification package must contain exactly seven wheels"
        )

    lock = bundle / "tools" / "physical" / "qualification_runtime_lock.txt"
    if sha256_file(lock) != provenance.get("qualification_runtime_lock_sha256"):
        raise QualificationPackageVerificationError(
            "qualification runtime lock digest changed"
        )
    return provenance


def verify_required_runtime_files(bundle: Path) -> None:
    required = (
        "tools/physical/launch_physical_qualification.py",
        "tools/physical/serve_physical_host.py",
        "tools/physical/physical_qualification_runtime.js",
        "tools/physical/run_packaged_physical_qualification.sh",
        "plugins/robot_windows/blockly_v2/blockly_v2.html",
        "plugins/robot_windows/blockly_v2/vendor/VERSION",
        "plugins/robot_windows/blockly_v2/vendor/blockly_compressed.js",
        "plugins/robot_windows/blockly_v2/vendor/blocks_compressed.js",
        "plugins/robot_windows/blockly_v2/vendor/msg/fr.js",
        "plugins/robot_windows/blockly/webeeblocks/semantic_ast.js",
        "plugins/robot_windows/blockly/webeeblocks/physical_submission_bridge.js",
        "plugins/robot_windows/blockly/google-blockly-31ee4ea/blocks/crazyflie_v2.js",
        "worlds/crazyflie_runtime_v2.wbt",
        "controllers/crazyflie_runtime_v2/crazyflie_runtime_v2",
        "support/cflib-source/cflib/__init__.py",
    )
    for relative in required:
        if not (bundle / relative).is_file():
            raise QualificationPackageVerificationError(
                f"required packaged file missing: {relative}"
            )

    if (
        bundle / "plugins/robot_windows/blockly_v2/vendor/VERSION"
    ).read_text(encoding="utf-8").strip() != "13.2.1":
        raise QualificationPackageVerificationError("packaged Blockly version is not 13.2.1")

    world = (bundle / "worlds/crazyflie_runtime_v2.wbt").read_text(encoding="utf-8")
    if "raw.githubusercontent.com/cyberbotics/webots/" in world:
        raise QualificationPackageVerificationError(
            "packaged world retains a remote Cyberbotics URL"
        )
    if world.count("webots://") != 4:
        raise QualificationPackageVerificationError(
            "packaged world does not use exact R2025a webots:// closure"
        )

    controller = bundle / "controllers/crazyflie_runtime_v2/crazyflie_runtime_v2"
    if controller.read_bytes()[:4] != b"\x7fELF":
        raise QualificationPackageVerificationError(
            "packaged Runtime v2 controller is not ELF"
        )


def verify_runtime_closure(bundle: Path) -> None:
    if sys.version_info[:2] != (3, 10):
        raise QualificationPackageVerificationError(
            f"Python 3.10 required, got {sys.version.split()[0]}"
        )
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise QualificationPackageVerificationError(
            f"Linux x86_64 required, got {platform.system()} {platform.machine()}"
        )
    verifier = bundle / "tools" / "physical" / "verify_qualification_runtime.py"
    try:
        subprocess.run(
            [
                sys.executable,
                str(verifier),
                str(bundle / "support" / "cflib-source"),
                str(bundle / "support" / "wheels"),
            ],
            check=True,
            cwd=bundle,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise QualificationPackageVerificationError(
            "packaged qualification runtime closure failed effect-free verification"
        ) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify deterministic offline physical qualification bundle"
    )
    parser.add_argument("bundle", type=Path)
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="verify package bytes/provenance without reinstalling the locked runtime",
    )
    args = parser.parse_args(argv)

    bundle = args.bundle.resolve()
    verify_manifest(bundle)
    verify_provenance(bundle)
    verify_required_runtime_files(bundle)
    if not args.manifest_only:
        verify_runtime_closure(bundle)
    print("PASS: exact offline physical qualification package verified without hardware")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except QualificationPackageVerificationError as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        raise SystemExit(1)

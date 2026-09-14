#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
PACKAGER_PATH = PHYSICAL / "package_physical_qualification.py"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "ci.yml"

sys.path.insert(0, str(PHYSICAL))
spec = importlib.util.spec_from_file_location("package_physical_qualification", PACKAGER_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load physical qualification bundle packager")
packager = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = packager
spec.loader.exec_module(packager)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_bundle_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except packager.QualificationBundleError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError(f"expected QualificationBundleError containing {pattern!r}")


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def main() -> int:
    source = PACKAGER_PATH.read_text(encoding="utf-8")
    for required in (
        "runtime.verify_cflib_provenance(cflib_root)",
        "runtime.verify_wheelhouse(entries, wheelhouse)",
        '"sourceSha": source_sha',
        '"executionAuthority": False',
        '"launcher": "tools/physical/launch_physical_qualification.py"',
        'gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0)',
        'git", "-C", str(source_root), "archive"',
    ):
        require(required in source, f"missing exact bundle contract: {required}")

    runner = packager._runner_text()
    for required in (
        "Python 3.10 requis",
        "Linux x86_64 requis",
        "verify_qualification_runtime.py",
        "--no-index --no-deps --ignore-installed",
        "PYTHONNOUSERSITE=1",
        "python3:$cflib:$SITE" if False else "$ROOT/tools/physical:$cflib:$SITE",
        " -S ",
        "launch_physical_qualification.py",
    ):
        require(required in runner, f"offline runner contract is missing: {required}")

    with tempfile.TemporaryDirectory(prefix="webeeblocks-bundle-test-") as temp_text:
        temp = Path(temp_text)
        staged = temp / "stage"
        staged.mkdir()
        (staged / "alpha.txt").write_text("alpha\n", encoding="utf-8")
        nested = staged / "nested"
        nested.mkdir()
        executable = nested / "runner.sh"
        executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        executable.chmod(0o755)

        archive_one = temp / "one.tar.gz"
        archive_two = temp / "two.tar.gz"
        packager._write_archive(staged, archive_one)
        packager._write_archive(staged, archive_two)
        require(
            packager._sha256(archive_one) == packager._sha256(archive_two),
            "identical staged content must produce byte-identical qualification archives",
        )
        with tarfile.open(archive_one, "r:gz") as bundle:
            members = {member.name: member for member in bundle.getmembers()}
        require(packager.BUNDLE_ROOT in members, "bundle root directory is missing")
        require(
            f"{packager.BUNDLE_ROOT}/alpha.txt" in members
            and f"{packager.BUNDLE_ROOT}/nested/runner.sh" in members,
            "bundle archive omitted staged content",
        )
        for member in members.values():
            require(member.mtime == 0, "bundle tar metadata must have normalized mtime")
            require(member.uid == 0 and member.gid == 0, "bundle tar ownership must be normalized")
        require(
            members[f"{packager.BUNDLE_ROOT}/nested/runner.sh"].mode == 0o755,
            "runner executable bit must survive normalized archive creation",
        )

        manifest_root = temp / "manifest"
        manifest_root.mkdir()
        wheels = (
            {"spec": "example==1", "filename": "example.whl", "sha256": "0" * 64},
        )
        packager._write_manifest(manifest_root, "a" * 40, wheels)
        manifest = json.loads((manifest_root / packager.MANIFEST_NAME).read_text(encoding="utf-8"))
        require(manifest["sourceSha"] == "a" * 40, "manifest must bind exact WebeeBlocks SHA")
        require(manifest["executionAuthority"] is False, "bundle preparation must remain non-authority")
        require(
            manifest["cflib"]
            == {
                "commit": packager.runtime.EXPECTED_CFLIB_COMMIT,
                "tree": packager.runtime.EXPECTED_CFLIB_TREE,
                "subtree": packager.runtime.EXPECTED_CFLIB_SUBTREE,
            },
            "manifest must bind exact cflib provenance",
        )
        require(manifest["wheels"] == list(wheels), "manifest must preserve exact locked wheel evidence")
        require((manifest_root / packager.RUNNER_NAME).stat().st_mode & 0o111, "bundle runner must be executable")

        git_root = temp / "git-source"
        git_root.mkdir()
        subprocess.run(["git", "init", "-q", str(git_root)], check=True)
        subprocess.run(["git", "-C", str(git_root), "config", "user.email", "ci@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(git_root), "config", "user.name", "CI"], check=True)
        (git_root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(git_root), "add", "tracked.txt"], check=True)
        subprocess.run(["git", "-C", str(git_root), "commit", "-q", "-m", "fixture"], check=True)
        sha = _git(git_root, "rev-parse", "HEAD")
        require(packager._validate_source(git_root, sha) == sha, "exact clean source SHA must validate")
        expect_bundle_error(
            lambda: packager._validate_source(git_root, "0" * 40),
            "source HEAD does not match requested bundle SHA",
        )
        (git_root / "tracked.txt").write_text("dirty\n", encoding="utf-8")
        expect_bundle_error(
            lambda: packager._validate_source(git_root, sha),
            "tracked WebeeBlocks source tree is not clean",
        )

    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    for required in (
        "Package exact physical qualification bundle",
        "Verify exact physical qualification bundle",
        "Upload exact physical qualification bundle",
        "python3 tools/physical/package_physical_qualification.py",
        "WebeeBlocks-Physical-Qualification.tar.gz",
        "Run-Physical-Qualification.sh",
        "actions/upload-artifact@v4",
        "python3 tools/ci/test_physical_qualification_bundle.py",
    ):
        require(required in workflow, f"workflow is missing physical qualification bundle proof: {required}")

    print("PASS: exact offline physical qualification bundle packaging contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

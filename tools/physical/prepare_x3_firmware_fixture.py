#!/usr/bin/env python3
"""Prepare or verify the exact cached #251 X3 firmware fixture.

The fixture is generated only during authorized maintenance/Draft CI when the
exact qualification runtime cache is being primed. Ready acceptance never falls
back to network acquisition or a mutable builder image: it must consume the
already-restored exact fixture and verify its digest.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SUPPORT_ROOT = ROOT / ".ci-support" / "qualification-runtime" / "x3-firmware"
FIXTURE = SUPPORT_ROOT / "cf2.bin"
PROVENANCE = SUPPORT_ROOT / "PROVENANCE.txt"
EXPECTED_REQUEST_SOURCE_SHA = "6562ad827bf0c8bf2c9b609edad36f3e15652133"
EXPECTED_FIRMWARE_SHA256 = "67d71f2fc74c06001bb141ed6206b0d06df23497a48f498531c3aba192f0b738"
UPSTREAM_FIRMWARE_REPOSITORY = "https://github.com/bitcraze/crazyflie-firmware.git"
UPSTREAM_FIRMWARE_COMMIT = "54f31e243a0b28b67efef5ba20dbb6d9890a5478"
S3_ORACLE = ROOT / "experiments" / "crazyflie-ukf-surface-range" / "run_s3_build_oracle.sh"
BUILDER_IMAGE = "bitcraze/builder:latest"


class FixtureError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def maintenance_allowed(
    *,
    github_actions: str,
    event_name: str,
    draft: bool | None,
    head_repo: str,
    repository: str,
) -> bool:
    if github_actions != "true":
        return False
    if event_name == "pull_request":
        return draft is True and bool(repository) and head_repo == repository
    return event_name in {"schedule", "workflow_dispatch"}


def maintenance_allowed_from_environment() -> bool:
    github_actions = os.environ.get("GITHUB_ACTIONS", "")
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if event_name != "pull_request":
        return maintenance_allowed(
            github_actions=github_actions,
            event_name=event_name,
            draft=None,
            head_repo="",
            repository=repository,
        )

    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not event_path:
        return False
    try:
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    pull_request = event.get("pull_request") or {}
    head_repo = (((pull_request.get("head") or {}).get("repo") or {}).get("full_name") or "")
    return maintenance_allowed(
        github_actions=github_actions,
        event_name=event_name,
        draft=pull_request.get("draft"),
        head_repo=head_repo,
        repository=repository,
    )


def _expected_provenance() -> str:
    return "\n".join(
        (
            "schema=webeeblocks.x3.firmware-fixture.v1",
            f"request_source_sha={EXPECTED_REQUEST_SOURCE_SHA}",
            f"upstream_firmware_commit={UPSTREAM_FIRMWARE_COMMIT}",
            f"cf2_bin_sha256={EXPECTED_FIRMWARE_SHA256}",
            "physical_effect=none",
            "firmware_flash=not-performed",
            "execution_authority=none",
            "",
        )
    )


def verify_fixture() -> None:
    if not FIXTURE.is_file():
        raise FixtureError("exact #251 X3 firmware fixture is missing")
    if sha256(FIXTURE) != EXPECTED_FIRMWARE_SHA256:
        raise FixtureError("cached X3 firmware fixture digest changed")
    try:
        provenance = PROVENANCE.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise FixtureError("cached X3 firmware fixture provenance is missing") from exc
    if provenance != _expected_provenance():
        raise FixtureError("cached X3 firmware fixture provenance changed")


def _clone_exact_firmware(destination: Path) -> None:
    subprocess.run(["git", "init", str(destination)], check=True)
    subprocess.run(
        ["git", "-C", str(destination), "remote", "add", "origin", UPSTREAM_FIRMWARE_REPOSITORY],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(destination), "fetch", "--depth=1", "origin", UPSTREAM_FIRMWARE_COMMIT],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(destination), "checkout", "--detach", "FETCH_HEAD"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(destination), "submodule", "update", "--init", "--recursive", "--depth=1"],
        check=True,
    )
    resolved = subprocess.run(
        ["git", "-C", str(destination), "rev-parse", "HEAD"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    if resolved != UPSTREAM_FIRMWARE_COMMIT:
        raise FixtureError("X3 firmware maintenance checkout resolved to unexpected commit")


def _restore_ownership(firmware_root: Path) -> None:
    if not firmware_root.exists():
        return
    image = subprocess.run(
        ["docker", "image", "inspect", BUILDER_IMAGE],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if image.returncode != 0:
        return
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--user",
            "0:0",
            "-v",
            f"{firmware_root}:/module",
            BUILDER_IMAGE,
            "bash",
            "-lc",
            f"chown -R {os.getuid()}:{os.getgid()} /module",
        ],
        check=True,
    )


def prepare_fixture() -> None:
    if FIXTURE.exists() or PROVENANCE.exists():
        verify_fixture()
        return
    if not maintenance_allowed_from_environment():
        raise FixtureError(
            "exact #251 X3 firmware fixture cache is missing outside an authorized maintenance run"
        )

    with tempfile.TemporaryDirectory(prefix="webeeblocks-x3-fixture-") as temp_text:
        firmware_root = Path(temp_text) / "crazyflie-firmware"
        _clone_exact_firmware(firmware_root)
        try:
            subprocess.run(["bash", str(S3_ORACLE), str(firmware_root)], cwd=ROOT, check=True)
            built = firmware_root / "build" / "cf2.bin"
            if not built.is_file() or sha256(built) != EXPECTED_FIRMWARE_SHA256:
                raise FixtureError("maintenance build did not reproduce exact #251 cf2.bin")
            SUPPORT_ROOT.mkdir(parents=True, exist_ok=False)
            shutil.copy2(built, FIXTURE)
            PROVENANCE.write_text(_expected_provenance(), encoding="utf-8")
            verify_fixture()
        finally:
            _restore_ownership(firmware_root)


def main() -> int:
    try:
        prepare_fixture()
    except (OSError, subprocess.CalledProcessError, FixtureError) as exc:
        print(f"FAIL: {exc}")
        return 1
    print(f"PASS: exact cached #251 X3 firmware fixture verified: {EXPECTED_FIRMWARE_SHA256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

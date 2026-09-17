#!/usr/bin/env python3
"""Verify exact deterministic generated inputs used by physical qualification packaging."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOCK = Path(__file__).with_name("qualification_generated_lock.json")
DEFAULT_VENDOR = ROOT / "plugins" / "robot_windows" / "blockly_v2" / "vendor"
DEFAULT_CONTROLLER = ROOT / "controllers" / "crazyflie_runtime_v2" / "crazyflie_runtime_v2"
FORMAT = "webeeblocks-qualification-generated-lock-v1"
ALGORITHM = "sha256-path-size-sha256-v1"
CANONICAL_CI_WORKFLOW = "CI Gate"
EXPECTED_WEBOTS_IMAGE = (
    "cyberbotics/webots@sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099"
)
EXPECTED_WEBOTS_CACHE_MEMBER = (
    "plugins/robot_windows/blockly_v2/vendor/.qualification-webots-r2025a-image.tar"
)


class QualificationGeneratedInputError(RuntimeError):
    """Fail-closed generated-input verification error."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def vendor_closure(vendor: Path) -> tuple[int, str]:
    vendor = vendor.resolve()
    if not vendor.is_dir():
        raise QualificationGeneratedInputError(f"generated vendor directory missing: {vendor}")
    files: list[tuple[str, int, str]] = []
    for path in vendor.rglob("*"):
        if path.is_symlink():
            raise QualificationGeneratedInputError(
                f"generated vendor symlink is not allowed: {path.relative_to(vendor).as_posix()}"
            )
        if not path.is_file():
            continue
        relative = path.relative_to(vendor).as_posix()
        files.append((relative, path.stat().st_size, sha256_file(path)))
    digest = hashlib.sha256()
    for relative, size, file_digest in sorted(files):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(size).encode("ascii"))
        digest.update(b"\0")
        digest.update(file_digest.encode("ascii"))
        digest.update(b"\n")
    return len(files), digest.hexdigest()


def load_lock(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QualificationGeneratedInputError(f"invalid generated-input lock: {path}") from exc
    if not isinstance(value, dict) or set(value) != {
        "format",
        "vendor",
        "controller",
        "webots_image_support",
    }:
        raise QualificationGeneratedInputError("generated-input lock has unsupported shape")
    if value.get("format") != FORMAT:
        raise QualificationGeneratedInputError("generated-input lock format changed")
    vendor = value.get("vendor")
    controller = value.get("controller")
    support = value.get("webots_image_support")
    if not isinstance(vendor, dict) or set(vendor) != {"algorithm", "file_count", "sha256"}:
        raise QualificationGeneratedInputError("generated vendor lock has unsupported shape")
    if vendor.get("algorithm") != ALGORITHM:
        raise QualificationGeneratedInputError("generated vendor lock algorithm changed")
    if not isinstance(vendor.get("file_count"), int) or vendor["file_count"] < 1:
        raise QualificationGeneratedInputError("generated vendor lock file count is invalid")
    if not isinstance(vendor.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", vendor["sha256"]):
        raise QualificationGeneratedInputError("generated vendor lock digest is invalid")
    if not isinstance(controller, dict) or set(controller) != {"path", "size", "sha256"}:
        raise QualificationGeneratedInputError("generated controller lock has unsupported shape")
    if controller.get("path") != "controllers/crazyflie_runtime_v2/crazyflie_runtime_v2":
        raise QualificationGeneratedInputError("generated controller lock path changed")
    if not isinstance(controller.get("size"), int) or controller["size"] < 1:
        raise QualificationGeneratedInputError("generated controller lock size is invalid")
    if not isinstance(controller.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", controller["sha256"]):
        raise QualificationGeneratedInputError("generated controller lock digest is invalid")
    if not isinstance(support, dict) or set(support) != {"cache_member", "image"}:
        raise QualificationGeneratedInputError("Webots image support lock has unsupported shape")
    if support.get("image") != EXPECTED_WEBOTS_IMAGE:
        raise QualificationGeneratedInputError("Webots image support digest changed")
    if support.get("cache_member") != EXPECTED_WEBOTS_CACHE_MEMBER:
        raise QualificationGeneratedInputError("Webots image support cache member changed")
    return value


def verify_generated_inputs(vendor: Path, controller: Path, lock_path: Path = DEFAULT_LOCK) -> None:
    lock = load_lock(lock_path)
    vendor_lock = lock["vendor"]
    controller_lock = lock["controller"]
    assert isinstance(vendor_lock, dict)
    assert isinstance(controller_lock, dict)

    count, digest = vendor_closure(vendor)
    if count != vendor_lock["file_count"] or digest != vendor_lock["sha256"]:
        raise QualificationGeneratedInputError(
            f"generated vendor closure changed: count={count} sha256={digest}"
        )

    controller = controller.resolve()
    if not controller.is_file() or controller.is_symlink():
        raise QualificationGeneratedInputError(f"generated controller missing or unsupported: {controller}")
    size = controller.stat().st_size
    digest = sha256_file(controller)
    if size != controller_lock["size"] or digest != controller_lock["sha256"]:
        raise QualificationGeneratedInputError(
            f"generated controller changed: size={size} sha256={digest}"
        )


def _canonical_ci() -> bool:
    return (
        os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_WORKFLOW") == CANONICAL_CI_WORKFLOW
    )


def _maintenance_context() -> bool:
    if not _canonical_ci():
        return False
    if os.environ.get("GITHUB_EVENT_NAME") != "pull_request":
        return True
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        raise QualificationGeneratedInputError("canonical PR event payload is unavailable")
    try:
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QualificationGeneratedInputError("canonical PR event payload is invalid") from exc
    pull_request = event.get("pull_request")
    if not isinstance(pull_request, dict):
        raise QualificationGeneratedInputError("canonical PR event lacks pull_request")
    head = pull_request.get("head")
    head_repo = head.get("repo") if isinstance(head, dict) else None
    head_full_name = head_repo.get("full_name") if isinstance(head_repo, dict) else None
    return bool(pull_request.get("draft")) and head_full_name == os.environ.get("GITHUB_REPOSITORY")


def _run_docker(args: list[str], *, purpose: str) -> None:
    try:
        result = subprocess.run(
            ["docker", *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise QualificationGeneratedInputError(f"{purpose} could not execute") from exc
    if result.returncode != 0:
        raise QualificationGeneratedInputError(
            f"{purpose} failed: {result.stdout[-4000:]}"
        )


def _support_tar(vendor: Path, lock: dict[str, object]) -> Path:
    support = lock["webots_image_support"]
    assert isinstance(support, dict)
    member = Path(str(support["cache_member"]))
    if member.parent.as_posix() != "plugins/robot_windows/blockly_v2/vendor":
        raise QualificationGeneratedInputError("Webots image support cache location escaped vendor cache")
    return vendor.resolve() / member.name


def _consume_or_sanitize_support(vendor: Path, lock: dict[str, object]) -> None:
    support_tar = _support_tar(vendor, lock)
    if not support_tar.exists():
        if _canonical_ci() and not _maintenance_context():
            raise QualificationGeneratedInputError(
                "exact cached Webots R2025a image support is missing in canonical Ready CI"
            )
        return
    if not support_tar.is_file() or support_tar.is_symlink():
        raise QualificationGeneratedInputError("Webots image support cache member is unsupported")
    if _canonical_ci():
        _run_docker(["load", "--input", str(support_tar)], purpose="cached Webots image load")
        _run_docker(["image", "inspect", EXPECTED_WEBOTS_IMAGE], purpose="exact Webots image verification")
    support_tar.unlink()


def _prime_support_after_verification(vendor: Path, lock: dict[str, object]) -> None:
    if not _maintenance_context():
        return
    support_tar = _support_tar(vendor, lock)
    if support_tar.exists():
        raise QualificationGeneratedInputError("Webots image support cache member unexpectedly survived verification")
    _run_docker(["image", "inspect", EXPECTED_WEBOTS_IMAGE], purpose="maintenance Webots image verification")
    temporary = support_tar.with_name(support_tar.name + ".tmp")
    temporary.unlink(missing_ok=True)
    _run_docker(["save", "--output", str(temporary), EXPECTED_WEBOTS_IMAGE], purpose="maintenance Webots image export")
    if not temporary.is_file() or temporary.stat().st_size < 1024 * 1024:
        temporary.unlink(missing_ok=True)
        raise QualificationGeneratedInputError("maintenance Webots image export is unexpectedly small")
    temporary.replace(support_tar)
    print("PASS: exact pinned Webots R2025a image support primed for Draft/maintenance cache")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify locked qualification generated inputs")
    parser.add_argument("--vendor", type=Path, default=DEFAULT_VENDOR)
    parser.add_argument("--controller", type=Path, default=DEFAULT_CONTROLLER)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    args = parser.parse_args(argv)
    lock = load_lock(args.lock)
    support_tar = _support_tar(args.vendor, lock)
    prime = _maintenance_context() and not support_tar.exists()
    if not prime:
        _consume_or_sanitize_support(args.vendor, lock)
    verify_generated_inputs(args.vendor, args.controller, args.lock)
    if prime:
        _prime_support_after_verification(args.vendor, lock)
    print("PASS: exact locked qualification generated inputs verified")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except QualificationGeneratedInputError as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        raise SystemExit(1)

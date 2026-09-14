#!/usr/bin/env python3
"""Verify exact deterministic generated inputs used by physical qualification packaging."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOCK = Path(__file__).with_name("qualification_generated_lock.json")
DEFAULT_VENDOR = ROOT / "plugins" / "robot_windows" / "blockly_v2" / "vendor"
DEFAULT_CONTROLLER = ROOT / "controllers" / "crazyflie_runtime_v2" / "crazyflie_runtime_v2"
FORMAT = "webeeblocks-qualification-generated-lock-v1"
ALGORITHM = "sha256-path-size-sha256-v1"


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
    if not isinstance(value, dict) or set(value) != {"format", "vendor", "controller"}:
        raise QualificationGeneratedInputError("generated-input lock has unsupported shape")
    if value.get("format") != FORMAT:
        raise QualificationGeneratedInputError("generated-input lock format changed")
    vendor = value.get("vendor")
    controller = value.get("controller")
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify locked qualification generated inputs")
    parser.add_argument("--vendor", type=Path, default=DEFAULT_VENDOR)
    parser.add_argument("--controller", type=Path, default=DEFAULT_CONTROLLER)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    args = parser.parse_args(argv)
    verify_generated_inputs(args.vendor, args.controller, args.lock)
    print("PASS: exact locked qualification generated inputs verified")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except QualificationGeneratedInputError as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        raise SystemExit(1)

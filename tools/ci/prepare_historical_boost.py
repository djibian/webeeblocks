#!/usr/bin/env python3
"""Prepare the exact Boost 1.74 header closure used by historical Webots CI.

This helper deliberately does not use apt metadata, ambient package resolution or
network download fallback.  It accepts only one already-provisioned exact Ubuntu
Jammy archive, verifies byte size and SHA-256, extracts it with dpkg-deb, and
verifies the Boost version header before exposing it to the pinned Webots R2025a
build container.  A missing support archive fails closed.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

PACKAGE_NAME = "libboost1.74-dev_1.74.0-14ubuntu3_amd64.deb"
PACKAGE_SIZE = 9_608_510
PACKAGE_SHA256 = "4d9c90e43f0d25db6280d1ee326771cbb76462f73b9430f06bac1de8d05b7a78"
BOOST_VERSION = 107400


class SupportError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_archive(path: Path) -> None:
    if not path.is_file():
        raise SupportError("pinned Boost archive is missing")
    if path.stat().st_size != PACKAGE_SIZE:
        raise SupportError("pinned Boost archive size mismatch")
    if sha256(path) != PACKAGE_SHA256:
        raise SupportError("pinned Boost archive SHA-256 mismatch")


def verify_tree(root: Path) -> None:
    header = root / "usr/include/boost/version.hpp"
    if not header.is_file():
        raise SupportError("extracted Boost version header is missing")
    match = re.search(r"^#define BOOST_VERSION\s+(\d+)\s*$", header.read_text(), re.MULTILINE)
    if match is None or int(match.group(1)) != BOOST_VERSION:
        raise SupportError("extracted Boost version is not exactly 1.74.0")


def prepare(output: Path, archive: Path | None = None) -> Path:
    output = output.resolve()
    package = archive.resolve() if archive is not None else output.parent / PACKAGE_NAME
    verify_archive(package)

    if output.exists():
        verify_tree(output)
        return output

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=output.name + ".", dir=output.parent))
    try:
        subprocess.run(["dpkg-deb", "-x", str(package), str(temporary)], check=True)
        verify_tree(temporary)
        temporary.replace(output)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(".ci-support/boost-1.74"))
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    try:
        root = prepare(args.output, args.archive)
    except (OSError, SupportError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"FAIL pinned historical Boost closure: {exc}") from exc
    print(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

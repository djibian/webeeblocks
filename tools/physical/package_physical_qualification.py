#!/usr/bin/env python3
"""Build one deterministic offline bundle for later physical qualification.

This packager is machine-only.  It verifies the already-pinned qualification
runtime inputs, copies only repository-controlled/runtime inputs into a
repository-shaped bundle, localizes the pinned Webots world to webots://, and
writes a complete SHA-256 manifest.  It never opens Crazyradio, starts Webots,
creates execution authority, or emits a physical effect.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

from verify_qualification_runtime import (
    EXPECTED_CFLIB_COMMIT,
    EXPECTED_CFLIB_TREE,
    EXPECTED_CFLIB_SUBTREE,
    parse_lock,
    verify_cflib_provenance,
    verify_wheelhouse,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REMOTE_WEBOTS_PREFIX = "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/"
LOCAL_WEBOTS_PREFIX = "webots://"
EXPECTED_WORLD_REMOTE_REFS = 4
BUNDLE_NAME = "WebeeBlocks-Physical-Qualification"
MANIFEST_NAME = "SHA256SUMS.json"
PROVENANCE_NAME = "PROVENANCE.json"
SOURCE_SHA_NAME = "SOURCE_SHA"
RUNTIME_TARGET = "ubuntu-22.04-python-3.10-x86_64"

SHARED_WEBEEBLOCKS = REPO_ROOT / "plugins" / "robot_windows" / "blockly" / "webeeblocks"
GOOGLE_BLOCK = (
    REPO_ROOT
    / "plugins"
    / "robot_windows"
    / "blockly"
    / "google-blockly-31ee4ea"
    / "blocks"
    / "crazyflie_v2.js"
)


class QualificationPackageError(RuntimeError):
    """Fail-closed offline qualification package error."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_source_sha(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise QualificationPackageError("exact lowercase 40-character source SHA required")
    try:
        observed = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise QualificationPackageError("repository HEAD is unavailable") from exc
    if observed != value:
        raise QualificationPackageError(
            f"source SHA does not match checkout HEAD: expected {value}, got {observed}"
        )
    return value


def _copy_tree(source: Path, target: Path, *, ignore_names: set[str] | None = None) -> None:
    if not source.is_dir():
        raise QualificationPackageError(f"required directory missing: {source}")
    ignored = ignore_names or set()

    def ignore(_directory: str, names: list[str]) -> set[str]:
        return {
            name
            for name in names
            if name in ignored or name == "__pycache__" or name.endswith(".pyc")
        }

    shutil.copytree(source, target, symlinks=False, ignore=ignore)


def _copy_file(source: Path, target: Path) -> None:
    if not source.is_file():
        raise QualificationPackageError(f"required file missing: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _verify_prepared_runtime() -> None:
    plugin = REPO_ROOT / "plugins" / "robot_windows" / "blockly_v2"
    required = (
        plugin / "blockly_v2.html",
        plugin / "main.js",
        plugin / "physical_preflight_runtime.js",
        plugin / "webots" / "RobotWindow.js",
        plugin / "vendor" / "blockly_compressed.js",
        plugin / "vendor" / "blocks_compressed.js",
        plugin / "vendor" / "msg" / "fr.js",
        plugin / "vendor" / "media",
    )
    for path in required:
        if not path.exists():
            raise QualificationPackageError(
                "Runtime v2 assets are incomplete; run tools/prepare_runtime_v2.sh first: "
                + str(path)
            )
    version = plugin / "vendor" / "VERSION"
    if not version.is_file() or version.read_text(encoding="utf-8").strip() != "13.2.1":
        raise QualificationPackageError("prepared Runtime v2 must be exact Blockly 13.2.1")


def _localize_world(source: Path, target: Path) -> None:
    text = source.read_text(encoding="utf-8")
    count = text.count(REMOTE_WEBOTS_PREFIX)
    if count != EXPECTED_WORLD_REMOTE_REFS:
        raise QualificationPackageError(
            f"expected {EXPECTED_WORLD_REMOTE_REFS} pinned Webots R2025a world references, found {count}"
        )
    localized = text.replace(REMOTE_WEBOTS_PREFIX, LOCAL_WEBOTS_PREFIX)
    if "raw.githubusercontent.com/cyberbotics/webots/" in localized:
        raise QualificationPackageError("remote Cyberbotics reference remains after localization")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(localized, encoding="utf-8")


def _copy_controller(bundle: Path) -> None:
    source = REPO_ROOT / "controllers" / "crazyflie_runtime_v2"
    binary = source / "crazyflie_runtime_v2"
    if not binary.is_file():
        raise QualificationPackageError(
            "Linux Runtime v2 controller binary is missing; build it with Webots R2025a before packaging"
        )
    if not (binary.stat().st_mode & stat.S_IXUSR):
        raise QualificationPackageError("Runtime v2 controller binary is not executable")
    with binary.open("rb") as stream:
        if stream.read(4) != b"\x7fELF":
            raise QualificationPackageError("Runtime v2 controller is not an ELF executable")

    target = bundle / "controllers" / "crazyflie_runtime_v2"
    target.mkdir(parents=True, exist_ok=True)
    for path in sorted(source.iterdir()):
        if path.name == "__pycache__" or path.suffix in {".o", ".d"}:
            continue
        if path.is_file() and (
            path.name == "crazyflie_runtime_v2"
            or path.name == "Makefile"
            or path.suffix in {".c", ".cc", ".cpp", ".h", ".hpp"}
        ):
            _copy_file(path, target / path.name)

    pid_source = REPO_ROOT / "controllers" / "crazyflie_square"
    pid_target = bundle / "controllers" / "crazyflie_square"
    for name in ("pid_controller.c", "pid_controller.h"):
        _copy_file(pid_source / name, pid_target / name)


def _manifest_files(bundle: Path) -> list[dict[str, object]]:
    files: list[dict[str, object]] = []
    for path in sorted(p for p in bundle.rglob("*") if p.is_file()):
        relative = path.relative_to(bundle).as_posix()
        if relative == MANIFEST_NAME or relative.startswith(".runtime/"):
            continue
        files.append(
            {
                "path": relative,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return files


def build_bundle(
    *,
    source_sha: str,
    cflib_root: Path,
    wheelhouse: Path,
    output_root: Path,
) -> Path:
    source_sha = _require_source_sha(source_sha)
    _verify_prepared_runtime()

    cflib_root = cflib_root.resolve()
    wheelhouse = wheelhouse.resolve()
    verify_cflib_provenance(cflib_root)
    entries = parse_lock()
    verify_wheelhouse(entries, wheelhouse)

    bundle = output_root.resolve() / BUNDLE_NAME
    if bundle.exists():
        shutil.rmtree(bundle)
    bundle.mkdir(parents=True)

    _copy_tree(REPO_ROOT / "tools" / "physical", bundle / "tools" / "physical")
    _copy_tree(
        REPO_ROOT / "plugins" / "robot_windows" / "blockly_v2",
        bundle / "plugins" / "robot_windows" / "blockly_v2",
        ignore_names={"node_modules"},
    )
    _copy_tree(
        SHARED_WEBEEBLOCKS,
        bundle / "plugins" / "robot_windows" / "blockly" / "webeeblocks",
    )
    _copy_file(
        GOOGLE_BLOCK,
        bundle
        / "plugins"
        / "robot_windows"
        / "blockly"
        / "google-blockly-31ee4ea"
        / "blocks"
        / "crazyflie_v2.js",
    )
    _copy_controller(bundle)

    _localize_world(
        REPO_ROOT / "worlds" / "crazyflie_runtime_v2.wbt",
        bundle / "worlds" / "crazyflie_runtime_v2.wbt",
    )

    _copy_tree(cflib_root, bundle / "support" / "cflib-source")
    (bundle / "support" / "wheels").mkdir(parents=True, exist_ok=True)
    for wheel in verify_wheelhouse(entries, wheelhouse):
        _copy_file(wheel, bundle / "support" / "wheels" / wheel.name)

    (bundle / SOURCE_SHA_NAME).write_text(source_sha + "\n", encoding="utf-8")
    (bundle / "README.md").write_text(
        "# WebeeBlocks — qualification physique hors ligne\n\n"
        f"Source exacte : `{source_sha}`.\n\n"
        "Pré-requis : Ubuntu 22.04 x86-64, Python 3.10, Webots R2025a et accès au Crazyradio de référence. "
        "Ce bundle ne constitue pas une autorisation de vol ni un résultat de qualification.\n\n"
        "Lorsqu'un checkpoint humain séparé et autorisé le demande, vérifier d'abord le bundle puis lancer :\n\n"
        "```bash\n"
        "python3 tools/physical/verify_physical_qualification_package.py .\n"
        "bash tools/physical/run_packaged_physical_qualification.sh --uri radio://...\n"
        "```\n\n"
        "Le lanceur conserve la préflight exacte, l'autorisation enseignant distincte et l'exécution paramètre-free du host.\n",
        encoding="utf-8",
    )
    lock_digest = sha256_file(
        REPO_ROOT / "tools" / "physical" / "qualification_runtime_lock.txt"
    )
    provenance = {
        "format": "webeeblocks-physical-qualification-provenance-v1",
        "source_sha": source_sha,
        "runtime_target": RUNTIME_TARGET,
        "cflib": {
            "commit": EXPECTED_CFLIB_COMMIT,
            "tree": EXPECTED_CFLIB_TREE,
            "subtree": EXPECTED_CFLIB_SUBTREE,
        },
        "qualification_runtime_lock_sha256": lock_digest,
        "wheel_count": len(entries),
        "blockly_version": "13.2.1",
        "webots_version": "R2025a",
        "execution_authority_packaged": False,
    }
    (bundle / PROVENANCE_NAME).write_text(
        json.dumps(provenance, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "format": "webeeblocks-physical-qualification-manifest-v1",
        "files": _manifest_files(bundle),
    }
    (bundle / MANIFEST_NAME).write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic offline WebeeBlocks physical qualification bundle"
    )
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--cflib-root", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)

    bundle = build_bundle(
        source_sha=args.source_sha,
        cflib_root=args.cflib_root,
        wheelhouse=args.wheelhouse,
        output_root=args.output_root,
    )
    print(f"PASS: deterministic offline physical qualification bundle built at {bundle}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except QualificationPackageError as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        raise SystemExit(1)

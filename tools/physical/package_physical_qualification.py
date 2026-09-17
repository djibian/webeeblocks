#!/usr/bin/env python3
"""Build one deterministic offline bundle for later physical qualification.

This packager is machine-only. It verifies already-pinned qualification runtime
inputs, copies only exact repository/runtime content into a repository-shaped
bundle, closes the Runtime v2 world over a self-contained R2025a qualification
PROTO, and writes a complete SHA-256 manifest. It never opens Crazyradio, starts
Webots, creates execution authority, or emits a physical effect.
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
import tarfile
import tempfile

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
EXPECTED_WORLD_REMOTE_REFS = 4
QUALIFICATION_PROTO_NAME = "QualificationCrazyflieR2025a"
QUALIFICATION_PROTO_RELATIVE = f"../tools/physical/{QUALIFICATION_PROTO_NAME}.proto"
BUNDLE_NAME = "WebeeBlocks-Physical-Qualification"
MANIFEST_NAME = "SHA256SUMS.json"
PROVENANCE_NAME = "PROVENANCE.json"
SOURCE_SHA_NAME = "SOURCE_SHA"
RUNTIME_TARGET = "ubuntu-22.04-python-3.10-x86_64"
WEBOTS_BUILD_IMAGE_DIGEST = (
    "sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099"
)

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
QUALIFICATION_PROTO = REPO_ROOT / "tools" / "physical" / "qualification_crazyflie_r2025a.proto"
PACKAGED_SOURCE_PATHS = (
    "tools/physical",
    "plugins/robot_windows/blockly_v2",
    "plugins/robot_windows/blockly/webeeblocks",
    "plugins/robot_windows/blockly/google-blockly-31ee4ea/blocks/crazyflie_v2.js",
    "worlds/crazyflie_runtime_v2.wbt",
    "controllers/crazyflie_runtime_v2",
    "controllers/crazyflie_square/pid_controller.c",
    "controllers/crazyflie_square/pid_controller.h",
)
GENERATED_CONTROLLER_PATH = "controllers/crazyflie_runtime_v2/crazyflie_runtime_v2"
GENERATED_VENDOR_PREFIX = "plugins/robot_windows/blockly_v2/vendor/"


class QualificationPackageError(RuntimeError):
    """Fail-closed offline qualification package error."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), *args],
            check=True,
            text=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise QualificationPackageError("repository Git provenance is unavailable") from exc
    return result.stdout.strip()


def _would_copy_untracked(relative: str) -> bool:
    path = Path(relative)
    parts = path.parts
    if relative == GENERATED_CONTROLLER_PATH or relative.startswith(GENERATED_VENDOR_PREFIX):
        return False
    if relative.startswith("tools/physical/"):
        return "__pycache__" not in parts and path.suffix != ".pyc"
    if relative.startswith("plugins/robot_windows/blockly_v2/"):
        return (
            "node_modules" not in parts
            and "__pycache__" not in parts
            and path.suffix != ".pyc"
        )
    if relative.startswith("plugins/robot_windows/blockly/webeeblocks/"):
        return "__pycache__" not in parts and path.suffix != ".pyc"
    if relative.startswith("controllers/crazyflie_runtime_v2/"):
        return path.name in {"Makefile", "runtime.ini"} or path.suffix in {
            ".c",
            ".cc",
            ".cpp",
            ".h",
            ".hpp",
        }
    return relative in {
        "plugins/robot_windows/blockly/google-blockly-31ee4ea/blocks/crazyflie_v2.js",
        "worlds/crazyflie_runtime_v2.wbt",
        "controllers/crazyflie_square/pid_controller.c",
        "controllers/crazyflie_square/pid_controller.h",
    }


def _unexpected_untracked_package_paths(status: str) -> tuple[str, ...]:
    # Git porcelain `-z` emits exact, unquoted path bytes as NUL-terminated
    # records. Keep line parsing only for direct regression fixtures and older
    # callers; real repository provenance always uses the lossless NUL form.
    records = status.split("\0") if "\0" in status else status.splitlines()
    unexpected: list[str] = []
    for record in records:
        if not (record.startswith("?? ") or record.startswith("!! ")):
            continue
        relative = record[3:]
        if _would_copy_untracked(relative):
            unexpected.append(relative)
    return tuple(sorted(unexpected))


def _require_source_sha(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise QualificationPackageError("exact lowercase 40-character source SHA required")
    observed = _git("rev-parse", "HEAD")
    if observed != value:
        raise QualificationPackageError(
            f"source SHA does not match checkout HEAD: expected {value}, got {observed}"
        )
    tracked_status = _git("status", "--porcelain", "--untracked-files=no")
    if tracked_status:
        raise QualificationPackageError(
            "tracked repository content is dirty; exact source SHA cannot bind package bytes"
        )
    package_status = _git(
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--ignored",
        "--",
        *PACKAGED_SOURCE_PATHS,
    )
    unexpected = _unexpected_untracked_package_paths(package_status)
    if unexpected:
        raise QualificationPackageError(
            "untracked or ignored repository content would enter exact-source package: "
            + ", ".join(unexpected)
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


def _copy_canonical_cflib(cflib_root: Path, target: Path) -> None:
    """Materialize only the exact tracked cflib Git tree, never checkout metadata."""
    verify_cflib_provenance(cflib_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="webeeblocks-cflib-archive-") as temp_text:
        archive = Path(temp_text) / "cflib-source.tar"
        try:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(cflib_root),
                    "archive",
                    "--format=tar",
                    "--output",
                    str(archive),
                    EXPECTED_CFLIB_COMMIT,
                ],
                check=True,
                text=True,
                capture_output=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise QualificationPackageError("canonical cflib source archive failed") from exc

        target.mkdir(parents=True, exist_ok=False)
        root = target.resolve()
        with tarfile.open(archive, "r:") as source_tar:
            for member in source_tar.getmembers():
                if member.isdev() or member.isfifo():
                    raise QualificationPackageError("unsupported cflib archive member type")
                candidate = (target / member.name).resolve()
                try:
                    candidate.relative_to(root)
                except ValueError as exc:
                    raise QualificationPackageError("cflib archive escaped package root") from exc
            source_tar.extractall(target)
    if (target / ".git").exists():
        raise QualificationPackageError("canonical cflib source unexpectedly contains .git")


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


def _verify_qualification_proto() -> None:
    if not QUALIFICATION_PROTO.is_file():
        raise QualificationPackageError("self-contained qualification Crazyflie PROTO is missing")
    text = QUALIFICATION_PROTO.read_text(encoding="utf-8")
    if re.search(r'"(?:https?|webots)://', text):
        raise QualificationPackageError("qualification Crazyflie PROTO contains an external runtime URL")
    for required in (
        f"PROTO {QUALIFICATION_PROTO_NAME} [",
        'name "m1_motor"',
        'name "m2_motor"',
        'name "m3_motor"',
        'name "m4_motor"',
        'name "range_front"',
        'name "range_back"',
        'name "range_left"',
        'name "range_right"',
        'name "inertial_unit"',
        "children IS extensionSlot",
        "mass 0.05",
    ):
        if required not in text:
            raise QualificationPackageError(
                "qualification Crazyflie PROTO lost required R2025a device/physics contract: "
                + required
            )


def _localize_world(source: Path, target: Path) -> None:
    text = source.read_text(encoding="utf-8")
    count = text.count(REMOTE_WEBOTS_PREFIX)
    if count != EXPECTED_WORLD_REMOTE_REFS:
        raise QualificationPackageError(
            f"expected {EXPECTED_WORLD_REMOTE_REFS} pinned Webots R2025a references, found {count}"
        )

    crazyflie = (
        'EXTERNPROTO "'
        + REMOTE_WEBOTS_PREFIX
        + 'projects/robots/bitcraze/crazyflie/protos/Crazyflie.proto"'
    )
    background = (
        'EXTERNPROTO "'
        + REMOTE_WEBOTS_PREFIX
        + 'projects/objects/backgrounds/protos/TexturedBackground.proto"'
    )
    background_light = (
        'EXTERNPROTO "'
        + REMOTE_WEBOTS_PREFIX
        + 'projects/objects/backgrounds/protos/TexturedBackgroundLight.proto"'
    )
    floor_proto = (
        'EXTERNPROTO "'
        + REMOTE_WEBOTS_PREFIX
        + 'projects/objects/floors/protos/Floor.proto"'
    )
    for reference in (crazyflie, background, background_light, floor_proto):
        if text.count(reference) != 1:
            raise QualificationPackageError("pinned Runtime v2 world reference is ambiguous")
    stock_crazyflie_node = "\nCrazyflie {"
    if text.count(stock_crazyflie_node) != 1:
        raise QualificationPackageError("pinned Runtime v2 Crazyflie node is ambiguous")

    localized = text.replace(
        crazyflie,
        f'EXTERNPROTO "{QUALIFICATION_PROTO_RELATIVE}"',
        1,
    )
    localized = localized.replace(
        stock_crazyflie_node,
        f"\n{QUALIFICATION_PROTO_NAME} {{",
        1,
    )
    for reference in (background, background_light, floor_proto):
        localized = localized.replace(reference + "\n", "", 1)
    localized = localized.replace(
        "TexturedBackground { }",
        "Background { skyColor [ 0.75 0.83 0.92 ] }",
        1,
    )
    localized = localized.replace(
        "TexturedBackgroundLight { }",
        "DirectionalLight { direction -0.4 -0.5 -1 intensity 1.5 }",
        1,
    )
    floor = """Solid {
  translation 0 0 -0.025
  children [
    Shape {
      appearance PBRAppearance { baseColor 0.65 0.68 0.72 roughness 0.8 }
      geometry Box { size 4 4 0.05 }
    }
  ]
  boundingObject Box { size 4 4 0.05 }
}"""
    localized = localized.replace("Floor { size 4 4 }", floor, 1)

    if "raw.githubusercontent.com/cyberbotics/webots/" in localized:
        raise QualificationPackageError("remote Cyberbotics reference remains after localization")
    if re.search(r'"(?:https?|webots)://', localized):
        raise QualificationPackageError("packaged world still depends on an external Webots asset")
    if localized.count(f'EXTERNPROTO "{QUALIFICATION_PROTO_RELATIVE}"') != 1:
        raise QualificationPackageError("packaged world lost local qualification Crazyflie binding")
    if localized.count(f"\n{QUALIFICATION_PROTO_NAME} {{") != 1 or stock_crazyflie_node in localized:
        raise QualificationPackageError("packaged world qualification PROTO declaration and node binding disagree")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(localized, encoding="utf-8")


def _copy_controller(bundle: Path) -> None:
    source = REPO_ROOT / "controllers" / "crazyflie_runtime_v2"
    binary = source / "crazyflie_runtime_v2"
    if not binary.is_file():
        raise QualificationPackageError(
            "Linux Runtime v2 controller binary is missing; build it with exact Webots R2025a before packaging"
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
            or path.name in {"Makefile", "runtime.ini"}
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
    _verify_qualification_proto()

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
    _copy_file(
        QUALIFICATION_PROTO,
        bundle / "tools" / "physical" / f"{QUALIFICATION_PROTO_NAME}.proto",
    )
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

    _copy_canonical_cflib(cflib_root, bundle / "support" / "cflib-source")
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
        "webots_build_image_digest": WEBOTS_BUILD_IMAGE_DIGEST,
        "preparation_execution_authority": False,
        "execution_requires_teacher_authorization": True,
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
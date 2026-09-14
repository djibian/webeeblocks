#!/usr/bin/env python3
"""Build one exact offline WebeeBlocks physical-qualification bundle.

The packager is machine-only: it verifies the already-pinned qualification
runtime support, archives the exact tracked WebeeBlocks source tree, and embeds
the verified wheelhouse plus pinned cflib checkout. It never opens Crazyradio,
starts Webots, creates teacher authority or emits a physical effect.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile
import tempfile

import verify_qualification_runtime as runtime

BUNDLE_ROOT = "webeeblocks-physical-qualification"
SUPPORT_DIR = ".qualification-runtime"
MANIFEST_NAME = "QUALIFICATION_MANIFEST.json"
RUNNER_NAME = "Run-Physical-Qualification.sh"


class QualificationBundleError(RuntimeError):
    """Fail-closed qualification bundle preparation error."""


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            text=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise QualificationBundleError("exact source Git provenance is unavailable") from exc
    return result.stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_source(source_root: Path, expected_sha: str) -> str:
    exact_sha = _git(source_root, "rev-parse", "HEAD")
    if exact_sha != expected_sha:
        raise QualificationBundleError(
            f"source HEAD does not match requested bundle SHA: {exact_sha} != {expected_sha}"
        )
    if _git(source_root, "status", "--porcelain", "--untracked-files=no"):
        raise QualificationBundleError("tracked WebeeBlocks source tree is not clean")
    return exact_sha


def _archive_source(source_root: Path, source_sha: str, destination: Path) -> None:
    archive = destination.parent / "source.tar"
    try:
        subprocess.run(
            [
                "git", "-C", str(source_root), "archive", "--format=tar",
                "--output", str(archive), source_sha,
            ],
            check=True,
            text=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise QualificationBundleError("exact WebeeBlocks source archive failed") from exc
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive, "r:") as source_tar:
        for member in source_tar.getmembers():
            target = (destination / member.name).resolve()
            try:
                target.relative_to(destination.resolve())
            except ValueError as exc:
                raise QualificationBundleError("source archive escaped bundle root") from exc
        source_tar.extractall(destination)


def _copy_verified_support(cflib_root: Path, wheelhouse: Path, destination: Path) -> tuple[dict[str, object], ...]:
    runtime.verify_cflib_provenance(cflib_root)
    entries = runtime.parse_lock()
    wheels = runtime.verify_wheelhouse(entries, wheelhouse)

    support = destination / SUPPORT_DIR
    bundled_cflib = support / "cflib-source"
    bundled_wheels = support / "wheels"
    shutil.copytree(cflib_root, bundled_cflib, symlinks=True)
    bundled_wheels.mkdir(parents=True)
    for wheel in wheels:
        shutil.copy2(wheel, bundled_wheels / wheel.name)

    return tuple(
        {
            "spec": entry.spec,
            "filename": entry.filename,
            "sha256": entry.sha256,
        }
        for entry in entries
    )


def _runner_text() -> str:
    return r'''#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"
SUPPORT="$ROOT/.qualification-runtime"
SITE="$SUPPORT/site"

"$PYTHON" - <<'PY'
import platform, sys
if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"Python 3.10 requis, version détectée: {sys.version.split()[0]}")
if platform.system() != "Linux" or platform.machine() != "x86_64":
    raise SystemExit(f"Linux x86_64 requis, plateforme détectée: {platform.system()} {platform.machine()}")
PY

python_verifier="$ROOT/tools/physical/verify_qualification_runtime.py"
cflib="$SUPPORT/cflib-source"
wheelhouse="$SUPPORT/wheels"
"$PYTHON" "$python_verifier" "$cflib" "$wheelhouse"

rm -rf "$SITE"
mkdir -p "$SITE"
"$PYTHON" -m pip install \
  --disable-pip-version-check \
  --no-index --no-deps --ignore-installed \
  --target "$SITE" \
  "$wheelhouse"/*.whl

export PYTHONNOUSERSITE=1
export PYTHONPATH="$ROOT/tools/physical:$cflib:$SITE"
exec "$PYTHON" -S "$ROOT/tools/physical/launch_physical_qualification.py" "$@"
'''


def _write_manifest(destination: Path, source_sha: str, wheels: tuple[dict[str, object], ...]) -> None:
    manifest = {
        "format": "webeeblocks-physical-qualification-v1",
        "sourceSha": source_sha,
        "target": {
            "os": "Ubuntu 22.04 compatible Linux",
            "machine": "x86_64",
            "python": "CPython 3.10",
        },
        "cflib": {
            "commit": runtime.EXPECTED_CFLIB_COMMIT,
            "tree": runtime.EXPECTED_CFLIB_TREE,
            "subtree": runtime.EXPECTED_CFLIB_SUBTREE,
        },
        "wheels": list(wheels),
        "launcher": "tools/physical/launch_physical_qualification.py",
        "runner": RUNNER_NAME,
        "executionAuthority": False,
        "note": "Bundle preparation is machine evidence only; real execution still requires the trusted host and explicit teacher approval.",
    }
    (destination / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    runner = destination / RUNNER_NAME
    runner.write_text(_runner_text(), encoding="utf-8")
    runner.chmod(0o755)


def _normalized_tarinfo(path: Path, arcname: str) -> tarfile.TarInfo:
    info = tarfile.TarInfo(arcname)
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    info.mtime = 0
    mode = path.lstat().st_mode
    if stat.S_ISDIR(mode):
        info.type = tarfile.DIRTYPE
        info.mode = 0o755
        info.size = 0
    elif stat.S_ISLNK(mode):
        info.type = tarfile.SYMTYPE
        info.mode = 0o777
        info.linkname = os.readlink(path)
        info.size = 0
    elif stat.S_ISREG(mode):
        info.type = tarfile.REGTYPE
        info.mode = 0o755 if (mode & 0o111) else 0o644
        info.size = path.stat().st_size
    else:
        raise QualificationBundleError(f"unsupported bundle filesystem entry: {path}")
    return info


def _write_archive(staged_root: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output.with_suffix(output.suffix + ".tmp")
    if temp_output.exists():
        temp_output.unlink()
    with temp_output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as bundle:
                root_info = _normalized_tarinfo(staged_root, BUNDLE_ROOT)
                bundle.addfile(root_info)
                for path in sorted(staged_root.rglob("*"), key=lambda item: item.relative_to(staged_root).as_posix()):
                    relative = path.relative_to(staged_root).as_posix()
                    info = _normalized_tarinfo(path, f"{BUNDLE_ROOT}/{relative}")
                    if info.isfile():
                        with path.open("rb") as stream:
                            bundle.addfile(info, stream)
                    else:
                        bundle.addfile(info)
    temp_output.replace(output)


def build_bundle(source_root: Path, cflib_root: Path, wheelhouse: Path, output: Path, source_sha: str) -> str:
    source_root = source_root.resolve()
    cflib_root = cflib_root.resolve()
    wheelhouse = wheelhouse.resolve()
    output = output.resolve()
    exact_sha = _validate_source(source_root, source_sha)
    with tempfile.TemporaryDirectory(prefix="webeeblocks-qualification-bundle-") as temp_text:
        temp = Path(temp_text)
        staged_root = temp / BUNDLE_ROOT
        _archive_source(source_root, exact_sha, staged_root)
        wheels = _copy_verified_support(cflib_root, wheelhouse, staged_root)
        _write_manifest(staged_root, exact_sha, wheels)
        _write_archive(staged_root, output)
    return _sha256(output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build exact offline physical qualification bundle")
    parser.add_argument("source_root", type=Path)
    parser.add_argument("cflib_root", type=Path)
    parser.add_argument("wheelhouse", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args(argv)

    digest = build_bundle(
        args.source_root,
        args.cflib_root,
        args.wheelhouse,
        args.output,
        args.source_sha,
    )
    print(f"PHYSICAL_QUALIFICATION_BUNDLE={args.output.resolve()}")
    print(f"PHYSICAL_QUALIFICATION_BUNDLE_SHA256={digest}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (QualificationBundleError, runtime.QualificationRuntimeError) as exc:
        print("FAIL: " + str(exc), file=os.sys.stderr)
        raise SystemExit(1)

#!/usr/bin/env python3
"""Build the exact offline #70 X3 props-off characterization bundle.

Machine preparation only: this helper never opens Crazyradio, flashes firmware,
changes parameters, publishes evidence, mints execution authority or requests a
human checkpoint.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_FIRMWARE_SHA256 = "67d71f2fc74c06001bb141ed6206b0d06df23497a48f498531c3aba192f0b738"
EXPECTED_CFLIB_COMMIT = "45fdb784c9d13074c42835f3b5ac1d12133bf873"
EXPECTED_CFLIB_TREE = "a78cf78d2b4aba51a0fa2b03de0260664b523401"
EXPECTED_CFLIB_SUBTREE = "750e850390753de14019f0e1f55d4fbc44317699"
RUNTIME = "ubuntu-22.04-python-3.10-x86_64"
PROFILE = "x3-independent-props-off"
BUNDLE_NAME = "WebeeBlocks-X3-Characterization"
MANIFEST_NAME = "MANIFEST.json"
MANIFEST_FORMAT = "webeeblocks-x3-characterization-manifest-v1"
LOCK = ROOT / "tools" / "physical" / "reference_probe_lock.txt"
RUNNER = ROOT / "tools" / "physical" / "run_x3_independent_capture.sh"
VERIFIER = ROOT / "tools" / "physical" / "verify_x3_characterization_bundle.py"
EXPERIMENT = ROOT / "experiments" / "crazyflie-ukf-surface-range"
CAPTURE = EXPERIMENT / "capture_independent_inputs.py"
METRIC_REFERENCE = EXPERIMENT / "metric_reference.py"
PRESSURE_PROBE = EXPERIMENT / "frozen_pressure_probe.py"
METRIC_REFERENCE_DOC = EXPERIMENT / "METRIC_REFERENCE.md"
PREREGISTRATION = EXPERIMENT / "X3_CHARACTERIZATION_PREREGISTRATION.md"
CHECKPOINT_SUPPORT = EXPERIMENT / "X3_CHECKPOINT_SUPPORT.md"
REFERENCE_WITNESS = EXPERIMENT / "X3_REFERENCE_WITNESS.md"
REFERENCE_WITNESS_TEMPLATE = EXPERIMENT / "X3_REFERENCE_WITNESS_TEMPLATE.csv"


class PackageError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            text=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PackageError("required exact Git provenance is unavailable") from exc
    return result.stdout.strip()


def require_source(source_sha: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise PackageError("exact lowercase 40-character repository SHA required")
    if git(ROOT, "rev-parse", "HEAD") != source_sha:
        raise PackageError("repository HEAD does not match requested target SHA")
    if git(ROOT, "status", "--porcelain", "--untracked-files=no"):
        raise PackageError("tracked repository source is not clean")
    return source_sha


def locked_wheels() -> tuple[tuple[str, str, str], ...]:
    rows: list[tuple[str, str, str]] = []
    for raw in LOCK.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = tuple(part.strip() for part in line.split("|"))
        if len(parts) != 3 or not re.fullmatch(r"[0-9a-f]{64}", parts[2]):
            raise PackageError("malformed reference runtime lock")
        rows.append((parts[0], parts[1], parts[2]))
    if len(rows) != 4:
        raise PackageError("exact four-wheel reference runtime lock required")
    return tuple(rows)


def verify_cflib(root: Path) -> None:
    if git(root, "rev-parse", "HEAD") != EXPECTED_CFLIB_COMMIT:
        raise PackageError("cflib commit changed")
    if git(root, "rev-parse", "HEAD^{tree}") != EXPECTED_CFLIB_TREE:
        raise PackageError("cflib tree changed")
    if git(root, "rev-parse", "HEAD:cflib") != EXPECTED_CFLIB_SUBTREE:
        raise PackageError("cflib subtree changed")
    if git(root, "status", "--porcelain", "--untracked-files=no"):
        raise PackageError("tracked cflib checkout is not clean")


def verify_wheels(wheelhouse: Path) -> tuple[Path, ...]:
    rows = locked_wheels()
    expected = {filename for _spec, filename, _digest in rows}
    actual = {path.name for path in wheelhouse.glob("*.whl") if path.is_file()}
    if actual != expected:
        raise PackageError(f"wheelhouse must contain exactly locked wheels: {sorted(expected)!r}")
    paths: list[Path] = []
    for _spec, filename, digest in rows:
        path = wheelhouse / filename
        if sha256(path) != digest:
            raise PackageError(f"wheel digest mismatch: {filename}")
        paths.append(path)
    return tuple(paths)


def export_cflib(root: Path, destination: Path) -> None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "archive", "--format=tar", EXPECTED_CFLIB_COMMIT, "cflib"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PackageError("cannot export canonical cflib tree") from exc
    destination.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as archive:
        for member in archive.getmembers():
            if member.islnk() or member.issym() or member.name.startswith("/") or ".." in Path(member.name).parts:
                raise PackageError("unsafe path in canonical cflib archive")
            if member.name != "cflib" and not member.name.startswith("cflib/"):
                raise PackageError("unexpected path in canonical cflib archive")
        archive.extractall(destination)


def copy_file(source: Path, destination: Path, *, executable: bool = False) -> None:
    if not source.is_file():
        raise PackageError(f"required support file missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    if executable:
        destination.chmod(destination.stat().st_mode | 0o111)


def write_manifest(bundle: Path) -> None:
    files = []
    for path in sorted(p for p in bundle.rglob("*") if p.is_file() and p.name != MANIFEST_NAME):
        relative = path.relative_to(bundle).as_posix()
        files.append(
            {
                "path": relative,
                "size": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    manifest = {"format": MANIFEST_FORMAT, "files": files}
    (bundle / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build(*, source_sha: str, firmware_bin: Path, cflib_root: Path, wheelhouse: Path, output_root: Path) -> Path:
    source_sha = require_source(source_sha)
    firmware_bin = firmware_bin.resolve()
    cflib_root = cflib_root.resolve()
    wheelhouse = wheelhouse.resolve()
    if not firmware_bin.is_file() or sha256(firmware_bin) != EXPECTED_FIRMWARE_SHA256:
        raise PackageError("firmware is not exact #251 cf2.bin")
    verify_cflib(cflib_root)
    wheels = verify_wheels(wheelhouse)

    bundle = output_root.resolve() / BUNDLE_NAME
    if bundle.exists():
        raise PackageError(f"output already exists: {bundle}")
    bundle.mkdir(parents=True)

    copy_file(firmware_bin, bundle / "cf2.bin")
    copy_file(CAPTURE, bundle / "capture_independent_inputs.py", executable=True)
    copy_file(RUNNER, bundle / "run_x3_independent_capture.sh", executable=True)
    copy_file(VERIFIER, bundle / "verify_x3_characterization_bundle.py", executable=True)
    copy_file(METRIC_REFERENCE, bundle / "metric_reference.py", executable=True)
    copy_file(PRESSURE_PROBE, bundle / "frozen_pressure_probe.py", executable=True)
    copy_file(METRIC_REFERENCE_DOC, bundle / "METRIC_REFERENCE.md")
    copy_file(PREREGISTRATION, bundle / "X3_CHARACTERIZATION_PREREGISTRATION.md")
    copy_file(CHECKPOINT_SUPPORT, bundle / "X3_CHECKPOINT_SUPPORT.md")
    copy_file(REFERENCE_WITNESS, bundle / "X3_REFERENCE_WITNESS.md")
    copy_file(REFERENCE_WITNESS_TEMPLATE, bundle / "X3_REFERENCE_WITNESS_TEMPLATE.csv")
    copy_file(LOCK, bundle / "reference_probe_lock.txt")
    export_cflib(cflib_root, bundle / "cflib-source")
    (bundle / "wheels").mkdir()
    for wheel in wheels:
        copy_file(wheel, bundle / "wheels" / wheel.name)

    provenance = [
        f"repository_target_sha={source_sha}",
        f"test_profile={PROFILE}",
        f"firmware_bin_sha256={EXPECTED_FIRMWARE_SHA256}",
        f"cflib_commit={EXPECTED_CFLIB_COMMIT}",
        f"cflib_tree={EXPECTED_CFLIB_TREE}",
        f"cflib_subtree={EXPECTED_CFLIB_SUBTREE}",
        f"runtime={RUNTIME}",
        "reference_processing=conditional-only",
        "reference_witness=measured-guide-csv-v1",
        "evidence_profile=physical-csv-text-v1",
        "physical_effect=none-during-packaging",
        "firmware_flash=not-performed",
        "execution_authority=none",
        "human_checkpoint=request-not-issued",
    ]
    (bundle / "PROVENANCE.txt").write_text("\n".join(provenance) + "\n", encoding="utf-8")
    write_manifest(bundle)
    return bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--firmware-bin", type=Path, required=True)
    parser.add_argument("--cflib-root", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        bundle = build(
            source_sha=args.source_sha,
            firmware_bin=args.firmware_bin,
            cflib_root=args.cflib_root,
            wheelhouse=args.wheelhouse,
            output_root=args.output_root,
        )
    except (OSError, UnicodeError, PackageError) as exc:
        print(f"FAIL: {exc}")
        return 1
    print(f"PASS: exact X3 characterization bundle built at {bundle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

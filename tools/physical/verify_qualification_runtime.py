#!/usr/bin/env python3
"""Verify the exact offline Python runtime used by physical qualification.

This verifier is deliberately machine-only.  It never opens Crazyradio, starts
Webots, creates a physical session, writes a parameter or emits a flight command.
It proves that the pinned cflib source plus the exact locked wheelhouse can import
the production qualification launcher and trusted-host module graph in an
isolated CPython 3.10 environment.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile

EXPECTED_CFLIB_COMMIT = "45fdb784c9d13074c42835f3b5ac1d12133bf873"
EXPECTED_CFLIB_TREE = "a78cf78d2b4aba51a0fa2b03de0260664b523401"
EXPECTED_CFLIB_SUBTREE = "750e850390753de14019f0e1f55d4fbc44317699"
LOCK_PATH = Path(__file__).with_name("qualification_runtime_lock.txt")
REPO_ROOT = Path(__file__).resolve().parents[2]
PHYSICAL_DIR = REPO_ROOT / "tools" / "physical"

HOST_IMPORTS = (
    "launch_physical_qualification",
    "physical_execution_domain",
    "physical_run_dispatch",
    "post_reset_capability_bridge",
    "probe_reference_hardware",
    "serve_reference_capabilities",
    "teacher_run_authorization",
)
RUNTIME_IMPORTS = (
    "cflib",
    "cflib.crtp",
    "cflib.crazyflie",
    "usb",
    "libusb_package",
    "importlib_resources",
    "numpy",
    "scipy",
    "packaging",
    "yaml",
)
POISON_ROOTS = (
    "cflib",
    "usb",
    "libusb_package",
    "importlib_resources",
    "numpy",
    "scipy",
    "packaging",
    "yaml",
)


class QualificationRuntimeError(RuntimeError):
    """Fail-closed qualification-runtime provenance error."""


@dataclass(frozen=True, slots=True)
class LockedWheel:
    spec: str
    filename: str
    sha256: str


def parse_lock(path: Path = LOCK_PATH) -> tuple[LockedWheel, ...]:
    entries: list[LockedWheel] = []
    seen_specs: set[str] = set()
    seen_files: set[str] = set()
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) != 3:
            raise QualificationRuntimeError(f"lock line {number} must have three fields")
        spec, filename, digest = parts
        if not spec or not filename or Path(filename).name != filename:
            raise QualificationRuntimeError(f"lock line {number} has invalid spec/filename")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise QualificationRuntimeError(f"lock line {number} has invalid sha256")
        if spec in seen_specs or filename in seen_files:
            raise QualificationRuntimeError(f"lock line {number} duplicates a package or wheel")
        seen_specs.add(spec)
        seen_files.add(filename)
        entries.append(LockedWheel(spec, filename, digest))
    if not entries:
        raise QualificationRuntimeError("qualification runtime lock is empty")
    return tuple(entries)


def _git(cflib_root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(cflib_root), *args],
            check=True,
            text=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise QualificationRuntimeError("exact cflib Git provenance is unavailable") from exc
    return result.stdout.strip()


def verify_cflib_provenance(cflib_root: Path) -> None:
    if _git(cflib_root, "rev-parse", "HEAD") != EXPECTED_CFLIB_COMMIT:
        raise QualificationRuntimeError("cflib commit does not match qualification pin")
    if _git(cflib_root, "rev-parse", "HEAD^{tree}") != EXPECTED_CFLIB_TREE:
        raise QualificationRuntimeError("cflib tree does not match qualification pin")
    if _git(cflib_root, "rev-parse", "HEAD:cflib") != EXPECTED_CFLIB_SUBTREE:
        raise QualificationRuntimeError("cflib subtree does not match qualification pin")
    if not (cflib_root / "cflib").is_dir():
        raise QualificationRuntimeError("pinned cflib package directory is missing")


def verify_wheelhouse(entries: tuple[LockedWheel, ...], wheelhouse: Path) -> tuple[Path, ...]:
    if not wheelhouse.is_dir():
        raise QualificationRuntimeError("qualification wheelhouse directory is missing")
    expected_names = {entry.filename for entry in entries}
    actual_names = {path.name for path in wheelhouse.glob("*.whl") if path.is_file()}
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        extra = sorted(actual_names - expected_names)
        raise QualificationRuntimeError(
            f"qualification wheelhouse is not exact; missing={missing!r} extra={extra!r}"
        )
    verified: list[Path] = []
    for entry in entries:
        path = wheelhouse / entry.filename
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry.sha256:
            raise QualificationRuntimeError(f"wheel sha256 mismatch: {entry.filename}")
        verified.append(path)
    return tuple(verified)


def _write_hostile_ambient(root: Path) -> None:
    for module in POISON_ROOTS:
        package = root / module
        package.mkdir(parents=True, exist_ok=True)
        (package / "__init__.py").write_text(
            'raise RuntimeError("ambient package must never be imported")\n',
            encoding="utf-8",
        )


def _import_probe_code() -> str:
    return r'''
import importlib
import pathlib
import sys

repo = pathlib.Path(sys.argv[1]).resolve()
physical = (repo / "tools" / "physical").resolve()
source = pathlib.Path(sys.argv[2]).resolve()
site = pathlib.Path(sys.argv[3]).resolve()

host_imports = tuple(sys.argv[4].split(","))
runtime_imports = tuple(sys.argv[5].split(","))

for name in runtime_imports:
    importlib.import_module(name)
for name in host_imports:
    importlib.import_module(name)

cflib = importlib.import_module("cflib")
cflib_file = pathlib.Path(cflib.__file__).resolve()
if source not in cflib_file.parents:
    raise SystemExit(f"FAIL: cflib escaped exact bundled source: {cflib_file}")

for name in ("usb", "libusb_package", "importlib_resources", "numpy", "scipy", "packaging", "yaml"):
    module = importlib.import_module(name)
    module_file = pathlib.Path(module.__file__).resolve()
    if site not in module_file.parents:
        raise SystemExit(f"FAIL: dependency escaped isolated wheelhouse: {name} -> {module_file}")

for name in host_imports:
    module = importlib.import_module(name)
    module_file = pathlib.Path(module.__file__).resolve()
    if physical not in module_file.parents:
        raise SystemExit(f"FAIL: qualification host module escaped repository source: {name} -> {module_file}")

print("PASS: qualification launcher and trusted-host imports use exact isolated runtime closure")
'''


def _run_real_entrypoint_help(script: Path, env: dict[str, str]) -> None:
    try:
        result = subprocess.run(
            [sys.executable, "-S", str(script), "--help"],
            check=True,
            text=True,
            capture_output=True,
            env=env,
            cwd=REPO_ROOT,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = "" if not isinstance(exc, subprocess.CalledProcessError) else (exc.stdout + exc.stderr)
        raise QualificationRuntimeError(
            f"isolated production entrypoint import failed: {script.name}\n{detail}"
        ) from exc
    if "usage:" not in result.stdout.lower():
        raise QualificationRuntimeError(
            f"production entrypoint did not reach argparse help without effects: {script.name}"
        )


def verify_isolated_imports(cflib_root: Path, wheels: tuple[Path, ...]) -> None:
    with tempfile.TemporaryDirectory(prefix="webeeblocks-qualification-runtime-") as temp_text:
        temp = Path(temp_text)
        site = temp / "site"
        ambient = temp / "hostile-ambient"
        site.mkdir()
        ambient.mkdir()
        _write_hostile_ambient(ambient)

        try:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--no-index",
                    "--no-deps",
                    "--ignore-installed",
                    "--target",
                    str(site),
                    *(str(path) for path in wheels),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise QualificationRuntimeError("offline locked-wheel installation failed") from exc

        env = os.environ.copy()
        env["PYTHONNOUSERSITE"] = "1"
        env["PYTHONPATH"] = os.pathsep.join(
            (str(PHYSICAL_DIR), str(cflib_root), str(site), str(ambient))
        )
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-S",
                    "-c",
                    _import_probe_code(),
                    str(REPO_ROOT),
                    str(cflib_root),
                    str(site),
                    ",".join(HOST_IMPORTS),
                    ",".join(RUNTIME_IMPORTS),
                ],
                check=True,
                text=True,
                capture_output=True,
                env=env,
                cwd=REPO_ROOT,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            detail = "" if not isinstance(exc, subprocess.CalledProcessError) else (exc.stdout + exc.stderr)
            raise QualificationRuntimeError("isolated qualification import proof failed\n" + detail) from exc

        # Exercise the real executable import paths, not only a mirrored import list.
        # Both entrypoints parse --help before creating any Webots process, Crazyradio
        # session, teacher authority, parameter write or physical effect object.
        _run_real_entrypoint_help(PHYSICAL_DIR / "launch_physical_qualification.py", env)
        _run_real_entrypoint_help(PHYSICAL_DIR / "serve_physical_host.py", env)
        print(result.stdout.strip())
        print("PASS: real qualification launcher/host entrypoints import under exact isolated closure")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify exact offline runtime closure for physical qualification without hardware"
    )
    parser.add_argument("cflib_root", type=Path, help="exact pinned crazyflie-lib-python checkout")
    parser.add_argument("wheelhouse", type=Path, help="directory containing only locked wheels")
    args = parser.parse_args(argv)

    if sys.version_info[:2] != (3, 10):
        raise QualificationRuntimeError(f"Python 3.10 required, got {sys.version.split()[0]}")
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise QualificationRuntimeError(
            f"Linux x86_64 required, got {platform.system()} {platform.machine()}"
        )

    cflib_root = args.cflib_root.resolve()
    wheelhouse = args.wheelhouse.resolve()
    entries = parse_lock()
    verify_cflib_provenance(cflib_root)
    wheels = verify_wheelhouse(entries, wheelhouse)
    verify_isolated_imports(cflib_root, wheels)
    print("PASS: exact physical qualification runtime closure verified without hardware")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except QualificationRuntimeError as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        raise SystemExit(1)

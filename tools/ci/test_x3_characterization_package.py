#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "physical" / "package_x3_characterization.py"
VERIFIER_PATH = ROOT / "tools" / "physical" / "verify_x3_characterization_bundle.py"
RUNNER = ROOT / "tools" / "physical" / "run_x3_independent_capture.sh"
CAPTURE = ROOT / "experiments" / "crazyflie-ukf-surface-range" / "capture_independent_inputs.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


package = load_module("package_x3_characterization", MODULE_PATH)
manifest = load_module("verify_x3_characterization_bundle", VERIFIER_PATH)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_package_error(callable_, contains: str) -> None:
    try:
        callable_()
    except package.PackageError as exc:
        require(contains in str(exc), f"expected {contains!r} in {exc!r}")
        return
    raise AssertionError(f"expected PackageError containing {contains!r}")


def expect_manifest_error(callable_, contains: str) -> None:
    try:
        callable_()
    except manifest.ManifestError as exc:
        require(contains in str(exc), f"expected {contains!r} in {exc!r}")
        return
    raise AssertionError(f"expected ManifestError containing {contains!r}")


def file_snapshot(root: Path) -> tuple[tuple[str, int, str], ...]:
    rows = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append((path.relative_to(root).as_posix(), path.stat().st_size, digest))
    return tuple(rows)


def verify_manifest_oracles() -> None:
    with tempfile.TemporaryDirectory(prefix="webeeblocks-x3-manifest-test-") as temp_text:
        bundle = Path(temp_text) / "bundle"
        bundle.mkdir()
        (bundle / "alpha.txt").write_text("alpha\n", encoding="utf-8")
        (bundle / "nested").mkdir()
        (bundle / "nested" / "beta.bin").write_bytes(b"beta\x00")
        shutil.copy2(VERIFIER_PATH, bundle / "verify_x3_characterization_bundle.py")
        package.write_manifest(bundle)

        before = file_snapshot(bundle)
        manifest.verify_bundle(bundle)
        subprocess.run(
            [sys.executable, "-B", str(bundle / "verify_x3_characterization_bundle.py"), str(bundle)],
            check=True,
            text=True,
            capture_output=True,
            env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        require(file_snapshot(bundle) == before, "manifest verification must be observational")

        extra = bundle / "unexpected.py"
        extra.write_text("raise RuntimeError('must never enter bundle')\n", encoding="utf-8")
        expect_manifest_error(lambda: manifest.verify_bundle(bundle), "file set mismatch")
        extra.unlink()

        beta = bundle / "nested" / "beta.bin"
        original_beta = beta.read_bytes()
        beta.unlink()
        expect_manifest_error(lambda: manifest.verify_bundle(bundle), "file set mismatch")
        beta.write_bytes(original_beta)

        alpha = bundle / "alpha.txt"
        original_alpha = alpha.read_bytes()
        alpha.write_bytes(original_alpha + b"x")
        expect_manifest_error(lambda: manifest.verify_bundle(bundle), "size mismatch")
        alpha.write_bytes(original_alpha)
        manifest.verify_bundle(bundle)


def main() -> int:
    rows = package.locked_wheels()
    require(len(rows) == 4, "X3 runtime must retain exactly four locked wheels")
    require(
        {row[1] for row in rows}
        == {
            "pyusb-1.2.1-py3-none-any.whl",
            "libusb_package-1.0.26.3-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
            "importlib_resources-6.5.2-py3-none-any.whl",
            "numpy-2.2.6-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
        },
        "X3 package wheel identity changed",
    )

    head = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    require(package.require_source(head) == head, "clean exact repository HEAD must validate")
    expect_package_error(lambda: package.require_source("0" * 40), "does not match")
    expect_package_error(lambda: package.require_source("main"), "40-character")

    with tempfile.TemporaryDirectory(prefix="webeeblocks-x3-wheel-test-") as temp_text:
        wheelhouse = Path(temp_text)
        expect_package_error(lambda: package.verify_wheels(wheelhouse), "exactly locked wheels")
        for _spec, filename, _digest in rows:
            (wheelhouse / filename).write_bytes(b"not-the-locked-wheel")
        expect_package_error(lambda: package.verify_wheels(wheelhouse), "wheel digest mismatch")
        (wheelhouse / "unexpected.whl").write_bytes(b"x")
        expect_package_error(lambda: package.verify_wheels(wheelhouse), "exactly locked wheels")

    verify_manifest_oracles()

    source = MODULE_PATH.read_text(encoding="utf-8")
    for required in (
        package.EXPECTED_FIRMWARE_SHA256,
        package.EXPECTED_CFLIB_COMMIT,
        package.EXPECTED_CFLIB_TREE,
        package.EXPECTED_CFLIB_SUBTREE,
        '"status", "--porcelain", "--untracked-files=no"',
        '"archive", "--format=tar", EXPECTED_CFLIB_COMMIT, "cflib"',
        'MANIFEST_NAME = "MANIFEST.json"',
        'VERIFIER = ROOT / "tools" / "physical" / "verify_x3_characterization_bundle.py"',
        "physical_effect=none-during-packaging",
        "firmware_flash=not-performed",
        "execution_authority=none",
    ):
        require(required in source, f"X3 package contract missing: {required}")
    require("shutil.copytree(cflib_root" not in source, "cflib checkout metadata must not be copied")

    runner = RUNNER.read_text(encoding="utf-8")
    verifier_call = 'python3 -B "$HERE/verify_x3_characterization_bundle.py" "$HERE"'
    for required in (
        package.EXPECTED_FIRMWARE_SHA256,
        package.EXPECTED_CFLIB_COMMIT,
        package.EXPECTED_CFLIB_TREE,
        package.EXPECTED_CFLIB_SUBTREE,
        'EXPECTED_TEST_PROFILE="x3-independent-props-off"',
        "--verify-environment",
        "--props-removed",
        "--installed-bin-confirmed",
        "export PYTHONDONTWRITEBYTECODE=1",
        verifier_call,
    ):
        require(required in runner, f"X3 runner contract missing: {required}")
    require(
        runner.count("\nverify_bundle\n") >= 3,
        "runner must verify exact bundle before and after environment probing and after capture",
    )
    require("sha256sum -c" not in runner, "runner must not accept manifest-listed files while ignoring extras")
    for forbidden in ("set_value", "send_position_setpoint", "send_hover_setpoint"):
        require(forbidden not in runner, f"X3 runner unexpectedly exposes effect surface: {forbidden}")

    capture = CAPTURE.read_text(encoding="utf-8")
    for required in (
        'TEST_PROFILE = "x3-independent-props-off"',
        '"barometer": (20, ("baro.asl", "baro.pressure", "baro.temp"))',
        '"imu": (10, ("acc.x", "acc.y", "acc.z", "gyro.x", "gyro.y", "gyro.z"))',
        "--props-removed",
        "--installed-bin-confirmed",
    ):
        require(required in capture, f"collector contract missing: {required}")

    print("PASS: exact machine-only X3 characterization package, strict manifest and observational verification contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

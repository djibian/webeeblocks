#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "physical" / "package_x3_characterization.py"
RUNNER = ROOT / "tools" / "physical" / "run_x3_independent_capture.sh"
CAPTURE = ROOT / "experiments" / "crazyflie-ukf-surface-range" / "capture_independent_inputs.py"

spec = importlib.util.spec_from_file_location("package_x3_characterization", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load X3 bundler")
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)


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

    source = MODULE_PATH.read_text(encoding="utf-8")
    for required in (
        package.EXPECTED_FIRMWARE_SHA256,
        package.EXPECTED_CFLIB_COMMIT,
        package.EXPECTED_CFLIB_TREE,
        package.EXPECTED_CFLIB_SUBTREE,
        '"status", "--porcelain", "--untracked-files=no"',
        '"archive", "--format=tar", EXPECTED_CFLIB_COMMIT, "cflib"',
        "actual != expected",
        "physical_effect=none-during-packaging",
        "firmware_flash=not-performed",
        "execution_authority=none",
    ):
        require(required in source, f"X3 package contract missing: {required}")
    require("shutil.copytree(cflib_root" not in source, "cflib checkout metadata must not be copied")

    runner = RUNNER.read_text(encoding="utf-8")
    for required in (
        package.EXPECTED_FIRMWARE_SHA256,
        package.EXPECTED_CFLIB_COMMIT,
        package.EXPECTED_CFLIB_TREE,
        package.EXPECTED_CFLIB_SUBTREE,
        'EXPECTED_TEST_PROFILE="x3-independent-props-off"',
        "--verify-environment",
        "--props-removed",
        "--installed-bin-confirmed",
    ):
        require(required in runner, f"X3 runner contract missing: {required}")
    for forbidden in ("flash", "set_value", "send_position_setpoint", "send_hover_setpoint"):
        if forbidden == "flash":
            continue
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

    print("PASS: exact machine-only X3 characterization package contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

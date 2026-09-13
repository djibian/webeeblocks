#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[2]
VERIFIER_PATH = ROOT / "tools" / "physical" / "verify_qualification_runtime.py"
LOCK_PATH = ROOT / "tools" / "physical" / "qualification_runtime_lock.txt"

spec = importlib.util.spec_from_file_location("verify_qualification_runtime", VERIFIER_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load qualification runtime verifier")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)

EXPECTED = {
    "pyusb==1.2.1": (
        "pyusb-1.2.1-py3-none-any.whl",
        "2b4c7cb86dbadf044dfb9d3a4ff69fd217013dbe78a792177a3feb172449ea36",
    ),
    "libusb-package==1.0.26.3": (
        "libusb_package-1.0.26.3-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
        "433e89dd1f9f9a4149b975247cf1d493170454945fec54b4db9fe61c9e6b861f",
    ),
    "importlib-resources==6.5.2": (
        "importlib_resources-6.5.2-py3-none-any.whl",
        "789cfdc3ed28c78b67a06acb8126751ced69a3d5f79c095a98298cd8a760ccec",
    ),
    "numpy==2.2.6": (
        "numpy-2.2.6-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
        "fc7b73d02efb0e18c000e9ad8b83480dfcd5dfd11065997ed4c6747470ae8915",
    ),
    "scipy==1.14.1": (
        "scipy-1.14.1-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
        "8e32dced201274bf96899e6491d9ba3e9a5f6b336708656466ad0522d8528f69",
    ),
    "packaging==25.0": (
        "packaging-25.0-py3-none-any.whl",
        "29572ef2b1f17581046b3a2227d5c611fb25ec70ca1ba8554b24b0e69331a484",
    ),
    "PyYAML==6.0.3": (
        "pyyaml-6.0.3-cp310-cp310-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl",
        "9c7708761fccb9397fe64bbc0395abcae8c4bf7b0eac081e12b809bf47700d0b",
    ),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_runtime_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except verifier.QualificationRuntimeError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError(f"expected QualificationRuntimeError containing {pattern!r}")


def main() -> int:
    entries = verifier.parse_lock(LOCK_PATH)
    observed = {entry.spec: (entry.filename, entry.sha256) for entry in entries}
    require(observed == EXPECTED, "qualification runtime lock must remain exact")
    require(len(entries) == 7, "qualification runtime closure must contain exactly seven wheels")

    require(
        verifier.EXPECTED_CFLIB_COMMIT == "45fdb784c9d13074c42835f3b5ac1d12133bf873"
        and verifier.EXPECTED_CFLIB_TREE == "a78cf78d2b4aba51a0fa2b03de0260664b523401"
        and verifier.EXPECTED_CFLIB_SUBTREE == "750e850390753de14019f0e1f55d4fbc44317699",
        "qualification runtime must preserve exact cflib provenance",
    )
    require(
        verifier.HOST_IMPORTS
        == (
            "launch_physical_qualification",
            "physical_execution_domain",
            "physical_run_dispatch",
            "post_reset_capability_bridge",
            "probe_reference_hardware",
            "serve_reference_capabilities",
            "teacher_run_authorization",
        ),
        "verifier must cover the production launcher and trusted-host import roots",
    )
    require(
        set(verifier.RUNTIME_IMPORTS)
        == {
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
        },
        "verifier must cover the complete locked runtime package roots",
    )
    require(
        set(verifier.POISON_ROOTS)
        == {"cflib", "usb", "libusb_package", "importlib_resources", "numpy", "scipy", "packaging", "yaml"},
        "every ambient runtime package root must be poisoned",
    )

    with tempfile.TemporaryDirectory(prefix="webeeblocks-lock-test-") as temp_text:
        wheelhouse = Path(temp_text)
        for entry in entries:
            (wheelhouse / entry.filename).write_bytes(b"not-the-locked-wheel")
        expect_runtime_error(
            lambda: verifier.verify_wheelhouse(entries, wheelhouse),
            "wheel sha256 mismatch",
        )
        (wheelhouse / "unexpected.whl").write_bytes(b"unexpected")
        expect_runtime_error(
            lambda: verifier.verify_wheelhouse(entries, wheelhouse),
            "qualification wheelhouse is not exact",
        )

    probe = verifier._import_probe_code()
    require("importlib.import_module" in probe, "isolated proof must import real module roots")
    require("escaped exact bundled source" in probe, "isolated proof must pin cflib source path")
    require("escaped isolated wheelhouse" in probe, "isolated proof must pin dependency paths")
    require("escaped repository source" in probe, "isolated proof must pin host-module source paths")

    source = VERIFIER_PATH.read_text(encoding="utf-8")
    for required in (
        '"--no-index"',
        '"--no-deps"',
        '"--ignore-installed"',
        '"-S"',
        'env["PYTHONNOUSERSITE"] = "1"',
    ):
        require(required in source, f"missing fail-closed isolation contract: {required}")

    print("PASS: exact physical qualification runtime lock and offline isolation verifier contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

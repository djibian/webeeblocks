#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
VERIFIER_PATH = ROOT / "tools" / "physical" / "verify_qualification_runtime.py"
LOCK_PATH = ROOT / "tools" / "physical" / "qualification_runtime_lock.txt"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "ci.yml"

spec = importlib.util.spec_from_file_location("verify_qualification_runtime", VERIFIER_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load qualification runtime verifier")
verifier = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = verifier
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
        'PHYSICAL_DIR / "launch_physical_qualification.py"',
        'PHYSICAL_DIR / "serve_physical_host.py"',
        '"--help"',
    ):
        require(required in source, f"missing fail-closed isolation contract: {required}")

    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    maintenance = "github.event_name != 'pull_request' || (github.event.pull_request.draft == true && github.event.pull_request.head.repo.full_name == github.repository)"
    for required in (
        "id: qualification-runtime-cache",
        "uses: actions/cache/restore@v4",
        "path: .ci-support/qualification-runtime",
        "qualification-runtime-ubuntu22-cp310-cflib-45fdb784c9d13074c42835f3b5ac1d12133bf873-${{ hashFiles('tools/physical/qualification_runtime_lock.txt') }}",
        "repository: bitcraze/crazyflie-lib-python",
        "ref: 45fdb784c9d13074c42835f3b5ac1d12133bf873",
        "persist-credentials: false",
        "--no-deps --only-binary=:all:",
        "test \"$(find \"$wheelhouse\" -maxdepth 1 -type f -name '*.whl' | wc -l)\" -eq 7",
        "python3 tools/physical/verify_qualification_runtime.py \"$source\" \"$wheelhouse\"",
        "uses: actions/cache/save@v4",
        "python3 tools/ci/test_physical_qualification_runtime_lock.py",
    ):
        require(required in workflow, f"missing qualification runtime CI support: {required}")
    require(workflow.count(maintenance) >= 3, "qualification support acquisition must stay maintenance-only")
    section = workflow.split("- name: Restore exact physical qualification runtime support", 1)[1].split(
        "- name: Verify selector and repository contracts", 1
    )[0]
    require("restore-keys:" not in section, "qualification runtime cache must be exact-key only")
    require(
        "steps.qualification-runtime-cache.outputs.cache-hit != 'true'" in section,
        "qualification support acquisition must be cache-miss-only",
    )
    require(
        "github.event.pull_request.draft == false" in section,
        "Ready candidates must verify restored qualification support",
    )
    require(
        section.count("python3 tools/physical/verify_qualification_runtime.py") == 2,
        "qualification runtime must be verified both before cache save and on canonical consumption",
    )

    print("PASS: exact physical qualification runtime lock, hermetic CI cache and isolated import contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

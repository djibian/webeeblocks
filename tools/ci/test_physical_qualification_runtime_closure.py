#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / "tools" / "physical" / "qualification_runtime_lock.txt"
RUNNER = ROOT / "tools" / "physical" / "run_physical_qualification_environment.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

EXPECTED_LOCK = {
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
    "pyyaml==6.0.3": (
        "pyyaml-6.0.3-cp310-cp310-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl",
        "9c7708761fccb9397fe64bbc0395abcae8c4bf7b0eac081e12b809bf47700d0b",
    ),
}

EXPECTED_CFLIB_DEPENDENCIES = {
    "pyusb~=1.2",
    "libusb-package~=1.0",
    "scipy~=1.14",
    "numpy~=2.2",
    "packaging~=25.0",
    "pyyaml>=6.0.3",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def parse_lock() -> dict[str, tuple[str, str]]:
    entries: dict[str, tuple[str, str]] = {}
    for raw in LOCK.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        require(len(parts) == 3, f"malformed qualification lock line: {line!r}")
        spec, filename, digest = parts
        require(spec not in entries, f"duplicate qualification package spec: {spec}")
        require(filename.endswith(".whl"), f"qualification dependency must be a wheel: {filename}")
        require(re.fullmatch(r"[0-9a-f]{64}", digest) is not None, f"invalid SHA-256 for {filename}")
        entries[spec] = (filename, digest)
    return entries


def parse_cflib_dependencies(pyproject: Path) -> set[str]:
    text = pyproject.read_text(encoding="utf-8")
    match = re.search(r"(?ms)^dependencies\s*=\s*\[(.*?)^\]", text)
    require(match is not None, "pinned cflib pyproject dependency block missing")
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def check_ready_ci_uses_prepared_wheel_support() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    restore_name = "- name: Restore exact physical qualification runtime wheels"
    acquire_name = "- name: Acquire exact physical qualification runtime wheels for maintenance runs"
    save_name = "- name: Save exact physical qualification runtime wheels for maintenance runs"
    checkout_name = "- name: Checkout pinned cflib for physical qualification runtime"
    proof_name = "- name: Prove isolated physical qualification runtime closure"
    next_name = "- name: Select bounded X3 observer diagnostic"
    for marker in (restore_name, acquire_name, save_name, checkout_name, proof_name, next_name):
        require(marker in workflow, "qualification CI support marker missing: " + marker)

    restore = workflow.split(restore_name, 1)[1].split(acquire_name, 1)[0]
    acquire = workflow.split(acquire_name, 1)[1].split(save_name, 1)[0]
    save = workflow.split(save_name, 1)[1].split(checkout_name, 1)[0]
    proof = workflow.split(proof_name, 1)[1].split(next_name, 1)[0]
    cache_key = "physical-qualification-jammy-cp310-${{ hashFiles('tools/physical/qualification_runtime_lock.txt') }}"

    require("uses: actions/cache/restore@v4" in restore, "qualification Ready path must restore prepared wheel support")
    require(cache_key in restore and cache_key in save, "qualification cache key must bind the exact lock contents")
    require(
        "fail-on-cache-miss: ${{ github.event_name == 'pull_request' && github.event.pull_request.draft == false }}" in restore,
        "Ready qualification acceptance must fail closed when prepared wheel support is absent",
    )
    require("python3 -m pip download" in acquire, "maintenance path must be able to prepare the exact wheel cache")
    require("github.event_name != 'pull_request'" in acquire, "non-PR maintenance must be allowed to prepare wheel support")
    require("github.event.pull_request.draft == true" in acquire, "only Draft PR maintenance may acquire wheel support")
    require("github.event.pull_request.head.repo.full_name == github.repository" in acquire, "Draft cache preparation must be repository-local")
    require("uses: actions/cache/save@v4" in save, "verified maintenance support must be cached")
    require("python3 -m pip download" not in proof, "Ready qualification proof must consume prepared support without package-network resolution")
    require(".ci-support/physical-qualification-wheels" in proof, "qualification proof must use the restored exact wheelhouse")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cflib-root", type=Path, default=ROOT / ".ci-cflib")
    args = parser.parse_args()

    require(parse_lock() == EXPECTED_LOCK, "qualification runtime lock differs from reviewed exact closure")
    dependencies = parse_cflib_dependencies(args.cflib_root / "pyproject.toml")
    require(
        dependencies == EXPECTED_CFLIB_DEPENDENCIES,
        f"pinned cflib runtime dependencies changed: {sorted(dependencies)!r}",
    )
    check_ready_ci_uses_prepared_wheel_support()

    runner = RUNNER.read_text(encoding="utf-8")
    for required in (
        "python3 -S",
        "PYTHONNOUSERSITE=1",
        "exact seven-wheel physical qualification closure required",
        "launch_physical_qualification.py\" --help",
        "serve_physical_host.py\" --help",
        "hostile ambient package must never be imported",
        "import scipy",
        "import packaging",
        "import yaml",
        "from cflib.utils.power_switch import PowerSwitch",
    ):
        require(required in runner, "qualification environment proof missing: " + required)
    for forbidden in (
        "init_drivers(",
        "open_link(",
        "radio://",
        "APPROVE",
        "execute_approved_program",
    ):
        require(forbidden not in runner, "qualification environment proof must remain effect-free: " + forbidden)

    print("PASS: pinned cflib declaration maps to exact prepared seven-wheel effect-free qualification closure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

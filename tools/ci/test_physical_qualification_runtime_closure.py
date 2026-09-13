#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / "tools" / "physical" / "qualification_runtime_lock.txt"
RUNNER = ROOT / "tools" / "physical" / "run_physical_qualification_environment.sh"

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

    print("PASS: pinned cflib declaration maps to exact seven-wheel effect-free qualification closure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

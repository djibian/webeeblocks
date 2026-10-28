#!/usr/bin/env python3
"""Exercise the production Qt-free file protocol parser with a fake dialog provider.

The native test existed but was not invoked by any CI owner. A focused mutation
proves that the browser-path rejection assertion is not an inert green oracle.
No Webots process, Qt runtime, file dialog, network or physical device is used.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "controllers" / "crazyflie_runtime_v2"
SOURCE = CONTROLLER / "file_broker.cpp"
TEST = ROOT / "tools" / "ci" / "test_firefox_file_broker.cpp"

# This specific regression would allow a browser-provided absolute filename to
# reach the file-dialog provider. The existing native probe must reject it.
GUARD = "|| !safeSuggestedName(name)"
BROKEN_GUARD = "|| (!safeSuggestedName(name) && false)"


def build(source: Path, destination: Path) -> None:
    command = [
        os.environ.get("CXX", "c++"),
        "-std=c++17", "-Wall", "-Wextra", "-Werror",
        "-I", str(CONTROLLER), str(source), str(TEST), "-o", str(destination),
    ]
    compiled = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=90)
    if compiled.returncode:
        raise RuntimeError(
            f"Native broker compiler failed ({compiled.returncode}):\n"
            + compiled.stdout + compiled.stderr
        )


def main() -> int:
    original = SOURCE.read_text(encoding="utf-8")
    if original.count(GUARD) != 1:
        raise AssertionError("B4 file protocol path guard changed; revalidate the mutation")

    with tempfile.TemporaryDirectory(prefix="webeeblocks-file-broker-native-") as directory:
        temp = Path(directory)
        real_binary = temp / "file-broker"
        build(SOURCE, real_binary)
        real = subprocess.run([str(real_binary)], cwd=ROOT, text=True, capture_output=True, timeout=30)
        if real.returncode or "PASS firefox-file-broker:" not in real.stdout:
            raise AssertionError(f"Production file-broker probe failed ({real.returncode}):\n"
                                 + real.stdout + real.stderr)

        mutant_source = temp / "file_broker_mutant.cpp"
        mutant_source.write_text(original.replace(GUARD, BROKEN_GUARD), encoding="utf-8")
        mutant_binary = temp / "file-broker-mutant"
        build(mutant_source, mutant_binary)
        mutant = subprocess.run([str(mutant_binary)], cwd=ROOT, text=True, capture_output=True, timeout=30)
        if mutant.returncode == 0 or "pathInjection" not in mutant.stderr:
            raise AssertionError(
                f"Path-guard mutant escaped the expected native assertion ({mutant.returncode}):\n"
                + mutant.stdout + mutant.stderr
            )

    print(real.stdout.strip())
    print("PASS B4-I0 native file broker: real parser executed; unsafe path-guard mutant rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

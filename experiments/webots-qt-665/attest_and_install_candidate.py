#!/usr/bin/env python3
"""Fail-closed, opt-in Linux Webots R2025a binary adoption for #665.

Without --replace-disposable-installation this program only attests bytes.
Never run this on an official installation without an explicit, approved
deployment. Linux ELF is not a Windows webots-bin.exe qualification.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile

BASELINE = "1445efb2820d151dee40b79ef4128dca7e4a75e02630b49354e557c7e35e66eb"
# Only the parent-shutdown-safe complete Linux ELF has native/Qt qualification.
# Never accept the earlier d3140f65... build: its parent-destruction UAF was
# independently reproduced (40352255637). A caller-supplied SHA alone cannot
# authorize an otherwise unqualified artifact for even disposable replacement.
QUALIFIED_PARENT_SAFE_ELF = "e45a90b580a00f50dc08746e6f43d1a86a83fcf1b23f55538737309154150545"
QT = {
    "libQt6Widgets.so.6.5.3":
        "868b516dde6d020badc7243facd48f880b0d606c76e46e50427c1c744a2c1024",
    "libQt6Core.so.6.5.3":
        "ac391204135f1435ca1c97a7f92e6f94d9d369f6b12fb823923496360a272bd8",
}
IMAGE = "cyberbotics/webots@sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require(condition: bool, message: str):
    if not condition:
        raise ValueError(message)


def require_qualified_candidate_sha256(value: str) -> None:
    require(re.fullmatch(r"[0-9a-f]{64}", value) is not None,
            "candidate identity must be an explicit lowercase SHA-256")
    require(value == QUALIFIED_PARENT_SAFE_ELF,
            "candidate ELF SHA-256 is not the qualified parent-safe build")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runtime-home", type=Path, required=True,
                   help="Path of exact R2025a Linux installation")
    p.add_argument("--candidate", type=Path, required=True,
                   help="Newly linked and independently qualified Linux ELF")
    p.add_argument("--expected-candidate-sha256", required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--replace-disposable-installation", action="store_true",
                   help="Explicitly replace only a disposable R2025a runtime")
    a = p.parse_args()
    manifest = {"mode": "UNQUALIFIED", "expected_image": IMAGE}
    try:
        # Qualify the *expected* identity before any filesystem side effect.
        # Checking only digest(candidate) == user-supplied expected digest would
        # also permit an old known-vulnerable experimental ELF.
        require_qualified_candidate_sha256(a.expected_candidate_sha256)
        home = a.runtime_home.resolve(strict=True)
        candidate = a.candidate.resolve(strict=True)
        target = home / "bin/webots-bin"
        require(platform.system() == "Linux" and platform.machine() == "x86_64",
                "Linux x86_64 is required; Windows qualification is separate")
        require((home / "resources/version.txt").read_text().strip() == "R2025a",
                "wrong Webots version; no fallback")
        require(target.is_file() and candidate.is_file(), "missing Webots ELF")
        with candidate.open("rb") as stream:
            elf = stream.read(20)
        require(len(elf) == 20 and elf[:5] == b"\x7fELF\x02"
                and elf[5] == 1 and elf[18:20] == b"\x3e\x00",
                "not a Linux x86_64 little-endian ELF")
        require(digest(target) == BASELINE, "official baseline ELF identity mismatch")
        actual = digest(candidate)
        require(actual == a.expected_candidate_sha256, "candidate ELF SHA-256 mismatch")
        require(actual != BASELINE, "candidate is the unmodified official Webots")
        libraries = {}
        for name, expected in QT.items():
            path = home / "lib/webots" / name
            require(path.is_file() and digest(path) == expected,
                    "wrong Qt runtime library: " + name)
            libraries[name] = expected
        plugins = list(home.rglob("libqxcb.so"))
        require(len(plugins) >= 1, "Qt XCB platform plugin missing")
        env = dict(os.environ)
        env["LD_LIBRARY_PATH"] = str(home / "lib/webots")
        linked = subprocess.run(["ldd", str(candidate)], env=env,
                                capture_output=True, text=True, timeout=25,
                                check=False)
        require(linked.returncode == 0 and "not found" not in linked.stdout
                and "not found" not in linked.stderr, "unresolved ELF libraries")
        for name in ("libQt6Widgets.so.6", "libQt6Core.so.6"):
            matches = re.findall(r"^\s*" + re.escape(name) + r"\s+=>\s+(/\S+)",
                                 linked.stdout, flags=re.MULTILINE)
            require(len(matches) == 1 and
                    Path(matches[0]).resolve().is_relative_to(
                        (home / "lib/webots").resolve()),
                    "Qt library resolved outside the exact Webots runtime: " + name)
        manifest.update(
            mode="VERIFIED_NOT_INSTALLED", runtime_home=str(home),
            source_sha256=actual, original_sha256=BASELINE, qt= libraries,
            resolved_qt_from_runtime=True, native_ldd=linked.stdout,
            xcb_plugin_count=len(plugins))
        if a.replace_disposable_installation:
            # Caller MUST supply an expendable filesystem: overwriting production
            # is not authorized by an otherwise-green method-level experiment.
            temp = None
            try:
                with tempfile.NamedTemporaryFile(prefix=".qt665-", dir=target.parent,
                                                 delete=False) as output:
                    temp = Path(output.name)
                    with candidate.open("rb") as source:
                        shutil.copyfileobj(source, output)
                    output.flush()
                    os.fsync(output.fileno())
                temp.chmod(stat.S_IMODE(target.stat().st_mode))
                require(digest(temp) == actual, "temporary copy differs from candidate")
                os.replace(temp, target)
                require(digest(target) == actual, "installed binary differs from candidate")
            finally:
                if temp is not None and temp.exists():
                    temp.unlink()
            manifest["mode"] = "DISPOSABLE_INSTALLATION_VERIFIED"
            print("QT665_DISPOSABLE_LINUX_ADOPTION=PASS")
        else:
            print("QT665_LINUX_ELF_ATTESTATION=PASS NOT_INSTALLED")
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        manifest["error"] = str(exc)
        print("QT665_LINUX_ADOPTION=FAIL " + str(exc), file=sys.stderr)
        a.manifest.parent.mkdir(parents=True, exist_ok=True)
        a.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True))
        raise SystemExit(1)
    a.manifest.parent.mkdir(parents=True, exist_ok=True)
    a.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

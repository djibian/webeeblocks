#!/usr/bin/env python3
"""Verify exact pinned UKF reset semantics from upstream firmware source."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

EXPECTED_COMMIT = "54f31e243a0b28b67efef5ba20dbb6d9890a5478"
EXPECTED_ESTIMATOR_BLOB = "57c0e8405c07b63a29538019895ed17d0a379440"
ESTIMATOR_PATH = Path("src/modules/src/estimator/estimator_ukf.c")


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: test_x3_reset_firmware_semantics.py <crazyflie-firmware-root>")
    root = Path(sys.argv[1]).resolve()
    require((root / ".git").is_dir(), "exact Crazyflie firmware checkout is required")
    require(git(root, "rev-parse", "HEAD") == EXPECTED_COMMIT, "unexpected firmware commit")
    require(
        git(root, "rev-parse", f"HEAD:{ESTIMATOR_PATH.as_posix()}") == EXPECTED_ESTIMATOR_BLOB,
        "pinned estimator_ukf.c blob changed",
    )

    source = (root / ESTIMATOR_PATH).read_text(encoding="utf-8")
    declarations = (
        "static bool resetNavigation = true;",
        'PARAM_ADD(PARAM_UINT8, resetEstimation, &resetNavigation)',
    )
    for required in declarations:
        require(required in source, f"pinned reset declaration missing: {required}")

    consume = "if (resetNavigation)"
    initialize = "errorEstimatorUkfInit();"
    auto_clear_param = 'paramSetInt(paramGetVarId("ukf", "resetEstimation"), 0);'
    auto_clear_flag = "resetNavigation = false;"
    for required in (consume, initialize, auto_clear_param, auto_clear_flag):
        require(required in source, f"pinned reset consumption step missing: {required}")
    require(
        source.index(consume)
        < source.index(initialize)
        < source.index(auto_clear_param)
        < source.index(auto_clear_flag),
        "pinned firmware reset consume/auto-clear order changed",
    )

    print(
        "PASS: exact pinned UKF reset is uint8_t-backed and firmware-owned "
        "consumption reinitializes then auto-clears resetEstimation to 0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

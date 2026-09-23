#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    proofs = (
        "tools/ci/run_runtime_v2_outcome_freshness.py",
        "tools/ci/run_progression_sequence_mission.py",
        "tools/ci/run_progression_repeat_mission.py",
    )
    for proof in proofs:
        result = subprocess.run([sys.executable, proof], cwd=ROOT, check=False)
        if result.returncode:
            return result.returncode
    print("PASS real-Webots activity outcome foundation and executable progression missions 1-3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

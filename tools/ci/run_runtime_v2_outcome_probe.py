#!/usr/bin/env python3
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def proofs_for_job(job: str) -> tuple[str, ...]:
    freshness = "tools/ci/run_runtime_v2_outcome_freshness.py"
    progression = (
        "tools/ci/run_progression_sequence_mission.py",
        "tools/ci/run_progression_repeat_mission.py",
        "tools/ci/run_progression_simple_decision_mission.py",
        "tools/ci/run_progression_reactive_mission.py",
        "tools/ci/run_progression_combined_decisions_mission.py",
        "tools/ci/run_progression_memory_mission.py",
        "tools/ci/run_progression_memory_overwrite.py",
    )
    # The canonical Runtime suite already runs this full outcome/progression
    # probe in the sibling runtime-v2-core job on the same exact target SHA.
    # Do not spend the bounded student-ui or runtime-v2-webots integration
    # budgets on the same long real-Webots progression missions a second time;
    # those jobs still prove outcome freshness here before their own dedicated
    # UI/render/dynamic-Webots evidence.
    if job in ("runtime-v2-webots", "student-ui"):
        return (freshness,)
    return (freshness, *progression)


def main() -> int:
    proofs = proofs_for_job(os.environ.get("GITHUB_JOB", ""))
    for proof in proofs:
        result = subprocess.run([sys.executable, proof], cwd=ROOT, check=False)
        if result.returncode:
            return result.returncode
    if len(proofs) == 1:
        print("PASS real-Webots activity outcome foundation; progression missions are proved by runtime-v2-core on the same exact CI target")
    else:
        print("PASS real-Webots activity outcome foundation and executable progression missions 1-7, including required reuse of the Activity 7 stored value at the second decision")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

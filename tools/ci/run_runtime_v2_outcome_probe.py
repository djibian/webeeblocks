#!/usr/bin/env python3
from pathlib import Path
import argparse
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
FRESHNESS = "tools/ci/run_runtime_v2_outcome_freshness.py"

# Each native mission retains every original world, negative case and oracle.
# A shard changes only which isolated GitHub runner executes the entire script.
PROGRESSION = (
        "tools/ci/run_progression_sequence_mission.py",
        "tools/ci/run_classroom_neutral_start.py",
        "tools/ci/run_progression_repeat_mission.py",
        "tools/ci/run_progression_simple_decision_mission.py",
        "tools/ci/run_progression_reactive_mission.py",
        "tools/ci/run_progression_combined_decisions_mission.py",
        "tools/ci/run_progression_memory_mission.py",
        "tools/ci/run_progression_memory_overwrite.py",
        "tools/ci/run_progression_autonomous_mission.py",
    )

# Three nearly equal wall-clock groups, based on 2026-10-21 R2025a logs:
# sequence/reactive/overwrite, neutral/combined/autonomous, repeat/simple/memory.
# This table partitions the nine *entire* scripts without slicing their tests.
SHARD_INDICES = ((0, 4, 7), (1, 5, 8), (2, 3, 6))


def proofs_for_shard(shard: int) -> tuple[str, ...]:
    if shard not in range(len(SHARD_INDICES)):
        raise ValueError(f"invalid progression shard: {shard}")
    return (FRESHNESS, *(PROGRESSION[i] for i in SHARD_INDICES[shard]))


def proofs_for_job(job: str) -> tuple[str, ...]:
    # The canonical Runtime suite already runs this full outcome/progression
    # probe in the sibling runtime-v2-core job on the same exact target SHA.
    # Do not spend the bounded student-ui or runtime-v2-webots integration
    # budgets on the same long real-Webots progression missions a second time;
    # those jobs still prove outcome freshness here before their own dedicated
    # UI/render/dynamic-Webots evidence.
    if job in ("runtime-v2-webots", "student-ui"):
        return (FRESHNESS,)
    return (FRESHNESS, *PROGRESSION)


def main() -> int:
    parser = argparse.ArgumentParser(description="Unchanged native R2025a outcome/progression oracles")
    parser.add_argument("--shard", type=int, choices=range(len(SHARD_INDICES)),
                        help="run one complete partition in an isolated required CI job")
    args = parser.parse_args()
    proofs = (proofs_for_shard(args.shard) if args.shard is not None
              else proofs_for_job(os.environ.get("GITHUB_JOB", "")))
    for proof in proofs:
        result = subprocess.run([sys.executable, proof], cwd=ROOT, check=False)
        if result.returncode:
            return result.returncode
    if args.shard is not None:
        print(f"PASS native R2025a freshness and entire progression shard {args.shard}")
    elif len(proofs) == 1:
        print("PASS real-Webots activity outcome foundation; progression missions are proved by the required Runtime suite on the same exact CI target")
    else:
        print("PASS real-Webots activity outcome foundation and executable progression missions 1-8, including stored-value reuse and autonomous strategy synthesis across retained world configurations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

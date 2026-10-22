#!/usr/bin/env python3
from pathlib import Path
import argparse
import os
import subprocess
import sys
import json
import time

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

# 2026-10-22 adversarial CI #39768379510 falsified the original three-way
# timing estimate: e.g. repeat took ~18 min rather than ~5, while all three
# 30-minute jobs were cancelled before their final mission. Partition seven
# isolated runners by native cost, leaving variable/heavy missions separate.
# The nine complete original programs, physical oracles and negative cases
# remain unchanged; only scheduling/runner budgets change.
SHARD_INDICES = ((0, 3), (1,), (2,), (4, 7), (5,), (6,), (8,))


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
    # Do not conflate an Actions pull-request merge ref with the exact tested
    # candidate. Every native runner checks the checkout against its target SHA.
    if args.shard is not None:
        checkout_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        expected_sha = os.environ.get("WEBEEBLOCKS_CI_TARGET_SHA")
        if expected_sha and checkout_sha != expected_sha:
            print(f"FAIL native shard checkout {checkout_sha} != {expected_sha}", file=sys.stderr)
            return 2

    completed = []
    for proof in proofs:
        began = time.monotonic()
        print(f"BEGIN native R2025a proof {proof}", flush=True)
        result = subprocess.run([sys.executable, proof], cwd=ROOT, check=False)
        seconds = round(time.monotonic() - began, 2)
        print(f"END native R2025a proof {proof}: exit={result.returncode} elapsed={seconds}s", flush=True)
        if result.returncode:
            return result.returncode
        completed.append({"script": proof, "elapsed_seconds": seconds})
    if args.shard is not None:
        # A full-shard manifest only exists when *every* native subprocess
        # succeeded. On abort/timeout only diagnostic artifacts are retained.
        manifest = ROOT / f"ci-artifacts/runtime-v2-progression-shard-{args.shard}/manifest.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({
            "schema_version": 1,
            "head_sha": checkout_sha,
            "shard": args.shard,
            "required_proofs": list(proofs),
            "completed_proofs": completed,
            "complete": True,
        }, indent=2) + "\n", encoding="utf-8")
        print(f"PASS native R2025a freshness and entire progression shard {args.shard}")
    elif len(proofs) == 1:
        print("PASS real-Webots activity outcome foundation; progression missions are proved by the required Runtime suite on the same exact CI target")
    else:
        print("PASS real-Webots activity outcome foundation and executable progression missions 1-8, including stored-value reuse and autonomous strategy synthesis across retained world configurations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

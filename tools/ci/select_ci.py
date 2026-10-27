#!/usr/bin/env python3
"""Conservatively select WebeeBlocks CI suites from changed paths."""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DOC_ONLY = ("*.md", "docs/**", "documentation/**", ".github/pull_request_template.md")
FORCE_FULL = (
    ".github/workflows/**",
    # Webots Qt lifetime patches affect the native Runtime/Grand Prix consumer,
    # Windows deployment and Webots, not just the experimental source files.
    # A Webots-only Ready Gate would miss those product oracles.
    "experiments/webots-qt-665/**",
    "tools/ci/select_ci.py",
    "tools/ci/test_select_ci.py",
    "tools/ci/check_ci_gate.py",
    "tools/ci/test_ci_gate.py",
    "tools/ci/test_workflow_contract.py",
    "tools/ci/test_repository_hygiene.py",
    "tools/ci/test_windows_release_contract.py",
    # These native Windows composition fixtures are exercised only by the
    # full-gated runtime-v2-windows-release job, not the partial Runtime suite.
    "tools/ci/fixtures/gp_u_*",
    "tools/ci/test_controller_contract.py",
    "tools/build_windows_classroom_release.ps1",
    "packaging/windows/**",
    "plugins/robot_windows/blockly_v2/webots/**",
    "tools/prepare_runtime_v2.*",
    # These U controller/evaluator inputs feed Runtime's native Grand Prix
    # probe and its full-only Windows release/composition job. Webots alone
    # cannot exercise either owner: request the entire gate.
    "controllers/grand_prix_u_flight/**",
    "controllers/grand_prix_u_evaluator/**",
    "controllers/crazyflie_runtime_v2/**",
    "worlds/crazyflie_runtime_v2*",
)
RUNTIME = (
    "plugins/robot_windows/blockly_v2/**",
    "plugins/robot_windows/blockly/webeeblocks/**",
    "tools/prepare_runtime_v2.*",
    "tools/ci/*runtime_v2*",
    "tools/ci/test_physical_host_activation.py",
    "experiments/runtime-v2-student-ui/**",
)
WEBOTS = (
    "controllers/**",
    "worlds/**",
    "plugins/robot_windows/blockly/google-blockly-31ee4ea/**",
    "tools/ci/**",
    "experiments/**",
)
# These tests/fixtures exercise the physical core from ci-runtime.yml. Their
# former generic tools/ci match selected only Webots, skipping their own oracles.
PHYSICAL_RUNTIME_EVIDENCE = (
    "tools/ci/test_physical_*",
    "tools/ci/test_dynamic_*",
    "tools/ci/test_production_takeoff_run.py",
    "tools/ci/test_teacher_run_authorization.py",
    "tools/ci/fixtures/physical_*",
)
SHARED_RUNTIME_WEBOTS = (
    # The pre-controller observer is exercised by Runtime's outcome preflight.
    "tools/ci/observe_outcome_startup.py",
    "tools/ci/test_outcome_startup_observer.py",
    # The sequence LAND diagnostic is compiled and exercised by Runtime's
    # progression shards; generic tools/ci selection would skip its own oracle.
    "tools/ci/run_progression_sequence_mission.py",
    "tools/ci/test_progression_land_instrumentation.py",
    # The LAND/contact forensic reader and its tests run in the native Runtime
    # progression preflight; a Webots-only selection skips their owning oracle.
    "tools/ci/land_contact_summary.py",
    "tools/ci/test_land_contact_summary.py",
    "plugins/robot_windows/sequence_probe/sequence_probe.js",
    # The product Blockly definition contract is executed by Runtime student-ui.
    # Generic tools/ci/** must not select Webots alone and skip that owner.
    "tools/ci/test_blockly_v2_product_definitions.js",
    "tools/ci/test_progression_sequence_contract.js",
    # Activity 6's positive/negative native proof is in Runtime progression shard 4.
    # A Webots-only selection incorrectly reports green while skipping that proof.
    "tools/ci/run_progression_combined_decisions_mission.py",
    "tools/ci/test_progression_combined_decisions_contract.js",
    "tools/ci/test_activity6_setup_phase.py",
    # Each of these runs or checks the autonomous R2025a RESET probe.
    # Their earlier generic tools/ci match selected Webots only, silently
    # skipping the real runtime-v2-core job that owns their native evidence.
    "tools/ci/run_progression_autonomous_mission.py",
    "tools/ci/test_progression_autonomous_contract.js",
    "tools/ci/fixtures/autonomous_reset_observer.py",
    "tools/ci/reset_native_summary.py",
    "tools/ci/test_reset_native_summary.py",
    "tools/ci/reset_post_teleport.py",
    "tools/ci/test_reset_post_teleport.py",
    "experiments/runtime-v2-student-ui/**",
    "controllers/crazyflie_runtime_v2/**",
    "worlds/crazyflie_runtime_v2*",
    "plugins/robot_windows/blockly/webeeblocks/wwi_backend.js",
)

# Grand Prix's native probes and their host diagnostics live in ci-runtime.yml
# (grand-prix-prototype), not in ci-webots.yml. Keep existing Webots coverage
# and additionally select the Runtime suite for changes to those exact inputs.
GRAND_PRIX_RUNTIME_EVIDENCE = (
    "tools/ci/*grand_prix*",
    # These gp_u_* native pose fixtures are compiled by the Windows composition
    # test in ci-runtime.yml; the original grand_prix* name glob misses them.
    "tools/ci/fixtures/gp_u_*",
    "tools/ci/*webots_startup_diagnostics*",
)


# These native visual and Windows release checks are executed by ci-runtime.yml,
# not by ci-webots.yml. A generic tools/ci or controllers path selects only
# Webots; select Runtime as well without dropping existing Webots evidence.
RUNTIME_VISUAL_RELEASE_EVIDENCE = (
    "controllers/color_led_visual_probe/**",
    "tools/ci/*color_led*",
    "tools/ci/test_windows_classroom_release.ps1",
)

# These real R2025a progression/oracle inputs belong to ci-runtime.yml.
# Generic tools/ci/** otherwise selects Webots only, skipping their owner.
# Match future progression scripts/tests conservatively; never drop Webots.
RUNTIME_ORACLE_EVIDENCE = (
    "tools/ci/run_progression_*",
    "tools/ci/test_progression_*",
    "tools/ci/run_classroom_neutral_start.py",
    "tools/ci/test_runtime_activity_outcome.js",
    # Shared WWI event ingestion is also directly invoked from Runtime jobs.
    "tools/ci/runtime_wwi_event_server.py",
)


def matches(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)

@dataclass(frozen=True)
class Selection:
    runtime: bool
    webots: bool
    full: bool
    reason: str
    paths: tuple[str, ...]

    def outputs(self) -> dict[str, str]:
        return {
            "runtime": str(self.runtime).lower(),
            "webots": str(self.webots).lower(),
            "full": str(self.full).lower(),
            "reason": self.reason,
        }

def select(paths: Iterable[str], *, force_full: bool = False) -> Selection:
    changed = tuple(sorted({path.strip() for path in paths if path.strip()}))
    if force_full:
        return Selection(True, True, True, "scheduled or manual full verification", changed)
    if not changed:
        return Selection(True, True, True, "empty or indeterminate diff", changed)
    if any(matches(path, FORCE_FULL) for path in changed):
        return Selection(True, True, True, "full-gate path changed", changed)
    runtime = False
    webots = False
    unknown: list[str] = []
    for path in changed:
        if matches(path, PHYSICAL_RUNTIME_EVIDENCE):
            runtime = True
        if matches(path, DOC_ONLY):
            continue
        if (matches(path, SHARED_RUNTIME_WEBOTS) or matches(path, GRAND_PRIX_RUNTIME_EVIDENCE)
                or matches(path, RUNTIME_VISUAL_RELEASE_EVIDENCE)
                or matches(path, RUNTIME_ORACLE_EVIDENCE)):
            runtime = True
            webots = True
        elif matches(path, RUNTIME):
            runtime = True
        elif matches(path, WEBOTS):
            webots = True
        else:
            unknown.append(path)
    if unknown:
        return Selection(True, True, True, f"unknown/shared path: {unknown[0]}", changed)
    reason = "documentation only" if not runtime and not webots else "path-scoped suites"
    return Selection(runtime, webots, False, reason, changed)

def git_changed_paths(base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", f"{base}...{head}"],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.splitlines()

def write_github_output(path: Path, selection: Selection) -> None:
    with path.open("a", encoding="utf-8") as stream:
        for key, value in selection.outputs().items():
            stream.write(f"{key}={value}\n")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--base-ref", default="")
    parser.add_argument("--draft", default="false")
    parser.add_argument("--paths-file", type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    if args.draft.lower() == "true":
        selection = Selection(False, False, False, "draft PR", ())
    else:
        force_full = args.event != "pull_request"
        if args.paths_file:
            paths = args.paths_file.read_text(encoding="utf-8").splitlines()
        elif force_full:
            paths = ()
        elif args.base and args.head:
            paths = git_changed_paths(args.base, args.head)
        else:
            paths = ()
        selection = select(paths, force_full=force_full)

    if args.github_output:
        write_github_output(args.github_output, selection)
    print(json.dumps({**selection.outputs(), "paths": selection.paths}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

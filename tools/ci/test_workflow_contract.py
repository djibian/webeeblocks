#!/usr/bin/env python3
"""Static contract for V5 CI and human-checkpoint topology."""

from pathlib import Path
import sys
import json
import re
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"

EXPECTED = {
    "human-checkpoint.yml": {"validate", "historical-boost-support", "runtime", "webots", "physical", "publish"},
    "ci.yml": {"select", "runtime", "webots", "gate"},
    "ci-optimization.yml": {"analyze"},
    "ci-runtime.yml": {
        "grand-prix-prototype",
        "runtime-v2-core", "runtime-v2-progression", "runtime-v2-windows-assets", "runtime-v2-windows-release",
        "clean-checkout-runtime-v2", "runtime-v2-observability",
        "runtime-v2-project-files", "reset-contract-fast", "reset-replay-webots",
        "runtime-v2-webots", "student-ui", "grand-prix-u-geometry",
    },
    "ci-webots.yml": {
        "crazyflie-ab-matrix", "crazyflie-b-edges", "crazyflie-blockly-l",
        "timed-challenge-ux", "first-collision-obstacle", "crazyflie-l-course",
        "parametric-blockly-obstacle", "crazyflie-primitive-matrix",
        "crazyflie-runtime-wwi", "crazyflie-square-position", "crazyflie-square",
        "stop-vs-chain", "strategy-timing", "historical-blockly-ui",
        "encoders-historical", "gyro-gps-historical", "light-sensor-historical",
        "sensor-probing-historical", "robot-window-roundtrip", "webots-smoke",
        "s3-surface-offset-build", "c-world-z-research",
    },
}

def job_ids(text: str) -> set[str]:
    jobs = text.split("\njobs:\n", 1)[1]
    return set(re.findall(r"^  ([A-Za-z0-9_-]+):\s*$", jobs, re.MULTILINE))

def workflow_files() -> list[Path]:
    return sorted(
        path for path in WORKFLOWS.iterdir()
        if path.is_file() and path.suffix in {".yml", ".yaml"}
    )

class WorkflowTests(unittest.TestCase):
    def test_only_approved_workflows_exist(self):
        names = {path.name for path in workflow_files()}
        self.assertEqual(names, set(EXPECTED))

    def test_inventory_rejects_extra_or_missing_workflows(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for name in EXPECTED:
                (directory / name).touch()
            with patch(f"{__name__}.WORKFLOWS", directory):
                self.test_only_approved_workflows_exist()
                for suffix in (".yml", ".yaml"):
                    with self.subTest(suffix=suffix):
                        extra = directory / f"unexpected{suffix}"
                        extra.touch()
                        with self.assertRaises(AssertionError):
                            self.test_only_approved_workflows_exist()
                        extra.unlink()
                (directory / "ci.yml").unlink()
                with self.assertRaises(AssertionError):
                    self.test_only_approved_workflows_exist()

    def test_push_trigger_check_covers_both_yaml_extensions(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            with patch(f"{__name__}.WORKFLOWS", directory):
                for suffix in (".yml", ".yaml"):
                    with self.subTest(suffix=suffix):
                        workflow = directory / f"unexpected{suffix}"
                        workflow.write_text("on:\n  push:\n", encoding="utf-8")
                        with self.assertRaises(AssertionError):
                            self.test_no_post_merge_push_trigger()
                        workflow.unlink()

    def test_advisory_optimization_has_no_merge_authority(self):
        workflow = (WORKFLOWS / "ci-optimization.yml").read_text(encoding="utf-8")
        self.assertTrue(workflow.startswith("name: CI Optimization (advisory)\n"))
        self.assertIn("  schedule:\n", workflow)
        self.assertIn("  workflow_dispatch:\n", workflow)
        self.assertIn("  actions: read\n", workflow)
        self.assertIn("  contents: read\n", workflow)
        self.assertIn("run: python3 -m unittest discover -s tools/ci -p test_ci_optimization_report.py", workflow)
        self.assertIn("python3 tools/ci/ci_optimization_report.py", workflow)
        self.assertNotIn("\n  push:", workflow)
        self.assertNotIn("\n  pull_request:", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("pull-requests: write", workflow)
        self.assertNotIn("issues: write", workflow)
        self.assertNotIn("name: CI Gate\n", workflow)

    def test_parametric_obstacle_browser_archive_is_reused_with_integrity(self):
        # A second HTTP GET between direct and detour silently failed with wget
        # exit 8 on PR #643; native oracles must remain unchanged.
        source = (WORKFLOWS / "ci-webots.yml").read_text(encoding="utf-8")
        scoped = source.split("\n  parametric-blockly-obstacle:\n", 1)[1].split(
            "\n  crazyflie-primitive-matrix:\n", 1)[0]
        direct = scoped.split("      - name: Run direct Blockly mission into physical obstacle", 1)[1].split(
            "      - name: Run Blockly L detour around the same obstacle", 1)[0]
        detour = scoped.split("      - name: Run Blockly L detour around the same obstacle", 1)[1]
        cache = 'webeeblocks-parametric-browser'
        self.assertIn('mkdir -p "$RUNNER_TEMP/' + cache + '"', scoped)
        self.assertIn('-v "$RUNNER_TEMP/' + cache + ':/browser-cache"', direct)
        self.assertIn('-v "$RUNNER_TEMP/' + cache + ':/browser-cache:ro"', detour)
        self.assertEqual(scoped.count('https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb'), 1)
        self.assertIn('wget --server-response --no-verbose -O /browser-cache/google-chrome.deb', direct)
        self.assertNotIn('wget --server-response', detour)
        self.assertNotIn('wget -q -O', detour)
        for phase in (direct, detour):
            self.assertIn('sha256sum -c google-chrome.sha256', phase)
            self.assertIn('apt-get install -y /browser-cache/google-chrome.deb', phase)
            self.assertIn('set -e', phase)
        self.assertIn('timeout -k 5s 45s xvfb-run', direct)
        self.assertIn('timeout -k 5s 60s xvfb-run', detour)
        self.assertIn('WEBEEBLOCKS_OBSTACLE_RESULT status=COLLISION', direct)
        self.assertIn('WEBEEBLOCKS_CF_L_RESULT status=success gates=2', detour)

    def test_job_sets(self):
        for name, expected in EXPECTED.items():
            self.assertEqual(job_ids((WORKFLOWS / name).read_text(encoding="utf-8")), expected, name)

    def test_native_progression_sharding_preserves_required_gate(self):
        runtime = (WORKFLOWS / "ci-runtime.yml").read_text(encoding="utf-8")
        core = runtime.split("\n  runtime-v2-core:\n", 1)[1].split(
            "\n  runtime-v2-progression:\n", 1
        )[0]
        shards = runtime.split("\n  runtime-v2-progression:\n", 1)[1].split(
            "\n  runtime-v2-windows-assets:\n", 1
        )[0]
        self.assertIn("WEBEEBLOCKS_CI_NATIVE_PROGRESSION_MODE: sharded", core)
        self.assertIn("WEBEEBLOCKS_RESET_PHASE_TRACE: '1'", core)
        self.assertIn("WEBEEBLOCKS_RESET_PHASE_DEFER_STEPS: '0'", core)
        for required in (
            "runs-on: ubuntu-22.04",
            "timeout-minutes: 60",
            "fail-fast: false",
            "shard: [0, 1, 2, 3, 4, 5, 6]",
            "ref: ${{ inputs.target_sha || github.sha }}",
            "node-version: '22'",
            "bash ./tools/prepare_runtime_v2.sh",
            "WEBEEBLOCKS_RESET_PHASE_TRACE: '1'",
            "WEBEEBLOCKS_RESET_PHASE_DEFER_STEPS: '0'",
            "WEBEEBLOCKS_CI_TARGET_SHA: ${{ inputs.target_sha || github.sha }}",
            'python3 tools/ci/run_runtime_v2_outcome_probe.py --shard "${{ matrix.shard }}"',
            "Require full native shard attestation",
            "test -s ci-artifacts/runtime-v2-progression-shard-${{ matrix.shard }}/manifest.json",
            "if: always()",
            "name: runtime-v2-progression-shard-${{ matrix.shard }}",
            "ci-artifacts/runtime-v2-progression-shard-${{ matrix.shard }}/",
            "ci-artifacts/runtime-v2-outcome-provider/",
            "ci-artifacts/progression-*/",
            "if-no-files-found: error",
        ):
            self.assertIn(required, shards)
        self.assertNotIn("continue-on-error:", shards)
        self.assertNotIn("if: false", shards)
        self.assertNotIn("needs:", shards)
        outcome = (ROOT / "tools/ci/test_runtime_activity_outcome.js").read_text(encoding="utf-8")
        for required in (
            "if (mode !== undefined)",
            "assert.strictEqual(mode, 'sharded'",
            "assert.strictEqual(process.env.GITHUB_ACTIONS, 'true'",
            "assert.strictEqual(process.env.GITHUB_JOB, 'runtime-v2-core'",
            "proveRealWebotsOutcomeFreshness();",
        ):
            self.assertIn(required, outcome)
        gate = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("uses: ./.github/workflows/ci-runtime.yml", gate)
        self.assertIn("needs: [select, runtime, webots]", gate)
        self.assertIn("python3 tools/ci/check_ci_gate.py", gate)

    def test_student_ui_real_webots_oracle_retained_with_outer_budget(self):
        # Canonical Ready CI 39777648835 proved all seven progression shards,
        # but student-ui was canceled at its old 15-minute outer budget.
        # Keep the full physical/visual assertion chain rather than skipping it.
        runtime = (WORKFLOWS / "ci-runtime.yml").read_text(encoding="utf-8")
        student = runtime.split("\n  student-ui:\n", 1)[1].split(
            "\n  runtime-v2-windows-release:\n", 1
        )[0]
        for required in (
            "timeout-minutes: 30",
            "python3 tools/ci/run_runtime_v2_core_harness.py",
            "docker pull ghcr.io/djibian/webeeblocks-qt665-r2025a@sha256:7a9272dfef96e7668f8f31eaac9099b0417a9028e3181df6f8376eea59fe1aca",
            "bash /workspace/experiments/runtime-v2-student-ui/run.sh",
            "Validate visual shell, strict AST and keyboard path",
            "test -s ci-artifacts/runtime-v2-student-ui/metrics.json",
            "test -s ci-artifacts/runtime-v2-student-ui/workspace-1366x768.png",
            "if: always()",
            "if-no-files-found: error",
        ):
            self.assertIn(required, student)
        self.assertNotIn("continue-on-error:", student)
        self.assertNotIn("if: false", student)

    def test_bounded_native_jobs_retain_complete_oracles_after_outer_budget_adjustment(self):
        # CI 39782202176: two jobs reached their original 12/15-min outer
        # budgets. All native constraints, assertions and event chains remain.
        runtime = (WORKFLOWS / "ci-runtime.yml").read_text(encoding="utf-8")
        obs = runtime.split("\n  runtime-v2-observability:\n", 1)[1].split(
            "\n  runtime-v2-project-files:\n", 1
        )[0]
        for required in (
            "timeout-minutes: 30",
            "node tools/ci/test_runtime_v2_observability.js",
            "Run real wall-blocked action to controller fail-safe",
            "timeout -k 5s 190s xvfb-run",
            "if: always()",
            "if-no-files-found: error",
        ):
            self.assertIn(required, obs)
        self.assertNotIn("continue-on-error:", obs)
        self.assertNotIn("if: false", obs)

        webots = (WORKFLOWS / "ci-webots.yml").read_text(encoding="utf-8")
        challenge = webots.split("\n  timed-challenge-ux:\n", 1)[1].split(
            "\n  first-collision-obstacle:\n", 1
        )[0]
        for required in (
            "timeout-minutes: 30",
            "Run three student attempts in one Robot Window session",
            "for i in $(seq 1 1500)",
            "Prove causal states timer results and same-session resubmission",
            "test -s ci-artifacts/crazyflie-challenge-ux/complete.sentinel",
            "WEBEEBLOCKS_MISSION_V1 VALIDATED",
            "CHALLENGE_TEST_COMPLETE",
            "if: always()",
            "if-no-files-found: warn",
        ):
            self.assertIn(required, challenge)
        self.assertNotIn("continue-on-error:", challenge)
        self.assertNotIn("if: false", challenge)

    def test_runtime_v2_webots_dynamic_evidence_retained_after_outer_budget_adjustment(self):
        # Run 39798558609: the original 12-minute runner envelope cancelled
        # the dynamic Blockly/Webots proof, despite intact native timeouts.
        # A raised outer budget must never omit downstream assertions.
        runtime = (WORKFLOWS / "ci-runtime.yml").read_text(encoding="utf-8")
        webots = runtime.split("\n  runtime-v2-webots:\n", 1)[1].split(
            "\n  student-ui:\n", 1
        )[0]
        for required in (
            "timeout-minutes: 30",
            "Re-prove Runtime v2 semantic core",
            "Render fixed Color LED evidence in official Webots R2025a",
            "Prove Color LED is perceptible from fixed normal views",
            "Run real Blockly to dynamic Webots Runtime v2",
            "timeout -k 5s 300s xvfb-run",
            "Prove pre-READY gate, pinned Blockly runtime and dynamic STOP actions",
            "test -s ci-artifacts/runtime-v2-webots/browser-launch.log",
            "grep -Fq 'WEBEEBLOCKS_RUNTIME_V2 READY' \"$LOG\"",
            "if: always()",
            "if-no-files-found: error",
        ):
            self.assertIn(required, webots)
        self.assertNotIn("continue-on-error:", webots)
        self.assertNotIn("if: false", webots)

    def test_historical_webots_jobs_keep_all_oracles_with_runner_headroom(self):
        # CI 39809565629: apt index/network stalls consumed the entire
        # external envelopes (smoke 7 min; strategy 12 min). No native oracle,
        # offline-world condition or test-level timeout may be altered.
        suite = (WORKFLOWS / "ci-webots.yml").read_text(encoding="utf-8")
        smoke = suite.split("\n  webots-smoke:\n", 1)[1]
        strategy = suite.split("\n  strategy-timing:\n", 1)[1].split(
            "\n  historical-blockly-ui:\n", 1
        )[0]
        for required in (
            "timeout-minutes: 30",
            "Checkout pinned Webots R2025a projects",
            "Execute historical Blockly browser oracle",
            "Rebuild and exercise Blockly sidecar protocol",
            "Rebuild supervisor for Webots R2025a",
            "Run historical empty world in Webots R2025a",
            "Validate Webots runtime diagnostics",
            "Execute generated historical controller in box challenge",
            "Exercise simulation reset and controller restart",
            "Validate controller restart diagnostics",
            "if: always()",
            "if-no-files-found: error",
        ):
            self.assertIn(required, smoke)
        self.assertEqual(smoke.count("--network none"), 3)
        for required in (
            "timeout-minutes: 30",
            "Run both Blockly strategies in fresh Webots processes",
            "run_strategy S0 controllers/Blockly_Programs/CrazyflieL.xml",
            "run_strategy S1 controllers/Blockly_Programs/CrazyflieShortcut85.xml",
            "source /workspace/tools/ci/stop_webots_group.sh",
            "Compare physical success and Webots times",
            "assert delta > 0.0",
            "if: always()",
            "if-no-files-found: error",
        ):
            self.assertIn(required, strategy)
        for text in (smoke, strategy):
            self.assertNotIn("continue-on-error:", text)
            self.assertNotIn("if: false", text)

    def test_native_progression_partition_is_complete_and_fail_closed(self):
        # Unit-check the actual dispatch code; never run or stub a physical
        # acceptance oracle. The required native scripts run in CI unchanged.
        import importlib.util
        from types import SimpleNamespace

        path = ROOT / "tools/ci/run_runtime_v2_outcome_probe.py"
        spec = importlib.util.spec_from_file_location("progression_shard_test_target", path)
        probe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(probe)
        exact_scripts = (
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
        self.assertEqual(probe.PROGRESSION, exact_scripts)
        self.assertEqual(probe.proofs_for_job("runtime-v2-core"),
                         (probe.FRESHNESS, *exact_scripts))
        self.assertEqual(probe.proofs_for_job("runtime-v2-webots"), (probe.FRESHNESS,))
        self.assertEqual(probe.proofs_for_job("student-ui"), (probe.FRESHNESS,))
        expected_groups = ((0, 3), (1,), (2,), (4, 7), (5,), (6,), (8,))
        self.assertEqual(probe.SHARD_INDICES, expected_groups)
        visited = []
        for shard in range(len(expected_groups)):
            actual = probe.proofs_for_shard(shard)
            self.assertEqual(actual[0], probe.FRESHNESS)
            self.assertEqual(actual[1:], tuple(exact_scripts[i] for i in expected_groups[shard]))
            visited.extend(actual[1:])
        self.assertEqual(len(visited), 9)
        self.assertEqual(set(visited), set(exact_scripts))
        for invalid in (-1, len(expected_groups), 99):
            with self.assertRaises(ValueError):
                probe.proofs_for_shard(invalid)

        # An exit code from any native mission is never converted to PASS and
        # subsequent missions are not executed after a failed dependency.
        with patch.object(probe.sys, "argv", [str(path), "--shard", "1"]):
            with patch.object(probe.subprocess, "run",
                              side_effect=[SimpleNamespace(returncode=0),
                                           SimpleNamespace(returncode=17)]) as runner:
                self.assertEqual(probe.main(), 17)
        self.assertEqual(runner.call_count, 2)
        self.assertEqual(runner.call_args_list[0].args[0][1], probe.FRESHNESS)
        self.assertEqual(runner.call_args_list[1].args[0][1], exact_scripts[1])

    def test_ci_targets_main_only(self):
        text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("branches: [main]", text)
        self.assertNotIn("develop", text)
        self.assertIn("types: [opened, synchronize, reopened, ready_for_review]", text)

    def test_ready_gate_is_exact_head_and_draft_has_distinct_check_name(self):
        text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        candidate = "${{ github.event.pull_request.head.sha || github.sha }}"
        self.assertEqual(text.count(candidate), 4)
        self.assertNotIn("target_sha: ${{ github.sha }}", text)
        self.assertIn(
            "github.event.pull_request.draft && 'CI Gate (Draft)' || 'CI Gate'",
            text,
        )
        self.assertIn('--draft "${{ github.event.pull_request.draft || false }}"', text)

    def test_main_pr_is_not_implicit_full_promotion(self):
        selector = (ROOT / "tools" / "ci" / "select_ci.py").read_text(encoding="utf-8")
        self.assertIn('force_full = args.event != "pull_request"', selector)
        self.assertNotIn('args.base_ref == "main"', selector)

    def test_checkpoint_is_exact_full_single_slot_and_fail_closed(self):
        text = (WORKFLOWS / "human-checkpoint.yml").read_text(encoding="utf-8")
        for required in (
            "CHECKPOINT_REQUEST ([0-9a-f]{40})",
            "github.actor == 'djibian'",
            "uses: ./.github/workflows/ci-runtime.yml",
            "uses: ./.github/workflows/ci-webots.yml",
            "full: true",
            "group: webeeblocks-human-test-open",
            "WEBEEBLOCKS_HUMAN_TEST_OPEN=1",
            "WEBEEBLOCKS_TEST_FINGERPRINT=",
            "'windows-low-end': 'WebeeBlocks-Windows-R2025a',",
            "'s3-props-off': 'experimental-s3-surface-offset-2026-08',",
            "'s3-props-off': {'checkpoint'},",
            "'physical-capabilities-readonly': 'WebeeBlocks-Physical-Capability-Probe',",
            "'physical-capabilities-readonly': {'checkpoint'},",
            "needs.validate.outputs.test_profile == 'physical-capabilities-readonly'",
            "repository: bitcraze/crazyflie-lib-python",
            "ref: 45fdb784c9d13074c42835f3b5ac1d12133bf873",
            "git -C .ci-cflib rev-parse 'HEAD:cflib'",
            "--no-deps --only-binary=:all:",
            "sha256sum -c",
            'PYTHONPATH="$ambient" "$bundle/run_reference_probe.sh" --verify-environment',
            "name: WebeeBlocks-Physical-Capability-Probe",
            "Purpose {purpose} is not allowed for profile {profile}",
            "Unknown test profile; add deterministic preparation before enabling it",
            "Required artifact is missing a valid sha256 digest",
            "sha256:[0-9a-f]{64}",
            "/issues?state={state}&per_page=100&page={page}",
            "[TEST_REQUIRED]",
            "https://ntfy.sh/",
        ):
            self.assertIn(required, text)
        self.assertNotIn("search/issues", text)
        self.assertNotIn("artifact.get('digest', 'unavailable')", text)
        self.assertNotIn("profile.startswith('windows')", text)
        webots = (WORKFLOWS / "ci-webots.yml").read_text(encoding="utf-8")
        self.assertIn(
            "cp .ci-crazyflie-firmware/build/cf2.bin ci-artifacts/s3-surface-offset/cf2.bin",
            webots,
        )
        self.assertIn(
            "name: experimental-s3-surface-offset-2026-08",
            webots,
        )
        for obsolete in ("READY_FOR_REVIEW", "SESSION_LIMIT", "RELANCE CONTRÔLEUR", "Candidate Evidence"):
            self.assertNotIn(obsolete, text)

    def test_grand_prix_windows_checkpoint_requires_exact_native_artifact(self):
        checkpoint = (WORKFLOWS / "human-checkpoint.yml").read_text(encoding="utf-8")
        suite = (WORKFLOWS / "ci-runtime.yml").read_text(encoding="utf-8")
        self.assertIn("'grand-prix-windows': 'grand-prix-u-windows-project',", checkpoint)
        self.assertIn("'grand-prix-windows': {'checkpoint'},", checkpoint)
        self.assertNotIn("'grand-prix-windows': {'checkpoint', 'release'}", checkpoint)
        self.assertIn("full: true", checkpoint)
        self.assertIn("uses: ./.github/workflows/ci-runtime.yml", checkpoint)
        self.assertIn("needs.runtime.result == 'success'", checkpoint)
        self.assertIn("matching = [a for a in artifacts if a.get('name') == required_artifact]", checkpoint)
        self.assertIn("if len(matching) != 1:", checkpoint)
        self.assertIn("if artifact.get('expired'):", checkpoint)
        self.assertIn("sha256:[0-9a-f]{64}", checkpoint)
        release = suite.split("\n  runtime-v2-windows-release:\n", 1)[1].split(
            "\n  grand-prix-prototype:\n", 1
        )[0]
        self.assertIn("inputs.full", release)
        self.assertIn("ref: ${{ inputs.target_sha || github.sha }}", release)
        self.assertIn("Falsify installed Grand Prix project closure", release)
        self.assertIn("test_grand_prix_windows_project.ps1", release)
        self.assertIn("name: grand-prix-u-windows-native", release)
        self.assertIn("name: grand-prix-u-windows-project", release)
        self.assertIn(
            "path: ci-artifacts/gp-windows-project/WebeeBlocks-Grand-Prix-Windows-R2025a.zip",
            release,
        )
        self.assertIn("if-no-files-found: error", release)
        self.assertLess(
            release.index("Falsify installed Grand Prix project closure"),
            release.index("Upload installed Grand Prix Windows project"),
        )
        self.assertLess(
            release.index("test_grand_prix_windows_project.ps1"),
            release.index("name: grand-prix-u-windows-project"),
        )
        native = release.split("      - name: Falsify installed Grand Prix project closure", 1)[1]
        upload = release.split("      - name: Upload installed Grand Prix Windows project", 1)[1]
        self.assertIn("test_grand_prix_windows_native.py", native)
        self.assertIn("test_grand_prix_windows_project.ps1", native)
        self.assertIn("if-no-files-found: error", upload)

    def test_checkpoint_python_heredocs_remain_inside_yaml_scalars(self):
        text = (WORKFLOWS / "human-checkpoint.yml").read_text(encoding="utf-8")
        blocks = text.split("          python3 - <<'PY'\n")[1:]
        self.assertEqual(len(blocks), 3)
        for block in blocks:
            body, separator, _ = block.partition("          PY\n")
            self.assertTrue(separator, "checkpoint Python heredoc is not closed at YAML scalar indentation")
            for line in body.splitlines():
                if line:
                    self.assertTrue(
                        line.startswith("          "),
                        f"checkpoint Python escaped YAML scalar indentation: {line!r}",
                    )

    def test_checkpoint_ignores_spoofed_slot_and_fingerprint_markers(self):
        text = (WORKFLOWS / "human-checkpoint.yml").read_text(encoding="utf-8")
        for required in (
            "'pull_request' not in item",
            ".startswith('[TEST_REQUIRED] ')",
            "user.get('login') == 'github-actions[bot]'",
            "WEBEEBLOCKS_TEST_FINGERPRINT=[0-9a-f]{64}$",
            "history = [item for item in issues('all') if canonical_test_issue(item)]",
        ):
            self.assertIn(required, text)
        self.assertNotIn("history = issues('all')\n          if any(marker", text)

    def test_reusable_suites_receive_exact_target(self):
        ci = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        candidate = "${{ github.event.pull_request.head.sha || github.sha }}"
        self.assertEqual(ci.count(f"target_sha: {candidate}"), 2)
        target = "ref: ${{ inputs.target_sha || github.sha }}"
        for name in ("ci-runtime.yml", "ci-webots.yml"):
            suite = (WORKFLOWS / name).read_text(encoding="utf-8")
            all_checkouts = suite.count("uses: actions/checkout@v4")
            external = (
                suite.count("repository: cyberbotics/webots")
                + suite.count("repository: bitcraze/crazyflie-firmware")
            )
            self.assertEqual(suite.count(target), all_checkouts - external, name)

    def test_s3_build_is_bounded_before_external_checkout(self) -> None:
        suite = (WORKFLOWS / "ci-webots.yml").read_text(encoding="utf-8")
        s3 = suite.split("\n  s3-surface-offset-build:\n", 1)[1].split(
            "\n  crazyflie-ab-matrix:\n", 1
        )[0]
        self.assertIn("python3 tools/ci/select_s3_build.py", s3)
        self.assertIn("id: s3-scope", s3)
        self.assertIn("fetch-depth: 0", s3)
        self.assertGreaterEqual(
            s3.count("if: steps.s3-scope.outputs.run == 'true'"), 2
        )
        self.assertEqual(
            s3.count("always() && steps.s3-scope.outputs.run == 'true'"), 2
        )
        orchestrator = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("python3 tools/ci/test_select_s3_build.py", orchestrator)
        selector = (ROOT / "tools" / "ci" / "select_s3_build.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"experiments/crazyflie-ukf-surface-range/**"', selector)
        self.assertIn('".github/workflows/ci-webots.yml"', selector)


    def test_robot_window_roundtrip_ack_proof_survives_webots_shutdown(self) -> None:
        suite = (WORKFLOWS / "ci-webots.yml").read_text(encoding="utf-8")
        job = suite.split("\n  robot-window-roundtrip:\n", 1)[1].split(
            "\n  webots-smoke:\n", 1
        )[0]
        controller = (
            ROOT / "controllers" / "ci_robot_window_probe" / "ci_robot_window_probe.py"
        ).read_text(encoding="utf-8")

        proof = "robot-window-roundtrip-proof.txt"
        self.assertIn("timeout-minutes: 8", job)
        self.assertIn("timeout -k 5s 60s", job)
        self.assertIn('grep -Fq "BROWSER_LAUNCHED"', job)
        self.assertIn('grep -F "WEBEEBLOCKS_CI_WINDOW_TO_CONTROLLER_OK" "$LOG"', job)
        self.assertIn('grep -F "WEBEEBLOCKS_CI_CONTROLLER_TO_WINDOW_SENT" "$LOG"', job)
        self.assertIn(f"rm -f ci-artifacts/{proof}", job)
        self.assertIn(f"PROOF=ci-artifacts/{proof}", job)
        self.assertIn(
            'grep -Fx "WEBEEBLOCKS_CI_WWI_RX=WEBEEBLOCKS_CI_WINDOW_ACK" "$PROOF"',
            job,
        )
        self.assertIn(
            'grep -Fx "WEBEEBLOCKS_CI_ROBOT_WINDOW_ROUNDTRIP_OK" "$PROOF"',
            job,
        )
        self.assertNotIn(
            'grep -F "WEBEEBLOCKS_CI_WWI_RX=WEBEEBLOCKS_CI_WINDOW_ACK" "$LOG"',
            job,
        )
        self.assertNotIn(
            'grep -F "WEBEEBLOCKS_CI_ROBOT_WINDOW_ROUNDTRIP_OK" "$LOG"',
            job,
        )

        self.assertIn(proof, controller)
        self.assertIn('elif message == ACK:', controller)
        self.assertIn('temp_proof.replace(PROOF)', controller)
        self.assertLess(
            controller.index('temp_proof.replace(PROOF)'),
            controller.index('robot.simulationQuit(0)'),
        )

    def test_windows_release_requires_full_or_non_pr_and_is_pinned(self) -> None:
        orchestrator = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        runtime = (WORKFLOWS / "ci-runtime.yml").read_text(encoding="utf-8")
        self.assertIn("full: ${{ needs.select.outputs.full == 'true' }}", orchestrator)
        release = runtime.split("\n  runtime-v2-windows-release:\n", 1)[1]
        self.assertIn("github.event_name != 'pull_request' || inputs.full", release)
        self.assertIn("ref: c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b", release)
        self.assertIn(
            "9e326a54c104fc5fc88121e26014a409d1e35f0bbf30e23f3a712e7f842b08e7",
            release,
        )
        self.assertIn("test_windows_classroom_release.ps1", release)

    def test_webots_projects_checkout_is_commit_pinned(self) -> None:
        suite = (WORKFLOWS / "ci-webots.yml").read_text(encoding="utf-8")
        self.assertNotIn("ref: R2025a", suite)
        self.assertEqual(
            suite.count("ref: c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b"),
            5,
        )

    def test_encoders_historical_runtime_is_offline(self) -> None:
        suite = (WORKFLOWS / "ci-webots.yml").read_text(encoding="utf-8")
        encoders = suite.split("\n  encoders-historical:\n", 1)[1].split(
            "\n  gyro-gps-historical:\n", 1
        )[0]
        self.assertIn("Prepare offline historical encoder world", encoders)
        self.assertIn(
            "/workspace/worlds/.ci-boxChallenge-encoders-local.wbt",
            encoders,
        )
        self.assertIn("--network none", encoders)
        self.assertIn("/usr/local/webots/projects:ro", encoders)

    def test_gyro_gps_historical_runtime_is_offline(self) -> None:
        suite = (WORKFLOWS / "ci-webots.yml").read_text(encoding="utf-8")
        gyro = suite.split("\n  gyro-gps-historical:\n", 1)[1].split(
            "\n  light-sensor-historical:\n", 1
        )[0]
        self.assertIn("timeout-minutes: 5", gyro)
        self.assertIn("timeout -k 5s 30s xvfb-run", gyro)
        self.assertIn("ref: c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b", gyro)
        for subtree in ("robots/adept/pioneer3", "objects/backgrounds", "objects/floors", "objects/apartment_structure", "objects/solids", "appearances", "default"):
            self.assertIn("projects/" + subtree, gyro)
        self.assertNotIn("sparse-checkout: projects\n", gyro)
        self.assertIn("python3 tools/ci/check_gyro_gps_assets.py .ci-webots-r2025a", gyro)
        self.assertIn("Prepare offline historical Gyro GPS world", gyro)
        self.assertIn("/workspace/worlds/.ci-boxChallenge-gyro-gps-local.wbt", gyro)
        self.assertIn("--network none", gyro)
        self.assertIn("/usr/local/webots/projects:ro", gyro)

    def test_light_sensor_historical_runtime_is_offline(self) -> None:
        suite = (WORKFLOWS / "ci-webots.yml").read_text(encoding="utf-8")
        light = suite.split("\n  light-sensor-historical:\n", 1)[1].split(
            "\n  sensor-probing-historical:\n", 1
        )[0]
        self.assertIn("Prepare offline historical world", light)
        self.assertIn("/workspace/worlds/.ci-lightSensorBoxChallenge-local.wbt", light)
        self.assertIn("--network none", light)
        self.assertIn("/usr/local/webots/projects:ro", light)
        self.assertIn("Pinned Pioneer3dx motor seam changed", light)
        self.assertIn("seam + '\\n            sound \"\"'", light)
        self.assertIn("Expected exactly two Pioneer motor sound overrides.", light)

    def test_sensor_probing_historical_runtime_is_offline(self) -> None:
        suite = (WORKFLOWS / "ci-webots.yml").read_text(encoding="utf-8")
        sensor = suite.split("\n  sensor-probing-historical:\n", 1)[1].split(
            "\n  robot-window-roundtrip:\n", 1
        )[0]
        self.assertIn(
            "Prepare offline historical sensor-probing world",
            sensor,
        )
        self.assertIn(
            "/workspace/worlds/.ci-empty-sensor-probing-local.wbt",
            sensor,
        )
        self.assertIn("--network none", sensor)
        self.assertIn("/usr/local/webots/projects:ro", sensor)

    def test_webots_smoke_runtime_is_offline(self) -> None:
        suite = (WORKFLOWS / "ci-webots.yml").read_text(encoding="utf-8")
        smoke = suite.split("\n  webots-smoke:\n", 1)[1]
        self.assertIn("Prepare offline smoke worlds", smoke)
        self.assertIn("Checkout pinned Webots R2025a projects", smoke)
        self.assertIn("/workspace/worlds/.ci-empty-local.wbt", smoke)
        self.assertIn("/workspace/worlds/.ci-boxChallenge-local.wbt", smoke)
        self.assertEqual(smoke.count("--network none"), 3)
        self.assertEqual(smoke.count("/usr/local/webots/projects:ro"), 3)
        restart = (
            ROOT / "controllers" / "ci_restart_supervisor" / "restart_smoke.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'WORLD = ROOT / "worlds" / ".ci-empty-local.wbt"',
            restart,
        )

    def test_physical_checkpoint_support_is_fully_locked(self) -> None:
        lock = (ROOT / "tools" / "physical" / "reference_probe_lock.txt").read_text(encoding="utf-8")
        expected = {
            "pyusb==1.2.1|pyusb-1.2.1-py3-none-any.whl|2b4c7cb86dbadf044dfb9d3a4ff69fd217013dbe78a792177a3feb172449ea36",
            "libusb-package==1.0.26.3|libusb_package-1.0.26.3-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl|433e89dd1f9f9a4149b975247cf1d493170454945fec54b4db9fe61c9e6b861f",
            "importlib-resources==6.5.2|importlib_resources-6.5.2-py3-none-any.whl|789cfdc3ed28c78b67a06acb8126751ced69a3d5f79c095a98298cd8a760ccec",
            "numpy==2.2.6|numpy-2.2.6-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl|fc7b73d02efb0e18c000e9ad8b83480dfcd5dfd11065997ed4c6747470ae8915",
        }
        actual = {line for line in lock.splitlines() if line and not line.startswith("#")}
        self.assertEqual(actual, expected)

        workflow = (WORKFLOWS / "human-checkpoint.yml").read_text(encoding="utf-8")
        for required in (
            "45fdb784c9d13074c42835f3b5ac1d12133bf873",
            "a78cf78d2b4aba51a0fa2b03de0260664b523401",
            "750e850390753de14019f0e1f55d4fbc44317699",
            "--no-deps --only-binary=:all:",
            "--platform manylinux2014_x86_64",
            "--implementation cp --python-version 310 --abi cp310",
            "test \"$(find \"$wheelhouse\" -maxdepth 1 -type f -name '*.whl' | wc -l)\" -eq 4",
            "sha256sum -c \"$expected\"",
        ):
            self.assertIn(required, workflow)
        self.assertNotIn("pip wheel", workflow)

        runner = (ROOT / "tools" / "physical" / "run_reference_probe.sh").read_text(encoding="utf-8")
        for required in (
            "sha256sum -c SHA256SUMS",
            "--no-index --no-deps --ignore-installed",
            'PYTHONPATH="$HERE/cflib-source:$ISOLATED_SITE"',
            "PYTHONNOUSERSITE=1",
            "python3 -S",
            "exact four-wheel runtime closure required",
            "executionAuthority must remain false",
        ):
            self.assertIn(required, runner)

    def test_c_world_z_retained_results_are_ci_bound(self) -> None:
        suite = (WORKFLOWS / "ci-webots.yml").read_text(encoding="utf-8")
        lab = suite.split("  c-world-z-research:", 1)[1].split(
            "  s3-surface-offset-build:", 1
        )[0]
        self.assertIn("    if: github.workflow == 'CI Gate'\n", lab)
        self.assertTrue((WORKFLOWS / "ci.yml").read_text(encoding="utf-8").startswith("name: CI Gate\n"))
        self.assertEqual(suite.count("    if: github.workflow == 'CI Gate'\n"), 1)
        self.assertIn("Reject stale or tampered retained scientific results", lab)
        self.assertIn(
            "cmp -- experiments/crazyflie-c-world-z/results.json", lab
        )
        self.assertIn("ci-artifacts/c-world-z/results.json", lab)
        self.assertLess(lab.index("Recompute archived and synthetic scientific evidence"),
                        lab.index("Reject stale or tampered retained scientific results"))
        self.assertLess(lab.index("Reject stale or tampered retained scientific results"),
                        lab.index("Publish host-only research evidence"))

    def test_c_world_z_ci_comparison_rejects_material_evidence_mutation(self):
        suite = (WORKFLOWS / "ci-webots.yml").read_text(encoding="utf-8")
        comparison = suite.split("Reject stale or tampered retained scientific results", 1)[1]
        command = re.search(r"run: >-\n((?:          .+\n)+)", comparison)
        self.assertIsNotNone(command)
        argv = shlex.split(command.group(1))
        retained_path = "experiments/crazyflie-c-world-z/results.json"
        generated_path = "ci-artifacts/c-world-z/results.json"
        retained = (ROOT / retained_path).read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in (retained_path, generated_path):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(retained)
            self.assertEqual(subprocess.run(argv, cwd=root, capture_output=True).returncode, 0)
            mutated = json.loads(retained)
            mutated["archive"]["continuous_slow_from_50s"]["max_z_m"] = 0.005
            (root / retained_path).write_text(json.dumps(mutated), encoding="utf-8")
            self.assertNotEqual(subprocess.run(argv, cwd=root, capture_output=True).returncode, 0)

    def test_c_feasibility_oracle_runs_in_mandatory_select_job(self) -> None:
        # Scientific evidence is mandatory in the existing selector-contract
        # step, without editing ci.yml or triggering unrelated X3 firmware builds.
        ci = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        required = ci.split("- name: Verify selector and repository contracts", 1)[1]
        required = required.split("- name: Select required suites", 1)[0]
        self.assertIn("python3 tools/ci/test_workflow_contract.py", required)
        subprocess.run(
            [sys.executable, str(ROOT / "tools/ci/test_c_feasibility.py")],
            cwd=ROOT, check=True, timeout=120,
        )

    def test_strategy_timing_retires_the_owned_webots_group(self):
        webots = (WORKFLOWS / "ci-webots.yml").read_text(encoding="utf-8")
        strategy = webots.split("  strategy-timing:", 1)[1].split("\n  historical-blockly-ui:", 1)[0]
        self.assertIn("source /workspace/tools/ci/stop_webots_group.sh", strategy)
        self.assertIn("setsid xvfb-run -a webots", strategy)
        self.assertIn("--port=1234", strategy)
        self.assertEqual(strategy.count('stop_webots_group "$webots_pid"'), 2)
        self.assertNotIn('kill "$webots_pid"', strategy)
        subprocess.run([sys.executable, str(ROOT / "tools/ci/test_webots_group_cleanup.py")],
                       cwd=ROOT, check=True, timeout=20)

    def test_no_post_merge_push_trigger(self):
        for path in workflow_files():
            self.assertNotIn("  push:\n", path.read_text(encoding="utf-8"), path.name)

if __name__ == "__main__":
    unittest.main()

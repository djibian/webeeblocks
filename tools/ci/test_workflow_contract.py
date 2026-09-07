#!/usr/bin/env python3
"""Static contract for V4 CI and human-checkpoint topology."""

from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"

EXPECTED = {
    "human-checkpoint.yml": {"validate", "runtime", "webots", "physical", "publish"},
    "ci.yml": {"select", "runtime", "webots", "gate"},
    "ci-runtime.yml": {
        "runtime-v2-core", "runtime-v2-windows-assets", "runtime-v2-windows-release",
        "clean-checkout-runtime-v2", "runtime-v2-observability",
        "runtime-v2-project-files", "reset-contract-fast", "reset-replay-webots",
        "runtime-v2-webots", "student-ui",
    },
    "ci-webots.yml": {
        "crazyflie-ab-matrix", "crazyflie-b-edges", "crazyflie-blockly-l",
        "timed-challenge-ux", "first-collision-obstacle", "crazyflie-l-course",
        "parametric-blockly-obstacle", "crazyflie-primitive-matrix",
        "crazyflie-runtime-wwi", "crazyflie-square-position", "crazyflie-square",
        "stop-vs-chain", "strategy-timing", "historical-blockly-ui",
        "encoders-historical", "gyro-gps-historical", "light-sensor-historical",
        "sensor-probing-historical", "robot-window-roundtrip", "webots-smoke",
        "s3-surface-offset-build",
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
    def test_only_v4_workflows_exist(self):
        names = {path.name for path in workflow_files()}
        self.assertEqual(names, set(EXPECTED))

    def test_inventory_rejects_extra_or_missing_workflows(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for name in EXPECTED:
                (directory / name).touch()
            with patch(f"{__name__}.WORKFLOWS", directory):
                self.test_only_v4_workflows_exist()
                for suffix in (".yml", ".yaml"):
                    with self.subTest(suffix=suffix):
                        extra = directory / f"unexpected{suffix}"
                        extra.touch()
                        with self.assertRaises(AssertionError):
                            self.test_only_v4_workflows_exist()
                        extra.unlink()
                (directory / "ci.yml").unlink()
                with self.assertRaises(AssertionError):
                    self.test_only_v4_workflows_exist()

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

    def test_job_sets(self):
        for name, expected in EXPECTED.items():
            self.assertEqual(job_ids((WORKFLOWS / name).read_text(encoding="utf-8")), expected, name)

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
            "python3 tools/ci/test_physical_capability_probe.py",
            "node tools/ci/test_physical_capability_contract.js",
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

    def test_checkpoint_python_heredocs_remain_inside_yaml_scalars(self):
        text = (WORKFLOWS / "human-checkpoint.yml").read_text(encoding="utf-8")
        blocks = text.split("          python3 - <<'PY'\n")[1:]
        self.assertEqual(len(blocks), 2)
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
        self.assertIn("Prepare offline historical Gyro GPS world", gyro)
        self.assertIn("/workspace/worlds/.ci-boxChallenge-gyro-gps-local.wbt", gyro)
        self.assertIn("--network none", gyro)
        self.assertIn("/usr/local/webots/projects:ro", gyro)

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

    def test_physical_checkpoint_cflib_is_exact_commit(self):
        requirements = (
            ROOT / "tools" / "physical" / "reference_probe_requirements.txt"
        ).read_text(encoding="utf-8").strip()
        self.assertEqual(
            requirements,
            "cflib @ git+https://github.com/bitcraze/crazyflie-lib-python.git@"
            "45fdb784c9d13074c42835f3b5ac1d12133bf873",
        )

        workflow = (WORKFLOWS / "human-checkpoint.yml").read_text(encoding="utf-8")
        for required in (
            "python3 -m pip wheel --disable-pip-version-check",
            "-r tools/physical/reference_probe_requirements.txt",
            "cflib_commit=45fdb784c9d13074c42835f3b5ac1d12133bf873",
            "find . -type f ! -name SHA256SUMS -print0",
        ):
            self.assertIn(required, workflow)

        runner = (
            ROOT / "tools" / "physical" / "run_reference_probe.sh"
        ).read_text(encoding="utf-8")
        for required in (
            'sha256sum -c SHA256SUMS',
            "--no-index",
            '--find-links "$HERE/wheels"',
            "--ignore-installed",
            '--target "$ISOLATED_SITE"',
            "PYTHONNOUSERSITE=1",
            'python3 -S "$HERE/probe_reference_hardware.py"',
            "FAIL: exact packaged cflib wheel is missing or ambiguous",
        ):
            self.assertIn(required, runner)
        self.assertNotIn(
            'python3 "$HERE/probe_reference_hardware.py"',
            runner,
        )

    def test_no_post_merge_push_trigger(self):
        for path in workflow_files():
            self.assertNotIn("  push:\n", path.read_text(encoding="utf-8"), path.name)

if __name__ == "__main__":
    unittest.main()

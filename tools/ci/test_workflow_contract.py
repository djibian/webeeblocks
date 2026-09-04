#!/usr/bin/env python3
"""Static contract for V4 CI and human-checkpoint topology."""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"

EXPECTED = {
    "human-checkpoint.yml": {"validate", "runtime", "webots", "publish"},
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
    },
}

def job_ids(text: str) -> set[str]:
    jobs = text.split("\njobs:\n", 1)[1]
    return set(re.findall(r"^  ([A-Za-z0-9_-]+):\s*$", jobs, re.MULTILINE))

class WorkflowTests(unittest.TestCase):
    def test_only_v4_workflows_exist(self):
        names = {path.name for path in WORKFLOWS.glob("*.yml")}
        self.assertEqual(names, set(EXPECTED))

    def test_job_sets(self):
        for name, expected in EXPECTED.items():
            self.assertEqual(job_ids((WORKFLOWS / name).read_text(encoding="utf-8")), expected, name)

    def test_ci_targets_main_only(self):
        text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("branches: [main]", text)
        self.assertNotIn("develop", text)
        self.assertIn("types: [opened, synchronize, reopened, ready_for_review]", text)

    def test_main_pr_is_not_implicit_full_promotion(self):
        selector = (ROOT / "tools" / "ci" / "select_ci.py").read_text(encoding="utf-8")
        self.assertIn('force_full = args.event != "pull_request"', selector)
        self.assertNotIn('args.base_ref == "main"', selector)

    def test_checkpoint_is_exact_full_and_single_slot(self):
        text = (WORKFLOWS / "human-checkpoint.yml").read_text(encoding="utf-8")
        for required in (
            "CHECKPOINT_REQUEST ([0-9a-f]{40})",
            "uses: ./.github/workflows/ci-runtime.yml",
            "uses: ./.github/workflows/ci-webots.yml",
            "full: true",
            "group: webeeblocks-human-test-open",
            "WEBEEBLOCKS_HUMAN_TEST_OPEN=1",
            "WEBEEBLOCKS_TEST_FINGERPRINT=",
            "WebeeBlocks-Windows-R2025a",
            "[TEST_REQUIRED]",
            "https://ntfy.sh/",
        ):
            self.assertIn(required, text)
        for obsolete in ("READY_FOR_REVIEW", "SESSION_LIMIT", "RELANCE CONTRÔLEUR", "Candidate Evidence"):
            self.assertNotIn(obsolete, text)

    def test_reusable_suites_receive_exact_target(self):
        ci = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        self.assertEqual(ci.count("target_sha: ${{ github.sha }}"), 2)
        target = "ref: ${{ inputs.target_sha || github.sha }}"
        for name in ("ci-runtime.yml", "ci-webots.yml"):
            suite = (WORKFLOWS / name).read_text(encoding="utf-8")
            all_checkouts = suite.count("uses: actions/checkout@v4")
            external = suite.count("repository: cyberbotics/webots")
            self.assertEqual(suite.count(target), all_checkouts - external, name)

    def test_no_post_merge_push_trigger(self):
        for path in WORKFLOWS.glob("*.yml"):
            self.assertNotIn("  push:\n", path.read_text(encoding="utf-8"), path.name)

if __name__ == "__main__":
    unittest.main()

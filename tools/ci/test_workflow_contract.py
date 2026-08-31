#!/usr/bin/env python3
"""Static contract for the three-file CI topology."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"

EXPECTED = {
    "ci.yml": {"select", "runtime", "webots", "gate"},
    "ci-runtime.yml": {
        "runtime-v2-core",
        "runtime-v2-windows-assets",
        "clean-checkout-runtime-v2",
        "runtime-v2-observability",
        "runtime-v2-project-files",
        "reset-contract-fast",
        "reset-replay-webots",
        "runtime-v2-webots",
        "student-ui",
    },
    "ci-webots.yml": {
        "crazyflie-ab-matrix",
        "crazyflie-b-edges",
        "crazyflie-blockly-l",
        "timed-challenge-ux",
        "first-collision-obstacle",
        "crazyflie-l-course",
        "parametric-blockly-obstacle",
        "crazyflie-primitive-matrix",
        "crazyflie-runtime-wwi",
        "crazyflie-square-position",
        "crazyflie-square",
        "stop-vs-chain",
        "strategy-timing",
        "historical-blockly-ui",
        "encoders-historical",
        "gyro-gps-historical",
        "light-sensor-historical",
        "sensor-probing-historical",
        "robot-window-roundtrip",
        "webots-smoke",
    },
}


def job_ids(text: str) -> set[str]:
    jobs = text.split("\njobs:\n", 1)[1]
    return set(re.findall(r"^  ([A-Za-z0-9_-]+):\s*$", jobs, re.MULTILINE))


class WorkflowContractTests(unittest.TestCase):
    def test_only_three_workflows_exist(self) -> None:
        names = {path.name for path in WORKFLOWS.glob("*.yml")}
        self.assertEqual(names, set(EXPECTED))

    def test_every_oracle_job_is_preserved_once(self) -> None:
        observed: set[str] = set()
        for name, expected in EXPECTED.items():
            current = job_ids((WORKFLOWS / name).read_text(encoding="utf-8"))
            self.assertEqual(current, expected, name)
            self.assertFalse(observed.intersection(current), name)
            observed.update(current)

    def test_only_orchestrator_receives_pull_requests(self) -> None:
        orchestrator = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("  pull_request:\n", orchestrator)
        self.assertIn("branches: [develop, main]", orchestrator)
        for name in ("ci-runtime.yml", "ci-webots.yml"):
            suite = (WORKFLOWS / name).read_text(encoding="utf-8")
            self.assertIn("  workflow_call:\n", suite)
            self.assertNotIn("  pull_request:\n", suite)

    def test_no_post_merge_push_trigger(self) -> None:
        for path in WORKFLOWS.glob("*.yml"):
            self.assertNotIn("  push:\n", path.read_text(encoding="utf-8"), path.name)

    def test_webots_projects_checkout_is_commit_pinned(self) -> None:
        suite = (WORKFLOWS / "ci-webots.yml").read_text(encoding="utf-8")
        self.assertNotIn("ref: R2025a", suite)
        self.assertEqual(
            suite.count("ref: c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b"),
            3,
        )

    def test_gyro_gps_historical_runtime_is_offline(self) -> None:
        suite = (WORKFLOWS / "ci-webots.yml").read_text(encoding="utf-8")
        gyro = suite.split("\n  gyro-gps-historical:\n", 1)[1].split(
            "\n  light-sensor-historical:\n", 1
        )[0]
        self.assertIn("Prepare offline historical Gyro GPS world", gyro)
        self.assertIn("/workspace/worlds/.ci-boxChallenge-gyro-gps-local.wbt", gyro)
        self.assertIn("--network none", gyro)
        self.assertIn("/usr/local/webots/projects:ro", gyro)

    def test_webots_smoke_runtime_is_offline(self) -> None:
        suite = (WORKFLOWS / "ci-webots.yml").read_text(encoding="utf-8")
        smoke = suite.split("\n  webots-smoke:\n", 1)[1]
        self.assertIn("Prepare offline smoke worlds", smoke)
        self.assertIn("Checkout pinned Webots R2025a projects", smoke)
        self.assertIn("/workspace/worlds/.ci-empty-local.wbt", smoke)
        self.assertIn("/workspace/worlds/.ci-boxChallenge-local.wbt", smoke)
        self.assertGreaterEqual(smoke.count("--network none"), 2)
        self.assertGreaterEqual(smoke.count("/usr/local/webots/projects:ro"), 2)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Static contract for the CI topology, candidate evidence and trusted transport boundary."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"

TRANSPORT_WORKFLOWS = {"controller-handoff-ntfy.yml"}

EXPECTED = {
    "candidate-evidence.yml": {
        "validate_target",
        "candidate_runtime",
        "candidate_webots",
        "candidate_evidence",
    },
    "ci.yml": {"select", "runtime", "webots", "gate"},
    "ci-runtime.yml": {
        "runtime-v2-core",
        "runtime-v2-windows-assets",
        "runtime-v2-windows-release",
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
    def test_expected_workflows_plus_transport_exist(self) -> None:
        names = {path.name for path in WORKFLOWS.glob("*.yml")}
        self.assertEqual(names, set(EXPECTED).union(TRANSPORT_WORKFLOWS))

    def test_transport_cannot_run_candidate_code(self) -> None:
        transport = (WORKFLOWS / "controller-handoff-ntfy.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("  issue_comment:\n", transport)
        self.assertIn("  pull_request_review:\n", transport)
        self.assertNotIn("  workflow_run:\n", transport)
        self.assertNotIn("workflows: [CI Gate]", transport)
        self.assertIn("github.repository == 'djibian/webeeblocks'", transport)
        self.assertIn("github.actor == 'djibian'", transport)
        self.assertIn("sender.get('login') != TRUSTED_AUTHOR", transport)
        self.assertIn(
            "https://api.github.com/repos/{REPOSITORY}/pulls/{number}",
            transport,
        )
        self.assertIn(
            "current_head != head or current_base != 'develop'",
            transport,
        )
        self.assertIn(
            "https://api.github.com/repos/{REPOSITORY}/commits/develop",
            transport,
        )
        self.assertLess(
            transport.index("if is_pull_request:"),
            transport.index("topic = os.environ.get('NTFY_TOPIC'"),
        )
        for status in (
            "READY_FOR_REVIEW",
            "NO_GO",
            "HUMAN_REQUIRED",
            "BLOCKED",
            "SESSION_LIMIT",
        ):
            self.assertIn(status, transport)
        self.assertNotIn("UNPROVEN", transport)
        self.assertIn("WebeeBlocks — TEST À EFFECTUER", transport)
        self.assertIn("WebeeBlocks — RELANCE CONTRÔLEUR", transport)
        self.assertNotIn("PREUVE À ARBITRER", transport)
        self.assertIn("permissions: {}", transport)
        self.assertNotIn("  pull_request:\n", transport)
        self.assertNotIn("  pull_request_target:\n", transport)
        self.assertNotIn("actions/checkout", transport)
        self.assertNotIn("github.token", transport)
        self.assertNotIn("CI Gate terminé", transport)

    def test_every_workflow_job_is_preserved_once(self) -> None:
        observed: set[str] = set()
        for name, expected in EXPECTED.items():
            current = job_ids((WORKFLOWS / name).read_text(encoding="utf-8"))
            self.assertEqual(current, expected, name)
            self.assertFalse(observed.intersection(current), name)
            observed.update(current)

    def test_only_orchestrator_receives_pull_requests(self) -> None:
        orchestrator = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("  pull_request:\n", orchestrator)
        self.assertIn(
            "python3 tools/ci/test_repository_hygiene.py",
            orchestrator,
        )
        self.assertIn(
            "python3 tools/ci/test_windows_release_contract.py",
            orchestrator,
        )
        self.assertIn("branches: [develop, main]", orchestrator)
        self.assertIn(
            "types: [opened, synchronize, reopened, ready_for_review]",
            orchestrator,
        )
        for name in ("candidate-evidence.yml", "ci-runtime.yml", "ci-webots.yml"):
            suite = (WORKFLOWS / name).read_text(encoding="utf-8")
            self.assertIn("  workflow_call:\n", suite)
            self.assertNotIn("  pull_request:\n", suite)

    def test_candidate_evidence_is_exact_head_full_and_dormant(self) -> None:
        candidate = (WORKFLOWS / "candidate-evidence.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("name: Candidate Evidence\n", candidate)
        self.assertIn("  workflow_call:\n", candidate)
        self.assertNotIn("  workflow_dispatch:\n", candidate)
        self.assertNotIn("  pull_request:\n", candidate)
        self.assertNotIn("  pull_request_review:\n", candidate)
        self.assertNotIn("  issue_comment:\n", candidate)
        self.assertNotIn("  push:\n", candidate)
        self.assertIn("permissions:\n  contents: read\n", candidate)
        self.assertIn("      target_sha:\n", candidate)
        self.assertIn("        required: true\n", candidate)
        self.assertIn("        type: string\n", candidate)
        self.assertIn("  validate_target:\n", candidate)
        self.assertIn("TARGET_SHA: ${{ inputs.target_sha }}", candidate)
        self.assertIn('test "${#TARGET_SHA}" -eq 40', candidate)
        self.assertIn("*[!0-9a-fA-F]*|'')", candidate)
        self.assertEqual(candidate.count("needs: validate_target"), 2)
        self.assertEqual(candidate.count("target_sha: ${{ inputs.target_sha }}"), 2)
        self.assertIn("uses: ./.github/workflows/ci-runtime.yml", candidate)
        self.assertIn("uses: ./.github/workflows/ci-webots.yml", candidate)
        self.assertIn("      full: true\n", candidate)
        self.assertIn(
            "needs: [candidate_runtime, candidate_webots]",
            candidate,
        )
        self.assertNotIn("actions/checkout", candidate)
        self.assertNotIn("CI Gate", candidate)

    def test_reusable_suites_receive_an_explicit_git_target(self) -> None:
        orchestrator = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        self.assertEqual(orchestrator.count("target_sha: ${{ github.sha }}"), 2)
        self.assertEqual(orchestrator.count("ref: ${{ github.sha }}"), 2)

        target_ref = "ref: ${{ inputs.target_sha || github.sha }}"
        for name in ("ci-runtime.yml", "ci-webots.yml"):
            suite = (WORKFLOWS / name).read_text(encoding="utf-8")
            self.assertIn("      target_sha:\n", suite, name)
            self.assertIn("        required: true\n", suite, name)
            self.assertIn("        type: string\n", suite, name)
            all_checkouts = suite.count("uses: actions/checkout@v4")
            external_checkouts = suite.count("repository: cyberbotics/webots")
            repository_checkouts = all_checkouts - external_checkouts
            self.assertGreater(repository_checkouts, 0, name)
            self.assertEqual(suite.count(target_ref), repository_checkouts, name)

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

    def test_no_post_merge_push_trigger(self) -> None:
        for path in WORKFLOWS.glob("*.yml"):
            self.assertNotIn("  push:\n", path.read_text(encoding="utf-8"), path.name)

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


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3

import unittest
from unittest import mock

from select_ci import git_changed_paths, select


class SelectCiTests(unittest.TestCase):
    def test_documentation_only(self) -> None:
        result = select(["docs/DEVELOPMENT.md", "README.md"])
        self.assertFalse(result.runtime)
        self.assertFalse(result.webots)
        self.assertFalse(result.full)

    def test_runtime_only(self) -> None:
        result = select(["plugins/robot_windows/blockly_v2/project_ui.js"])
        self.assertTrue(result.runtime)
        self.assertFalse(result.webots)
        self.assertFalse(result.full)

    def test_physical_host_activation_regression_routes_to_runtime(self) -> None:
        result = select(["tools/ci/test_physical_host_activation.py"])
        self.assertTrue(result.runtime)
        self.assertFalse(result.webots)
        self.assertFalse(result.full)

    def test_physical_test_and_fixture_edits_keep_prior_suites_and_run_their_oracles(self) -> None:
        for path in (
            "tools/ci/test_physical_fail_554.py",
            "tools/ci/fixtures/physical_fail_554_ast.json",
            "tools/ci/test_dynamic_physical_run.py",
            "tools/ci/test_production_takeoff_run.py",
            "tools/ci/test_teacher_run_authorization.py",
        ):
            with self.subTest(path=path):
                result = select([path])
                self.assertTrue(result.runtime)
                self.assertTrue(result.webots)  # retain the previous selection too

    def test_sequence_land_diagnostic_selects_its_runtime_shards(self) -> None:
        for path in (
            "tools/ci/run_progression_sequence_mission.py",
            "tools/ci/test_progression_land_instrumentation.py",
            "plugins/robot_windows/sequence_probe/sequence_probe.js",
            "tools/ci/test_progression_sequence_contract.js",
        ):
            with self.subTest(path=path):
                selection = select([path])
                self.assertTrue(selection.runtime)
                self.assertTrue(selection.webots)  # preserve prior coverage
                self.assertFalse(selection.full)

    def test_activity6_native_inputs_run_own_runtime_progression_shard(self) -> None:
        # Shard 4 runs the native combined-decisions Activity 6 mission.
        # Each changed source or regression test must select that real oracle.
        paths = (
            "tools/ci/run_progression_combined_decisions_mission.py",
            "tools/ci/test_progression_combined_decisions_contract.js",
            "tools/ci/test_activity6_setup_phase.py",
        )
        for path in paths:
            with self.subTest(path=path):
                selection = select([path])
                self.assertTrue(selection.runtime)
                self.assertTrue(selection.webots)
                self.assertFalse(selection.full)

        # Exact proposed #693 diff must not produce a Webots-only green Gate.
        combined = select([
            "tools/ci/run_progression_combined_decisions_mission.py",
            "tools/ci/test_activity6_setup_phase.py",
        ])
        self.assertTrue(combined.runtime)
        self.assertTrue(combined.webots)

    def test_outcome_startup_observer_selects_its_runtime_preflight(self) -> None:
        for path in (
            "tools/ci/observe_outcome_startup.py",
            "tools/ci/test_outcome_startup_observer.py",
        ):
            with self.subTest(path=path):
                selection = select([path])
                self.assertTrue(selection.runtime)
                self.assertTrue(selection.webots)
                self.assertFalse(selection.full)

    def test_autonomous_reset_probe_changes_select_the_real_runtime_oracle(self) -> None:
        for path in (
            "tools/ci/run_progression_autonomous_mission.py",
            "tools/ci/test_progression_autonomous_contract.js",
            "tools/ci/fixtures/autonomous_reset_observer.py",
            "tools/ci/reset_native_summary.py",
            "tools/ci/test_reset_native_summary.py",
            "tools/ci/reset_post_teleport.py",
            "tools/ci/test_reset_post_teleport.py",
        ):
            with self.subTest(path=path):
                selection = select([path])
                self.assertTrue(selection.runtime)
                self.assertTrue(selection.webots)  # existing Webots evidence retained
                self.assertFalse(selection.full)

    def test_grand_prix_runtime_inputs_keep_both_suites(self) -> None:
        # The actual native grand-prix-prototype job is defined in ci-runtime.yml.
        # Generic tools/ci patterns previously ran Webots only and skipped it.
        for path in (
            "tools/ci/run_grand_prix_u_prototype.py",
            "tools/ci/webots_startup_diagnostics.py",
            "tools/ci/test_webots_startup_diagnostics.py",
            "tools/ci/test_grand_prix_u_timeout_probe.py",
            "tools/ci/test_grand_prix_evaluator_bootstrap.py",
        ):
            with self.subTest(path=path):
                selection = select([path])
                self.assertTrue(selection.runtime)
                self.assertTrue(selection.webots)
                self.assertFalse(selection.full)

    def test_native_windows_gp_u_fixtures_require_full_release_validation(self) -> None:
        # The Windows-only composed C/C++ test lives behind inputs.full.
        # Running just the partial Runtime suite silently skips that job.
        for path in (
            "tools/ci/fixtures/gp_u_pose_driver.cpp",
            "tools/ci/fixtures/gp_u_pose_webots.h",
            "tools/ci/fixtures/gp_u_file_provider.hpp",
        ):
            with self.subTest(path=path):
                selection = select([path])
                self.assertTrue(selection.runtime)
                self.assertTrue(selection.webots)
                self.assertTrue(selection.full)

    def test_visual_and_windows_release_inputs_select_runtime(self) -> None:
        # Their native or release validators live in ci-runtime.yml.
        for path in (
            "controllers/color_led_visual_probe/color_led_visual_probe.py",
            "tools/ci/prepare_color_led_visual_render.py",
            "tools/ci/check_color_led_visual_render.py",
            "tools/ci/test_color_led_deck_visual.py",
            "tools/ci/test_windows_classroom_release.ps1",
        ):
            with self.subTest(path=path):
                selection = select([path])
                self.assertTrue(selection.runtime)
                self.assertTrue(selection.webots)
                self.assertFalse(selection.full)

    def test_shared_runtime_backend(self) -> None:
        result = select(["controllers/crazyflie_runtime_v2/controller.c"])
        self.assertTrue(result.runtime)
        self.assertTrue(result.webots)
        self.assertTrue(result.full)

    def test_runtime_v2_student_ui_experiment_routes_to_runtime(self) -> None:
        result = select(["experiments/runtime-v2-student-ui/probe.py"])
        self.assertTrue(result.runtime)
        self.assertTrue(result.webots)
        self.assertFalse(result.full)

    def test_windows_packaging_change_is_full(self) -> None:
        result = select(["packaging/windows/Launch-WebeeBlocks.ps1"])
        self.assertTrue(result.runtime)
        self.assertTrue(result.webots)
        self.assertTrue(result.full)

    def test_legacy_webots_only(self) -> None:
        result = select(["controllers/crazyflie_square/pid_controller.c"])
        self.assertFalse(result.runtime)
        self.assertTrue(result.webots)

    def test_workflow_change_is_full(self) -> None:
        result = select([".github/workflows/ci.yml"])
        self.assertTrue(result.runtime)
        self.assertTrue(result.webots)
        self.assertTrue(result.full)

    def test_repository_hygiene_contract_change_is_full(self) -> None:
        result = select(["tools/ci/test_repository_hygiene.py"])
        self.assertTrue(result.runtime)
        self.assertTrue(result.webots)
        self.assertTrue(result.full)

    def test_windows_release_contract_change_is_full(self) -> None:
        result = select(["tools/ci/test_windows_release_contract.py"])
        self.assertTrue(result.runtime)
        self.assertTrue(result.webots)
        self.assertTrue(result.full)

    def test_unknown_is_fail_safe_full(self) -> None:
        result = select(["activities/new_activity.json"])
        self.assertTrue(result.runtime)
        self.assertTrue(result.webots)
        self.assertTrue(result.full)

    def test_empty_diff_is_full(self) -> None:
        result = select([])
        self.assertTrue(result.full)

    def test_explicit_full_is_full(self) -> None:
        result = select(["README.md"], force_full=True)
        self.assertTrue(result.runtime)
        self.assertTrue(result.webots)
        self.assertTrue(result.full)

    @mock.patch("select_ci.subprocess.run")
    def test_git_diff_keeps_deletion_and_both_rename_sides(
        self, run: mock.Mock
    ) -> None:
        run.return_value.stdout = (
            "controllers/removed_controller.c\n"
            "plugins/robot_windows/blockly_v2/moved_controller.c\n"
        )

        paths = git_changed_paths("base-sha", "head-sha")
        self.assertEqual(
            paths,
            [
                "controllers/removed_controller.c",
                "plugins/robot_windows/blockly_v2/moved_controller.c",
            ],
        )
        selection = select(paths)
        self.assertTrue(selection.runtime)
        self.assertTrue(selection.webots)
        run.assert_called_once_with(
            [
                "git",
                "diff",
                "--name-only",
                "--no-renames",
                "base-sha...head-sha",
            ],
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()

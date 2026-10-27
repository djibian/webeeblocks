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

    def test_land_contact_forensics_selects_own_runtime_preflight(self) -> None:
        paths = (
            "tools/ci/land_contact_summary.py",
            "tools/ci/test_land_contact_summary.py",
        )
        for path in paths:
            with self.subTest(path=path):
                selection = select([path])
                self.assertTrue(selection.runtime)
                self.assertTrue(selection.webots)  # preserve prior coverage
                self.assertFalse(selection.full)

        combined = select(list(paths))
        self.assertEqual(combined.outputs()["runtime"], "true")
        self.assertEqual(combined.outputs()["webots"], "true")

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

    def test_native_progression_edits_run_the_real_runtime_oracles(self) -> None:
        # The Webots-only legacy match must not silently skip shard 1/2/3/4
        # or the activity-outcome oracle executed by Runtime's core harness.
        paths = (
            "tools/ci/run_classroom_neutral_start.py",
            "tools/ci/run_progression_repeat_mission.py",
            "tools/ci/run_progression_simple_decision_mission.py",
            "tools/ci/run_progression_reactive_mission.py",
            "tools/ci/run_progression_memory_mission.py",
            "tools/ci/run_progression_memory_overwrite.py",
            "tools/ci/test_runtime_activity_outcome.js",
        )
        for path in paths:
            with self.subTest(path=path):
                selection = select([path])
                self.assertTrue(selection.runtime)
                self.assertTrue(selection.webots)
                self.assertFalse(selection.full)

        # A newly added progression runner/contract must retain its native
        # coverage without manually adding a selector exception.
        for path in (
            "tools/ci/run_progression_new_mission.py",
            "tools/ci/test_progression_new_contract.js",
        ):
            with self.subTest(future_path=path):
                selection = select([path])
                self.assertTrue(selection.runtime)
                self.assertTrue(selection.webots)
                self.assertFalse(selection.full)

        combined = select(["docs/DEVELOPMENT.md", *paths])
        self.assertTrue(combined.runtime)
        self.assertTrue(combined.webots)
        self.assertFalse(combined.full)

        # Increasing native coverage must not turn documentation-only or
        # unrelated legacy Webots-only changes into mandatory Runtime.
        self.assertFalse(select(["docs/DEVELOPMENT.md"]).runtime)
        self.assertFalse(select(["controllers/crazyflie_square/pid_controller.c"]).runtime)

    def test_shared_wwi_event_server_edits_run_own_runtime_jobs(self) -> None:
        # Directly invoked by ci-runtime.yml's native browser/observability
        # jobs, not just by ci-webots.yml. Editing it alone must run Runtime.
        selection = select(["tools/ci/runtime_wwi_event_server.py"])
        self.assertTrue(selection.runtime)
        self.assertTrue(selection.webots)
        self.assertFalse(selection.full)

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

    def test_grand_prix_u_controller_and_evaluator_require_full_windows_gate(self) -> None:
        # These sources are compiled/consumed by ci-runtime.yml's native
        # grand-prix-prototype. The Windows release/composition job is
        # additionally gated by inputs.full; Webots-only is insufficient.
        for path in (
            "controllers/grand_prix_u_flight/Makefile",
            "controllers/grand_prix_u_flight/grand_prix_u_deadline.cpp",
            "controllers/grand_prix_u_flight/new_native_probe.c",
            "controllers/grand_prix_u_evaluator/grand_prix_u_evaluator.py",
            "controllers/grand_prix_u_evaluator/new_oracle.py",
        ):
            with self.subTest(path=path):
                selection = select([path])
                self.assertTrue(selection.runtime)
                self.assertTrue(selection.webots)
                self.assertTrue(selection.full)

        # Keep the existing scoped path for the native test scripts and do
        # not expand unrelated historical controllers into full CI.
        scoped = select(["tools/ci/test_grand_prix_u_timeout_probe.py"])
        self.assertTrue(scoped.runtime)
        self.assertTrue(scoped.webots)
        self.assertFalse(scoped.full)
        legacy = select(["controllers/crazyflie_square/pid_controller.c"])
        self.assertFalse(legacy.runtime)
        self.assertTrue(legacy.webots)
        self.assertFalse(legacy.full)

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

    def test_product_blockly_definition_test_keeps_its_runtime_owner(self) -> None:
        # #721 introduced this test in Runtime student-ui. A generic tools/ci/**
        # edit previously selected Webots alone and skipped the actual oracle.
        result = select(["tools/ci/test_blockly_v2_product_definitions.js"])
        self.assertTrue(result.runtime)
        self.assertTrue(result.webots)  # preserve existing Webots coverage
        self.assertFalse(result.full)

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

    def test_webots_qt_lifetime_candidate_requires_full_product_ci(self) -> None:
        # A source patch kept under experiments/ still affects native consumers.
        # Do not allow a Ready CI Gate with Runtime/Grand Prix silently skipped.
        for path in (
            "experiments/webots-qt-665/webots-r2025a-guarded-progress-retirement.patch",
            "experiments/webots-qt-665/repair_parent_shutdown.py",
            "experiments/webots-qt-665/qt665_parent_counterprobe.py",
        ):
            with self.subTest(path=path):
                result = select([path])
                self.assertTrue(result.runtime)
                self.assertTrue(result.webots)
                self.assertTrue(result.full)

        # Do not broaden all unrelated research experiments to full coverage.
        other = select(["experiments/other-research/observations.py"])
        self.assertFalse(other.runtime)
        self.assertTrue(other.webots)
        self.assertFalse(other.full)

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

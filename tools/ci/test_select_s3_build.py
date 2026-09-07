#!/usr/bin/env python3

import unittest
from unittest import mock

from select_s3_build import git_changed_paths, selected


class SelectS3BuildTests(unittest.TestCase):
    def test_x3_experiment_runs(self) -> None:
        self.assertTrue(
            selected(["experiments/crazyflie-ukf-surface-range/apply_surface_offset_s3.py"])
        )

    def test_s3_workflow_contract_change_runs(self) -> None:
        self.assertTrue(selected([".github/workflows/ci-webots.yml"]))

    def test_unrelated_webots_change_does_not_run(self) -> None:
        self.assertFalse(selected(["controllers/crazyflie_square/pid_controller.c"]))

    def test_unrelated_runtime_change_does_not_run(self) -> None:
        self.assertFalse(selected(["plugins/robot_windows/blockly_v2/main.js"]))

    def test_non_pr_full_verification_runs(self) -> None:
        self.assertTrue(selected([], non_pr=True))

    @mock.patch("select_s3_build.subprocess.run")
    def test_diff_is_exact_and_no_renames(self, run: mock.Mock) -> None:
        run.return_value.stdout = (
            "controllers/crazyflie_square/pid_controller.c\n"
            "experiments/crazyflie-ukf-surface-range/run_s3_build_oracle.sh\n"
        )
        paths = git_changed_paths("base-sha", "head-sha")
        self.assertTrue(selected(paths))
        run.assert_called_once_with(
            ["git", "diff", "--name-only", "--no-renames", "base-sha...head-sha"],
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3

import unittest
from unittest import mock

from select_ci import git_changed_paths, select

class SelectCiTests(unittest.TestCase):
    def test_documentation_only(self):
        result = select(["docs/DEVELOPMENT.md", "README.md"])
        self.assertFalse(result.runtime)
        self.assertFalse(result.webots)
        self.assertFalse(result.full)

    def test_runtime_only(self):
        result = select(["plugins/robot_windows/blockly_v2/project_ui.js"])
        self.assertTrue(result.runtime)
        self.assertFalse(result.webots)

    def test_shared_runtime_backend_is_full(self):
        result = select(["controllers/crazyflie_runtime_v2/controller.c"])
        self.assertTrue(result.runtime)
        self.assertTrue(result.webots)
        self.assertTrue(result.full)

    def test_workflow_change_is_full(self):
        self.assertTrue(select([".github/workflows/ci.yml"]).full)

    def test_unknown_is_fail_safe_full(self):
        self.assertTrue(select(["activities/new_activity.json"]).full)

    def test_empty_diff_is_full(self):
        self.assertTrue(select([]).full)

    def test_explicit_full_is_full(self):
        self.assertTrue(select(["README.md"], force_full=True).full)

    @mock.patch("select_ci.subprocess.run")
    def test_git_diff_disables_rename_elision(self, run):
        run.return_value.stdout = "controllers/a.c\nplugins/robot_windows/blockly_v2/b.c\n"
        paths = git_changed_paths("base", "head")
        self.assertEqual(paths, ["controllers/a.c", "plugins/robot_windows/blockly_v2/b.c"])
        run.assert_called_once_with(
            ["git", "diff", "--name-only", "--no-renames", "base...head"],
            check=True, capture_output=True, text=True,
        )

if __name__ == "__main__":
    unittest.main()

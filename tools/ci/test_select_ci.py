#!/usr/bin/env python3

import unittest

from select_ci import select


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

    def test_shared_runtime_backend(self) -> None:
        result = select(["controllers/crazyflie_runtime_v2/controller.c"])
        self.assertTrue(result.runtime)
        self.assertTrue(result.webots)

    def test_legacy_webots_only(self) -> None:
        result = select(["controllers/crazyflie_square/pid_controller.c"])
        self.assertFalse(result.runtime)
        self.assertTrue(result.webots)

    def test_workflow_change_is_full(self) -> None:
        result = select([".github/workflows/ci.yml"])
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


if __name__ == "__main__":
    unittest.main()


#!/usr/bin/env python3

import contextlib
import io
import os
import unittest
from unittest.mock import patch

import check_ci_gate


class GateTests(unittest.TestCase):
    def run_gate(self, selection: str, needs: str) -> int:
        with patch.dict(
            os.environ,
            {"CI_SELECTION": selection, "CI_NEEDS": needs},
            clear=True,
        ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return check_ci_gate.main()

    def test_selected_success_and_unselected_skip_pass(self) -> None:
        result = self.run_gate(
            '{"runtime":"true","webots":"false"}',
            '{"select":{"result":"success"},"runtime":{"result":"success"},"webots":{"result":"skipped"}}',
        )
        self.assertEqual(result, 0)

    def test_selected_skip_fails_closed(self) -> None:
        result = self.run_gate(
            '{"runtime":"true","webots":"true"}',
            '{"select":{"result":"success"},"runtime":{"result":"success"},"webots":{"result":"skipped"}}',
        )
        self.assertEqual(result, 1)

    def test_selector_failure_fails_closed(self) -> None:
        result = self.run_gate(
            '{}',
            '{"select":{"result":"failure"},"runtime":{"result":"skipped"},"webots":{"result":"skipped"}}',
        )
        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()

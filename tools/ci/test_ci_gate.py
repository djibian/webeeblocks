#!/usr/bin/env python3

import contextlib
import io
import itertools
import json
import os
import unittest
from unittest.mock import patch

import check_ci_gate


class GateTests(unittest.TestCase):
    def run_gate(self, selection: str | None, needs: str | None) -> int:
        with patch.dict(
            os.environ,
            {key: value for key, value in
             (("CI_SELECTION", selection), ("CI_NEEDS", needs)) if value is not None},
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
            '{"runtime":"false","webots":"false"}',
            '{"select":{"result":"failure"},"runtime":{"result":"skipped"},"webots":{"result":"skipped"}}',
        )
        self.assertEqual(result, 1)

    def test_all_selection_and_job_result_combinations(self) -> None:
        successes = 0
        for flags in itertools.product(("true", "false"), repeat=2):
            selection = dict(zip(("runtime", "webots"), flags))
            for results in itertools.product(
                ("success", "failure", "cancelled", "skipped"), repeat=3
            ):
                needs = dict(zip(
                    ("select", "runtime", "webots"),
                    ({"result": result} for result in results),
                ))
                expected = ("success",) + tuple(
                    "success" if flag == "true" else "skipped" for flag in flags
                )
                with self.subTest(selection=selection, results=results):
                    result = self.run_gate(json.dumps(selection), json.dumps(needs))
                    self.assertEqual(result, 0 if results == expected else 1)
                    successes += result == 0
        # Includes documentation-only and either suite selected independently.
        self.assertEqual(successes, 4)

    def test_invalid_selection_never_exempts_suites(self) -> None:
        needs = '{"select":{"result":"success"},"runtime":{"result":"skipped"},"webots":{"result":"skipped"}}'
        cases = [None, [], {}, {"runtime": "false"},
                 {"runtime": "false", "webots": "false", "other": "false"}]
        for suite in ("runtime", "webots"):
            for invalid in ("", "tru", "False", False, True, None, 0, []):
                cases.append({"runtime": "false", "webots": "false", suite: invalid})
        for selection in cases:
            with self.subTest(selection=selection):
                self.assertEqual(self.run_gate(json.dumps(selection), needs), 1)

    def test_missing_or_invalid_job_evidence_fails_closed(self) -> None:
        selection = '{"runtime":"false","webots":"false"}'
        valid = {"select": {"result": "success"},
                 "runtime": {"result": "skipped"}, "webots": {"result": "skipped"}}
        cases = [None, [], {}, {**valid, "other": {"result": "success"}}]
        for job in valid:
            cases.append({key: value for key, value in valid.items() if key != job})
            for invalid in (None, [], {}, {"result": None}, {"result": False}):
                cases.append({**valid, job: invalid})
            for result in ("", "neutral", "timed_out", "action_required", "unknown"):
                cases.append({**valid, job: {"result": result}})
        for needs in cases:
            with self.subTest(needs=needs):
                self.assertEqual(self.run_gate(selection, json.dumps(needs)), 1)

    def test_nested_job_metadata_does_not_replace_result(self) -> None:
        self.assertEqual(self.run_gate(
            '{"runtime":"false","webots":"false"}',
            '{"select":{"result":"success","outputs":{}},"runtime":{"result":"skipped"},"webots":{"result":"skipped"}}',
        ), 0)

    def test_absent_malformed_or_duplicate_json_is_a_controlled_failure(self) -> None:
        selection = '{"runtime":"false","webots":"false"}'
        needs = '{"select":{"result":"success"},"runtime":{"result":"skipped"},"webots":{"result":"skipped"}}'
        cases = [(invalid, needs) for invalid in (None, "", "{")]
        cases += [(selection, invalid) for invalid in (None, "", "{")]
        cases += [
            ('{"runtime":"true","runtime":"false","webots":"false"}', needs),
            (selection, needs.replace('"result":"skipped"',
                                      '"result":"failure","result":"skipped"', 1)),
        ]
        for selected, observed in cases:
            with self.subTest(selection=selected, needs=observed):
                environment = {key: value for key, value in
                               (("CI_SELECTION", selected), ("CI_NEEDS", observed))
                               if value is not None}
                error = io.StringIO()
                with patch.dict(os.environ, environment, clear=True), \
                        contextlib.redirect_stderr(error):
                    self.assertEqual(check_ci_gate.main(), 1)
                self.assertIn("invalid CI evidence", error.getvalue())


if __name__ == "__main__":
    unittest.main()

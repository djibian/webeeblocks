#!/usr/bin/env python3
"""Discriminating tests for the controller workflow authority audit."""

from __future__ import annotations

import unittest
from pathlib import Path

import check_controller_workflow_contract as contract


HEADER = """name: Contract fixture
on:
  pull_request:
    branches: [webots-ci]
    {types}
permissions:
  contents: read
jobs:
  audit:
    runs-on: ubuntu-22.04
    steps:
      - run: true
"""


def errors(source: str) -> list[str]:
    is_pull_request, found = contract.audit_source(Path("fixture.yml"), source)
    if not is_pull_request:
        raise AssertionError("Fixture was not recognized as a pull_request workflow")
    return found


class ControllerWorkflowContractTests(unittest.TestCase):
    def test_accepts_implicit_and_explicit_synchronize(self) -> None:
        self.assertEqual(errors(HEADER.format(types="")), [])
        self.assertEqual(
            errors(HEADER.format(types="types: [opened, synchronize, ready_for_review]")),
            [],
        )

    def test_synchronize_in_comment_or_path_is_not_an_event_type(self) -> None:
        fixture = HEADER.format(
            types="types: [opened]  # synchronize\n    paths: ['.github/synchronize/**']"
        )
        self.assertIn("explicit pull_request.types omits synchronize", errors(fixture))

    def test_rejects_secret_expression_variants(self) -> None:
        for expression in (
            "${{secrets.TOKEN}}",
            "${{ secrets['TOKEN'] }}",
            "${{ secrets[\"TOKEN\"] }}",
            "${{ toJSON(secrets) }}",
        ):
            with self.subTest(expression=expression):
                fixture = HEADER.format(types="types: [synchronize]").replace(
                    "      - run: true", f"      - run: {expression}"
                )
                self.assertIn(
                    "pull_request workflow consumes or transmits a secret",
                    errors(fixture),
                )

    def test_rejects_reusable_workflow_secret_inheritance(self) -> None:
        fixture = HEADER.format(types="types: [synchronize]").replace(
            "    runs-on: ubuntu-22.04\n    steps:\n      - run: true",
            "    uses: ./.github/workflows/reusable.yml\n    secrets: inherit",
        )
        self.assertIn("pull_request workflow consumes or transmits a secret", errors(fixture))

    def test_rejects_missing_inline_and_write_all_permissions(self) -> None:
        valid = HEADER.format(types="types: [synchronize]")
        variants = (
            valid.replace("permissions:\n  contents: read\n", ""),
            valid.replace("permissions:\n  contents: read", "permissions: write-all"),
            valid.replace("permissions:\n  contents: read", "permissions: {issues: write}"),
        )
        for fixture in variants:
            with self.subTest(fixture=fixture):
                self.assertIn(
                    "pull_request workflow must declare exactly top-level contents: read",
                    errors(fixture),
                )

    def test_rejects_job_level_permissions(self) -> None:
        fixture = HEADER.format(types="types: [synchronize]").replace(
            "    runs-on: ubuntu-22.04", "    permissions:\n      issues: write\n    runs-on: ubuntu-22.04"
        )
        self.assertIn("job-level permissions are forbidden in pull_request workflows", errors(fixture))

    def test_rejects_inline_or_duplicate_authority_keys(self) -> None:
        valid = HEADER.format(types="types: [synchronize]")
        inline_event = valid.replace("  pull_request:\n", "  pull_request: {types: [opened]}\n")
        duplicate_permissions = valid + "permissions:\n  issues: write\n"
        self.assertIn("pull_request event must use an auditable block mapping", errors(inline_event))
        self.assertIn(
            "pull_request workflow must declare exactly top-level contents: read",
            errors(duplicate_permissions),
        )


if __name__ == "__main__":
    unittest.main()

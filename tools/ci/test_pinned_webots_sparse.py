#!/usr/bin/env python3
"""Sparse pinned-Webots acquisition contract. Uses a local Git fixture, no network."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import run_crazyflie_primitive_matrix as matrix


def git(cwd, *arguments):
    return subprocess.run(
        ["git", *arguments], cwd=cwd, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout.strip()


class PinnedWebotsSparseTests(unittest.TestCase):
    def test_paths_cover_all_required_pinned_proto_assets(self):
        self.assertEqual(len(matrix.SPARSE_PROJECT_PATHS),
                         len(set(matrix.SPARSE_PROJECT_PATHS)))
        for asset in matrix.REQUIRED_PROJECT_ASSETS:
            self.assertTrue(
                any(asset.startswith(prefix + "/")
                    for prefix in matrix.SPARSE_PROJECT_PATHS), asset
            )

    def test_exact_git_head_and_sparse_project_tree_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            origin = root / "source"
            origin.mkdir()
            git(origin, "init", "-q")
            git(origin, "config", "user.name", "WebeeBlocks Test")
            git(origin, "config", "user.email", "ci@example.invalid")
            for relative in matrix.REQUIRED_PROJECT_ASSETS:
                file = origin / relative
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("R2025a test fixture\n", encoding="utf-8")
            extra = origin / "unrelated" / "unneeded.bin"
            extra.parent.mkdir(parents=True)
            extra.write_bytes(b"unrelated source")
            git(origin, "add", ".")
            git(origin, "commit", "-qm", "fixture")
            exact_sha = git(origin, "rev-parse", "HEAD")
            workspace = root / "workspace"
            workspace.mkdir()
            with (mock.patch.object(matrix, "WEBOTS_REPOSITORY", str(origin)),
                  mock.patch.object(matrix, "WEBOTS_SHA", exact_sha),
                  mock.patch.object(matrix, "WEBOTS_CHECKOUT", ".ci-pinned-test")):
                projects = matrix.prepare_pinned_webots_projects(workspace)
                self.assertEqual(projects, workspace / ".ci-pinned-test" / "projects")
                self.assertEqual(git(projects.parent, "rev-parse", "HEAD"),
                                 exact_sha)
                for relative in matrix.REQUIRED_PROJECT_ASSETS:
                    self.assertTrue((projects.parent / relative).is_file(), relative)
                self.assertFalse((projects.parent / "unrelated" / "unneeded.bin").exists())
                # Reusing a partial checkout must still verify all assets.
                missing = projects.parent / matrix.REQUIRED_PROJECT_ASSETS[0]
                missing.unlink()
                with self.assertRaisesRegex(RuntimeError, "assets missing"):
                    matrix.prepare_pinned_webots_projects(workspace)
                missing.write_text("R2025a test fixture\n", encoding="utf-8")
                git(projects.parent, "-c", "user.name=Test",
                    "-c", "user.email=ci@example.invalid",
                    "commit", "--allow-empty", "-qm", "wrong HEAD")
                with self.assertRaisesRegex(RuntimeError, "checkout mismatch"):
                    matrix.prepare_pinned_webots_projects(workspace)


if __name__ == "__main__":
    unittest.main()

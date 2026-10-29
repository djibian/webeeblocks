#!/usr/bin/env python3
"""Keep archived vendor material out while preserving legacy runtime assets."""

from pathlib import Path
import importlib.util
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
LEGACY_BLOCKLY = (
    ROOT / "plugins" / "robot_windows" / "blockly" / "google-blockly-31ee4ea"
)

ARCHIVED_UPSTREAM_DIRECTORIES = (
    ".github",
    "appengine",
    "demos",
    "externs",
    "tests",
    "typings",
)

REQUIRED_RUNTIME_ASSETS = (
    "blockly_uncompressed.js",
    "closure/goog/base.js",
    "core/blockly.js",
    "blocks/logic.js",
    "blocks/crazyflie.js",
    "generators/python.js",
    "generators/python/logic.js",
    "media/sprites.png",
    "msg/js/en.js",
)


class RepositoryHygieneTests(unittest.TestCase):
    def test_upstream_development_directories_stay_archived(self) -> None:
        for relative in ARCHIVED_UPSTREAM_DIRECTORIES:
            with self.subTest(path=relative):
                self.assertFalse((LEGACY_BLOCKLY / relative).exists())

    def test_legacy_runtime_assets_stay_available(self) -> None:
        for relative in REQUIRED_RUNTIME_ASSETS:
            with self.subTest(path=relative):
                self.assertTrue((LEGACY_BLOCKLY / relative).is_file())

    def test_product_blocks_live_outside_archived_upstream(self) -> None:
        product = ROOT / "plugins/robot_windows/blockly/webeeblocks/crazyflie_v2.js"
        self.assertTrue(product.is_file())
        self.assertFalse((LEGACY_BLOCKLY / "blocks/crazyflie_v2.js").exists())

    def test_python_cache_is_not_tracked(self) -> None:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        tracked_cache = []
        for relative in result.stdout.split("\0"):
            path = Path(relative)
            if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                tracked_cache.append(relative)
        self.assertEqual(tracked_cache, [])

    def test_qt665_candidate_attestation_rejects_unqualified_elf(self) -> None:
        """A user-supplied checksum cannot authorize the known-vulnerable ELF."""
        script = ROOT / "experiments/webots-qt-665/attest_and_install_candidate.py"
        spec = importlib.util.spec_from_file_location("qt665_attestation", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        policy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(policy)

        good = "e45a90b580a00f50dc08746e6f43d1a86a83fcf1b23f55538737309154150545"
        self.assertEqual(policy.QUALIFIED_PARENT_SAFE_ELF, good)
        policy.require_qualified_candidate_sha256(good)
        for bad in (
            "d3140f65e361a109efd9ca3e7b5cac48594eb1fe87ccc35099a58ed117116fa9",
            policy.BASELINE,
            "0" * 64,
            good.upper(),
            "",
        ):
            with self.subTest(unqualified=bad):
                with self.assertRaises(ValueError):
                    policy.require_qualified_candidate_sha256(bad)

        # Verify the same policy is reached by the real CLI before even
        # consulting a runtime directory (no Webots installation required).
        with tempfile.TemporaryDirectory(prefix="qt665-attester-policy-") as tmp:
            missing = str(Path(tmp) / "not-installed")
            for bad in (
                "d3140f65e361a109efd9ca3e7b5cac48594eb1fe87ccc35099a58ed117116fa9",
                policy.BASELINE,
            ):
                with self.subTest(cli_unqualified=bad):
                    result = subprocess.run(
                        [sys.executable, str(script), "--runtime-home", missing,
                         "--candidate", missing, "--expected-candidate-sha256", bad,
                         "--manifest", str(Path(tmp) / "manifest.json"),
                         "--replace-disposable-installation"],
                        cwd=ROOT, capture_output=True, text=True, timeout=15,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("not the qualified parent-safe build", result.stderr)


    def test_qt665_running_consumer_fail_closed(self) -> None:
        """No standalone installation hash can claim a running Webots consumer."""
        subprocess.run(
            [sys.executable, "experiments/webots-qt-665/test_attest_running_consumer.py"],
            cwd=ROOT, check=True, timeout=30,
        )

    def test_qt665_linux_immutable_consumer_inventory(self) -> None:
        """Keep every Linux consumer pinned to the qualified OCI digest."""
        subprocess.run(
            [sys.executable, "tools/ci/test_qt665_linux_adoption.py"],
            cwd=ROOT, check=True, timeout=30,
        )

    def test_qt665_windows_native_identity_verifier(self) -> None:
        """Reject evaluator substitution, wrong DLLs, SDK lookup and damaged packages."""
        subprocess.run(
            [sys.executable, '-m', 'unittest', 'discover',
             '-s', 'experiments/webots-qt-665', '-p', 'test_probe_windows_packaged_runtime.py'],
            cwd=ROOT, check=True, timeout=30,
        )

    def test_x3_characterization_package_contract(self) -> None:
        """Keep the new machine-only firmware bundle on an always-run CI path."""
        subprocess.run(
            [sys.executable, "tools/ci/test_x3_characterization_package.py"],
            cwd=ROOT,
            check=True,
        )


if __name__ == "__main__":
    unittest.main()

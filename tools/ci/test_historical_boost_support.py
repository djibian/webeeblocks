#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PREPARER_PATH = ROOT / "tools/ci/prepare_historical_boost.py"
BUILDER_PATH = ROOT / "tools/ci/build_historical_blockly_sidecar.sh"
WEBOTS_WORKFLOW = ROOT / ".github/workflows/ci-webots.yml"

spec = importlib.util.spec_from_file_location("prepare_historical_boost", PREPARER_PATH)
assert spec is not None and spec.loader is not None
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)


class HistoricalBoostSupportTests(unittest.TestCase):
    def test_exact_archive_identity_is_pinned(self) -> None:
        self.assertEqual(subject.PACKAGE_NAME, "libboost1.74-dev_1.74.0-14ubuntu3_amd64.deb")
        self.assertEqual(subject.PACKAGE_SIZE, 9_608_510)
        self.assertEqual(
            subject.PACKAGE_SHA256,
            "4d9c90e43f0d25db6280d1ee326771cbb76462f73b9430f06bac1de8d05b7a78",
        )
        self.assertEqual(subject.BOOST_VERSION, 107400)

    def test_missing_archive_fails_closed_without_network_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "boost-1.74"
            with self.assertRaisesRegex(subject.SupportError, "archive is missing"):
                subject.prepare(output)
        source = PREPARER_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "urllib",
            "urlopen",
            "archive.ubuntu.com",
            "http://",
            "https://",
            "apt-get",
        ):
            self.assertNotIn(forbidden, source)

    def test_bad_archive_fails_closed_without_package_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / subject.PACKAGE_NAME
            archive.write_bytes(b"not the pinned package")
            with self.assertRaisesRegex(subject.SupportError, "size mismatch"):
                subject.verify_archive(archive)

    def test_extracted_tree_requires_exact_boost_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            header = root / "usr/include/boost/version.hpp"
            header.parent.mkdir(parents=True)
            header.write_text("#define BOOST_VERSION 107300\n", encoding="utf-8")
            with self.assertRaisesRegex(subject.SupportError, "not exactly 1.74.0"):
                subject.verify_tree(root)
            header.write_text("#define BOOST_VERSION 107400\n", encoding="utf-8")
            subject.verify_tree(root)

    def test_builder_is_offline_and_has_no_apt_fallback(self) -> None:
        text = BUILDER_PATH.read_text(encoding="utf-8")
        self.assertIn("cyberbotics/webots:R2025a-ubuntu22.04", text)
        self.assertIn("--network none", text)
        self.assertIn("/opt/webeeblocks-boost/include:ro", text)
        self.assertIn("CPLUS_INCLUDE_PATH=/opt/webeeblocks-boost/include", text)
        self.assertIn("--with-supervisor", text)
        self.assertIn("WEBEEBLOCKS_BUILD_SUPERVISOR", text)
        self.assertNotIn("apt-get", text)
        self.assertNotIn("apt ", text)
        self.assertNotIn("curl ", text)
        self.assertNotIn("wget ", text)

    def test_affected_historical_jobs_use_only_pinned_boost_builder(self) -> None:
        text = WEBOTS_WORKFLOW.read_text(encoding="utf-8")
        boundaries = (
            ("historical-blockly-ui", "encoders-historical", False),
            ("encoders-historical", "gyro-gps-historical", True),
            ("gyro-gps-historical", "light-sensor-historical", True),
            ("light-sensor-historical", "sensor-probing-historical", True),
            ("sensor-probing-historical", "robot-window-roundtrip", True),
        )
        for job, next_job, with_supervisor in boundaries:
            with self.subTest(job=job):
                block = text.split(f"\n  {job}:\n", 1)[1].split(
                    f"\n  {next_job}:\n", 1
                )[0]
                invocation = "bash tools/ci/build_historical_blockly_sidecar.sh"
                if with_supervisor:
                    invocation += " --with-supervisor"
                self.assertIn(invocation, block)
                self.assertNotIn("libboost-dev", block)
                self.assertNotIn("apt-get update", block)

    def test_linux_sidecar_remains_header_only_boost(self) -> None:
        makefile = (ROOT / "controllers/supervisor/blocklyServer/Makefile").read_text(encoding="utf-8")
        linux = makefile.split("else\n", 1)[1].split("endif", 1)[0]
        self.assertIn("LIBRARIES=-lpthread", linux)
        self.assertNotIn("-lboost", linux)


if __name__ == "__main__":
    unittest.main()

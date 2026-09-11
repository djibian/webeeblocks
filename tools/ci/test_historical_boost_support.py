#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PREPARER_PATH = ROOT / "tools/ci/prepare_historical_boost.py"
BUILDER_PATH = ROOT / "tools/ci/build_historical_blockly_sidecar.sh"

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
        self.assertIn("archive.ubuntu.com/ubuntu/pool/main/b/boost1.74/", subject.PACKAGE_URL)

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
        self.assertNotIn("apt-get", text)
        self.assertNotIn("apt ", text)
        self.assertNotIn("curl ", text)
        self.assertNotIn("wget ", text)

    def test_linux_sidecar_remains_header_only_boost(self) -> None:
        makefile = (ROOT / "controllers/supervisor/blocklyServer/Makefile").read_text(encoding="utf-8")
        linux = makefile.split("else\n", 1)[1].split("endif", 1)[0]
        self.assertIn("LIBRARIES=-lpthread", linux)
        self.assertNotIn("-lboost", linux)


if __name__ == "__main__":
    unittest.main()

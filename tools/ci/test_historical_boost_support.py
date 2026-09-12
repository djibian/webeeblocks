#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / "tools/ci"
PREPARER_PATH = CI / "prepare_historical_boost.py"
FETCHER_PATH = CI / "fetch_historical_boost_archive.py"
BUILDER_PATH = CI / "build_historical_blockly_sidecar.sh"
ACTION_PATH = ROOT / ".github/actions/historical-boost-support/action.yml"
CI_GATE_WORKFLOW = ROOT / ".github/workflows/ci.yml"
WEBOTS_WORKFLOW = ROOT / ".github/workflows/ci-webots.yml"

spec = importlib.util.spec_from_file_location("prepare_historical_boost", PREPARER_PATH)
assert spec is not None and spec.loader is not None
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)
sys.modules["prepare_historical_boost"] = subject

fetch_spec = importlib.util.spec_from_file_location(
    "fetch_historical_boost_archive", FETCHER_PATH
)
assert fetch_spec is not None and fetch_spec.loader is not None
fetcher = importlib.util.module_from_spec(fetch_spec)
fetch_spec.loader.exec_module(fetcher)


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self._sent = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, size: int) -> bytes:
        del size
        if self._sent:
            return b""
        self._sent = True
        return self._payload


class HistoricalBoostSupportTests(unittest.TestCase):
    def test_exact_archive_identity_is_pinned(self) -> None:
        self.assertEqual(subject.PACKAGE_NAME, "libboost1.74-dev_1.74.0-14ubuntu3_amd64.deb")
        self.assertEqual(subject.PACKAGE_SIZE, 9_608_510)
        self.assertEqual(
            subject.PACKAGE_SHA256,
            "4d9c90e43f0d25db6280d1ee326771cbb76462f73b9430f06bac1de8d05b7a78",
        )
        self.assertEqual(subject.BOOST_VERSION, 107400)
        self.assertEqual(
            fetcher.PACKAGE_URL,
            "https://archive.ubuntu.com/ubuntu/pool/main/b/boost1.74/"
            "libboost1.74-dev_1.74.0-14ubuntu3_amd64.deb",
        )

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

    def test_existing_tree_is_rebuilt_from_verified_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / subject.PACKAGE_NAME
            archive.write_bytes(b"test archive")
            output = root / "boost-1.74"
            boost = output / "usr/include/boost"
            boost.mkdir(parents=True)
            (boost / "version.hpp").write_text(
                "#define BOOST_VERSION 107400\n", encoding="utf-8"
            )
            stale = boost / "asio/version.hpp"
            stale.parent.mkdir(parents=True)
            stale.write_text("stale-tree-bytes\n", encoding="utf-8")

            def fake_extract(command, *, check):
                self.assertTrue(check)
                self.assertEqual(command[:2], ["dpkg-deb", "-x"])
                prepared = Path(command[3])
                fresh = prepared / "usr/include/boost"
                fresh.mkdir(parents=True, exist_ok=True)
                (fresh / "version.hpp").write_text(
                    "#define BOOST_VERSION 107400\n", encoding="utf-8"
                )
                replacement = fresh / "asio/version.hpp"
                replacement.parent.mkdir(parents=True, exist_ok=True)
                replacement.write_text("fresh-verified-tree\n", encoding="utf-8")
                return mock.Mock(returncode=0)

            with mock.patch.object(subject, "verify_archive") as verify_archive, mock.patch.object(
                subject.subprocess, "run", side_effect=fake_extract
            ) as extract:
                result = subject.prepare(output, archive)

            verify_archive.assert_called_once_with(archive.resolve())
            extract.assert_called_once()
            self.assertEqual(result, output.resolve())
            self.assertEqual(
                (output / "usr/include/boost/asio/version.hpp").read_text(encoding="utf-8"),
                "fresh-verified-tree\n",
            )

    def test_cache_fill_does_not_use_network_when_exact_archive_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / subject.PACKAGE_NAME
            output.write_bytes(b"already verified")
            with mock.patch.object(fetcher, "verify_archive") as verify, mock.patch.object(
                fetcher, "urlopen"
            ) as urlopen:
                result = fetcher.fetch(output)
            self.assertEqual(result, output.resolve())
            verify.assert_called_once_with(output.resolve())
            urlopen.assert_not_called()

    def test_cache_fill_verifies_temporary_bytes_before_atomic_exposure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / subject.PACKAGE_NAME
            payload = b"candidate exact archive bytes"
            verified: list[Path] = []

            def verify(path: Path) -> None:
                verified.append(Path(path))
                self.assertEqual(Path(path).read_bytes(), payload)

            with mock.patch.object(fetcher, "verify_archive", side_effect=verify), mock.patch.object(
                fetcher, "urlopen", return_value=_FakeResponse(payload)
            ) as urlopen:
                result = fetcher.fetch(output)

            self.assertEqual(result, output.resolve())
            self.assertEqual(output.read_bytes(), payload)
            self.assertEqual(len(verified), 2)
            self.assertNotEqual(verified[0], output.resolve())
            self.assertEqual(verified[1], output.resolve())
            urlopen.assert_called_once_with(fetcher.PACKAGE_URL, timeout=60)

    def test_failed_cache_fill_never_exposes_unverified_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / subject.PACKAGE_NAME
            with mock.patch.object(
                fetcher,
                "verify_archive",
                side_effect=subject.SupportError("injected digest mismatch"),
            ), mock.patch.object(
                fetcher, "urlopen", return_value=_FakeResponse(b"bad archive")
            ):
                with self.assertRaisesRegex(subject.SupportError, "digest mismatch"):
                    fetcher.fetch(output)
            self.assertFalse(output.exists())
            self.assertEqual(list(Path(temp).glob(output.name + ".download.*")), [])

    def test_cache_action_is_exact_and_apt_free(self) -> None:
        text = ACTION_PATH.read_text(encoding="utf-8")
        self.assertIn("uses: actions/cache@v4", text)
        self.assertIn(f"path: .ci-support/{subject.PACKAGE_NAME}", text)
        self.assertIn(subject.PACKAGE_SHA256, text)
        self.assertIn("steps.boost-cache.outputs.cache-hit != 'true'", text)
        self.assertIn("python3 tools/ci/fetch_historical_boost_archive.py", text)
        self.assertIn("from prepare_historical_boost import PACKAGE_NAME, verify_archive", text)
        self.assertNotIn("apt-get", text)
        self.assertNotIn("apt ", text)

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

    def test_support_contract_runs_in_canonical_selector_job(self) -> None:
        text = CI_GATE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python3 tools/ci/test_historical_boost_support.py", text)

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
                self.assertIn("uses: ./.github/actions/historical-boost-support", block)
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

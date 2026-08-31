#!/usr/bin/env python3
"""Keep archived vendor material out while preserving legacy runtime assets."""

from pathlib import Path
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
    "blocks/crazyflie_v2.js",
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

    def test_tracked_python_cache_does_not_return(self) -> None:
        tracked_cache = ROOT / "controllers" / "controller" / "__pycache__"
        self.assertFalse(tracked_cache.exists())


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from localize_webots_world import LOCAL_PREFIX, REMOTE_PREFIX, localize


class LocalizeWebotsWorldTests(unittest.TestCase):
    def test_localizes_only_the_pinned_prefix(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.wbt"
            target = root / "target.wbt"
            source.write_text(
                f'EXTERNPROTO "{REMOTE_PREFIX}projects/objects/Foo.proto"\n'
                "WorldInfo { basicTimeStep 16 }\n",
                encoding="utf-8",
            )

            self.assertEqual(localize(source, target, 1), 1)
            localized = target.read_text(encoding="utf-8")
            self.assertIn(f"{LOCAL_PREFIX}projects/objects/Foo.proto", localized)
            self.assertEqual(localized.replace(LOCAL_PREFIX, REMOTE_PREFIX), source.read_text(encoding="utf-8"))

    def test_refuses_an_unexpected_dependency_count(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.wbt"
            source.write_text("WorldInfo {}\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "expected exactly 1"):
                localize(source, root / "target.wbt", 1)


if __name__ == "__main__":
    unittest.main()

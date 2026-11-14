"""Fail-closed Windows FPS-only comparison, not a simulated physical PASS."""
import unittest

from tools.grand_prix.package_windows_route import (
    FPS, configure_windows_route_fps, route_world,
)


class WindowsRouteFpsContract(unittest.TestCase):
    def test_only_owner_requested_caps_are_accepted(self):
        self.assertEqual(FPS, (15, 20, 25))
        scene = ("DEF WEBEEBLOCKS_DEDICATED_RUNTIME_WORLD WorldInfo { "
                 "basicTimeStep 8 randomSeed 1 }")
        for invalid in (None, False, True, 0, 14, 21, 30, 60, "20", 20.0):
            with self.subTest(fps=invalid), self.assertRaises(ValueError):
                configure_windows_route_fps(scene, invalid)

    def test_strict_worldinfo_anchor(self):
        for invalid in ("", "WorldInfo { basicTimeStep 8 randomSeed 1 }",
                        "DEF WEBEEBLOCKS_DEDICATED_RUNTIME_WORLD WorldInfo { basicTimeStep 16 randomSeed 1 }",
                        "DEF WEBEEBLOCKS_DEDICATED_RUNTIME_WORLD WorldInfo { basicTimeStep 8 randomSeed 1 FPS 25 }",
                        "DEF WEBEEBLOCKS_DEDICATED_RUNTIME_WORLD WorldInfo { basicTimeStep 8 randomSeed 1 } WorldInfo { }"):
            with self.subTest(world=invalid), self.assertRaises(RuntimeError):
                configure_windows_route_fps(invalid, 20)

    def test_canonical_scene_unchanged_except_fps_on_all_twelve_routes(self):
        for index in range(12):
            reference, identity = route_world(index, 25)
            self.assertEqual(reference.count("FPS 25 "), 1)
            self.assertEqual(reference.count("basicTimeStep 8"), 1)
            for cap in (15, 20):
                with self.subTest(index=index, cap=cap):
                    alternative, actual = route_world(index, cap)
                    self.assertEqual(actual, identity)
                    self.assertEqual(alternative, reference.replace("FPS 25 ", f"FPS {cap} ", 1))
                    self.assertEqual(alternative.count("basicTimeStep 8"), 1)


if __name__ == "__main__":
    unittest.main()

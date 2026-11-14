"""Contract: only native FPS varies; all 12 static physical scenes stay identical."""
import unittest

from tools.grand_prix.package_windows_route import (
    FPS, FPS_MIN, FPS_MAX, DEFAULT_FPS, configure_windows_route_fps, route_world,
)


class WindowsRouteFpsContract(unittest.TestCase):
    def test_exact_slider_range_and_single_packaged_world_per_course(self):
        self.assertEqual((FPS_MIN, FPS_MAX, DEFAULT_FPS, FPS), (1, 60, 20, (20,)))
        scene = ("DEF WEBEEBLOCKS_DEDICATED_RUNTIME_WORLD WorldInfo { "
                 "basicTimeStep 8 randomSeed 1 }")
        for invalid in (None, False, True, -1, 0, 61, 90, "20", 20.0):
            with self.subTest(fps=invalid), self.assertRaises(ValueError):
                configure_windows_route_fps(scene, invalid)
        for allowed in (1, 2, 15, 20, 25, 30, 59, 60):
            with self.subTest(fps=allowed):
                self.assertEqual(configure_windows_route_fps(scene, allowed).count(
                    f"FPS {allowed} "), 1)

    def test_strict_worldinfo_anchor(self):
        for invalid in ("", "WorldInfo { basicTimeStep 8 randomSeed 1 }",
                        "DEF WEBEEBLOCKS_DEDICATED_RUNTIME_WORLD WorldInfo { basicTimeStep 16 randomSeed 1 }",
                        "DEF WEBEEBLOCKS_DEDICATED_RUNTIME_WORLD WorldInfo { basicTimeStep 8 randomSeed 1 FPS 25 }",
                        "DEF WEBEEBLOCKS_DEDICATED_RUNTIME_WORLD WorldInfo { basicTimeStep 8 randomSeed 1 } WorldInfo { }"):
            with self.subTest(world=invalid), self.assertRaises(RuntimeError):
                configure_windows_route_fps(invalid, 20)

    def test_same_physical_scene_across_all_routes_and_slider_extremes(self):
        for index in range(12):
            canonical, identity = route_world(index, 20)
            self.assertEqual(canonical.count("FPS 20 "), 1)
            self.assertEqual(canonical.count("basicTimeStep 8"), 1)
            for fps in (1, 2, 15, 19, 21, 25, 30, 59, 60):
                with self.subTest(index=index, fps=fps):
                    actual, actual_identity = route_world(index, fps)
                    self.assertEqual(actual_identity, identity)
                    self.assertEqual(actual, canonical.replace("FPS 20 ", f"FPS {fps} ", 1))
                    self.assertEqual(actual.count("basicTimeStep 8"), 1)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Static falsification for the independent Activity 2 altitude scene asset.

This intentionally does not claim Webots R2025a contacts, flight feasibility,
scene import/reset safety or pupil acceptance: those require a later native
integration and independent tests. No AST-shape oracle is authorized here.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCENE = ROOT / "worlds/scenes/altitude-v1.wbo"
CRAFT_HALF_SPAN_M = 0.09
NOMINAL_TAKEOFF_M = 0.45


def solid(source: str, name: str):
    pattern = (
        rf"DEF {re.escape(name)} Solid \{{"
        rf"[\s\S]*?translation (-?[0-9.]+) (-?[0-9.]+) (-?[0-9.]+)"
        rf"[\s\S]*?boundingObject Box \{{ size ([0-9.]+) ([0-9.]+) ([0-9.]+) \}}"
    )
    match = re.search(pattern, source)
    if match is None:
        raise AssertionError(f"missing physical collider {name}")
    return tuple(map(float, match.groups()))


class AltitudeSceneStaticProof(unittest.TestCase):
    def setUp(self):
        self.source = SCENE.read_text(encoding="utf-8")

    def test_isolated_versioned_scene_with_only_three_explicit_colliders(self):
        self.assertTrue(self.source.startswith("DEF WEBEEBLOCKS_ALTITUDE_SCENE Group {"))
        self.assertEqual(self.source.count(" Pose {"), 18)
        self.assertEqual(self.source.count(" Solid {"), 3)
        self.assertEqual(self.source.count("boundingObject Box"), 3)
        for name in ("ACTIVITY2_LOW_BARRIER", "ACTIVITY2_LEFT_WALL", "ACTIVITY2_RIGHT_WALL"):
            self.assertIn(f"DEF {name} Solid", self.source)
        self.assertNotIn("TouchSensor", self.source)
        self.assertEqual(self.source.count(" Robot {"), 1,
                         "only one dedicated native evaluator may exist")
        self.assertIn('controller "progression_altitude_v1"', self.source)
        self.assertIn("supervisor TRUE", self.source)
        self.assertNotIn('controller "python"', self.source)

    def test_known_low_barrier_forces_vertical_clearance_in_corridor(self):
        x, y, z, sx, sy, sz = solid(self.source, "ACTIVITY2_LOW_BARRIER")
        self.assertAlmostEqual(x, 0.62)
        self.assertAlmostEqual(y, 0.0)
        self.assertAlmostEqual(z + sz / 2, 0.62)
        self.assertGreater(z + sz / 2, NOMINAL_TAKEOFF_M + CRAFT_HALF_SPAN_M)
        self.assertLess(z + sz / 2 + CRAFT_HALF_SPAN_M, 0.85)
        self.assertLess(sx, 0.20)
        self.assertGreater(sy, 0.6)

        left = solid(self.source, "ACTIVITY2_LEFT_WALL")
        right = solid(self.source, "ACTIVITY2_RIGHT_WALL")
        self.assertAlmostEqual(left[0], right[0])
        self.assertAlmostEqual(left[2], right[2])
        self.assertAlmostEqual(left[1], -right[1])
        self.assertAlmostEqual(left[4], right[4])
        # Remaining gap at either end of the barrier must not allow a
        # body-width horizontal bypass at nominal altitude.
        wall_inner = left[1] - left[4] / 2
        barrier_outer = y + sy / 2
        self.assertGreater(wall_inner, barrier_outer)
        self.assertLess(wall_inner - barrier_outer, CRAFT_HALF_SPAN_M)
        self.assertGreater(left[5], sz)

    def test_start_and_target_are_separate_noncolliding_marks(self):
        self.assertIn("Pose { translation 0 0 0.002", self.source)
        self.assertRegex(self.source, r"Pose \{ translation 1\.35 0 0\.002[\s\S]*?size 0\.34 0\.34 0\.004")
        self.assertEqual(self.source.count("0.0042 children"), 16)
        # Landing zone is beyond the barrier's far face and body clearance.
        barrier = solid(self.source, "ACTIVITY2_LOW_BARRIER")
        self.assertGreater(1.35 - 0.34 / 2, barrier[0] + barrier[3] / 2 + CRAFT_HALF_SPAN_M)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Static falsification of the isolated Activity 3 orientation scene.

This test intentionally does NOT certify Webots parsing, real pose/yaw
measurement, contact behavior, scene selection, RESET or student usability.
A native independent outcome evaluator is required before catalogue exposure.
"""
from math import hypot, isclose, pi
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCENE = ROOT / "worlds/scenes/orientation-v1.wbo"
FLOAT = r"(-?\d+(?:\.\d+)?)"

CHECKPOINT = re.compile(
    r"# CHECKPOINT ([ABC]):[^\n]*\n\s*Pose \{ translation "
    + FLOAT + " " + FLOAT + " " + FLOAT,
)
DIRECTION = re.compile(
    r"# DIRECTION ([ABC]):[^\n]*\n\s*Pose \{ translation "
    + FLOAT + " " + FLOAT + " " + FLOAT
    + r" rotation 0 0 1 " + FLOAT,
)
ARRIVAL = re.compile(r"# ARRIVAL:[^\n]*\n\s*Pose \{ translation " + FLOAT + " " + FLOAT + " " + FLOAT)


class OrientationSceneStaticTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCENE.read_text(encoding="utf-8")
        cls.checkpoints = {
            label: (float(x), float(y), float(z))
            for label, x, y, z in CHECKPOINT.findall(cls.text)
        }
        cls.directions = {
            label: (float(x), float(y), float(z), float(angle))
            for label, x, y, z, angle in DIRECTION.findall(cls.text)
        }
        cls.arrival = tuple(map(float, ARRIVAL.search(cls.text).groups())) if ARRIVAL.search(cls.text) else None

    def test_standalone_visual_scene_has_no_hidden_physics_or_authority(self):
        self.assertTrue(self.text.startswith("DEF WEBEEBLOCKS_ORIENTATION_SCENE Group {"))
        self.assertIsNone(re.search(r"\bSolid\s*\{", self.text))
        self.assertEqual(len(re.findall(r"\bRobot\s*\{", self.text)), 1)
        self.assertRegex(self.text, r'Robot \{\s*name "Progression orientation 3D evaluator"'
                                      r'\s*controller "progression_orientation_3d"'
                                      r'\s*supervisor TRUE\s*synchronization TRUE\s*\}')
        self.assertNotIn("boundingObject", self.text)
        self.assertNotIn("controllerArgs", self.text)
        self.assertNotIn("TouchSensor", self.text)

    def test_ordered_3d_route_requires_real_heading_changes(self):
        self.assertEqual(set(self.checkpoints), {"A", "B", "C"})
        self.assertEqual(set(self.directions), {"A", "B", "C"})
        self.assertEqual(self.arrival, (0.9, -0.9, 0.002))
        p = [(0.0, 0.0)] + [self.checkpoints[k][:2] for k in "ABC"] + [self.arrival[:2]]
        steps = [(p[i + 1][0] - p[i][0], p[i + 1][1] - p[i][1]) for i in range(4)]
        for vx, vy in steps:
            self.assertTrue(isclose(hypot(vx, vy), 0.45, abs_tol=1e-9))
        # The successive legs must make three genuine right angles.
        for a, b in zip(steps, steps[1:]):
            self.assertTrue(isclose(a[0] * b[0] + a[1] * b[1], 0.0, abs_tol=1e-9))
        self.assertEqual(steps, [(0.45, 0.0), (0.0, -0.45), (0.45, 0.0), (0.0, -0.45)])
        self.assertGreater(self.checkpoints["B"][2], self.checkpoints["A"][2] + 0.10)
        self.assertTrue(isclose(self.checkpoints["A"][2], self.checkpoints["C"][2], abs_tol=1e-9))
        # These are the visible arrow poses, not a proxy for actual drone yaw.
        for label, heading in (("A", -pi / 2), ("B", 0.0), ("C", -pi / 2)):
            x, y, z = self.checkpoints[label]
            arrow_x, arrow_y, arrow_z, angle = self.directions[label]
            self.assertEqual((arrow_x, arrow_y), (x, y))
            self.assertTrue(isclose(arrow_z - z, 0.011, abs_tol=1e-9))
            self.assertTrue(isclose(angle, heading, abs_tol=1e-6))

    def test_all_targets_are_visible_noncolliding_marks(self):
        self.assertRegex(self.text, r"Pose \{ translation 0 0 0\.002 children")
        self.assertEqual(len(re.findall(r"0\.0042 children", self.text)), 16)
        self.assertIn("geometry Box { size 0.32 0.32 0.004 }", self.text)
        # Each elevated checkpoint has a visible 18 cm target and heading glyph.
        self.assertEqual(self.text.count("geometry Box { size 0.18 0.18 0.008 }"), 3)
        self.assertEqual(self.text.count("geometry Box { size 0.14 0.018 0.004 }"), 3)
        self.assertEqual(self.text.count("geometry Box { size 0.064 0.064 0.0002 }"), 16)


if __name__ == "__main__":
    unittest.main()

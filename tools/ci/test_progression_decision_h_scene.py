#!/usr/bin/env python3
"""A4 swapped-H/raised-threshold geometric counterexample (not Webots PASS).

One common blind centreline altitude history cannot be safe in both variants
because the same two x positions require opposite altitude clearances.
Real native Multi-ranger perception, actual flight and avoidance of sidestepping
are UNPROVEN. The later native mission oracle MUST enforce visual lane bounds,
under-H passage, real contacts, directed clearance, RESET and complete landing.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCENES = (ROOT / "worlds/scenes/decision-h-a-v1.wbo",
          ROOT / "worlds/scenes/decision-h-b-v1.wbo")
DECISION_X = 0.350
SENSOR_Z = 0.750
TARGET_X = 2.250
H_BOTTOM = 0.620
CURB_TOP = 0.550
PHYSICAL_MARGIN = 0.080
EXPECTED = {"A": (0.900, 1.650), "B": (1.650, 0.900)}


def collider(source, name):
    pattern = (
        rf"DEF {re.escape(name)} Solid \{{\s*"
        rf"translation (-?[0-9.]+) (-?[0-9.]+) (-?[0-9.]+)"
        rf"[\s\S]*?boundingObject Box \{{ size "
        rf"([0-9.]+) ([0-9.]+) ([0-9.]+) \}}"
    )
    match = re.search(pattern, source)
    if not match:
        raise AssertionError(f"missing real collider {name}")
    return tuple(map(float, match.groups()))


class DecisionHSceneTests(unittest.TestCase):
    def test_swapped_obstacles_physically_demand_opposite_height_choices(self):
        ranges = {}
        for letter, path in zip("AB", SCENES):
            with self.subTest(variant=letter):
                scene = path.read_text(encoding="utf-8")
                self.assertIn(f"DEF WEBEEBLOCKS_DECISION_{letter}_SCENE Group", scene)
                self.assertEqual(scene.count(" Pose {"), 23)
                self.assertEqual(scene.count(" Solid {"), 4)
                self.assertEqual(scene.count("boundingObject Box"), 4)
                self.assertEqual(scene.count("0.0042 children"), 16)
                self.assertNotIn("Robot {", scene)
                self.assertNotIn("TouchSensor", scene)
                self.assertNotIn("Supervisor {", scene)
                for marker in ("0 0 0.002", "0.35 0 0.002", "2.25 0 0.002"):
                    self.assertIn(f"Pose {{ translation {marker}", scene)
                self.assertEqual(scene.count("# corridor boundary"), 2)
                self.assertIn("Pose { translation 1.15 0.420 0.002", scene)
                self.assertIn("Pose { translation 1.15 -0.420 0.002", scene)

                left = collider(scene, f"ACTIVITY4_{letter}_H_LEFT")
                right = collider(scene, f"ACTIVITY4_{letter}_H_RIGHT")
                bar = collider(scene, f"ACTIVITY4_{letter}_H_BAR")
                curb = collider(scene, f"ACTIVITY4_{letter}_THRESHOLD")
                hx, cx = EXPECTED[letter]
                self.assertAlmostEqual(left[0], hx)
                self.assertAlmostEqual(right[0], hx)
                self.assertAlmostEqual(bar[0], hx)
                self.assertAlmostEqual(curb[0], cx)
                self.assertEqual(left[1], 0.300)
                self.assertEqual(right[1], -0.300)
                self.assertEqual(bar[1], 0.0)
                self.assertEqual(curb[1], 0.0)
                self.assertAlmostEqual(bar[2] - bar[5] / 2, H_BOTTOM)
                self.assertAlmostEqual(bar[2] + bar[5] / 2, 0.860)
                self.assertAlmostEqual(curb[2] - curb[5] / 2, 0.0)
                self.assertAlmostEqual(curb[2] + curb[5] / 2, CURB_TOP)
                self.assertAlmostEqual(curb[4], 0.74)
                self.assertLess(bar[3], 0.11)
                self.assertLess(curb[3], 0.11)
                self.assertIn(f"Pose {{ translation {hx:.3f} 0 0.002", scene)
                self.assertIn(f"Pose {{ translation {cx:.3f} 0 0.002", scene)
                # Same front ray at y=0,z=0.75: threshold is BELOW ray;
                # H posts are beside ray, and upper H bar crosses it.
                self.assertGreater(SENSOR_Z, CURB_TOP)
                self.assertGreater(SENSOR_Z, H_BOTTOM)
                self.assertLess(SENSOR_Z, bar[2] + bar[5] / 2)
                self.assertGreater(left[1] - left[4] / 2, 0.0)
                self.assertLess(right[1] + right[4] / 2, 0.0)
                ranges[letter] = hx - bar[3] / 2 - DECISION_X

        self.assertAlmostEqual(ranges["A"], 0.515)
        self.assertAlmostEqual(ranges["B"], 1.265)
        self.assertGreater(ranges["B"] - ranges["A"], 0.70)
        # At x=0.900, A must pass BELOW H and B ABOVE threshold.
        # At x=1.650, the opposite applies. With genuine body margin,
        # their admissible centreline altitude bands are disjoint.
        self.assertAlmostEqual(H_BOTTOM - PHYSICAL_MARGIN, 0.54)
        self.assertAlmostEqual(CURB_TOP + PHYSICAL_MARGIN, 0.63)
        self.assertLess(H_BOTTOM - PHYSICAL_MARGIN,
                        CURB_TOP + PHYSICAL_MARGIN)

    def test_no_hidden_answer_or_activity_id(self):
        for letter, path in zip("AB", SCENES):
            scene = path.read_text(encoding="utf-8")
            self.assertEqual(scene.count("DEF ACTIVITY4_"), 4)
            self.assertNotIn("DistanceSensor {", scene)
            self.assertNotIn("Receiver {", scene)


if __name__ == "__main__":
    unittest.main()

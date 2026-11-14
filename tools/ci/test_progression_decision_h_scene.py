#!/usr/bin/env python3
"""A4 physical scene invariants and explicit unqualified overflight witness.

Static tests are not a Webots pupil PASS. Both scenes require one common
non-branching H-crossing oracle, native contacts/real raycasts and the same
ordinary Blockly .wbb with permitted sensor conditional. An arbitrary blind
high overflight still exists if a mission oracle does not check H underpass.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
START_WORLD = ROOT / "worlds/crazyflie_classroom_start.wbt"
SCENES = (ROOT / "worlds/scenes/decision-h-a-v1.wbo",
          ROOT / "worlds/scenes/decision-h-b-v1.wbo")
DECISION_X = .200
SENSOR_Z = .750
TARGET_X = 1.750
FLOOR_HALF = 2.000
H_BOTTOM = .620
CURB_TOP = .700
CRAFT_MARGIN = .080
EXPECTED = {"A": (.750, 1.350), "B": (1.350, .750)}
CHECKERS = (1.637500, 1.712500, 1.787500, 1.862500)


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


def lower(box):
    return box[2] - box[5] / 2


def upper(box):
    return box[2] + box[5] / 2


class DecisionHSceneTests(unittest.TestCase):
    def test_world_bounds_and_real_collision_canalization(self):
        classroom = START_WORLD.read_text(encoding="utf-8")
        self.assertIn("Floor { size 4 4 }", classroom)
        self.assertLess(TARGET_X + .170, FLOOR_HALF)
        self.assertGreater(-.20, -FLOOR_HALF)
        self.assertLess(1.60, FLOOR_HALF)
        for letter, path in zip("AB", SCENES):
            with self.subTest(variant=letter):
                scene = path.read_text(encoding="utf-8")
                self.assertIn(f"DEF WEBEEBLOCKS_DECISION_{letter}_SCENE Group", scene)
                self.assertEqual(scene.count(" Pose {"), 23)
                self.assertEqual(scene.count(" Solid {"), 6)
                self.assertEqual(scene.count("boundingObject Box"), 6)
                self.assertEqual(scene.count("0.0042 children"), 16)
                for x in CHECKERS:
                    self.assertEqual(scene.count(f"Pose {{ translation {x:.6f} "), 4)
                    self.assertLess(x + .075/2, FLOOR_HALF)
                for marker in ("0 0 0.002", "0.20 0 0.002",
                               "1.75 0 0.002"):
                    self.assertIn(f"Pose {{ translation {marker}", scene)
                self.assertEqual(scene.count("# corridor boundary"), 2)

                left = collider(scene, f"ACTIVITY4_{letter}_CORRIDOR_LEFT")
                right = collider(scene, f"ACTIVITY4_{letter}_CORRIDOR_RIGHT")
                self.assertEqual(left, (0.70, .420, .520, 1.80, .08, 1.04))
                self.assertEqual(right, (0.70, -.420, .520, 1.80, .08, 1.04))
                self.assertAlmostEqual(left[0] - left[3]/2, -.20)
                self.assertAlmostEqual(left[0] + left[3]/2, 1.60)
                self.assertAlmostEqual(lower(left), 0.0)
                self.assertAlmostEqual(lower(right), 0.0)
                # Walls must leave less than the 8cm craft clearance
                # between the H posts and the physical lateral boundaries.
                post = collider(scene, f"ACTIVITY4_{letter}_H_LEFT")
                inner_wall_y = left[1] - left[4]/2
                outer_post_y = post[1] + post[4]/2
                self.assertGreater(inner_wall_y, outer_post_y)
                self.assertLess(inner_wall_y - outer_post_y, CRAFT_MARGIN)
                threshold = collider(scene, f"ACTIVITY4_{letter}_THRESHOLD")
                self.assertLess(inner_wall_y - threshold[4]/2, CRAFT_MARGIN)

    def test_open_h_vs_threshold_order_forces_different_altitudes(self):
        observed_ranges = {}
        for letter, path in zip("AB", SCENES):
            scene = path.read_text(encoding="utf-8")
            left = collider(scene, f"ACTIVITY4_{letter}_H_LEFT")
            right = collider(scene, f"ACTIVITY4_{letter}_H_RIGHT")
            bar = collider(scene, f"ACTIVITY4_{letter}_H_BAR")
            curb = collider(scene, f"ACTIVITY4_{letter}_THRESHOLD")
            h_x, curb_x = EXPECTED[letter]
            self.assertEqual((left[0], right[0], bar[0], curb[0]),
                             (h_x, h_x, h_x, curb_x))
            self.assertEqual((left[1], right[1], bar[1], curb[1]),
                             (.300, -.300, 0.0, 0.0))
            self.assertAlmostEqual(lower(bar), H_BOTTOM)
            self.assertAlmostEqual(upper(bar), .860)
            self.assertAlmostEqual(lower(curb), 0.0)
            self.assertAlmostEqual(upper(curb), CURB_TOP)
            self.assertGreater(SENSOR_Z, CURB_TOP)
            self.assertGreater(SENSOR_Z, lower(bar))
            self.assertLess(SENSOR_Z, upper(bar))
            self.assertGreater(left[1] - left[4]/2, 0)
            self.assertLess(right[1] + right[4]/2, 0)
            observed_ranges[letter] = h_x - bar[3]/2 - DECISION_X

        self.assertAlmostEqual(observed_ranges["A"], .515)
        self.assertAlmostEqual(observed_ranges["B"], 1.115)
        # Even for a zero-height point, one identical z(x) cannot pass
        # *under* H in A and *over* the threshold in B at x=.750.
        # The same contradictory requirements swap at x=1.350.
        self.assertLess(H_BOTTOM, CURB_TOP)
        self.assertLess(H_BOTTOM - CRAFT_MARGIN, CURB_TOP + CRAFT_MARGIN)

    def test_high_overflight_is_still_an_adversarial_bypass(self):
        # Explicitly preserve this negative witness until a native evaluator
        # requires under-H passage and bounded height. A draft geometry
        # test must NOT silently assert that ALL blind paths fail.
        for letter, path in zip("AB", SCENES):
            scene = path.read_text(encoding="utf-8")
            hbar = collider(scene, f"ACTIVITY4_{letter}_H_BAR")
            hleft = collider(scene, f"ACTIVITY4_{letter}_H_LEFT")
            curb = collider(scene, f"ACTIVITY4_{letter}_THRESHOLD")
            wall = collider(scene, f"ACTIVITY4_{letter}_CORRIDOR_LEFT")
            blind_height = 1.20
            for obstacle in (hbar, hleft, curb, wall):
                self.assertGreater(blind_height - CRAFT_MARGIN, upper(obstacle))
            # This is a test of an UNRESOLVED physical bypass, not success.
            self.assertNotIn("Robot {", scene)
            self.assertNotIn("Supervisor {", scene)
            self.assertNotIn("DistanceSensor {", scene)
            self.assertNotIn("Receiver {", scene)


if __name__ == "__main__":
    unittest.main()

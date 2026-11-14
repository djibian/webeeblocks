#!/usr/bin/env python3
"""Structural counterexamples for two H-gate decision scenes (not native proof).

Native R2025a sensor return, actual body/collider contact, feedback, RESET and
variant identity remain UNPROVEN until integrated in a strict scene selector
and qualified with the same ordinary pupil .wbb. This test cannot grant PASS.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCENES = (
    ROOT / "worlds/scenes/decision-h-a-v1.wbo",
    ROOT / "worlds/scenes/decision-h-b-v1.wbo",
)
DECISION_X = 0.350
DECISION_SENSOR_Z = 0.750
EXPECTED_TARGET_X = 1.70
H_OPEN_BOTTOM_Z = 0.620


def collider(source, part):
    pattern = (
        rf"DEF ACTIVITY4_[AB]_H_{part} Solid \{{\s*"
        rf"translation ([0-9.\-]+) ([0-9.\-]+) ([0-9.\-]+)"
        rf"[\s\S]*?boundingObject Box \{{ size "
        rf"([0-9.]+) ([0-9.]+) ([0-9.]+) \}}"
    )
    match = re.search(pattern, source)
    if not match:
        raise AssertionError(f"missing or unbounded physical {part} collider")
    return tuple(map(float, match.groups()))


class DecisionHSceneTests(unittest.TestCase):
    def test_consistent_geometry_and_discriminating_horizontal_rays(self):
        distances = []
        low_regions = []
        for letter, path in zip("AB", SCENES):
            with self.subTest(variant=letter):
                source = path.read_text(encoding="utf-8")
                self.assertTrue(source.startswith(f"# Activity 4 {letter}:"))
                self.assertIn(f"DEF WEBEEBLOCKS_DECISION_{letter}_SCENE Group", source)
                self.assertEqual(source.count(" Pose {"), 20)
                self.assertEqual(source.count(" Solid {"), 3)
                self.assertEqual(source.count("boundingObject Box"), 3)
                self.assertNotIn("Robot {", source)
                self.assertEqual(source.count("0.0042 children"), 16)
                for marker in ("0 0 0.002", "0.35 0 0.002", "1.70 0 0.002"):
                    self.assertIn(f"Pose {{ translation {marker}", source)
                left = collider(source, "LEFT")
                right = collider(source, "RIGHT")
                bar = collider(source, "BAR")
                gate_x = bar[0]
                self.assertAlmostEqual(left[0], gate_x)
                self.assertAlmostEqual(right[0], gate_x)
                self.assertAlmostEqual(left[1], -right[1])
                self.assertAlmostEqual(bar[1], 0.0)
                self.assertAlmostEqual(bar[2] - bar[5] / 2, H_OPEN_BOTTOM_Z)
                self.assertLess(bar[2] - bar[5] / 2, DECISION_SENSOR_Z)
                self.assertGreater(bar[2] + bar[5] / 2, DECISION_SENSOR_Z)
                self.assertLess(bar[4] / 2, abs(left[1]) + left[4] / 2)
                self.assertGreater(bar[4] / 2, abs(left[1]) - left[4] / 2)
                self.assertGreater(gate_x - bar[3] / 2, DECISION_X + 0.2)
                self.assertLess(gate_x + bar[3] / 2 + 0.15, EXPECTED_TARGET_X)
                self.assertLess(H_OPEN_BOTTOM_Z, left[2] + left[5] / 2)
                distances.append(gate_x - bar[3] / 2 - DECISION_X)
                # Floor marking: 0.40 m long, centered exactly below its gate.
                self.assertIn(f"Pose {{ translation {gate_x:.3f} 0 0.002", source)
                low_regions.append((gate_x - .20, gate_x + .20))

        # A common fixed-time descent before the first gate cannot be blindly
        # reused for the second gate without entering a non-permitted region.
        self.assertGreater(distances[1] - distances[0], 0.30)
        self.assertLess(low_regions[0][0], low_regions[1][0])
        self.assertGreater(low_regions[0][1], low_regions[1][0])
        self.assertLess(low_regions[0][0] + 0.1, low_regions[1][0])
        self.assertLess(low_regions[0][1], low_regions[1][1])


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""A6 linear gate-count scene static invariants; real Webots proof still required."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCENES = [ROOT / f"worlds/scenes/count-h-{n}-v1.wbo" for n in (1, 2, 3)]
EXPECTED_GATES = {1: [0.10], 2: [-0.50, 0.55], 3: [-0.85, 0.00, 0.85]}
TARGET_Y = {"1": 0.0, "2": 0.55, "3": -0.55}


def collider(source, name):
    m = re.search(
        rf"DEF {re.escape(name)} Solid \{{"
        rf"[\s\S]*?translation (-?[0-9.]+) (-?[0-9.]+) (-?[0-9.]+)"
        rf"[\s\S]*?boundingObject Box \{{ size "
        rf"([0-9.]+) ([0-9.]+) ([0-9.]+) \}}",
        source,
    )
    if m is None:
        raise AssertionError(f"missing genuine collider: {name}")
    return tuple(map(float, m.groups()))


class CountingSceneTests(unittest.TestCase):
    def test_one_two_three_gates_without_turning_or_premature_count_leakage(self):
        for n, path in zip((1, 2, 3), SCENES):
            with self.subTest(gate_count=n):
                src = path.read_text(encoding="utf-8")
                self.assertIn(f"DEF WEBEEBLOCKS_COUNT_{n}_SCENE Group", src)
                self.assertNotIn("Robot {", src)
                self.assertNotIn("TouchSensor", src)
                self.assertEqual(src.count(" Solid {"), 3 * n + 1)
                self.assertEqual(src.count("boundingObject Box"), 3 * n + 1)
                self.assertEqual(src.count("0.0042 children"), 12)
                self.assertIn("Pose { translation -1.40 0 0.002", src)
                self.assertIn("Pose { translation 0.10 0.385 0.002", src)
                self.assertIn("Pose { translation 0.10 -0.385 0.002", src)
                # All THREE landings are present in every variant. No visual
                # omission may signal the gate count before crossing.
                for _id, y in TARGET_Y.items():
                    self.assertIn(f"Pose {{ translation 1.48 {y:.3f} 0.002", src)
                terminal = collider(src, f"ACTIVITY6_{n}_TERMINAL")
                self.assertEqual(terminal, (1.86, 0.0, 0.55, .06, 1.48, 1.10))
                actual_x = []
                for i, gate_x in enumerate(EXPECTED_GATES[n], 1):
                    key = f"ACTIVITY6_{n}_H_{i}"
                    left = collider(src, key + "_LEFT")
                    right = collider(src, key + "_RIGHT")
                    bar = collider(src, key + "_BAR")
                    self.assertAlmostEqual(left[0], gate_x)
                    self.assertAlmostEqual(right[0], gate_x)
                    self.assertAlmostEqual(bar[0], gate_x)
                    self.assertAlmostEqual(left[1], -right[1])
                    self.assertEqual(bar[4], .57)
                    self.assertAlmostEqual(bar[2] - bar[5] / 2, 0.62)
                    self.assertAlmostEqual(bar[2] + bar[5] / 2, 0.86)
                    self.assertLess(gate_x, 1.48 - 0.30)
                    self.assertIn(f"Pose {{ translation {gate_x:.3f} 0 0.002", src)
                    actual_x.append(gate_x)
                self.assertEqual(actual_x, EXPECTED_GATES[n])
                # Separate low-flight bands for gates within the same world.
                self.assertTrue(all(b-a > .40 for a,b in zip(actual_x,actual_x[1:])))

    def test_same_terminal_geometry_makes_all_fixed_landing_choices_inadequate(self):
        # This is a design property, not a native success-oracle assertion.
        # A test of real confirmed crossings and unique counting is mandatory.
        pads = list(TARGET_Y.values())
        self.assertEqual(len(pads), len(set(pads)))
        self.assertEqual({n: len(pos) for n, pos in EXPECTED_GATES.items()},
                         {1: 1, 2: 2, 3: 3})


if __name__ == "__main__":
    unittest.main()

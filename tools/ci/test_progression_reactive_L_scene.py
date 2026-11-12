#!/usr/bin/env python3
"""Static falsification of Activity 5 physical L variants (not native sensing proof).

The three variants deliberately include A/C with identical origin-facing range
but opposite permitted turns. Actual Multi-ranger returns, loop behavior,
collisions, and world reset need R2025a qualification before use by pupils.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCENES = {letter: ROOT / f"worlds/scenes/reactive-L-{letter.lower()}-v1.wbo"
          for letter in "ABC"}


def collider(source, part):
    pattern = (
        rf"DEF ACTIVITY5_[ABC]_{part} Solid \{{"
        rf"[\s\S]*?translation (-?[0-9.]+) (-?[0-9.]+) (-?[0-9.]+)"
        rf"[\s\S]*?boundingObject Box \{{ size "
        rf"([0-9.]+) ([0-9.]+) ([0-9.]+) \}}"
    )
    match = re.search(pattern, source)
    if match is None:
        raise AssertionError(f"missing physical {part} collider")
    return tuple(map(float, match.groups()))


class ReactiveSceneTests(unittest.TestCase):
    def test_real_L_contacts_origin_range_equivalence_and_second_event(self):
        patterns = {}
        for letter, file in SCENES.items():
            with self.subTest(variant=letter):
                src = file.read_text(encoding="utf-8")
                self.assertTrue(src.startswith(f"# Activity 5 {letter}:"))
                self.assertIn(f"DEF WEBEEBLOCKS_REACTIVE_L_{letter}_SCENE Group", src)
                self.assertEqual(src.count(" Pose {"), 20)
                self.assertEqual(src.count(" Solid {"), 3)
                self.assertEqual(src.count("boundingObject Box"), 3)
                self.assertNotIn("Robot {", src)
                self.assertEqual(src.count("0.0042 children"), 16)
                front = collider(src, "L_FRONT")
                side = collider(src, "L_SIDE")
                terminal = collider(src, "TERMINAL")
                x, y, z, sx, sy, sz = front
                self.assertAlmostEqual(y, 0)
                self.assertAlmostEqual(z - sz / 2, 0)
                self.assertAlmostEqual(side[0], x - 0.22)
                self.assertAlmostEqual(side[2], z)
                self.assertAlmostEqual(terminal[0], side[0])
                self.assertAlmostEqual(terminal[2], z)
                # Front and wrong-side physical boxes must overlap to form L.
                self.assertLess(abs(side[0] - x), (side[3] + sx) / 2)
                self.assertLess(abs(side[1] - y), (side[4] + sy) / 2)
                self.assertGreater(abs(side[1]), sy / 2)
                self.assertAlmostEqual(abs(terminal[1]), 1.27)
                self.assertLess(abs(terminal[1] - side[1]), 1.65)
                self.assertIn(f"Pose {{ translation {side[0]:.3f} 0 0.002", src)
                self.assertIn(f"Pose {{ translation {side[0]:.3f} "
                              f"{(-1 if side[1] > 0 else 1) * 0.95:.3f} 0.002", src)
                # Original forward ray at x=0,y=0,z=0.5 meets front collider.
                self.assertLess(z - sz / 2, 0.5)
                self.assertGreater(z + sz / 2, 0.5)
                self.assertGreater(x - sx / 2, 0)
                patterns[letter] = {
                    "first_front": x - sx / 2,
                    "side_sign": 1 if side[1] > 0 else -1,
                    "target_side": -1 if side[1] > 0 else 1,
                    "junction": side[0],
                }

        # A/C are indistinguishable to a front ray from the origin, yet
        # need different turns after arriving at the junction.
        self.assertEqual(patterns["A"]["first_front"], patterns["C"]["first_front"])
        self.assertEqual(patterns["A"]["junction"], patterns["C"]["junction"])
        self.assertNotEqual(patterns["A"]["side_sign"], patterns["C"]["side_sign"])
        # B changes the first wall range and the direction, as required.
        self.assertNotEqual(patterns["A"]["first_front"], patterns["B"]["first_front"])
        self.assertNotEqual(patterns["A"]["target_side"], patterns["B"]["target_side"])


if __name__ == "__main__":
    unittest.main()

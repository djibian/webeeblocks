#!/usr/bin/env python3
"""Static scene proof for the Activity-7 Mini Grand Prix (not a native PASS)."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


def collider(text, label):
    hit = re.search(
        rf"DEF {re.escape(label)} Solid \{{"
        rf"[\s\S]*?translation (-?[0-9.]+) (-?[0-9.]+) (-?[0-9.]+)"
        rf"[\s\S]*?boundingObject Box \{{ size "
        rf"([0-9.]+) ([0-9.]+) ([0-9.]+) \}}", text,
    )
    if hit is None:
        raise AssertionError(f"missing physical collider {label}")
    return tuple(map(float, hit.groups()))


class MiniGrandPrixScenes(unittest.TestCase):
    def test_exactly_one_open_one_closed_and_one_turn_in_two_variants(self):
        layouts = {}
        for letter in "LR":
            path = ROOT / f"worlds/scenes/mini-grand-prix-{letter.lower()}-v1.wbo"
            text = path.read_text(encoding="utf-8")
            with self.subTest(variant=letter):
                self.assertIn(f"DEF WEBEEBLOCKS_MINI_GP_{letter}_SCENE Group", text)
                self.assertEqual(text.count(" Solid {"), 9)
                self.assertEqual(text.count("boundingObject Box"), 9)
                self.assertEqual(text.count("0.0042 children"), 16)
                self.assertNotIn("Robot {", text)
                self.assertNotIn("TouchSensor", text)
                self.assertEqual(text.count("# only arrival zone"), 1)
                self.assertIn("Pose { translation -1.40 0 0.002", text)
                # Open H has three genuine colliders and a positive underpass.
                open_left = collider(text, f"ACTIVITY7_{letter}_OPEN_LEFT")
                open_right = collider(text, f"ACTIVITY7_{letter}_OPEN_RIGHT")
                open_bar = collider(text, f"ACTIVITY7_{letter}_OPEN_BAR")
                self.assertAlmostEqual(open_left[0], open_bar[0])
                self.assertAlmostEqual(open_right[0], open_bar[0])
                self.assertAlmostEqual(open_left[1], -open_right[1])
                self.assertAlmostEqual(open_bar[2] - open_bar[5] / 2, 0.62)
                self.assertAlmostEqual(open_bar[2] + open_bar[5] / 2, 0.86)
                # A real L requires intersection of the two colliders.
                corner_front = collider(text, f"ACTIVITY7_{letter}_CORNER_FRONT")
                corner_side = collider(text, f"ACTIVITY7_{letter}_CORNER_SIDE")
                self.assertLess(abs(corner_front[0] - corner_side[0]),
                                (corner_front[3] + corner_side[3]) / 2)
                self.assertLess(abs(corner_front[1] - corner_side[1]),
                                (corner_front[4] + corner_side[4]) / 2)
                # Closed H lower panel closes ALL passage from z=0 to 1.30.
                closed_left = collider(text, f"ACTIVITY7_{letter}_CLOSED_LEFT")
                closed_right = collider(text, f"ACTIVITY7_{letter}_CLOSED_RIGHT")
                closed_bar = collider(text, f"ACTIVITY7_{letter}_CLOSED_BAR")
                closed_panel = collider(text, f"ACTIVITY7_{letter}_CLOSED_PANEL")
                self.assertAlmostEqual(closed_panel[2] - closed_panel[5] / 2, 0.0)
                self.assertAlmostEqual(closed_panel[2] + closed_panel[5] / 2, 1.30)
                self.assertAlmostEqual(closed_left[1], closed_panel[1])
                self.assertAlmostEqual(closed_right[1], closed_panel[1])
                self.assertAlmostEqual(closed_bar[1], closed_panel[1])
                self.assertGreater(closed_panel[3]/2, abs(closed_left[0]-closed_panel[0])-closed_left[3]/2)
                self.assertGreater(closed_panel[3]/2, abs(closed_right[0]-closed_panel[0])-closed_right[3]/2)
                self.assertLess(open_bar[0], corner_side[0])
                self.assertLess(abs(closed_panel[1]), 1.70)
                # Only one green landing pad before the closed H.
                pad = re.findall(
                    r"Pose \{ translation ([0-9.]+) (-?[0-9.]+) 0\.002"
                    r" children \[ Shape \{ appearance PBRAppearance "
                    r"\{ baseColor 0\.10 0\.72 0\.28", text
                )
                self.assertEqual(len(pad), 1)
                px,py = map(float,pad[0])
                self.assertAlmostEqual(px, corner_side[0])
                self.assertLess(abs(py), abs(closed_panel[1]) - 0.20)
                self.assertEqual(py > 0, letter == "L")
                layouts[letter] = (open_bar[0], corner_side[0], py)
        self.assertNotEqual(layouts["L"], layouts["R"])
        self.assertNotEqual(layouts["L"][0], layouts["R"][0])
        self.assertNotEqual(layouts["L"][1], layouts["R"][1])
        self.assertNotEqual(layouts["L"][2] > 0, layouts["R"][2] > 0)


if __name__ == "__main__":
    unittest.main()

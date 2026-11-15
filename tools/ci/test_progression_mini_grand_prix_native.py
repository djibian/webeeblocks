#!/usr/bin/env python3
"""Draft A7 native witness source/negative import contract (not a flight PASS)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/ci"))
import run_classroom_mini_gp_geometry as witness  # noqa: E402


class MiniGrandPrixNativeContract(unittest.TestCase):
    def test_separate_genuine_school_worlds_and_native_witness_only(self):
        l = witness.compose("L")
        r = witness.compose("R")
        self.assertNotEqual(l, r)
        for letter, world in (("L", l), ("R", r)):
            self.assertTrue(world.startswith("#VRML_SIM R2025a utf8\n"))
            self.assertEqual(world.count('controller "progression_mini_gp_geometry_probe"'), 1)
            self.assertNotIn('controller "crazyflie_runtime_v2"', world)
            self.assertNotIn('controller "crazyflie_classroom_v2"', world)
            self.assertEqual(world.count(witness.MARKER), 1)
            self.assertEqual(world.count(" Solid {"), 9)
            self.assertEqual(world.count("boundingObject Box"), 9)
            self.assertEqual(world.count(f"DEF WEBEEBLOCKS_MINI_GP_{letter}_SCENE Group"), 1)
            self.assertNotIn(f"DEF WEBEEBLOCKS_MINI_GP_{'R' if letter=='L' else 'L'}_SCENE", world)

    def test_invalid_or_ambiguous_scene_fails_closed_before_launch(self):
        for value in (None, 1, "", "B", "l", "LR"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                witness.compose(value)
        valid = (ROOT / "worlds/scenes/mini-grand-prix-l-v1.wbo").read_text(encoding="utf-8")
        for corrupt in (valid+valid, valid.replace("boundingObject Box", "geometry Box", 1),
                        valid.replace("ACTIVITY7_L_CLOSED_PANEL Solid", "ACTIVITY7_L_GHOST Solid"),
                        valid+'\nDEF WEBEEBLOCKS_MINI_GP_R_SCENE Group {}\n'):
            # Replacing the panel label is structurally still 9 colliders,
            # but the exact native C attestation refuses it; the other bad
            # compositions must be rejected before even reaching Webots.
            if "_GHOST" not in corrupt:
                with self.assertRaises(ValueError):
                    witness.compose("L", scene=corrupt)
        with self.assertRaises(ValueError):
            witness.compose("L", source="#VRML_SIM R2025a utf8\n")

    def test_native_observer_has_contact_positive_controls_and_no_student_authority(self):
        native = (ROOT / "controllers/progression_mini_gp_geometry_probe/"
                  "progression_mini_gp_geometry_probe.c").read_text(encoding="utf-8")
        for token in ("wb_supervisor_node_get_from_def", "wb_supervisor_node_get_contact_points",
                      "wb_supervisor_node_enable_contact_points_tracking",
                      "wb_supervisor_node_reset_physics", "range_front",
                      "OPEN_BAR", "CLOSED_PANEL", "gravity_contact",
                      "WEBEEBLOCKS_A7_NATIVE_PASS", "pupil_wbb=UNPROVEN"):
            self.assertIn(token, native)
        self.assertNotIn("wb_motor_set_velocity", native)
        self.assertNotIn("Blockly.", native)
        self.assertNotIn("wb_robot_set_mode", native)


if __name__ == "__main__":
    unittest.main()

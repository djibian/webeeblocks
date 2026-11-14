#!/usr/bin/env python3
"""Contract and adversarial mutations for the native Activity 2 smoke world."""
from __future__ import annotations

from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "tools/ci/prepare_classroom_altitude_smoke.py"
spec = importlib.util.spec_from_file_location("altitude_smoke_generator", MODULE)
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class NativeAltitudeSmokeWorld(unittest.TestCase):
    def setUp(self):
        self.start = generator.START.read_text(encoding="utf-8")
        self.scene = generator.SCENE.read_text(encoding="utf-8")

    def test_native_world_joins_two_actual_controllers_without_browser_or_legacy_oracle(self):
        prepared = generator.compose(self.start, self.scene)
        self.assertTrue(prepared.startswith("#VRML_SIM R2025a utf8\n"))
        self.assertEqual(prepared.count("DEF WEBEEBLOCKS_CLASSROOM_START_WORLD WorldInfo {"), 1)
        self.assertEqual(prepared.count("DEF WEBEEBLOCKS_ALTITUDE_SCENE Group {"), 1)
        self.assertEqual(prepared.count('controller "crazyflie_classroom_v2"'), 1)
        self.assertEqual(prepared.count('controller "progression_altitude_v1"'), 1)
        self.assertNotIn('controller "crazyflie_runtime_v2"', prepared)
        self.assertNotIn('window "blockly_v2"', prepared)
        self.assertNotIn("WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_BEGIN", prepared)
        self.assertNotIn("WEBEEBLOCKS_LEGACY_SCENE", prepared)
        for name in ("ACTIVITY2_START_CANOPY", "ACTIVITY2_LOW_BARRIER", "ACTIVITY2_LEFT_WALL",
                     "ACTIVITY2_RIGHT_WALL"):
            self.assertIn(f"DEF {name} Solid", prepared)
        # Source content is untouched: no change to flight physics / drone PROTO.
        self.assertEqual(self.start.count('controller "crazyflie_runtime_v2"'), 2)
        self.assertEqual(self.scene.count(" Solid {"), 4)

    def test_wrong_world_identity_or_missing_native_controller_is_refused(self):
        variants = (
            (self.start.replace("WorldInfo {", "Group {", 1), self.scene),
            (self.start.replace('name "Crazyflie WebeeBlocks"',
                                'name "not-Crazyflie WebeeBlocks"'), self.scene),
            (self.start.replace('window "blockly_v2"', 'window "test"'), self.scene),
            (self.start.replace("WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_END",
                                "BAD_END"), self.scene),
            (self.start, self.scene.replace('controller "progression_altitude_v1"',
                                             'controller "missing"')),
            (self.start, self.scene.replace("DEF ACTIVITY2_LOW_BARRIER Solid",
                                             "DEF ACTIVITY2_LOW_BARRIER Pose")),
            (self.start, self.scene.replace("boundingObject Box", "# collider removed", 1)),
        )
        for a, b in variants:
            with self.subTest(case=(len(a), len(b))):
                with self.assertRaises(ValueError):
                    generator.compose(a, b)

    def test_classroom_native_runtime_inherits_official_webots_qt_loader_paths(self):
        # This exact native startup failed in Ready CI 43402310288 with
        # "libQt6Core.so.6: cannot open shared object file"; the original
        # controller already has the documented Webots runtime.ini fix.
        physical_ini = (ROOT / "controllers/crazyflie_runtime_v2/runtime.ini").read_bytes()
        classroom_ini = (ROOT / "controllers/crazyflie_classroom_v2/runtime.ini").read_bytes()
        self.assertEqual(classroom_ini, physical_ini,
                         "native school controller must use the proven Webots Qt loader")
        self.assertIn(b"[environment variables for Linux]", classroom_ini)
        self.assertIn(b"WEBOTS_LIBRARY_PATH = $(WEBOTS_HOME)/lib/webots", classroom_ini)
        self.assertIn(b"QT_PLUGIN_PATH = $(WEBOTS_HOME)/lib/webots/qt/plugins", classroom_ini)

    def test_no_unauthorized_smoke_world_cleanup(self):
        source = MODULE.read_text(encoding="utf-8")
        self.assertIn('refusing to overwrite an existing native smoke world', source)
        self.assertIn('refusing to delete an unrecognized test world', source)
        self.assertIn('ROOT / "worlds/ci_classroom_altitude_smoke.wbt"', source)


if __name__ == "__main__":
    unittest.main()

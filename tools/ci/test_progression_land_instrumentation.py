#!/usr/bin/env python3
"""Keep CI-only LAND diagnostics valid on every independently repeated request."""
from pathlib import Path
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.ci.run_progression_sequence_mission import ROOT, instrument_position

SOURCE = ROOT / "controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c"


class LandInstrumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = SOURCE.read_text(encoding="utf-8")
        cls.instrumented = instrument_position(cls.original)

    def test_request_bound_sample_clock(self):
        # Global declaration plus per-LAND reset: every new LAND logs its first
        # commanded motor sample, including subsequent runs after RESET.
        self.assertEqual(self.instrumented.count("sequence_ci_land_samples = 0;"), 2)
        self.assertIn(
            "command = CMD_LAND;\n"
            "        sequence_ci_land_samples = 0;\n"
            "        stable_since = -1.0;",
            self.instrumented,
        )
        self.assertIn("sequence_ci_land_samples % 16 == 0", self.instrumented)
        self.assertIn("++sequence_ci_land_samples;", self.instrumented)

    def test_observation_after_all_four_unchanged_motor_calls(self):
        p = self.instrumented
        self.assertLess(p.index("wb_motor_set_velocity(m4, motor_power(power.m4));"),
                        p.index("WEBEEBLOCKS_SEQUENCE_CI_LAND id="))
        self.assertIn("motor1=%.9f motor2=%.9f motor3=%.9f motor4=%.9f", p)
        self.assertIn("if (command == CMD_LAND &&", p)
        self.assertIn('sequence_ci_position("land-stop"', p)

    def test_guard_fails_closed_if_land_entry_changes(self):
        changed = self.original.replace(
            "        command = CMD_LAND;\n        stable_since = -1.0;",
            "        command = CMD_LAND;\n        stable_since = 0.0;",
            1,
        )
        self.assertNotEqual(changed, self.original)
        with self.assertRaisesRegex(ValueError, "ambiguous sequence position instrumentation"):
            instrument_position(changed)

    def test_diagnostic_is_not_a_source_mutation(self):
        self.assertEqual(self.original, SOURCE.read_text(encoding="utf-8"))
        self.assertEqual(self.original.count("WEBEEBLOCKS_SEQUENCE_CI_LAND"), 0)


if __name__ == "__main__":
    unittest.main()

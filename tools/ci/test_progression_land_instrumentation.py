#!/usr/bin/env python3
"""Keep CI-only LAND diagnostics valid on every independently repeated request."""
from pathlib import Path
import hashlib
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.ci.run_progression_sequence_mission import ROOT, instrument_position, native_context, WEBOTS_IMAGE

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

    def test_native_supervisor_contact_observations_are_request_bound(self):
        p = self.instrumented
        self.assertIn(
            "WbContactPoint *points = wb_supervisor_node_get_contact_points(self, true, &contact_count);",
            p,
        )
        self.assertIn("wb_supervisor_node_get_velocity(self)", p)
        self.assertIn("double velocity[6] = {NAN, NAN, NAN, NAN, NAN, NAN};", p)
        self.assertLess(
            p.index("velocity[i] = observed_velocity[i];"),
            p.index("WbContactPoint *points = wb_supervisor_node_get_contact_points(self"),
        )
        self.assertIn("isfinite(points[i].point[axis])", p)
        self.assertIn("contact_count < 6 ? contact_count : 6", p)
        self.assertIn("status=%s contacts=%d shown=%d", p)
        self.assertEqual(p.count("sequence_ci_native_land(active_id, now, self_node);"), 1)
        self.assertIn(
            "sequence_ci_native_land(active_id, now, self_node);\n"
            "      }\n"
            "      if (command == CMD_LAND)",
            p,
        )
        self.assertLess(
            p.index("wb_motor_set_velocity(m4, motor_power(power.m4));"),
            p.index("sequence_ci_native_land(active_id, now, self_node);"),
        )
        helper = p.split("static void sequence_ci_native_land(", 1)[1].split(
            "int main(void) {", 1
        )[0]
        for forbidden in ("wb_robot_step(", "wb_motor_set_velocity(", "wb_supervisor_node_set_"):
            self.assertNotIn(forbidden, helper)

    def test_ci_move_dual_clock_observation(self):
        # Wall-clock and simulated progress must be recorded for the same
        # native request, without changing the student's action timeout.
        p = self.instrumented
        self.assertIn("#include <sys/time.h>", p)
        self.assertIn("gettimeofday(&tv, NULL)", p)
        self.assertIn("WEBEEBLOCKS_SEQUENCE_CI_MOVE id=%d sim=%.9f elapsed_sim=%.9f wall_ms=%lld", p)
        self.assertIn("sequence_ci_move_samples++ % 128 == 0", p)
        self.assertIn("sequence_ci_move_samples = 0;", p)
        self.assertEqual(p.count("WEBEEBLOCKS_SEQUENCE_CI_MOVE id="), 1)
        self.assertLess(
            p.index("WEBEEBLOCKS_SEQUENCE_CI_MOVE id="),
            p.index("if (command != CMD_IDLE && command != CMD_RESET &&"),
        )
        self.assertIn("now - action_start, sequence_ci_wall_ms()", p)
        self.assertNotIn("WEBEEBLOCKS_SEQUENCE_CI_MOVE", self.original)
        self.assertEqual(self.original.count("#define ACTION_TIMEOUT 25.0"), 1)
        self.assertEqual(p.count("#define ACTION_TIMEOUT 25.0"), 1)

    def test_move_monotonic_observation_discriminates_clock_adjustment(self):
        # Supplemental native source observation only: both clocks are sampled
        # in the same existing MOVE logging branch; deadlines are unchanged.
        p = self.instrumented
        self.assertIn("#include <time.h>", p)
        self.assertEqual(p.count("clock_gettime(CLOCK_MONOTONIC, &ts)"), 1)
        self.assertIn("static long long sequence_ci_monotonic_ms(void)", p)
        self.assertIn("return -1;  // Unavailable observation", p)
        self.assertIn(
            "WEBEEBLOCKS_SEQUENCE_CI_MOVE id=%d sim=%.9f elapsed_sim=%.9f "
            "wall_ms=%lld monotonic_ms=%lld x=%.9f", p,
        )
        self.assertEqual(p.count("WEBEEBLOCKS_SEQUENCE_CI_MOVE id="), 1)
        self.assertIn(
            "active_id, now, now - action_start, sequence_ci_wall_ms(), "
            "sequence_ci_monotonic_ms(), x, y, z,", p,
        )
        self.assertEqual(p.count("sequence_ci_monotonic_ms()"), 1)
        self.assertEqual(p.count("sequence_ci_move_samples++ % 128 == 0"), 1)
        self.assertNotIn("sequence_ci_monotonic_ms", self.original)
        self.assertEqual(p.count("#define ACTION_TIMEOUT 25.0"), 1)
        self.assertEqual(self.original.count("#define ACTION_TIMEOUT 25.0"), 1)

    def test_move_probe_guard_fails_closed(self):
        changed = self.original.replace(
            "        command = CMD_MOVE;\n        stable_since = -1.0;",
            "        command = CMD_MOVE;\n        stable_since = 1.0;",
            1,
        )
        self.assertNotEqual(changed, self.original)
        with self.assertRaisesRegex(ValueError, "ambiguous sequence position instrumentation"):
            instrument_position(changed)

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


class NativeContextTests(unittest.TestCase):
    """Inputs are reproducible; identical contact dynamics are not asserted."""

    def setUp(self):
        self.source = 'WorldInfo { basicTimeStep 8 }\\nRobot { window "blockly_v2" }\\n'

    def test_neutral_world_source_and_prepared_digests_are_distinct(self):
        prepared = self.source.replace('window "blockly_v2"', 'window "sequence_neutral_probe"')
        context = native_context('crazyflie_classroom_start.wbt', self.source, prepared, neutral=True)
        sha = lambda s: hashlib.sha256(s.encode('utf-8')).hexdigest()
        self.assertEqual(context['world_source_sha256'], sha(self.source))
        self.assertEqual(context['prepared_world_sha256'], sha(prepared))
        self.assertNotEqual(context['world_source_sha256'], context['prepared_world_sha256'])
        self.assertEqual(context['world_source_path'], 'worlds/crazyflie_classroom_start.wbt')
        self.assertEqual(context['webots_container_image'], WEBOTS_IMAGE)
        self.assertIn('not-reproducible-contact-physics', context['claim'])
        self.assertIn('ODE-contact-solver-initial-state', context['unattested'])

    def test_legacy_and_neutral_modes_cannot_be_mislabelled(self):
        legacy = self.source.replace('window "blockly_v2"', 'window "sequence_probe"')
        context = native_context('crazyflie_runtime_v2.wbt', self.source, legacy, neutral=False)
        self.assertFalse(context['neutral_start'])
        with self.assertRaises(ValueError):
            native_context('crazyflie_runtime_v2.wbt', self.source, legacy, neutral=True)
        with self.assertRaises(ValueError):
            native_context('missing.wbt', self.source, legacy, neutral=False)

    def test_source_mutation_or_unrelated_prepared_world_fails_closed(self):
        neutral = self.source.replace('window "blockly_v2"', 'window "sequence_neutral_probe"')
        with self.assertRaises(ValueError):
            native_context('crazyflie_classroom_start.wbt', self.source, neutral+'changed', neutral=True)
        with self.assertRaises(ValueError):
            native_context('crazyflie_classroom_start.wbt', self.source.replace(
                'window "blockly_v2"', 'window "sequence_probe"'), neutral, neutral=True)
        with self.assertRaises(ValueError):
            native_context('crazyflie_classroom_start.wbt', self.source, self.source, neutral=True)

    def test_runner_writes_manifest_before_docker_launch(self):
        source = (ROOT / 'tools/ci/run_progression_sequence_mission.py').read_text(encoding='utf-8')
        self.assertIn("json.dumps(native_context(world_name, source_world, prepared_world, neutral=NEUTRAL_START)", source)
        self.assertLess(source.index("(ARTIFACT_ROOT / 'native-context.json').write_text("),
                        source.index('pull = run(["docker", "pull", WEBOTS_IMAGE]'))


if __name__ == "__main__":
    unittest.main()

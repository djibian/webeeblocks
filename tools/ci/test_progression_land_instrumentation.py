#!/usr/bin/env python3
"""Keep CI-only LAND diagnostics valid on every independently repeated request."""
from pathlib import Path
import hashlib
import subprocess
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.ci.run_progression_sequence_mission import ROOT, instrument_position, native_context, WEBOTS_IMAGE, observed_runtime_environment

SOURCE = ROOT / "controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c"



class RuntimeEnvironmentTests(unittest.TestCase):
    """Only record effective package evidence; no false claim of equal physics."""

    def test_successful_package_queries_are_observations_not_contact_proof(self):
        calls = []

        def probe(argv, **kwargs):
            calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 0, stdout="123.4\n", stderr="")

        result = observed_runtime_environment(
            probe=probe, os_release_path=Path("/nonexistent-webeblocks-os-release"))
        self.assertEqual(result["schema"], "progression-native-runtime-environment-v1")
        self.assertEqual(result["webots_container_image"], WEBOTS_IMAGE)
        self.assertIn("not-contact-or-solver-equivalence", result["claim"])
        self.assertIsNone(result["os_release_sha256"])
        self.assertEqual(len(calls), 4)
        for argv, kwargs in calls:
            self.assertEqual(argv[:2], ["dpkg-query", "-W"])
            self.assertEqual(argv[2], "-f=${Version}")
            self.assertEqual(kwargs["timeout"], 3)
        self.assertTrue(all(value == {"status": "observed", "version": "123.4"}
                            for value in result["dpkg_versions"].values()))
        self.assertIn("initial-contact-manifold-and-impulses", result["unattested"])

    def test_missing_failed_invalid_or_timed_out_versions_are_unproven(self):
        def probe(argv, **kwargs):
            package = argv[3]
            if package == "google-chrome-stable":
                return subprocess.CompletedProcess(argv, 1, stdout="false-positive", stderr="")
            if package == "libc6":
                return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
            if package == "libode8":
                raise subprocess.TimeoutExpired(argv, 3)
            return subprocess.CompletedProcess(argv, 0, stdout="x" * 129, stderr="")

        result = observed_runtime_environment(
            probe=probe, os_release_path=Path("/nonexistent-webeblocks-os-release"))
        for value in result["dpkg_versions"].values():
            self.assertEqual(value, {"status": "unproven"})

    def test_effective_environment_is_captured_before_webots_without_new_run(self):
        script = (ROOT / "tools/ci/run_progression_sequence_mission.py").read_text(
            encoding="utf-8")
        shell = script.split("inner = r'''", 1)[1].split("'''.strip()", 1)[0]
        self.assertLess(shell.index("apt-get install -y /tmp/google-chrome.deb"),
                        shell.index("PY_NATIVE_CONTEXT"))
        self.assertLess(shell.index("PY_NATIVE_CONTEXT"),
                        shell.index("timeout -k 5s 260s xvfb-run"))
        self.assertEqual(shell.count("timeout -k 5s 260s xvfb-run"), 1)
        self.assertIn("effective-runtime-environment.json", shell)
        self.assertIn(
            "inner = inner.replace('progression-sequence-mission', ARTIFACT_ROOT.name)",
            script)
        self.assertIn('WEBEEBLOCKS_SEQUENCE_RESULT attempt=1 status=achieved', script)
        self.assertIn('WEBEEBLOCKS_SEQUENCE_RESULT attempt=3 status=not-achieved', script)


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

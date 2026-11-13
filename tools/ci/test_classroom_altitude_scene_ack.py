#!/usr/bin/env python3
"""Reject preloaded scenes and prove native SCENE probe stays test-only."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / "tools/ci/prepare_classroom_altitude_scene_ack.py"
RUNTIME = ROOT / "tools/ci/run_classroom_altitude_scene_ack.py"
PAGE = ROOT / "plugins/robot_windows/altitude_scene_ack_probe/altitude_scene_ack_probe.js"
PAGE_HTML = ROOT / "plugins/robot_windows/altitude_scene_ack_probe/altitude_scene_ack_probe.html"

spec = importlib.util.spec_from_file_location("classroom_scene_ack_compose", PREP)
producer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(producer)


class NativeSceneAckContract(unittest.TestCase):
    def setUp(self):
        self.source = producer.SOURCE.read_text(encoding="utf-8")

    def test_scene_must_be_imported_only_by_actual_runtime(self):
        world = producer.compose(self.source)
        self.assertEqual(world.count('controller "crazyflie_classroom_v2"'), 1)
        self.assertNotIn('controller "crazyflie_runtime_v2"', world)
        self.assertNotIn('Progression sequence evaluator', world)
        self.assertNotIn('controller "progression_altitude_v1"', world)
        self.assertNotIn('DEF WEBEEBLOCKS_ALTITUDE_SCENE', world)
        self.assertIn('window "altitude_scene_ack_probe"', world)
        self.assertIn('DEF WEBEEBLOCKS_CLASSROOM_START_WORLD WorldInfo {', world)
        self.assertIn('# WEBEEBLOCKS_CLASSROOM_ALTITUDE_SCENE_ACK_CI_ONLY', world)
        # Never rewrite the Crazyflie PROTO/sensors and committed starter.
        self.assertIn('DistanceSensor {', world)
        self.assertEqual(self.source.count('controller "crazyflie_runtime_v2"'), 2)

    def test_identity_or_preloaded_scene_mutants_fail(self):
        corruptions = (
            self.source.replace('#VRML_SIM R2025a utf8', '#VRML_SIM R2024a utf8', 1),
            self.source.replace('DEF WEBEEBLOCKS_CLASSROOM_START_WORLD', 'DEF UNRELATED'),
            self.source.replace('window "blockly_v2"', 'window "other"'),
            self.source.replace('controller "crazyflie_runtime_v2"', 'controller "bad"'),
            self.source.replace('WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_END', 'BAD_END'),
            self.source + '\nDEF WEBEEBLOCKS_ALTITUDE_SCENE Group { children [] }\n',
        )
        for damaged in corruptions:
            with self.subTest(corruption=damaged[:80]):
                with self.assertRaises(ValueError):
                    producer.compose(damaged)

    def test_browser_cannot_claim_a_mocked_ack_or_skip_native_start(self):
        js = PAGE.read_text(encoding="utf-8")
        html = PAGE_HTML.read_text(encoding="utf-8")
        runner = RUNTIME.read_text(encoding="utf-8")
        canonical_ci = (ROOT / "tools/ci/run_progression_sequence_mission.py").read_text(encoding="utf-8")
        # Webots only reads the configured RobotWindow browser on process
        # startup. Creating it after the native witness gave 0 page events.
        conf = '> /root/.config/Cyberbotics/Webots-R2025a.conf'
        witness = 'python3 /workspace/tools/ci/run_classroom_altitude_scene_ack.py'
        self.assertEqual(canonical_ci.count(conf), 1)
        self.assertEqual(canonical_ci.count(witness), 1)
        self.assertLess(canonical_ci.index(conf), canonical_ci.index(witness),
                        'browser configuration was written after the probe started')
        self.assertIn('CLASSROOM_WINDOW_HTML_LOADED', html)
        self.assertIn('CLASSROOM_PROBE_JS_STARTED', js)
        self.assertIn('CLASSROOM_BRIDGE_CONSTRUCTED', js)
        self.assertIn('browser_launched', runner)
        self.assertIn('altitude_scene_ack_probe.js', html)
        self.assertIn('WebeeBlocksWwiBackend', js)
        self.assertIn("windowBridge.send(PREFIX + ' REQUEST ' + id + ' ' + parts)", js)
        self.assertIn("window.crypto.getRandomValues(bytes)", js)
        self.assertIn("found[2] === waiter.expected", js)
        self.assertIn("SCENE_OK ' + altitudeNonce", js)
        self.assertIn("ERR SCENE_UNAVAILABLE", js)
        self.assertIn("LEGACY_SCENE_RESTORED", js)
        self.assertIn("ALTITUDE_SCENE_REATTACHED", js)
        self.assertIn("NATIVE_SCENE_ACK_TEST_COMPLETE", js)
        self.assertIn("ThreadingHTTPServer", runner)
        self.assertIn("two_evaluators =", runner)
        # A browser ACK may arrive before imported evaluator startup.
        # No early process teardown is allowed until two real READY witnesses.
        self.assertIn("ready_twice = complete and output.exists()", runner)
        self.assertIn("if ready_twice:", runner)
        self.assertNotIn('if any(e["event"] == "NATIVE_SCENE_ACK_TEST_COMPLETE" for e in EVENTS):\n                break', runner)
        self.assertIn("WEBEEBLOCKS_ALTITUDE_READY scene=altitude-v1", runner)
        self.assertIn("WEBEEBLOCKS_RUNTIME_V2 READY", runner)
        self.assertIn("world_probe.cleanup()", runner)
        self.assertNotIn("assertTrue(True)", runner)


if __name__ == "__main__":
    unittest.main()

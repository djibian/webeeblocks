"""Fail-closed pure tests. No Webots or radio execution is claimed."""
from __future__ import annotations

from pathlib import Path
import math
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.bitcraze_takeoff_nominal import (
    FIRMWARE_SHA, NOMINAL_PEAK_FACTOR, TAKEOFF_VELOCITY_M_S,
    HEIGHTS_M, nominal_takeoff, normalized_position, normalized_speed, rows,
)


class TestPinnedBitcrazeReference(unittest.TestCase):
    def test_firmware_and_physical_packet_9_provenance(self):
        source = (ROOT / "tools/physical/firmware/SOURCE.md").read_text()
        request = (ROOT / "tools/physical/takeoff_command.py").read_text()
        self.assertIn(FIRMWARE_SHA, source)
        self.assertIn("TAKEOFF_WITH_VELOCITY_COMMAND = 9", request)
        self.assertIn("TAKEOFF_VELOCITY_M_S = 0.5", request)
        self.assertIn("False,  # absolute target height", request)
        self.assertEqual(TAKEOFF_VELOCITY_M_S, .5)
        self.assertEqual(HEIGHTS_M, (.5, .8, 1.0))

    def test_exact_seventh_order_rest_to_rest_trajectory(self):
        self.assertEqual(normalized_position(0), 0)
        self.assertEqual(normalized_position(1), 1)
        self.assertAlmostEqual(normalized_position(.5), .5, places=12)
        self.assertEqual(normalized_speed(0), 0)
        self.assertEqual(normalized_speed(1), 0)
        self.assertAlmostEqual(normalized_speed(.5), NOMINAL_PEAK_FACTOR, places=12)
        for height in HEIGHTS_M:
            duration = height / .5
            z0, vz0, t0 = nominal_takeoff(height, 0, 0)
            zm, vzm, tm = nominal_takeoff(height, 0, duration / 2)
            z1, vz1, t1 = nominal_takeoff(height, 0, duration)
            self.assertEqual((z0, vz0, t0), (0, 0, duration))
            self.assertAlmostEqual(zm, height / 2)
            self.assertAlmostEqual(vzm, 35 / 16 * .5)
            self.assertAlmostEqual(z1, height)
            self.assertEqual(vz1, 0)
            self.assertEqual(t1, duration)

    def test_absolute_target_and_nonzero_estimated_initial_z(self):
        z, v, duration = nominal_takeoff(.8, .015, (.8 - .015) / (.5 * 2))
        self.assertAlmostEqual(z, (.8 + .015) / 2, places=10)
        self.assertAlmostEqual(v, .5 * 35 / 16, places=10)
        self.assertAlmostEqual(duration, 1.57, places=10)

    def test_invalid_reference_domain_is_not_silently_normalized(self):
        for bad in (float("nan"), float("inf"), -.1, .8):
            with self.assertRaises(ValueError):
                nominal_takeoff(.8, bad, .1)
        for bad in (float("nan"), -1.0):
            with self.assertRaises(ValueError):
                nominal_takeoff(.8, .0, bad)
        with self.assertRaises(ValueError):
            rows(step_s=0)

    def test_csv_sampling_contains_terminal_knots_without_fabricating_measurements(self):
        data = rows()
        self.assertTrue(data)
        self.assertEqual({r["ast_height_m"] for r in data}, set(HEIGHTS_M))
        for height in HEIGHTS_M:
            candidates = [r for r in data if r["ast_height_m"] == height]
            self.assertTrue(any(abs(r["t_s"] - height / .5) < 1e-9 for r in candidates))
            self.assertTrue(all(0 <= r["z_ref_m"] <= height + 1e-8 for r in candidates))


class TestNativeRunnerIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.python = (ROOT / "tools/grand_prix/run_takeoff_native_r2025a.py").read_text()
        cls.node = (ROOT / "tools/grand_prix/native_takeoff_stimulus.js").read_text()

    def test_three_separate_identical_worlds_and_real_evaluator(self):
        self.assertIn("HEIGHTS = (0.5, 0.8, 1.0)", self.python)
        self.assertIn("COURSE_INDEX = 5", self.python)
        self.assertIn("active_course_world(reference_course(COURSE_INDEX))", self.python)
        self.assertIn("world.write_text(source_world)", self.python)
        self.assertIn("run_case(home, index, height", self.python)
        self.assertIn("WBB_GP_TAKEOFF_TRACE=\"1\"", self.python)
        self.assertIn('"--mode=fast"', self.python)
        self.assertIn("compile_production(home)", self.python)
        self.assertNotIn("gp_route_evaluator_probe.py", self.python)
        self.assertNotIn("grand_prix_route_publisher_probe", self.python)

    def test_backend_admission_not_bypassed(self):
        self.assertIn("await backend.waitUntilReady()", self.node)
        self.assertIn("await backend.takeoff(height)", self.node)
        self.assertNotIn("backend._request(['TAKEOFF'", self.node)
        self.assertNotIn("robot:Crazyflie WebeeBlocks:WEBEEBLOCKS_RUNTIME_V2 REQUEST", self.node)
        self.assertNotIn("completeActivityMission", self.node)
        self.assertNotIn("backend.land()", self.node)
        self.assertNotIn("backend.resetSimulation()", self.node)

    def test_no_missing_trace_can_be_promoted_to_native_result(self):
        self.assertIn('status["status"] = "MISSING_OR_INVALID_TRACE"', self.python)
        self.assertIn('"TRACE_PARTIAL_OR_SAFETY_REFUSAL"', self.python)
        self.assertIn('"INCOMPLETE_OR_NATIVE_REFUSAL"', self.python)
        self.assertIn('status["first_oracle_closed"]', self.python)
        self.assertIn('status["safety_land_events"]', self.python)
        self.assertIn("status[\"metrics\"][\"max_pid_reconstruction_residual\"] < .0001",
                      self.python)
        self.assertIn("stop_owned_process", self.python)
        self.assertIn("source_sha = require_source(args.expected_head)", self.python)
        self.assertIn('"--untracked-files=no"', self.python)

    def test_node_js_syntax_if_available(self):
        if shutil.which("node") is None:
            self.skipTest("Node is unavailable: syntax check not executed")
        subprocess.run(["node", "--check",
                        str(ROOT / "tools/grand_prix/native_takeoff_stimulus.js")],
                       check=True, timeout=15)

    def test_invalid_webots_home_never_creates_simulated_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "must-not-exist"
            exact = subprocess.check_output(
                ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
            proc = subprocess.run(
                [sys.executable, str(ROOT / "tools/grand_prix/run_takeoff_native_r2025a.py"),
                 "--expected-head", exact,
                 "--webots-home", str(root / "not-webots"),
                 "--output", str(output), "--preflight-only"],
                cwd=ROOT, capture_output=True, text=True, timeout=15)
            self.assertNotEqual(proc.returncode, 0)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()

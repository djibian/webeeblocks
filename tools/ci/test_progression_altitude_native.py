#!/usr/bin/env python3
"""Adversarial executable tests of the independent Activity 2 native C oracle.

The C core is compiled by cc, not emulated in Python. Real Webots R2025a
collision points, controller loading, Runtime ACK and Save/Open remain a
separate, mandatory product qualification.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "controllers/progression_altitude_v1"
CORE = CONTROLLER / "altitude_core.h"
SOURCE = CONTROLLER / "progression_altitude_v1.c"
MAKEFILE = CONTROLLER / "Makefile"
SCENE = ROOT / "worlds/scenes/altitude-v1.wbo"

DRIVER = r"""
#include "altitude_core.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static wb_alt_verdict step(wb_alt_mission *m, double t,
                           double x, double y, double z,
                           double vx, int contact, int complete) {
  const wb_alt_sample sample = {
    .time=t, .x=x, .y=y, .z=z,
    .vx=vx, .vy=0.0, .vz=0.0,
    .obstacle_contact=contact, .completed=complete
  };
  return wb_alt_sample_mission(m, &sample);
}
static void normal_takeoff(wb_alt_mission *m, unsigned long long attempt) {
  wb_alt_reset(m, attempt, 0.0);
  assert(step(m, 0.0, 0.0, 0, 0.01, 0, 0, 0) == WB_ALT_WAIT);
  assert(step(m, 1.0, 0.0, 0, 0.45, 0, 0, 0) == WB_ALT_WAIT);
}
static void cross_higher(wb_alt_mission *m) {
  assert(step(m, 2.0, 0.48, 0, 0.78, 0, 0, 0) == WB_ALT_WAIT);
  assert(step(m, 2.5, 0.59, 0, 0.80, 0, 0, 0) == WB_ALT_WAIT);
  assert(step(m, 3.0, 0.81, 0, 0.80, 0, 0, 0) == WB_ALT_WAIT);
  assert(m->crossed_barrier);
}
int main(void) {
  wb_alt_mission m;
  normal_takeoff(&m, 1);
  cross_higher(&m);
  assert(step(&m, 6.0, 1.35, 0, 0.015, 0, 0, 1) == WB_ALT_ACHIEVED);
  assert(step(&m, 10.0, 0.0, 0, 1.4, 0, 1, 1) == WB_ALT_ACHIEVED);
  assert(m.result == WB_ALT_ACHIEVED);

  /* Re-use of attempt 2 after RESET cannot inherit success. */
  normal_takeoff(&m, 2);
  assert(!m.crossed_barrier && m.result == WB_ALT_WAIT);
  assert(step(&m, 5.0, 1.35, 0, 0.02, 0, 0, 1) == WB_ALT_WAIT);
  assert(step(&m, 6.6, 1.35, 0, 0.02, 0, 0, 1) == WB_ALT_NOT_ACHIEVED);

  /* Flying below the true physical barrier is terminal failure. */
  normal_takeoff(&m, 3);
  assert(step(&m, 1.1, 0.48, 0, 0.51, 0, 0, 0) == WB_ALT_NOT_ACHIEVED);

  /* Actual barrier and side-wall contact points are discriminated. */
  const double ground[3] = {0, 0, 0};
  const double bar[3] = {0.62, 0, 0.4};
  const double wall[3] = {0.68, 0.51, 0.4};
  const double invalid[3] = {NAN, 0, 0};
  assert(wb_alt_obstacle_point(ground) == 0);
  assert(wb_alt_obstacle_point(bar) == 1);
  assert(wb_alt_obstacle_point(wall) == 1);
  assert(wb_alt_obstacle_point(invalid) == -1);
  normal_takeoff(&m, 4);
  assert(step(&m, 1.1, 0.3, 0, 0.48, 0, 1, 0) == WB_ALT_NOT_ACHIEVED);

  /* No contact evidence is NOT permission to grant success. */
  normal_takeoff(&m, 5);
  assert(step(&m, 1.1, 0.3, 0, 0.48, 0, -1, 0) == WB_ALT_NOT_ACHIEVED);
  normal_takeoff(&m, 6);
  assert(step(&m, 1.1, 0.3, 0, NAN, 0, 0, 0) == WB_ALT_NOT_ACHIEVED);

  /* Wrong landing or moving flight never passes. */
  normal_takeoff(&m, 7);
  cross_higher(&m);
  assert(step(&m, 6.0, 1.35, 0.20, 0.02, 0, 0, 1) == WB_ALT_WAIT);
  assert(step(&m, 7.6, 1.35, 0.20, 0.02, 0, 0, 1) == WB_ALT_NOT_ACHIEVED);
  normal_takeoff(&m, 8);
  cross_higher(&m);
  assert(step(&m, 6.0, 1.35, 0, 0.02, 0.25, 0, 1) == WB_ALT_WAIT);
  assert(step(&m, 7.6, 1.35, 0, 0.02, 0.25, 0, 1) == WB_ALT_NOT_ACHIEVED);

  /* Takeoff without a physical crossing cannot certify climbing. */
  normal_takeoff(&m, 9);
  assert(step(&m, 3.0, 1.35, 0, 0.02, 0, 0, 1) == WB_ALT_WAIT);
  assert(step(&m, 5.0, 1.35, 0, 0.02, 0, 0, 1) == WB_ALT_NOT_ACHIEVED);

  /* Candidate cannot pass the wall by sliding around the rail at low height. */
  normal_takeoff(&m, 10);
  assert(step(&m, 2.0, 0.60, 0.48, 0.46, 0, 0, 0) == WB_ALT_NOT_ACHIEVED);

  puts("PASS native altitude C oracle: crossing, landing, collision, reset, negatives");
  return 0;
}
"""


class NativeAltitudeContract(unittest.TestCase):
    def test_pure_c_logic_executes_all_positive_and_adversarial_cases(self):
        cc = shutil.which("cc")
        if not cc:
            self.fail("C compiler required for native altitude qualification")
        with tempfile.TemporaryDirectory(prefix="wb-altitude-core-") as tmp:
            source = Path(tmp) / "test.c"
            target = Path(tmp) / "test"
            source.write_text(DRIVER, encoding="utf-8")
            build = subprocess.run(
                [cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic",
                 "-I", str(CONTROLLER), str(source), "-lm", "-o", str(target)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                timeout=30,
            )
            self.assertEqual(build.returncode, 0, build.stdout)
            run = subprocess.run(
                [str(target)], text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=30
            )
            self.assertEqual(run.returncode, 0, run.stdout)
            self.assertIn("PASS native altitude C oracle", run.stdout)

    def test_isolated_native_executable_never_links_into_physical_runtime(self):
        mk = MAKEFILE.read_text(encoding="utf-8")
        src = SOURCE.read_text(encoding="utf-8")
        scene = SCENE.read_text(encoding="utf-8")
        self.assertIn("C_SOURCES = progression_altitude_v1.c", mk)
        self.assertNotIn("crazyflie_runtime_v2", mk)
        self.assertIn("wb_supervisor_node_get_contact_points", src)
        self.assertIn("wb_supervisor_node_enable_contact_points_tracking", src)
        self.assertIn("wb_alt_sample_mission", src)
        self.assertIn('controller "progression_altitude_v1"', scene)
        self.assertIn("supervisor TRUE", scene)
        self.assertEqual(scene.count(" Robot {"), 1)
        self.assertEqual(scene.count(" Solid {"), 3)
        self.assertNotIn("Py_Initialize", src)
        self.assertNotIn("python.exe", src)
        # Do not reject the explanatory comment "No ... Blockly inspection";
        # prohibit Blockly coupling in the compiled implementation itself.
        implementation = src.split("*/", 1)[-1]
        self.assertNotIn("Blockly", implementation)
        self.assertNotIn("wb_robot_set_mode", src)
        self.assertTrue(CORE.is_file())

    def test_scene_does_not_drift_from_native_constants(self):
        text = SCENE.read_text(encoding="utf-8")
        core = CORE.read_text(encoding="utf-8")
        for define, value in {
            "WB_ALT_TARGET_X": "1.35",
            "WB_ALT_BARRIER_X": "0.62",
            "WB_ALT_BARRIER_TOP": "0.62",
            "WB_ALT_CRAFT_CLEARANCE": "0.09",
        }.items():
            self.assertRegex(core, rf"#define {define} {re.escape(value)}(?:\n|$)")
        self.assertIn("Pose { translation 1.35 0 0.002", text)
        self.assertIn("DEF ACTIVITY2_LOW_BARRIER Solid", text)


if __name__ == "__main__":
    unittest.main()

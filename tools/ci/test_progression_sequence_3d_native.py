#!/usr/bin/env python3
"""Compile and falsify the real pure-C Activity 1 oracle, without Webots mocks."""
from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "controllers/progression_sequence_3d"
CORE = NATIVE / "sequence_core.h"
SCENE = ROOT / "worlds/scenes/sequence-v1.wbo"

DRIVER = r"""
#include "sequence_core.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>

static wb_seq_verdict step(wb_seq_mission *m, double time,
                           double x, double y, double z,
                           double vx, double vy, double vz, int completed) {
  wb_seq_sample s = {time, x, y, z, vx, vy, vz, completed};
  return wb_seq_sample_mission(m, &s);
}

static void airborne(wb_seq_mission *m, unsigned long long attempt) {
  wb_seq_reset(m, attempt, 0.0);
  assert(step(m, 1, 0, 0, 0.50, 0, 0, 0, 0) == WB_SEQ_WAIT);
  assert(m->airborne);
}
int main(void) {
  wb_seq_mission m;
  airborne(&m, 1);
  assert(step(&m, 2, .35, .28, .02, 0, 0, 0, 0) == WB_SEQ_WAIT);
  assert(step(&m, 3, .35, .28, .02, 0, 0, 0, 1) == WB_SEQ_ACHIEVED);
  assert(step(&m, 9, 5, 5, 5, 9, 9, 9, 0) == WB_SEQ_ACHIEVED);

  /* A new native attempt never inherits the previous victory. */
  wb_seq_reset(&m, 2, 0);
  assert(!m.airborne && !m.completion_seen && m.result == WB_SEQ_WAIT);
  assert(step(&m, 4, .35, .28, .02, 0, 0, 0, 1) == WB_SEQ_WAIT);
  assert(step(&m, 5.6, .35, .28, .02, 0, 0, 0, 0) == WB_SEQ_NOT_ACHIEVED);

  /* Old center-only logic accepted positions that overhang the pad. */
  for (unsigned int kind = 0; kind < 2; ++kind) {
    airborne(&m, (unsigned long long)kind + 3);
    const double x = kind ? .35 : .43;
    const double y = kind ? .38 : .28;
    assert(step(&m, 2, x, y, .02, 0, 0, 0, 1) == WB_SEQ_WAIT);
    assert(step(&m, 3.6, x, y, .02, 0, 0, 0, 0) == WB_SEQ_NOT_ACHIEVED);
  }

  /* Nonzero X and Y displacement well inside full-pad margins still pass. */
  airborne(&m, 5);
  assert(step(&m, 2, .39, .34, .02, 0, 0, 0, 1) == WB_SEQ_ACHIEVED);

  /* Moving after completion cannot pass. */
  airborne(&m, 6);
  assert(step(&m, 2, .35, .28, .02, .3, 0, 0, 1) == WB_SEQ_WAIT);
  assert(step(&m, 3.6, .35, .28, .02, .3, 0, 0, 0) == WB_SEQ_NOT_ACHIEVED);

  /* Never landed; terminal negative cannot turn into positive later. */
  airborne(&m, 7);
  assert(step(&m, 2, .35, .28, .4, 0, 0, 0, 1) == WB_SEQ_WAIT);
  assert(step(&m, 3.6, .35, .28, .4, 0, 0, 0, 0) == WB_SEQ_NOT_ACHIEVED);
  assert(step(&m, 4, .35, .28, .02, 0, 0, 0, 0) == WB_SEQ_NOT_ACHIEVED);

  /* An unknown postcompletion physical state is never a success. */
  airborne(&m, 8);
  assert(step(&m, 2, .35, .28, .4, 0, 0, 0, 1) == WB_SEQ_WAIT);
  wb_seq_sample bad = {3, NAN, .28, .02, 0, 0, 0, 0};
  assert(wb_seq_sample_mission(&m, &bad) == WB_SEQ_NOT_ACHIEVED);

  wb_seq_reset(&m, 9, 0);
  assert(wb_seq_sample_mission(&m, NULL) == WB_SEQ_WAIT);
  wb_seq_sample completed_bad = {2, NAN, .28, .02, 0, 0, 0, 1};
  assert(wb_seq_sample_mission(&m, &completed_bad) == WB_SEQ_NOT_ACHIEVED);
  assert(wb_seq_sample_mission(NULL, &bad) == WB_SEQ_NOT_ACHIEVED);

  puts("PASS pure C Activity 1: fresh flight, complete, footprint, negative, settle");
  return 0;
}
"""


class NativeSequence3D(unittest.TestCase):
    def test_compile_and_run_real_c_behavior(self):
        cc = shutil.which("cc")
        self.assertIsNotNone(cc, "a real C compiler is mandatory")
        with tempfile.TemporaryDirectory(prefix="wb-sequence-native-") as tmp:
            source = Path(tmp) / "test.c"
            binary = Path(tmp) / "test"
            source.write_text(DRIVER, encoding="utf8")
            compiled = subprocess.run(
                [cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic",
                 "-I", str(NATIVE), str(source), "-lm", "-o", str(binary)],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True,
                                    text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PASS pure C Activity 1", result.stdout)

    def test_native_supervisor_is_observer_only_and_build_cannot_switch_active_oracle(self):
        source = (NATIVE / "progression_sequence_3d.c").read_text(encoding="utf8")
        makefile = (NATIVE / "Makefile").read_text(encoding="utf8")
        runner = (ROOT / "tools/ci/run_progression_sequence_mission.py").read_text(
            encoding="utf8")
        self.assertIn('#include "sequence_core.h"', source)
        self.assertIn("wb_supervisor_node_get_position(craft)", source)
        self.assertIn("wb_supervisor_node_get_velocity(craft)", source)
        self.assertIn("wb_supervisor_field_set_sf_string(channel, result)", source)
        for forbidden in ("wb_motor_set_velocity", "wb_motor_set_position",
                          "wb_supervisor_node_set_velocity", "wb_supervisor_node_set_position",
                          "parse_ast", "controllerArgs", "crazyflie_runtime_v2.c"):
            self.assertNotIn(forbidden, source)
        self.assertIn("C_SOURCES = progression_sequence_3d.c", makefile)
        self.assertIn("mktemp -d /tmp/wb-a1-native-", runner)
        # Webots R2025a Makefile.include computes BUILD_TYPE from the parent
        # folder name. A random /tmp basename would build lib*.so instead of
        # the expected executable, even with all the right source files.
        self.assertIn('proof_root=$(mktemp -d /tmp/wb-a1-native-', runner)
        self.assertIn('proof_dir=\\"$proof_root/controllers/progression_sequence_3d\\"', runner)
        self.assertIn('mkdir -p \\"$proof_dir\\"', runner)
        self.assertNotIn('proof_dir=$(mktemp -d /tmp/wb-a1-native-', runner)
        self.assertIn("cp Makefile progression_sequence_3d.c sequence_core.h", runner)
        self.assertIn('make -C \\"$proof_dir\\"', runner)
        self.assertIn('test -s \\"$proof_dir/progression_sequence_3d\\"', runner)
        self.assertNotIn('"make clean && make && test -s progression_sequence_3d"', runner)
        self.assertIn("test_progression_sequence_3d_native.py", runner)

    def test_windows_release_builds_native_observer_without_python_dependency(self):
        builder = (ROOT / "tools/build_windows_classroom_release.ps1").read_text(
            encoding="utf8")
        validator = (ROOT / "tools/ci/test_windows_classroom_release.ps1").read_text(
            encoding="utf8")
        self.assertIn("$sequenceObserverDir = Join-Path $repoRoot", builder)
        self.assertIn("& $make -C $sequenceObserverDir clean", builder)
        self.assertIn("& $make -C $sequenceObserverDir", builder)
        self.assertIn("progression_sequence_3d.exe", builder)
        self.assertIn("Copy-RequiredFile $observerBinary", builder)
        self.assertNotIn("Copy-RequiredFile `\n  (Join-Path $repoRoot 'controllers\\progression_sequence_3d\\progression_sequence_3d.py')", builder)
        self.assertIn("controllers\\progression_sequence_3d\\progression_sequence_3d.exe", validator)
        self.assertIn("$observerBytes[0] -eq 0x4d", validator)
        self.assertIn("$observerBytes[1] -eq 0x5a", validator)
        self.assertIn("Cannot connect to Webots instance", validator)
        self.assertIn("Windows release still depends on an Activity 1 Python observer.", validator)

    def test_oracle_constants_match_real_pad_and_python_reference(self):
        header = CORE.read_text(encoding="utf8")
        scene = SCENE.read_text(encoding="utf8")
        python = (NATIVE / "progression_sequence_3d.py").read_text(encoding="utf8")
        self.assertIn("geometry Box { size 0.28 0.34 0.004 }", scene)
        self.assertIn("Pose { translation 0.35 0.28 0.002", scene)
        for name, expected in {
            "WB_SEQ_CHILDREN": "18",
            "WB_SEQ_X": "0.35", "WB_SEQ_Y": "0.28",
            "WB_SEQ_X_TOL": "0.05", "WB_SEQ_Y_TOL": "0.08",
            "WB_SEQ_AIRBORNE": "0.20", "WB_SEQ_LAND_HEIGHT": "0.07",
            "WB_SEQ_MAX_SPEED": "0.12", "WB_SEQ_SETTLE": "1.5"
        }.items():
            self.assertRegex(header, rf"(?m)^#define {re.escape(name)} {re.escape(expected)}$")
        self.assertIn('WB_SEQ_ORACLE "progression-sequence-3d-v1"', header)
        self.assertIn("TARGET_X_TOLERANCE = 0.05", python)
        self.assertIn("TARGET_Y_TOLERANCE = 0.08", python)
        self.assertAlmostEqual(0.05 + 0.09, 0.28 / 2)
        self.assertAlmostEqual(0.08 + 0.09, 0.34 / 2)


if __name__ == "__main__":
    unittest.main()

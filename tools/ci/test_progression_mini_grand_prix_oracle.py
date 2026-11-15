#!/usr/bin/env python3
"""Fail-closed compiled C contract for the A7 Mini Grand Prix Draft oracle.

This is *not* a Webots flight, classroom acceptance, or hardware authorization.
It verifies the actual C source (not a copied Python reimplementation).
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
ORACLE = ROOT / "controllers/progression_mini_grand_prix_v1/mini_core.h"
HARNESS = ROOT / "tools/ci/test_progression_mini_grand_prix_oracle.c"


class MiniGrandPrixCompiledOracle(unittest.TestCase):
    def test_native_c11_compiles_and_rejects_adversarial_routes(self):
        self.assertTrue(ORACLE.is_file(), "missing isolated A7 C oracle")
        source = ORACLE.read_text(encoding="utf-8")
        self.assertIn("#define WB_MINI_LAND_Z 0.070", source)
        self.assertIn("#define WB_MINI_LAND_ABSOLUTE_Z 0.020", source)
        self.assertIn("s->z-m->origin_z<=WB_MINI_LAND_Z", source)
        self.assertIn("s->z<=WB_MINI_LAND_ABSOLUTE_Z", source)
        self.assertTrue(HARNESS.is_file(), "missing A7 adversarial C harness")
        compiler = shutil.which("cc")
        self.assertIsNotNone(compiler, "C compiler mandatory for A7 proof")
        with tempfile.TemporaryDirectory(prefix="a7-oracle-") as tmp:
            binary = Path(tmp) / "mini-grand-prix-oracle"
            compile_command = [
                compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-pedantic", "-O1", "-I", str(ORACLE.parent),
                str(HARNESS), "-lm", "-o", str(binary),
            ]
            built = subprocess.run(compile_command, capture_output=True,
                                   text=True, timeout=30, check=False)
            self.assertEqual(built.returncode, 0,
                             "A7 C compilation failed:\n" + built.stdout + built.stderr)
            self.assertTrue(binary.is_file(), "compiler produced no executable")
            executed = subprocess.run([str(binary)], capture_output=True,
                                      text=True, timeout=15, check=False)
            self.assertEqual(executed.returncode, 0,
                             "A7 adversarial assertions failed:\n" +
                             executed.stdout + executed.stderr)
            self.assertEqual(executed.stdout.strip(),
                             "PASS A7 isolated C oracle: fifty-one positive/adversarial scenarios")
            self.assertEqual(executed.stderr.strip(), "")


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Compile actual A5 v2 C code. Synthetic observations are NOT flown Webots."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "controllers/progression_reactive_L_v2/reactive_core_v2.h"
TEST = ROOT / "tools/ci/test_progression_reactive_L_v2_oracle.c"

class Activity5V2NativeCOracle(unittest.TestCase):
    def test_falsification_exercises_actual_strict_c11(self):
        self.assertTrue(CORE.is_file())
        self.assertTrue(TEST.is_file())
        compiler = shutil.which("cc")
        self.assertIsNotNone(compiler, "a real C compiler is required")
        with tempfile.TemporaryDirectory(prefix="a5-v2-oracle-") as tmp:
            binary = str(Path(tmp) / "oracle")
            command = [
                compiler, "-std=c11", "-O1", "-Wall", "-Wextra",
                "-Werror", "-pedantic", "-I", str(CORE.parent),
                str(TEST), "-lm", "-o", binary,
            ]
            compiled = subprocess.run(command, capture_output=True,
                                      text=True, timeout=30, check=False)
            self.assertEqual(compiled.returncode, 0,
                             "C compilation failed:\n"+compiled.stdout+compiled.stderr)
            executed = subprocess.run([binary],capture_output=True,
                                      text=True, timeout=30,check=False)
            self.assertEqual(executed.returncode,0,
                             "A5 v2 C oracle refuted:\n"+executed.stdout+executed.stderr)
            self.assertEqual(executed.stdout.strip(),
                             "PASS A5 V2 C oracle: 55 positive/adversarial cases")
            self.assertEqual(executed.stderr.strip(), "")

if __name__=="__main__":
    unittest.main()

#!/usr/bin/env python3
"""Fail closed if the one-run #637 step experiment contaminates other proofs."""
import os
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.ci import run_runtime_v2_outcome_probe as probe


class NativeSequenceStepTimingExperiment(unittest.TestCase):
    def test_only_sequence_collision_receives_real_step_probe(self):
        observed = []
        proofs = (probe.FRESHNESS, probe.PROGRESSION[0], probe.PROGRESSION[1])

        def fake_run(argv, **kwargs):
            observed.append((argv[1], dict(kwargs["env"])))
            return SimpleNamespace(returncode=0)

        # Even if a parent exports the probe switch, the wrapper must confine
        # it to the exact sequence proof, not the freshness or other missions.
        with patch.object(probe, "proofs_for_job", return_value=proofs), \
             patch.object(probe.subprocess, "run", side_effect=fake_run), \
             patch.object(sys, "argv", ["run_runtime_v2_outcome_probe.py"]), \
             patch.dict(os.environ, {"WEBEEBLOCKS_SEQUENCE_CI_STEP_TIMING": "invalid"}):
            self.assertEqual(probe.main(), 0)

        self.assertEqual([row[0] for row in observed], list(proofs))
        for path, env in observed:
            if path == probe.PROGRESSION[0]:
                self.assertEqual(env["WEBEEBLOCKS_SEQUENCE_CI_STEP_TIMING"], "1")
            else:
                self.assertNotIn("WEBEEBLOCKS_SEQUENCE_CI_STEP_TIMING", env)

    def test_shard_zero_owns_the_original_collision_proof(self):
        self.assertEqual(probe.PROGRESSION[0], "tools/ci/run_progression_sequence_mission.py")
        self.assertIn(probe.PROGRESSION[0], probe.proofs_for_shard(0))
        for shard in range(1, len(probe.SHARD_INDICES)):
            self.assertNotIn(probe.PROGRESSION[0], probe.proofs_for_shard(shard))


if __name__ == "__main__":
    unittest.main()

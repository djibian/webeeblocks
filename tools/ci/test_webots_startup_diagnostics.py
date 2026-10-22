#!/usr/bin/env python3
"""Adversarial host-only checks of failure evidence, signal status and cleanup."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.ci.webots_startup_diagnostics import StartupEvidence


class StartupEvidenceTests(unittest.TestCase):
    def test_group_exit_status_sequence_and_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            command = [sys.executable, "-c", "import time; time.sleep(5)"]
            diagnostic = StartupEvidence(out, 4, command, dict(os.environ))
            child = subprocess.Popen(command, start_new_session=True)
            try:
                diagnostic.observe(child, force=True)
                self.assertTrue(any(p["pid"] == child.pid for p in
                                    diagnostic.samples[-1]["processes"]))
                os.killpg(child.pid, signal.SIGTERM)
                self.assertEqual(child.wait(timeout=5), -signal.SIGTERM)
                log = out / "webots.log"
                log.write_text("webots: line 105: 259 Segmentation fault (core dumped)\n")
                diagnostic.failure(child, out / "fake-home", log)
                diagnostic.after_cleanup(child.pid)
                evidence = json.loads((out / "startup-failure.json").read_text())
                self.assertEqual(evidence["status"], "NATIVE_READY_MISSING")
                self.assertEqual(evidence["wrapper_pid"], child.pid)
                self.assertEqual(evidence["wrapper_returncode"], -signal.SIGTERM)
                self.assertEqual(evidence["wrapper_signal"], signal.SIGTERM)
                self.assertEqual(evidence["sequence_index"], 4)
                self.assertEqual(evidence["prior_trials_validated"], 3)
                self.assertEqual(evidence["core"]["native_sigsegv_pids_in_log"], [259])
                self.assertFalse(evidence["core"]["raw_core_retained"])
                self.assertIn("cgroup_v2", evidence["resources_on_failure"])
                self.assertIn("meminfo", evidence["resources_before"])
                self.assertEqual(evidence["process_group_after_cleanup"], [])
            finally:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=5)

    def test_nonfailure_has_no_diagnostic_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            diagnostic = StartupEvidence(out, 1, ["fake"], dict(os.environ))
            self.assertFalse(diagnostic.failed)
            from types import SimpleNamespace
            diagnostic.ready(SimpleNamespace(pid=os.getpid(), poll=lambda: None),
                             "RUNTIME_READY")
            summary = json.loads((out / "startup-ready.json").read_text())
            self.assertEqual(summary["status"], "RUNTIME_READY")
            self.assertEqual(summary["sequence_index"], 1)
            self.assertIn("resources_at_readiness", summary)
            diagnostic.after_cleanup(os.getpid())
            self.assertFalse((out / "startup-failure.json").exists())
            self.assertFalse((out / "startup-backtrace.txt").exists())


if __name__ == "__main__":
    unittest.main()

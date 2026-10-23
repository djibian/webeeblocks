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
from tools.ci.webots_startup_diagnostics import StartupEvidence, census_difference, cgroup_census


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
                self.assertIn("cgroup_before", evidence)
                self.assertIn("cgroup_after_cleanup", evidence)
                self.assertIn("cgroup_delta", evidence)
            finally:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=5)

    def test_wrapper_exit_139_is_not_mistaken_for_a_python_signal(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            diagnostic = StartupEvidence(out, 16, ["xvfb-run", "webots"], dict(os.environ))
            (out / "webots.log").write_text(
                "webots: line 105: 812 Segmentation fault (core dumped)\n")
            diagnostic.failure(
                SimpleNamespace(pid=99999999, poll=lambda: 139),
                out / "fake-home", out / "webots.log")
            evidence = json.loads((out / "startup-failure.json").read_text())
            self.assertEqual(evidence["wrapper_returncode"], 139)
            self.assertIsNone(evidence["wrapper_signal"])
            self.assertEqual(evidence["sequence_index"], 16)
            self.assertEqual(evidence["core"]["native_sigsegv_pids_in_log"], [812])

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
            summary = json.loads((out / "startup-ready.json").read_text())
            self.assertIn("cgroup_before", summary)
            self.assertIn("cgroup_after_cleanup", summary)
            self.assertIn("cgroup_delta", summary)
            self.assertFalse((out / "startup-failure.json").exists())
            self.assertFalse((out / "startup-backtrace.txt").exists())

    def test_cgroup_comparison_refuses_partial_and_pid_reuse(self):
        def row(ticks):
            return {"pid": 101, "start_ticks": ticks, "pid_ns": "pid:[123]",
                    "ppid": 1, "pgid": 101, "sid": 101, "state": "S", "comm": "webots"}
        before = {"status": "complete", "scope": "/", "processes": [row(10)]}
        after = {"status": "complete", "scope": "/", "processes": [row(11)]}
        change = census_difference(before, after)
        self.assertEqual(change["status"], "comparable_not_causal")
        self.assertEqual(change["new_since_prelaunch"], [row(11)])
        self.assertEqual(change["gone_since_prelaunch"], [row(10)])
        after["status"] = "partial"
        self.assertEqual(census_difference(before, after)["status"], "unproven")
        after["status"] = "complete"
        after["scope"] = "/other"
        self.assertEqual(census_difference(before, after)["status"], "unproven")

    def test_live_cgroup_snapshot_has_bounded_non_secret_process_identity(self):
        census = cgroup_census(max_rows=256)
        self.assertIn(census["status"], ("complete", "partial", "unavailable"))
        if census["status"] == "unavailable":
            self.assertIn("reason", census)
            return
        self.assertGreaterEqual(census["visible_members"], len(census["processes"]))
        self.assertLessEqual(len(census["processes"]), 256)
        for task in census["processes"]:
            self.assertIn("start_ticks", task)
            self.assertIn("pid_ns", task)
            self.assertNotIn("cmdline", task)
            self.assertNotIn("environ", task)


if __name__ == "__main__":
    unittest.main()

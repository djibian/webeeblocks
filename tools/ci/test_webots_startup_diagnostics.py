#!/usr/bin/env python3
"""Adversarial host-only checks of failure evidence, signal status and cleanup."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.ci.webots_startup_diagnostics import StartupEvidence, cgroup_processes


class StartupEvidenceTests(unittest.TestCase):
    def test_native_docker_has_reaping_init_without_changing_oracles(self):
        # Host-side guard on the actual Docker invocation, not a replacement
        # for native cleanup evidence after each successful trial.
        source = (Path(__file__).parent / "run_grand_prix_u_prototype.py").read_text()
        self.assertIn("['docker','run','--rm','--init','--cidfile'", source)
        self.assertIn("timeout -k 5s 1400s python3 -u tools/ci/run_grand_prix_u_prototype.py --native", source)
        self.assertIn("if args.suite=='all':cases=", source)
        self.assertIn("if cid.exists():", source)

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
                self.assertIn("cgroup_on_failure", evidence)
                self.assertIn("cgroup_after_cleanup", evidence)
            finally:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=5)

    def test_same_cgroup_identity_is_bounded_and_has_pid_birth_ticks(self):
        snapshot = cgroup_processes()
        self.assertIn(snapshot["status"], ("ok", "partial", "unavailable"))
        self.assertLessEqual(len(snapshot["processes"]), 256)
        if snapshot["status"] == "unavailable":
            self.skipTest("current /proc cgroup membership unavailable")
        self.assertFalse(snapshot["truncated"] and
                         snapshot["matching_visible"] <= 256)
        for entry in snapshot["processes"]:
            self.assertGreater(entry["pid"], 0)
            self.assertGreater(entry["start_ticks"], 0)
            self.assertEqual(len(entry["state"]), 1)
            self.assertNotIn("cmdline", entry)
        if not snapshot["truncated"]:
            self.assertIn(os.getpid(), {entry["pid"] for entry in snapshot["processes"]})

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
            self.assertFalse((out / "startup-failure.json").exists())
            self.assertFalse((out / "startup-backtrace.txt").exists())
            cleanup = json.loads((out / "startup-cleanup.json").read_text())
            self.assertEqual(cleanup["sequence_index"], 1)
            self.assertIn("cgroup_after_cleanup", cleanup)


    def test_cgroup_task_census_includes_threads_without_new_process(self):
        before = cgroup_processes()
        if before["status"] == "unavailable":
            self.skipTest("unified cgroup /proc unavailable")
        pid = os.getpid()
        known = {r["tid"] for r in before["tasks"] if r["pid"] == pid}
        barrier = threading.Barrier(4)
        done = threading.Event()

        def worker():
            barrier.wait(timeout=5)
            done.wait(timeout=5)

        workers = [threading.Thread(target=worker) for _ in range(3)]
        for thread in workers:
            thread.start()
        try:
            barrier.wait(timeout=5)
            during = cgroup_processes()
            if during["status"] == "unavailable":
                self.skipTest("cgroup became unavailable")
            new = {r["tid"] for r in during["tasks"] if r["pid"] == pid}
            self.assertGreaterEqual(len(new - known), 3)
            self.assertEqual(
                {r["pid"] for r in during["processes"] if r["pid"] == pid},
                {pid})
            self.assertIn("descendant cgroups", during["scope_limitation"])
        finally:
            done.set()
            for thread in workers:
                thread.join(timeout=5)
                self.assertFalse(thread.is_alive())

    def test_truncated_cgroup_census_must_be_partial(self):
        snap = cgroup_processes(limit=0, task_limit=0)
        if snap["status"] == "unavailable":
            self.skipTest("cgroup unavailable")
        self.assertEqual(snap["status"], "partial")
        self.assertTrue(snap["truncated"])
        self.assertTrue(snap["task_truncated"])
        self.assertEqual(snap["processes"], [])
        self.assertEqual(snap["tasks"], [])
        self.assertGreater(snap["matching_visible_tasks"], 0)



    def test_threaded_cgroup_can_include_tid_with_external_leader(self):
        # /A owns PID 100; /B owns TID 101. This must not be silently
        # discarded by filtering the process leader before the task scan.
        import tools.ci.webots_startup_diagnostics as diagnostics
        def stat(pid, comm, start):
            return "%d (%s) " % (pid, comm) + " ".join(
                ["S", "1", "100", "100"] + ["0"] * 15 + [str(start)])
        def fake_read(path, maximum=8192):
            evidence = {
                "/proc/self/cgroup": "0::/B\\n",
                "/proc/100/cgroup": "0::/A\\n",
                "/proc/100/stat": stat(100, "leader", 1000),
                "/proc/100/task/101/cgroup": "0::/B\\n",
                "/proc/100/task/101/stat": stat(101, "thread", 1001),
            }
            return evidence.get(path, "UNAVAILABLE: test")
        def fake_listdir(path):
            return {"/proc": ["100"], "/proc/100/task": ["101"]}[path]
        with (patch.object(diagnostics, "read", side_effect=fake_read),
              patch.object(diagnostics.os, "listdir", side_effect=fake_listdir),
              patch.object(diagnostics.os, "readlink", return_value="pid:[100]")):
            snapshot = cgroup_processes()
        self.assertEqual(snapshot["status"], "ok")
        self.assertEqual(snapshot["matching_visible"], 0)
        self.assertEqual(snapshot["matching_visible_tasks"], 1)
        self.assertEqual(snapshot["processes"], [])
        self.assertEqual([(row["pid"], row["tid"]) for row in snapshot["tasks"]],
                         [(100, 101)])

    def test_more_than_256_process_leaders_are_partial_not_ok(self):
        import tools.ci.webots_startup_diagnostics as diagnostics
        pids = range(100, 358)
        def fake_read(path, maximum=8192):
            if path.endswith("/cgroup"):
                return "0::/B\\n"
            if path.endswith("/stat"):
                pid = int(path.split("/")[2])
                return "%d (worker) " % pid + " ".join(
                    ["S", "1", str(pid), str(pid)] + ["0"] * 15 + [str(1000 + pid)])
            return "UNAVAILABLE: test"
        def fake_listdir(path):
            if path == "/proc":
                return [str(pid) for pid in pids]
            if path.startswith("/proc/") and path.endswith("/task"):
                return [path.split("/")[2]]
            raise OSError("unexpected")
        with (patch.object(diagnostics, "read", side_effect=fake_read),
              patch.object(diagnostics.os, "listdir", side_effect=fake_listdir),
              patch.object(diagnostics.os, "readlink", return_value="pid:[100]")):
            snapshot = cgroup_processes()
        self.assertEqual(snapshot["status"], "partial")
        self.assertEqual(snapshot["matching_visible"], 258)
        self.assertEqual(len(snapshot["processes"]), 256)
        self.assertTrue(snapshot["truncated"])
        self.assertEqual(snapshot["matching_visible_tasks"], 258)


if __name__ == "__main__":
    unittest.main()

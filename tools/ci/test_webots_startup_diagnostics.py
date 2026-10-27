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
from tools.ci.grand_prix_u_log_capture import NativeLogCapture, require_no_terminal_crash


class NativeWebotsLogCaptureTests(unittest.TestCase):
    def test_dead_leader_late_descendant_crash_is_captured_and_refused(self):
        # Reproduce #708 deterministically: wrapper exits, descendant retains
        # stdout until the test releases it. A leader wait never proves EOF.
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'webots.log'
            gate = Path(directory) / 'release'
            child_code = (
                "from pathlib import Path\nimport time\n"
                "while not Path(" + repr(str(gate)) + ").is_file():\n"
                "    time.sleep(0.01)\n"
                "print('Segmentation fault PID458', flush=True)\n"
            )
            parent_code = (
                "import subprocess,sys;subprocess.Popen([sys.executable,'-c',"
                + repr(child_code) + "]);print('READY', flush=True)"
            )
            with NativeLogCapture(target) as capture:
                leader = subprocess.Popen([sys.executable, '-c', parent_code],
                                          stdout=capture, stderr=subprocess.STDOUT,
                                          start_new_session=True)
                self.assertEqual(leader.wait(timeout=2), 0)
            try:
                with self.assertRaisesRegex(RuntimeError, 'refuse seal'):
                    capture.finish(timeout=0.05)
            finally:
                gate.touch()  # Release the actual descendant even if assertion fails.
            capture.finish(timeout=3)
            self.assertEqual(target.read_text().splitlines(),
                             ['READY', 'Segmentation fault PID458'])
            with self.assertRaisesRegex(RuntimeError, 'native crash'):
                require_no_terminal_crash(target)

    def test_parent_pipe_open_cannot_be_sealed(self):
        with tempfile.TemporaryDirectory() as directory:
            with NativeLogCapture(Path(directory) / 'webots.log') as capture:
                with self.assertRaisesRegex(RuntimeError, 'refuse seal'):
                    capture.finish(timeout=0.01)
            capture.finish(timeout=2)

    def test_clean_stdout_finishes_without_native_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'webots.log'
            with NativeLogCapture(target) as capture:
                leader = subprocess.Popen([sys.executable, '-c',
                                           "print('READY', flush=True)"],
                                          stdout=capture, stderr=subprocess.STDOUT,
                                          start_new_session=True)
                self.assertEqual(leader.wait(timeout=2), 0)
            capture.finish(timeout=2)
            require_no_terminal_crash(target)
            self.assertEqual(target.read_text(), 'READY\n')


class NativeTrialTeardownTests(unittest.TestCase):
    """Host-only counterexamples: a failure cannot bypass later cleanup or seal."""

    @staticmethod
    def fixture(directory):
        from unittest.mock import Mock
        root = Path(directory)
        out = root/'capture'
        out.mkdir()
        (out/'webots.log').write_text('READY\\n'.replace('\\n', '\n'))
        target = root/'ci_gp_u_flight_sample.wbt'
        target.write_text('synthetic world')
        target.with_name('.' + target.stem + '.wbproj').write_text('synthetic project')
        children = [Mock(pid=4242)]
        log = Mock()
        startup = Mock()
        streams = [Mock(), Mock()]
        runtime = Mock()
        return out, target, children, log, startup, streams, runtime

    def test_successful_retirement_seals_only_after_every_cleanup(self):
        import hashlib
        from tools.ci.run_grand_prix_u_prototype import retire_trial
        with tempfile.TemporaryDirectory() as directory:
            out, target, children, log, startup, streams, runtime = self.fixture(directory)
            with patch('tools.ci.run_grand_prix_u_prototype.stop_groups') as stop:
                retire_trial(children, log, startup, streams, runtime, out, target)
                stop.assert_called_once_with(children)
            log.finish.assert_called_once_with()
            startup.after_cleanup.assert_called_once_with(4242)
            for stream in streams:
                stream.close.assert_called_once_with()
            runtime.cleanup.assert_called_once_with()
            self.assertFalse(target.exists())
            self.assertFalse(target.with_name('.' + target.stem + '.wbproj').exists())
            manifest = json.loads((out/'sha256.json').read_text())
            self.assertEqual(manifest['webots.log'],
                             hashlib.sha256((out/'webots.log').read_bytes()).hexdigest())
            self.assertEqual(list(manifest), ['webots.log'])
            self.assertFalse((out/'teardown-failures.json').exists())

    def test_stdout_eof_timeout_does_not_skip_diagnostics_or_runtime_cleanup(self):
        from tools.ci.run_grand_prix_u_prototype import retire_trial
        with tempfile.TemporaryDirectory() as directory:
            out, target, children, log, startup, streams, runtime = self.fixture(directory)
            log.finish.side_effect = RuntimeError('pipe held by surviving descendant')
            with patch('tools.ci.run_grand_prix_u_prototype.stop_groups') as stop:
                with self.assertRaisesRegex(RuntimeError, 'native_stdout_eof'):
                    retire_trial(children, log, startup, streams, runtime, out, target)
            stop.assert_called_once_with(children)
            startup.after_cleanup.assert_called_once_with(4242)
            for stream in streams:
                stream.close.assert_called_once_with()
            runtime.cleanup.assert_called_once_with()
            self.assertFalse(target.exists())
            self.assertFalse((out/'sha256.json').exists())
            failures = json.loads((out/'teardown-failures.json').read_text())
            self.assertEqual([item['stage'] for item in failures], ['native_stdout_eof'])

    def test_multiple_cleanup_faults_all_recorded_and_no_seal(self):
        from tools.ci.run_grand_prix_u_prototype import retire_trial
        with tempfile.TemporaryDirectory() as directory:
            out, target, children, log, startup, streams, runtime = self.fixture(directory)
            log.finish.side_effect = RuntimeError('no pipe EOF')
            startup.after_cleanup.side_effect = OSError('diagnostic unavailable')
            streams[0].close.side_effect = OSError('stream 0 failed')
            runtime.cleanup.side_effect = OSError('runtime teardown failed')
            with patch('tools.ci.run_grand_prix_u_prototype.stop_groups',
                       side_effect=PermissionError('signal denied')) as stop:
                with self.assertRaisesRegex(RuntimeError, 'stop_groups'):
                    retire_trial(children, log, startup, streams, runtime, out, target)
            stop.assert_called_once_with(children)
            streams[1].close.assert_called_once_with()
            runtime.cleanup.assert_called_once_with()
            self.assertFalse(target.exists())
            self.assertFalse((out/'sha256.json').exists())
            failures = json.loads((out/'teardown-failures.json').read_text())
            self.assertEqual([item['stage'] for item in failures],
                             ['stop_groups', 'native_stdout_eof',
                              'startup_after_cleanup', 'close_stream_0',
                              'runtime_state_cleanup'])

    def test_native_failure_remains_primary_even_if_log_retirement_fails(self):
        from tools.ci.run_grand_prix_u_prototype import retire_trial
        with tempfile.TemporaryDirectory() as directory:
            out, target, children, log, startup, streams, runtime = self.fixture(directory)
            log.finish.side_effect = RuntimeError('pipe held')
            with patch('tools.ci.run_grand_prix_u_prototype.stop_groups'):
                with self.assertRaisesRegex(ValueError, 'native result refuted'):
                    try:
                        raise ValueError('native result refuted')
                    finally:
                        retire_trial(children, log, startup, streams, runtime, out, target)
            startup.after_cleanup.assert_called_once_with(4242)
            runtime.cleanup.assert_called_once_with()
            self.assertFalse(target.exists())
            self.assertFalse((out/'sha256.json').exists())
            self.assertEqual(json.loads((out/'teardown-failures.json').read_text())[0]['stage'],
                             'native_stdout_eof')

    def test_late_crash_is_refused_without_skipping_any_teardown(self):
        from tools.ci.run_grand_prix_u_prototype import retire_trial
        with tempfile.TemporaryDirectory() as directory:
            out, target, children, log, startup, streams, runtime = self.fixture(directory)
            (out/'webots.log').write_text('READY\\nSegmentation fault\\n'.replace('\\n', '\n'))
            with patch('tools.ci.run_grand_prix_u_prototype.stop_groups'):
                with self.assertRaisesRegex(RuntimeError, 'native_terminal_crash'):
                    retire_trial(children, log, startup, streams, runtime, out, target)
            startup.after_cleanup.assert_called_once_with(4242)
            for stream in streams:
                stream.close.assert_called_once_with()
            runtime.cleanup.assert_called_once_with()
            self.assertFalse(target.exists())
            self.assertFalse((out/'sha256.json').exists())
            self.assertEqual(json.loads((out/'teardown-failures.json').read_text())[0]['stage'],
                             'native_terminal_crash')


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


    def test_native_container_uses_pid1_reaper_without_changing_evidence_command(self):
        from tools.ci.run_grand_prix_u_prototype import native_container_command
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            argv = native_container_command(root / "cid", root / "assets", root / "node",
                                            "echo native evidence")
            self.assertEqual(argv[:4], ["docker", "run", "--rm", "--init"])
            self.assertEqual(argv.count("--init"), 1)
            self.assertEqual(argv[argv.index("--cidfile") + 1], str(root / "cid"))
            self.assertEqual(argv[argv.index("--entrypoint") + 1], "/bin/bash")
            self.assertEqual(argv[-2:], ["-c", "echo native evidence"])
            self.assertIn(f'{root / "assets" / "projects"}:/usr/local/webots/projects:ro', argv)
            self.assertIn("-e", argv)
            self.assertIn("WEBOTS_HOME=/usr/local/webots", argv)
            core_options = ["--ulimit", "core=1024", "-v", "/tmp/gp-u-core-test:/tmp/gp-u-core-test"]
            with_core = native_container_command(root / "cid", root / "assets", root / "node",
                                                 "echo native evidence", core_options)
            self.assertEqual(with_core[4:8], core_options)
            self.assertEqual(with_core.count("--init"), 1)
            self.assertEqual(with_core[-2:], argv[-2:])


if __name__ == "__main__":
    unittest.main()

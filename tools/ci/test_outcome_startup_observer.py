#!/usr/bin/env python3
"""Adversarial scope tests for non-authoritative native startup snapshots."""
import json
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.ci import observe_outcome_startup as obs


class OutcomeStartupMonitorTests(unittest.TestCase):
    def test_stat_with_spaces_and_parenthesis(self):
        stat = "11 (name with ) spaces) S 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 44 21"
        self.assertEqual(obs.parse_stat(stat)["ppid"], 2)
        self.assertEqual(obs.parse_stat(stat)["start_ticks"], 44)
        self.assertIsNone(obs.parse_stat("incomplete"))

    def test_truncated_linux_comm_does_not_hide_native_controllers(self):
        # Linux /proc/PID/comm is truncated to TASK_COMM_LEN - 1 (15 bytes).
        self.assertIn("crazyflie_runtime_v2"[:15], obs.VISIBLE)
        self.assertIn("runtime_v2_outcome_probe"[:15], obs.VISIBLE)

    def test_exact_cgroup_and_no_commandline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc, cg = root / "proc", root / "cg"
            (proc / "self").mkdir(parents=True)
            cg.mkdir()
            (proc / "self/cgroup").write_text("0::/witness\n")
            (cg / "pids.current").write_text("8\n")
            fake_stat = "5 (webots-bin) S 1 " + " ".join(["0"] * 17) + " 77 0"
            for pid, membership, comm in (
                (5, "0::/witness\n", "webots-bin"),
                (6, "0::/other\n", "webots-bin"),
                (7, "0::/witness\n", "python3"),
            ):
                directory = proc / str(pid)
                directory.mkdir()
                (directory / "comm").write_text(comm + "\n")
                (directory / "cgroup").write_text(membership)
                (directory / "stat").write_text(fake_stat)
                (directory / "cmdline").write_text("private-token")
            data = obs.snapshot(proc, cg)
            self.assertEqual([p["pid"] for p in data["processes"]], [5, 7])
            self.assertEqual(data["processes"][1]["classification"], "python-unattributed")
            self.assertNotIn("private-token", json.dumps(data))
            self.assertEqual(data["resources"]["pids.current"], "8\n")
            self.assertEqual(data["status"], "partial")  # other cgroup metrics absent

    def test_python_census_is_complete_but_script_attribution_is_not_claimed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc, cg = root / "proc", root / "cg"
            (proc / "self").mkdir(parents=True)
            cg.mkdir()
            (proc / "self/cgroup").write_text("0::/witness\n")
            for name in obs.RESOURCE_FILES:
                (cg / name).write_text("0\n")
            for pid, comm in enumerate(sorted(obs.PYTHON_COMMS), 10):
                directory = proc / str(pid)
                directory.mkdir()
                (directory / "comm").write_text(comm + "\n")
                (directory / "cgroup").write_text("0::/witness\n")
                (directory / "stat").write_text(
                    f"{pid} ({comm}) S 1 " + " ".join(["0"] * 17) + " 77 0")
                (directory / "cmdline").write_text("private-script-and-token")
                (directory / "environ").write_text("PRIVATE=secret")
            with patch.object(obs, "read_limited", wraps=obs.read_limited) as read:
                data = obs.snapshot(proc, cg)
            self.assertEqual(data["status"], "ok")
            self.assertEqual(len(data["processes"]), len(obs.PYTHON_COMMS))
            self.assertTrue(all(p["classification"] == "python-unattributed"
                                for p in data["processes"]))
            self.assertEqual(data["observer_pid"], obs.os.getpid())
            self.assertFalse({"cmdline", "environ"} &
                             {call.args[0].name for call in read.call_args_list})
            self.assertNotIn("private-script", json.dumps(data))
            self.assertNotIn("secret", json.dumps(data))

    def test_executing_interpreter_comm_is_visible(self):
        comm = obs.read_limited(Path("/proc/self/comm"), 128)
        if comm is None:
            self.skipTest("current interpreter comm unavailable")
        self.assertIn(comm.strip(), obs.PYTHON_COMMS)

    def test_missing_proc_membership_is_partial_not_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.mkdir(exist_ok=True)
            data = obs.snapshot(root, root)
            self.assertEqual(data["status"], "partial")
            self.assertFalse(data["membership_observed"])

    def test_capture_validator_accepts_real_flushed_samples_including_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.jsonl"
            record = {
                "status": "partial", "membership_observed": True,
                "observer_pid": 77, "processes": [], "scan_errors": 0,
                "resources": {name: None for name in obs.RESOURCE_FILES},
            }
            with patch.object(obs, "snapshot", return_value=record), \
                 patch.object(obs.os, "getpid", return_value=77), \
                 patch.object(obs.time, "sleep"):
                obs.observe(path, 0.5, 2)
            self.assertEqual(obs.validate_capture(path), 2)

    def test_missing_empty_malformed_and_forged_observer_samples_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.jsonl"
            with self.assertRaisesRegex(ValueError, "unavailable"):
                obs.validate_capture(path)
            path.write_text("")
            with self.assertRaisesRegex(ValueError, "missing or unbounded"):
                obs.validate_capture(path)
            path.write_text("{broken\n")
            with self.assertRaisesRegex(ValueError, "malformed"):
                obs.validate_capture(path)
            valid = {
                "sample": 0, "elapsed_s": 0.001, "observer_pid": 77,
                "status": "partial", "membership_observed": True,
                "scan_errors": 0, "processes": [],
                "resources": {name: None for name in obs.RESOURCE_FILES},
            }
            for patch_fields in (
                {"sample": 1}, {"observer_pid": None}, {"elapsed_s": -1},
                {"resources": {}}, {"status": "healthy"},
            ):
                with self.subTest(patch_fields=patch_fields):
                    path.write_text(json.dumps({**valid, **patch_fields}) + "\n")
                    with self.assertRaises(ValueError):
                        obs.validate_capture(path)
            path.write_text(json.dumps(valid) + "\n" + "{truncated\n")
            with self.assertRaisesRegex(ValueError, "malformed"):
                obs.validate_capture(path)

    def test_observer_immediate_startup_failure_is_not_a_valid_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            # A nonexistent parent directory forces the actual CLI to fail
            # before its first sample, as a detached background process might.
            target = Path(tmp) / "missing-directory" / "capture.jsonl"
            proc = subprocess.run(
                [sys.executable, str(Path(obs.__file__).resolve()),
                 "--output", str(target), "--max-samples", "1"],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            with self.assertRaisesRegex(ValueError, "unavailable"):
                obs.validate_capture(target)

    def test_bounded_observer_flushes_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "samples.jsonl"
            with patch.object(obs, "snapshot", return_value={"status": "ok", "processes": []}), \
                 patch.object(obs.time, "sleep") as sleep:
                obs.observe(out, 0.5, 3)
            lines = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual([v["sample"] for v in lines], [0, 1, 2])
            self.assertEqual(sleep.call_count, 2)
            with self.assertRaises(FileExistsError):
                obs.observe(out, 0.5, 1)


if __name__ == "__main__":
    unittest.main()

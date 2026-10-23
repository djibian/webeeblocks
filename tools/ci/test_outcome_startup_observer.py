#!/usr/bin/env python3
"""Adversarial scope tests for non-authoritative native startup snapshots."""
import json
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
            self.assertEqual([p["pid"] for p in data["processes"]], [5])
            self.assertNotIn("private-token", json.dumps(data))
            self.assertEqual(data["resources"]["pids.current"], "8\n")
            self.assertEqual(data["status"], "partial")  # other cgroup metrics absent

    def test_missing_proc_membership_is_partial_not_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.mkdir(exist_ok=True)
            data = obs.snapshot(root, root)
            self.assertEqual(data["status"], "partial")
            self.assertFalse(data["membership_observed"])

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

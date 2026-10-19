"""Adversarial checks for observation-only RESET forensics."""
import json
import math
from pathlib import Path
import tempfile
import unittest

from reset_native_summary import HEADER, summarize


def s(t, attempt, pos, vel=None, contacts=None):
    return {"type": "sample", "time": t,
            "custom_data": "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 " + str(attempt),
            "position": pos,
            "orientation": [1, 0, 0, 0, 1, 0, 0, 0, 1],
            "velocity": vel or [0] * 6, "contacts": contacts or []}


class SummaryTests(unittest.TestCase):
    def report(self, entries):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "native-reset-state.jsonl"
            path.write_text("\n".join(json.dumps(x) for x in [HEADER, *entries]) + "\n")
            return summarize(path)

    def test_success_teleport_cannot_be_mistaken_for_ack(self):
        contact = [{"point": [.75, -2.22, .5], "node_id": 42}]
        data = self.report([s(10., 7, [.753, -2.218, .499], [0, 0, -.3, 0, 0, 1], contact),
                            s(10.032, 7, [0, 0, .015]),
                            s(10.064, 8, [0, 0, .015])])
        a = data["attempts"]["7"]
        self.assertEqual(a["samples"], 2)
        self.assertEqual(a["first_contact"]["time"], 10.)
        self.assertAlmostEqual(a["largest_observed_xyz_jump"]["distance_m"],
                               math.dist([.753, -2.218, .499], [0, 0, .015]))
        self.assertEqual(data["attempts"]["8"]["first_time"], 10.064)
        self.assertIn("not RESET request/ACK", data["scope"])

    def test_timeout_no_new_identity_does_not_imply_success(self):
        data = self.report([s(.032, 7, [.75, -2.21, .50], contacts=[{"node_id": 4, "point": [0, 0, 0]}]),
                            s(.064, 7, [0, 0, .015]), s(5.120, 7, [0, 0, .016])])
        self.assertEqual(set(data["attempts"]), {"7"})
        self.assertEqual(data["attempts"]["7"]["last_time"], 5.120)

    def test_evidence_malformed_fails_not_fabricated(self):
        for rows in ([], [s(.032, 7, [0, 0, 0]), s(.032, 8, [0, 0, 0])],
                     [dict(s(.032, 7, [0, 0, 0]), contacts=None)],
                     [dict(s(.032, 7, [0, 0, 0]), velocity=[0, 0])]):
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):
                    self.report(rows)

    def test_native_failure_probe_and_outcome_keep_post_collision_reset_in_attempt(self):
        # Reproduces the independent NO_GO: in native Webots customData evolves
        # ATTEMPT -> FAILURE_PROBE -> OUTCOME while retaining attempt=N.
        failure = "WEBEEBLOCKS_ACTIVITY_FAILURE_PROBE_V1 attempt=7 oracle=progression-autonomous-strategy-v1"
        outcome = "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=7 oracle=progression-autonomous-strategy-v1 status=not-achieved"
        outcome8 = "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=8 oracle=progression-autonomous-strategy-v1 status=not-achieved"
        contact = [{"point": [.75, -2.22, .499], "node_id": 42}]
        def phase_row(t, n, p, raw, contacts=None):
            row = s(t, n, p, contacts=contacts)
            row["custom_data"] = raw
            return row
        data = self.report([
            s(10., 7, [.75, -2.218, .499], contacts=contact),
            phase_row(10.032, 7, [.76, -2.218, .499], failure, contact),
            phase_row(10.064, 7, [.76, -2.218, .499], outcome),
            phase_row(10.096, 7, [0., 0., .015], outcome),
            s(10.128, 8, [0., 0., .015]),
            phase_row(10.160, 8, [.1, .1, .5], outcome8),
            phase_row(10.192, 8, [0., 0., .015], outcome8),
        ])
        self.assertEqual(set(data["attempts"]), {"7", "8"})
        seven, eight = data["attempts"]["7"], data["attempts"]["8"]
        self.assertEqual(seven["samples"], 4)
        self.assertEqual(seven["phases"], {"attempt": 1, "failure_probe": 1, "outcome": 2})
        self.assertEqual(eight["phases"], {"attempt": 1, "outcome": 2})
        self.assertEqual(seven["last_sample"]["custom_data"], outcome)
        self.assertEqual(seven["first_contact"]["phase"], "attempt")
        self.assertEqual(seven["last_contact"]["phase"], "failure_probe")
        self.assertEqual(seven["largest_observed_xyz_jump"]["from"]["custom_data"], outcome)
        self.assertEqual(seven["largest_observed_xyz_jump"]["to"]["custom_data"], outcome)
        self.assertAlmostEqual(seven["largest_observed_xyz_jump"]["distance_m"],
                               math.dist([.76, -2.218, .499], [0., 0., .015]))
        self.assertAlmostEqual(eight["largest_observed_xyz_jump"]["distance_m"],
                               math.dist([.1, .1, .5], [0., 0., .015]))
        self.assertNotEqual(seven["largest_observed_xyz_jump"]["distance_m"],
                            eight["largest_observed_xyz_jump"]["distance_m"])

    def test_unrecognized_identity_stays_explicitly_unattributed(self):
        row = s(.064, 9, [0., 0., .015])
        row["custom_data"] = "OUTCOME attempt=7 status=achieved"
        data = self.report([s(.032, 7, [.75, -2.218, .499]), row])
        self.assertEqual(set(data["attempts"]), {"7", "unattributed"})
        self.assertEqual(data["attempts"]["unattributed"]["last_sample"]["phase"], "unknown")
        self.assertEqual(data["attempts"]["unattributed"]["last_sample"]["custom_data"],
                         row["custom_data"])

    def test_nan_strings_do_not_become_motion_or_zero(self):
        data = self.report([s(.032, 7, ["nan", 0, 0]), s(.064, 7, [0, 0, 0])])
        self.assertIsNone(data["attempts"]["7"]["largest_observed_xyz_jump"])
        self.assertEqual(data["attempts"]["7"]["first_time"], .032)


if __name__ == "__main__":
    unittest.main()

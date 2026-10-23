"""Adversarial bounded tests of #637 native receipt-relative analysis."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reset_post_teleport import HEADER, analyze


def native(t, *, contacts=None, angular=0., custom_data=""):
    return {"type": "sample", "time": t, "custom_data": custom_data,
            "position": [0., 0., .015], "orientation": [1., 0., 0., 0., 1., 0., 0., 0., 1.],
            "velocity": [0., 0., 0., angular, 0., 0.], "contacts": contacts or []}


def phase(n, t, ok=True):
    return {"id": n, "begin_time": t,
            "terminal": f"WEBEEBLOCKS_RUNTIME_V2 RESPONSE {n} " + ("OK" if ok else "ERR RESET_TIMEOUT")}


class Tests(unittest.TestCase):
    def report(self, rows, phases):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "native.jsonl"
            path.write_text("\n".join(json.dumps(x) for x in [HEADER, *rows]) + "\n")
            return analyze(path, {"resets": phases})

    def test_realistic_receipt_alignment_and_failure_not_relabeled_pass(self):
        rows = [native(k*.032) for k in range(1, 19)]
        rows[11] = native(.384, angular=39.652, contacts=[{"point": [.0, -.01, -.03], "node_id": 198}])
        result = self.report(rows, [phase(11, .128), phase(22, .352, False)])
        self.assertEqual(result["offsets"], [-1, 0, 1, 2, 3])
        self.assertEqual(len(result["resets"]), 2)
        x = result["resets"][1]
        self.assertIn("ERR RESET_TIMEOUT", x["terminal"])
        self.assertEqual(x["steps"]["1"]["angular_speed_rad_s"], 39.652)
        self.assertEqual(x["steps"]["1"]["contact_count"], 1)
        self.assertEqual(x["steps"]["1"]["contacts"][0]["node_id"], 198)
        self.assertNotIn("achieved", str(result))

    def test_missing_native_receipt_sample_fails_closed(self):
        base = [native(k*.032) for k in range(1, 8)]
        for rows in (base[:3] + base[4:], base[:5], []):
            with self.subTest(count=len(rows)), self.assertRaises(ValueError):
                self.report(rows, [phase(1, .096)])

    def test_duplicate_nonmonotonic_invalid_and_unknown_terminal_refused(self):
        base = [native(k*.032) for k in range(1, 10)]
        invalid = [
            ([phase(1, .096), phase(1, .224)], base),
            ([phase(1, .224), phase(2, .096)], base),
            ([dict(phase(1, .096), begin_time=.097)], base),
            ([dict(phase(1, .096), terminal="WEBEEBLOCKS_RUNTIME_V2 RESPONSE 1 ERR BOGUS")], base),
            ([phase(1, .096)], base[:3] + [base[2]] + base[4:]),
            ([phase(1, .096)], base[:3] + [native(.128, angular=float('nan'))] + base[4:]),
            ([phase(1, .096)], base[:3] + [dict(base[3], contacts=[{"node_id": True, "point": [0,0,0]}])] + base[4:]),
        ]
        for phases, rows in invalid:
            with self.subTest(phases=phases, rows=len(rows)), self.assertRaises(ValueError):
                self.report(rows, phases)

    def test_uninstrumented_attempts_cannot_be_claimed_aligned(self):
        with self.assertRaises(ValueError):
            self.report([native(.032)], [])
        with self.assertRaises(ValueError):
            self.report([native(.032)], [phase(3, .05)])


if __name__ == '__main__':
    unittest.main()

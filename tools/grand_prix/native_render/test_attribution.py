"""Deterministic regressions for non-authoritative native WREN tail attribution.

No Webots run, render quality, product acceptance or 8-ms safety result is
implied by these purely synthetic overlap fixtures.
"""
import tempfile
from pathlib import Path
import unittest

from tools.grand_prix.native_render.run import attribute


class NativeDrawUnionTests(unittest.TestCase):
    def classify(self, draw_spans):
        # One complete 100 ms cycle with all required trace sections.
        cycle_ns = 100_000_000
        sections = [
            ("physics", 0, 1_000_000),
            ("controller_reply", 1_000_000, 2_000_000),
            ("qt_controller_ready", 2_000_000, 3_000_000),
            ("opengl_swap", 3_000_000, 4_000_000),
        ]
        sections.extend(("wren_draw", start, end) for start, end in draw_spans)
        with tempfile.TemporaryDirectory() as work:
            path = Path(work) / "performance.log.render.csv"
            rows = ["# webots-render-trace-v1 complete=1",
                    "section,start_ns,end_ns"]
            rows.extend(f"{section},{start},{end}" for section, start, end in sections)
            path.write_text("\n".join(rows) + "\n", encoding="utf-8")
            return attribute([(0, 0, 0), (cycle_ns, cycle_ns, cycle_ns)], path, 0)

    def test_duplicate_draw_spans_do_not_invent_majority(self):
        spans = [(10_000_000, 40_000_000)] * 2
        report = self.classify(spans)
        self.assertEqual(report["tail_cycles"], 1)
        self.assertEqual(report["draw_overlaps_majority_of_tail_cycles"], 0)
        self.assertEqual(report["p99_ms_by_stage"]["wren_draw"], 30.0)

    def test_disjoint_draw_intervals_still_prove_majority(self):
        report = self.classify([(10_000_000, 40_000_000),
                                (50_000_000, 80_000_000)])
        self.assertEqual(report["draw_overlaps_majority_of_tail_cycles"], 1)

    def test_partly_overlapping_draws_count_union_once(self):
        # 30+30 ms naive sum is 60 ms, but union [10,50] is only 40 ms.
        report = self.classify([(10_000_000, 40_000_000),
                                (20_000_000, 50_000_000)])
        self.assertEqual(report["draw_overlaps_majority_of_tail_cycles"], 0)


if __name__ == "__main__":
    unittest.main()

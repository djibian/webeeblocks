#!/usr/bin/env python3
"""Abstract event tests, deliberately not claimed as dynamic Webots evidence."""
from pathlib import Path
import math
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.grand_prix.lap_progress import Progress, MAX_LAPS, candidate_score
RING=('h:0','corner:0','corner:1','h:1','corner:2','junction')
FINAL=('final:0','final:1')
class Tests(unittest.TestCase):
    def lap(self, progress):
        for token in RING:self.assertTrue(progress.advance(token))
    def test_free_laps_same_route(self):
        for laps in (1,2,3,7,MAX_LAPS):
            progress=Progress(RING,FINAL)
            for _ in range(laps):self.lap(progress)
            self.assertEqual(progress.laps,laps)
            self.assertEqual(progress.crossings,2*laps)
            self.assertTrue(progress.choose_exit())
            for token in FINAL:self.assertTrue(progress.advance(token))
            self.assertTrue(progress.final_complete)
            self.assertEqual(progress.crossings,2*laps+2)
    def test_no_partial_exit_or_duplicate_points(self):
        p=Progress(RING,FINAL);self.assertFalse(p.choose_exit())
        for prefix in range(1,len(RING)):
            p=Progress(RING,FINAL);self.lap(p)
            for token in RING[:prefix]:self.assertTrue(p.advance(token))
            self.assertFalse(p.choose_exit());self.assertEqual(p.crossings,2)
        p=Progress(RING,FINAL);self.assertTrue(p.advance('h:0'))
        self.assertFalse(p.advance('h:0'));self.assertEqual(p.crossings,0)
        self.assertFalse(p.advance('corner:0'))
    def test_shortcuts_reverse_wrong_order(self):
        for token in ('junction','corner:1','h:1','final:0','h:0:reverse'):
            p=Progress(RING,FINAL);self.assertFalse(p.advance(token));self.assertEqual(p.crossings,0)
    def test_terminal_and_independent_bound(self):
        p=Progress(RING,());self.lap(p);self.assertTrue(p.choose_exit());self.assertTrue(p.final_complete)
        self.assertFalse(p.choose_exit());self.assertFalse(p.final_complete)
        p=Progress(RING,FINAL,max_laps=1);self.lap(p);self.assertFalse(p.advance('h:0'))
        q=Progress(RING,FINAL,max_laps=1);self.lap(q);self.assertTrue(q.choose_exit())
        for bound in (0,MAX_LAPS+1,True,1.5):
            with self.assertRaises(ValueError):Progress(RING,FINAL,max_laps=bound)
    def test_route_tokens_must_represent_only_gate_crossings_and_corners(self):
        for ring, final in (
            (('marker:0','junction'), ('final:0',)),
            (('h:0','junction'), ('landing',)),
            (('checkpoint','junction'), ()),
            (('corner:0','timer:0','junction'), ('final:0',)),
            (('h:','junction'), ()),
            (('h:0','junction'), ('final:',)),
        ):
            with self.subTest(ring=ring, final=final):
                with self.assertRaises(ValueError):
                    Progress(ring, final)

    def test_calibrated_penalty_threshold_is_explicit(self):
        self.assertEqual(candidate_score(10,180,180), 50)
        self.assertEqual(candidate_score(10,180.001,180), 49)
        self.assertEqual(candidate_score(10,180.001,300), 50)
        with self.assertRaises(TypeError):
            candidate_score(10,180)
        for threshold in (True, -1, None, math.nan, math.inf):
            with self.subTest(threshold=threshold):
                with self.assertRaises(ValueError):
                    candidate_score(10,180,threshold)

    def test_fractional_public_threshold_cannot_charge_extra_second(self):
        # 540.032 - 420.032 is 120.00000000000006 in binary, although
        # these integer-millisecond operands differ by exactly 120 seconds.
        # The public rule accepts integer seconds only; do not hide an epsilon.
        for threshold in (8.032,20.032,420.032,480.032,120.0):
            with self.subTest(threshold=threshold):
                with self.assertRaises(ValueError):
                    candidate_score(10,540.032,threshold)
        for threshold in (120,180,420,540):
            for extra,penalty in ((-.032,0),(0,0),(.032,1),(1,1),(1.032,2)):
                self.assertEqual(candidate_score(10,threshold+extra,threshold),50-penalty)
        self.assertEqual(candidate_score(10,540,420),-70)

    def test_candidate_score_boundaries(self):
        for seconds,score in [(119.999,50),(120,50),(120.000001,49),(120.999,49),(121,49),(121.000001,48),(600,-430)]:
            self.assertEqual(candidate_score(10,seconds,120),score)
        for points,seconds in [(True,120),(-1,120),(1,True),(1,-1),(1,math.nan),(1,math.inf)]:
            with self.assertRaises(ValueError):candidate_score(points,seconds,120)
    def test_profitability_and_bad_extra_lap_are_not_forced(self):
        # Explicit hypothetical durations: this test proves arithmetic, not
        # measured geometry, pupil advantage or fair CPU-independent execution.
        self.assertGreater(candidate_score(8,100,120),candidate_score(4,60,120))
        self.assertLess(candidate_score(8,160,120),candidate_score(4,100,120))
if __name__=='__main__':unittest.main()

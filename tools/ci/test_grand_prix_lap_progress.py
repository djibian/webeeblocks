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
    def test_candidate_score_boundaries(self):
        for seconds,score in [(119.999,50),(120,50),(120.000001,49),(120.999,49),(121,49),(121.000001,48),(600,-430)]:
            self.assertEqual(candidate_score(10,seconds),score)
        for points,seconds in [(True,120),(-1,120),(1,True),(1,-1),(1,math.nan),(1,math.inf)]:
            with self.assertRaises(ValueError):candidate_score(points,seconds)
    def test_profitability_and_bad_extra_lap_are_not_forced(self):
        # Explicit hypothetical durations: this test proves arithmetic, not
        # measured geometry, pupil advantage or fair CPU-independent execution.
        self.assertGreater(candidate_score(8,100),candidate_score(4,60))
        self.assertLess(candidate_score(8,160),candidate_score(4,100))
if __name__=='__main__':unittest.main()

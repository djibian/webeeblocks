#!/usr/bin/env python3
from pathlib import Path
import math
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.grand_prix.simulation_time import elapsed_seconds, milliseconds
class Tests(unittest.TestCase):
    def test_realizable_120_second_counterexample(self):
        start=251*32/1000;end=(251+3750)*32/1000
        self.assertGreater(end-start,120)
        self.assertEqual(math.ceil(max(0,end-start-120)),1)
        self.assertEqual(elapsed_seconds(start,end),120)
        self.assertEqual(math.ceil(max(0,elapsed_seconds(start,end)-120)),0)
    def test_many_simulation_origins_and_score_boundaries(self):
        for tick in range(10000):
            start=tick*32/1000
            for count,expected in ((3749,119.968),(3750,120),(3751,120.032),(18750,600),(18751,600.032)):
                elapsed=elapsed_seconds(start,(tick+count)*32/1000)
                self.assertEqual(elapsed,expected)
                if count<=3751:self.assertEqual(math.ceil(max(0,elapsed-120)),int(count==3751))
    def test_late_valid_time_is_never_forgiven(self):
        self.assertEqual(elapsed_seconds(8.032,128.033),120.001)
        self.assertEqual(math.ceil(max(0,elapsed_seconds(8.032,128.033)-120)),1)
    def test_unsupported_and_backward_clock_refuse(self):
        for value in (None,True,-1,math.nan,math.inf,8.032001,1e16):
            with self.assertRaises(ValueError):milliseconds(value)
        with self.assertRaises(ValueError):elapsed_seconds(2,1.999)
    def test_program_observation_and_official_clock_remain_separate(self):
        self.assertEqual(milliseconds(0),0)
        self.assertEqual(elapsed_seconds(2.016,2.048),.032)
from test_grand_prix_u_deadline import DeadlineTests

if __name__=='__main__':unittest.main()

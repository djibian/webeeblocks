#!/usr/bin/env python3
"""Falsify A6 variant-blind H pulse counter without using scene/AST oracles."""
import unittest

from tools.ci.analyze_count_h_dual_motor_sensor import (
    count_from_sensor_stream, inspect_motor_sensor_count
)


class DualNativeRayCounterTests(unittest.TestCase):
    @staticmethod
    def fixture(n,glitch=False,split_pulse=False):
        rows=[]
        def push(k,up,front):
            for _ in range(k):
                rows.append((.032*(len(rows)+1),up,front))
        push(20,2.,2.)
        for j in range(n):
            if glitch:
                push(2,.20,1.9)  # transient noise is not a physical H
                push(5,2.,1.9)
            if split_pulse:
                # Native #43895108217 blockly-n1: an early 5-tick near,
                # a 5-tick far gap, then the long near of the SAME gate.
                # Do not award two H for that 160-ms sensor dropout.
                push(5,.20,2. if j<2 else .97)
                push(5,2.,2. if j<2 else .97)
            push(12,.20,2. if j<2 else .97)
            push(40,2.,2. if j<2 else .91)
        # Distinctive FRONTAL wall cue occurs before the cyan terminal pulse.
        push(5,2.,.79)
        push(14,.22,.60)
        return rows

    def test_one_two_three_pulses_with_terminal_alias_not_counted(self):
        for n in (1,2,3):
            with self.subTest(n=n):
                result=count_from_sensor_stream(self.fixture(n,glitch=True))
                self.assertEqual(result["count"],n)
                self.assertTrue(result["terminal_detected"])

    def test_one_physical_h_split_by_real_160ms_far_dropout(self):
        for n in (1,2,3):
            with self.subTest(n=n):
                result=count_from_sensor_stream(
                    self.fixture(n,glitch=True,split_pulse=True))
                self.assertEqual(result["count"],n)
                self.assertTrue(result["terminal_detected"])

    def test_bad_step_sensor_values_and_absent_terminal_fail_closed(self):
        rows=self.fixture(2)
        self.assertFalse(count_from_sensor_stream(rows[:110])["terminal_detected"])
        for change in ((10,2.1,2.),(40,float("nan"),2.),
                       (40,.2,-1.)):
            damaged=list(rows)
            i,up,front=change
            t,_,_=damaged[i]
            damaged[i]=(t,up,front)
            with self.assertRaisesRegex(ValueError,"sensor stream"):
                count_from_sensor_stream(damaged)
        damaged=list(rows)
        del damaged[10]
        with self.assertRaisesRegex(ValueError,"gapped"):
            count_from_sensor_stream(damaged)

    def test_real_log_extraction_requires_native_takeoff_and_land(self):
        trace=("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 3 OK\n"+
            "".join(
                f"WEBEEBLOCKS_A6_UP_MOTOR t={(i+1)*.032:.6f} "
                f"x=-0.400000000 y=0.000000000 z=0.415000000 "
                f"up=2.000000000 step=32 front={.79 if i>=101 else 2.:.9f}\n"
                for i in range(104))+
            "WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1\n")
        result=inspect_motor_sensor_count(trace)
        self.assertEqual(result["count"],0)
        self.assertTrue(result["terminal_detected"])
        with self.assertRaisesRegex(ValueError,"TAKEOFF"):
            inspect_motor_sensor_count(trace.replace("RESPONSE 3 OK","RESPONSE 3 ERROR"))
        with self.assertRaisesRegex(ValueError,"LAND"):
            inspect_motor_sensor_count(trace.replace("TRACE LAND stop=1","TRACE RESET"))

if __name__=="__main__":
    unittest.main()

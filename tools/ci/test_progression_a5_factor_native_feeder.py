#!/usr/bin/env python3
"""Native-only A5 motor feeder contract, separate from failing Chrome UI witness."""
from pathlib import Path
import re
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools/ci"))
import run_classroom_reactive_L_factor_native_feeder as feeder

class NativeFeederTests(unittest.TestCase):
    def test_ci_only_feature_flag_and_transparent_unset_passthrough(self):
        source=(ROOT/"controllers/progression_reactive_L_factor_motor_pilot"/
                "factor_motor_feeder.c").read_text()
        make=(ROOT/"controllers/progression_reactive_L_factor_motor_pilot"/
              "Makefile").read_text()
        self.assertIn('getenv("WEBEEBLOCKS_A5_FACTOR_NATIVE_FEEDER")',source)
        self.assertIn('if(!enabled)return __real_wb_robot_wwi_receive_text()',source)
        self.assertIn('if(!enabled){',source)
        self.assertIn('dlsym(RTLD_NEXT,"wb_robot_wwi_send_text")',source)
        self.assertIn('if(!relay){fail("real_wwi_send_passthrough_unavailable");return;}',source)
        self.assertIn('relay(message);',source)
        self.assertNotIn('__real_wb_robot_wwi_send_text',source)
        self.assertIn("-ldl",make)
        self.assertIn("-Wl,--wrap=wb_robot_wwi_receive_text",make)
        self.assertIn("-Wl,--wrap=wb_robot_wwi_send_text",make)
        self.assertIn("../crazyflie_runtime_v2/crazyflie_runtime_v2.c",make)
        self.assertIn("../crazyflie_square/pid_controller.c",make)
        self.assertNotIn("wb_motor_set_velocity",source)
        self.assertNotIn("wb_motor_set_position",source)

    def test_late_native_sensor_controls_gate_direction(self):
        source=(ROOT/"controllers/progression_reactive_L_factor_motor_pilot"/
                "factor_motor_feeder.c").read_text()
        self.assertIn("case 6:return snprintf(out,n,PREFIX",source)
        self.assertIn('" REQUEST %d RANGE left"',source)
        self.assertIn("go_left=blind?1:(value>1.0)",source)
        self.assertIn("case 7:return snprintf(out,n,PREFIX",source)
        self.assertIn('" REQUEST %d TURN %d"',source)
        self.assertLess(source.index('" REQUEST %d RANGE left"'),
                        source.index('" REQUEST %d TURN %d"'))
        self.assertIn("if(blind&&variant!='B')",source)
        self.assertIn("WEBEEBLOCKS_A5_FACTOR_FEEDER_LATE_RANGE",source)
        self.assertIn("WEBEEBLOCKS_A5_FACTOR_FEEDER_DONE",source)

    def test_native_result_cannot_pass_on_browser_or_missing_floor(self):
        body=(ROOT/"tools/ci/run_classroom_reactive_L_factor_native_feeder.py").read_text()
        for token in (
            'env["WEBEEBLOCKS_A5_FACTOR_NATIVE_FEEDER"]=mode',
            'startup=re.findall(',
            'len(startup)==1 and len(wrong)==1',
            'WEBEEBLOCKS_A5_FACTOR_MOTOR_NATIVE_FLOOR',
            'native_collision_coverage(data,variant)',
            'land_ack and not invalid',
            'acks==list(range(1,expected_last+1))',
            '"browser_not_used":True',
            '"student_wbb":False',
            '"browser_integration_proven":False',
            'WEBEEBLOCKS_A5_FACTOR_MOTOR_SWEPT_COLLISION',
            '"pupil_wbb_or_mission_proven"'
        ):
            if token=='"pupil_wbb_or_mission_proven"':
                self.assertIn('"student_wbb_proven":False',body)
            else:
                self.assertIn(token,body)
        self.assertNotIn('continue-on-error',body)
        self.assertNotIn("|| true",body)

    def test_invalid_variant_and_blind_are_refused_before_world_creation(self):
        for args in (("C","positive"),("A","blind"),("AB","positive"),
                     ("B","unknown"),("", "positive")):
            with self.subTest(args=args),self.assertRaises(ValueError):
                feeder.run(*args)

if __name__=="__main__":
    unittest.main()

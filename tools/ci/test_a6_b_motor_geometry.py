"""A6 B native motor geometry adapter: bounded source and negative controls.

This is a SOURCE-ONLY and compilation-contract test, never a R2025a flight
PASS. The native C oracle independently attests physical colliders in Webots.
"""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools/ci"))
import prepare_classroom_count_h_motor_flight as motor

class BMotorGeometrySourceTests(unittest.TestCase):
    def test_all_six_private_worlds_are_real_and_otherwise_unchanged(self):
        for family in ("matched","sampling"):
            for n in (1,2,3):
                with self.subTest(family=family,n=n):
                    from tools.ci.test_a6_b_matched_tail_geometry import validate_scene
                    from tools.ci.test_a6_b_sampling_holdout import SECOND,CLASSIFIER_POSTS,GATE_HALF_X
                    file=(ROOT/f"tools/ci/fixtures/a6-b/count-h-{n}-"
                          f"{motor.B_PRIVATE_FAMILIES[family]}-private.wbo")
                    body=file.read_text(encoding="utf-8")
                    if family=="matched":
                        validate_scene(body,n)
                    else:
                        validate_scene(body,n,expected_positions=SECOND[n],
                            checked_checkpoints=CLASSIFIER_POSTS,
                            checkpoint_margin=GATE_HALF_X,terminal_h=.48)
                    combined=motor.compose(variant=n,scene=body)
                    self.assertEqual(combined.count("PRIVATE A6 CHOICE B"),1)
                    self.assertEqual(combined.count(f"WEBEEBLOCKS_COUNT_{n}_SCENE"),1)
                    self.assertEqual(combined.count(" Solid {"),3*n+2)
                    self.assertEqual(combined.count('controller "progression_count_h_school_pilot"'),1)
                    self.assertEqual(combined.count('controller "progression_count_h_flight_observer"'),0)
    def test_unknown_or_adversarial_source_rejected(self):
        with self.assertRaises(ValueError):
            motor.compose(variant=4)
        base=(ROOT/"tools/ci/fixtures/a6-b/count-h-3-sampling-holdout-private.wbo").read_text()
        with self.assertRaises(ValueError):
            motor.compose(variant=3,scene=base+'Robot { }')
    def test_compile_time_only_oracle_gate_positions_fail_closed(self):
        core=(ROOT/"controllers/progression_count_h_v1/count_core.h").read_text()
        observer=(ROOT/"controllers/progression_count_h_flight_observer/progression_count_h_flight_observer.c").read_text()
        self.assertIn("WEBEEBLOCKS_A6_B_PRIVATE_MOTOR_TEST_ONLY",core)
        self.assertIn("return -0.850 + 0.850 * (double)index;",core)
        self.assertIn("return index < WB_COUNT_MAX_GATES ? wb_count_b_private_gate_x[index] : NAN;",core)
        self.assertIn("if(b_family<0)return fail",observer)
        self.assertIn("WEBEEBLOCKS_A6_B_MOTOR_GEOMETRY_ATTESTED",observer)
        self.assertIn('if(!box(bar,x,0,.74,.07,.57,.24',observer)
        self.assertIn('if(!box(screen,1.235,0,.76,.07,1.48,.24',observer)

if __name__=="__main__":unittest.main()

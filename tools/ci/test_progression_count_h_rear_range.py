#!/usr/bin/env python3
"""Fail closed on mutated A6 world composition for the native leak experiment."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_classroom_count_h_rear_range as diagnostic

class CountHRearRangeWorldTests(unittest.TestCase):
    def test_terminal_multiranger_checker_rejects_one_leaking_or_missing_ray(self):
        # Adversarial arrays are only contract tests; they never count as
        # real Webots evidence. Any one of five rays can refute the premise.
        reference={
            n:{(pad,stage):(2.0,2.0,2.0,2.0,2.0)
               for pad in range(3) for stage in ("approach","landed")}
            for n in (1,2,3)
        }
        self.assertTrue(diagnostic.validate_terminal_indistinguishability(reference))
        for stage in ("approach","landed"):
            for channel in range(5):
                import copy
                wrong=copy.deepcopy(reference)
                values=list(wrong[3][(2,stage)])
                values[channel]=1.8
                wrong[3][(2,stage)]=tuple(values)
                with self.subTest(stage=stage,channel=channel), self.assertRaisesRegex(
                        AssertionError,"leaks H count"):
                    diagnostic.validate_terminal_indistinguishability(wrong)
        import copy
        missing=copy.deepcopy(reference)
        del missing[2][(1,"landed")]
        with self.assertRaisesRegex(AssertionError,"missing native terminal sense"):
            diagnostic.validate_terminal_indistinguishability(missing)
        invalid=copy.deepcopy(reference)
        invalid[2][(0,"landed")]=(2.0,2.0,float("nan"),2.0,2.0)
        with self.assertRaisesRegex(AssertionError,"invalid native terminal"):
            diagnostic.validate_terminal_indistinguishability(invalid)
        source=(diagnostic.ROOT/"controllers/progression_count_h_range_probe/"
                "progression_count_h_range_probe.c").read_text(encoding="utf-8")
        runner=(diagnostic.ROOT/"tools/ci/run_classroom_count_h_rear_range.py").read_text(
            encoding="utf-8")
        for sensor in ("front","back","left","right","up"):
            self.assertIn('"range_'+sensor+'"',source)
            self.assertIn("wb_distance_sensor_enable("+sensor+", step)",source)
        self.assertIn("const double stages[2]={0.415,0.015}",source)
        self.assertIn("WEBEEBLOCKS_COUNT_H_TERMINAL_RANGES",source)
        self.assertIn("len(terminal_rows)!=len(PADS)*len(TERMINAL_STAGES)",runner)
        self.assertIn("validate_terminal_indistinguishability(full_terminal)",runner)
        self.assertIn("all_five_native_rays_compared_at_0_415m_and_0_015m",runner)
        self.assertNotIn("wb_motor_set_",source)

    def test_cardinal_turns_falsify_late_count_leak_on_native_rays(self):
        # These intentionally forged arrays only test the fail-closed parser;
        # the actual 90/180/270-degree readings must come from R2025a.
        import copy
        reference={
            n:{(pad,phase,yaw):(2.0,2.0,2.0,2.0,2.0)
               for pad in range(3)
               for phase in ("approach","landed")
               for yaw in (90,180,270)}
            for n in (1,2,3)
        }
        self.assertTrue(diagnostic.validate_heading_indistinguishability(reference))
        for phase in ("approach","landed"):
            for yaw in diagnostic.TERMINAL_HEADINGS:
                for channel in range(5):
                    wrong=copy.deepcopy(reference)
                    values=list(wrong[3][(2,phase,yaw)])
                    values[channel]=1.80
                    wrong[3][(2,phase,yaw)]=tuple(values)
                    with self.subTest(phase=phase,yaw=yaw,channel=channel), self.assertRaisesRegex(
                            AssertionError,"leaks H count"):
                        diagnostic.validate_heading_indistinguishability(wrong)
        missing=copy.deepcopy(reference)
        del missing[1][(0,"approach",180)]
        with self.assertRaisesRegex(AssertionError,"missing native cardinal sense"):
            diagnostic.validate_heading_indistinguishability(missing)
        invalid=copy.deepcopy(reference)
        invalid[2][(1,"landed",270)]=(float("nan"),2.,2.,2.,2.)
        with self.assertRaisesRegex(AssertionError,"invalid native cardinal sense"):
            diagnostic.validate_heading_indistinguishability(invalid)
        source=(diagnostic.ROOT/"controllers/progression_count_h_range_probe/"
                "progression_count_h_range_probe.c").read_text(encoding="utf-8")
        runner=(diagnostic.ROOT/"tools/ci/run_classroom_count_h_rear_range.py").read_text(
            encoding="utf-8")
        for token in ("for(int heading=1;heading<=3;++heading)",
                      "wb_supervisor_node_get_orientation(self)",
                      "fabs(heading_matrix[0]-cos(yaw))",
                      "fabs(heading_matrix[3]-sin(yaw))",
                      "WEBEEBLOCKS_COUNT_H_HEADING_RANGES variant=%d"):
            self.assertIn(token,source)
        for token in ("TERMINAL_HEADINGS=(90,180,270)",
                      "len(heading_rows)!=len(PADS)*len(TERMINAL_STAGES)*len(TERMINAL_HEADINGS)",
                      "validate_heading_indistinguishability(full_headings)",
                      "A6_CARDINAL_MULTIRANGER_NATIVE_INVARIANT",
                      "cardinal_turns_90_180_270_tested_at_both_low_phases"):
            self.assertIn(token,runner)
        self.assertNotIn("wb_motor_set_",source)
        self.assertNotIn("continue-on-error",runner)

    def test_genuine_upward_ray_samples_every_H_without_a_pupil_algorithm(self):
        source=(diagnostic.ROOT/"controllers/progression_count_h_range_probe/"
                "progression_count_h_range_probe.c").read_text(encoding="utf-8")
        runner=(diagnostic.ROOT/"tools/ci/run_classroom_count_h_rear_range.py").read_text(
            encoding="utf-8")
        self.assertIn('"range_up"',source)
        self.assertIn("wb_distance_sensor_enable(up, step)",source)
        self.assertIn("for(int gate=0;gate<variant;++gate)",source)
        self.assertIn("for(int phase=0;phase<3;++phase)",source)
        self.assertIn("wb_distance_sensor_get_value(up)/1000.0",source)
        self.assertIn("WEBEEBLOCKS_COUNT_H_UP_SAMPLE variant=%d",source)
        self.assertIn("contacts!=0",source)
        self.assertIn("len(upper_rows)!=n*3",runner)
        self.assertIn("native_up_before_under_after_m",runner)
        self.assertIn("variable_counting_or_generic_wbb_unproven",runner)
        self.assertNotIn("wb_motor_set_",source)
        self.assertNotIn("Blockly.Workspace",source)

    def test_worlds_use_original_crazyflie_sensor_without_pupil_controller(self):
        for n in (1,2,3):
            world=diagnostic.compose(n)
            self.assertEqual(world.count('controller "progression_count_h_range_probe"'),1)
            self.assertNotIn('controller "crazyflie_runtime_v2"',world)
            self.assertNotIn('controller "crazyflie_classroom_v2"',world)
            self.assertEqual(world.count(f'DEF WEBEEBLOCKS_COUNT_{n}_SCENE Group'),1)
            for other in (1,2,3):
                if other!=n:
                    self.assertNotIn(f'DEF WEBEEBLOCKS_COUNT_{other}_SCENE Group',world)
            self.assertEqual(world.count("boundingObject Box"),3*n+2)
            self.assertEqual(world.count(f'DEF ACTIVITY6_{n}_FINISH_SCREEN Solid'),1)
            self.assertEqual(world.count(diagnostic.MARKER),1)

    def test_native_observer_probes_all_three_pads_not_legacy_single_ray(self):
        source=(diagnostic.ROOT /
                "controllers/progression_count_h_range_probe/"
                "progression_count_h_range_probe.c").read_text(encoding="utf-8")
        self.assertIn("for (int pad = 0; pad < 3; ++pad)", source)
        self.assertIn("WEBEEBLOCKS_COUNT_H_BACK_MASKED variant=%d pad=%d", source)
        self.assertNotIn("const int disclosed=", source)
        self.assertNotIn("WEBEEBLOCKS_COUNT_H_BACK_OBSERVED", source)
        runner=(diagnostic.ROOT /
                "tools/ci/run_classroom_count_h_rear_range.py").read_text(
                    encoding="utf-8")
        self.assertIn("len(findings)!=3", runner)
        self.assertIn("for pad in range(len(PADS)):", runner)
        self.assertIn("max(values)-min(values) > .025", runner)

    def test_real_contact_sweep_and_positive_control_cannot_be_silenced(self):
        source=(diagnostic.ROOT /
                "controllers/progression_count_h_range_probe/"
                "progression_count_h_range_probe.c").read_text(encoding="utf-8")
        self.assertIn("wb_supervisor_node_get_contact_points(self, true, &contact_count)", source)
        self.assertIn("wb_supervisor_node_get_contact_points(self, true, &self_contacts)", source)
        self.assertIn("wb_supervisor_node_enable_contact_points_tracking(self, step, true)", source)
        self.assertIn("wb_supervisor_node_get_contact_points(first_bar, false, &bar_contacts)", source)
        self.assertIn("WEBEEBLOCKS_COUNT_H_CONTACT_CONTROL variant=%d k=%d", source)
        self.assertIn("const double release_pose[3] = {-0.850, 0.0, 1.280}", source)
        self.assertIn("for (int k = 0; k < 80; ++k)", source)
        self.assertIn("if (bar_contacts > control_contacts) control_contacts = bar_contacts", source)
        self.assertIn("no real H-bar contact from gravity-driven positive control", source)
        self.assertNotIn("collision_pose", source)
        self.assertNotIn("wb_supervisor_node_get_contact_points(self, &contact_count, true)", source)
        self.assertIn("for (int i = 0; i <= 144 + 28 * 2; ++i)", source)
        self.assertIn("return invalid(\"no real H-bar contact from gravity-driven positive control\")", source)
        self.assertIn("WEBEEBLOCKS_COUNT_H_SWEEP_PASS variant=%d samples=%d", source)
        self.assertNotIn("WEBEEBLOCKS_COUNT_H_SWEEP_PASS", source.split(
            "wb_supervisor_node_get_contact_points", 1)[0])
        runner=(diagnostic.ROOT /
                "tools/ci/run_classroom_count_h_rear_range.py").read_text(
                    encoding="utf-8")
        self.assertIn("int(sweep[0][1])!=201", runner)
        self.assertIn("int(sweep[0][2])<1", runner)
        self.assertIn("A6_CONTACT_SWEEP_NATIVE_OK", runner)
        self.assertIn('TOKEN="WEBEEBLOCKS_COUNT_H_SWEEP_PASS"', runner)
        self.assertNotIn('TOKEN="WEBEEBLOCKS_COUNT_H_BACK_MASKED"', runner)

    def test_refuse_unknown_scene_or_corrupted_start(self):
        for n in (0,4,-1,'1'):
            with self.subTest(variant=n),self.assertRaises(ValueError):
                diagnostic.compose(n)
        source=diagnostic.classroom.SOURCE.read_text(encoding="utf-8")
        with self.assertRaises(ValueError):
            diagnostic.compose(1,source=source.replace(
                'name "Crazyflie WebeeBlocks"','name "Evil"'))

if __name__=="__main__":
    unittest.main()

#!/usr/bin/env python3
"""Draft-only A6 launcher source identity. Real Webots flight is separate."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
GENERIC=ROOT/'worlds/crazyflie_classroom_start.wbt'
COUNT=ROOT/'worlds/crazyflie_classroom_count_h_start.wbt'
PROJECT=ROOT/'worlds/.crazyflie_classroom_count_h_start.wbproj'
SELECTOR=ROOT/'controllers/crazyflie_classroom_v2/classroom_scene.cpp'
GATE=ROOT/'controllers/crazyflie_classroom_v2/count_h_scene_gate.h'
HEADER='# WEBEEBLOCKS_SEQUENCE_EVALUATOR_V1_BEGIN'
TRAILER='''

# A6 school-start world. No H geometry or native observer preloaded:
# the verified school SCENE request imports the selected 1/2/3 WBO.
# Dedicated school Robot Window is experimental; hidden A6 remains unpublished.
# Native scene admission is authoritative, not the browser initial-profile hint.
'''

class CountHSchoolStartTest(unittest.TestCase):
    def test_dedicated_world_project_activates_real_robot_window(self):
        self.assertEqual(PROJECT.read_text(encoding='utf-8'),
                         'Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n')

    def test_exactly_scoped_dedicated_native_start(self):
        generic=GENERIC.read_text(encoding='utf-8')
        school=COUNT.read_text(encoding='utf-8')
        self.assertEqual(generic.count(HEADER),1)
        self.assertEqual(generic.count('Crazyflie {\n'),1)
        self.assertEqual(generic.count('controller "crazyflie_runtime_v2"'),2)
        base=generic.partition(HEADER)[0]
        expected=(base
          .replace('Crazyflie {\n','Crazyflie {\n  translation -1.40 0 0.055\n')
          .replace('controller "crazyflie_runtime_v2"',
                   'controller "crazyflie_classroom_v2"')
          .replace('window "blockly_v2"', 'window "blockly_count_h"')
          .replace('title "WebeeBlocks — accueil"',
                   'title "WebeeBlocks — activité 6 : comptage de H (brouillon)"')
          .replace('position -2.4 -2.4 2.2','position -2.9 -2.4 2.1')
          .rstrip()+TRAILER)
        self.assertEqual(school,expected,
                         'A6 school launch diverged from canonical craft physics')
        for expected_line in ('#VRML_SIM R2025a utf8',
                              'DEF WEBEEBLOCKS_CLASSROOM_START_WORLD WorldInfo {',
                              'basicTimeStep 32',
                              'Crazyflie {\n  translation -1.40 0 0.055',
                              'controller "crazyflie_classroom_v2"',
                              'window "blockly_count_h"', 'range_up',
                              'Floor { size 4 4 }'):
            self.assertIn(expected_line,school)
        self.assertNotIn('progression_count_h_flight_observer',school)
        self.assertNotIn('DEF WEBEEBLOCKS_COUNT_',school)
        self.assertNotIn('Progression sequence evaluator',school)
        self.assertNotIn('controller "crazyflie_runtime_v2"',school)
    def test_real_chrome_browser_project_roundtrip_is_observed_and_scoped(self):
        # The actual A6 CDP runner must exercise the real browser project
        # manager, not merely compare an empty workspace across variants.
        # This is NOT a claim about an OS Save As/Open dialog on Windows.
        runner=(ROOT/'tools/ci/run_classroom_count_h_variant_cdp.py').read_text(
            encoding='utf-8')
        for marker in (
            'window.WebeeBlocksProjectManager',
            'manager.encodeCurrent()',
            'manager.openTemplateText',
            'WebeeBlocksProjectFiles.createStarterText',
            "'progression-sequence-v1'",
            'incompatible with the current Webots world',
            'real browser .wbb bytes changed during variants',
            'A6_REAL_BROWSER_WBB_ROUNDTRIP_PASS',
            'os_save_open=UNPROVEN',
            'same_native_epoch_preserved',
            'ack_after!=ack_before',
            'observer_after!=observer_before',
            'responses_after!=responses_before',
            'native_epoch_preserved=true',
        ):
            self.assertIn(marker,runner)
        self.assertIn('no_os_picker_proven',runner)
        self.assertIn('wbb_sha256',runner)

    def test_generic_start_remains_unmodified(self):
        generic=GENERIC.read_text(encoding='utf-8')
        self.assertIn('controller "crazyflie_runtime_v2"',generic)
        self.assertIn('Progression sequence evaluator',generic)
        self.assertNotIn('translation -1.40 0 0.055',generic)
    def test_wrong_start_refused_before_scene_mutation(self):
        native=SELECTOR.read_text(encoding='utf-8')
        gate=GATE.read_text(encoding='utf-8')
        self.assertIn('if(!webeeblocks_a6_gate::blueOrigin()) {',native)
        self.assertIn('WEBEEBLOCKS_A6_SCENE_DENIED n=%d stage=blue-origin',native)
        self.assertIn('WEBEEBLOCKS_A6_SCENE_DENIED n=%d stage=geometry',native)
        self.assertIn('WEBEEBLOCKS_A6_SCENE_DENIED n=%d stage=observer',native)
        self.assertIn('std::fabs(p[0]+1.40)<=.025',gate)
        self.assertIn('std::fabs(p[1])<=.025',gate)
        self.assertIn('wb_supervisor_node_get_position(craft)',gate)
        self.assertIn('WEBEEBLOCKS_A6_GATE_DENIED n=%d stage=%s item=%d',gate)
        self.assertIn('return deny(variant,"group-child-count"',gate)
        self.assertIn('return deny(variant,"terminal-screen")',gate)
        self.assertIn('webeeblocks_a6_gate::currentObserver(n)',native)
        self.assertIn('webeeblocks_a6_gate::realObserver()',native)
        self.assertNotIn('wb_supervisor_node_set_position',native)
        self.assertNotIn('wb_supervisor_node_reset_physics',native)

if __name__=='__main__':
    unittest.main()

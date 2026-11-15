#!/usr/bin/env python3
"""A5 v2 native observer source boundary, NOT real Webots flight acceptance."""
from pathlib import Path
import unittest
import re
ROOT=Path(__file__).resolve().parents[2]
DIR=ROOT/"controllers/progression_reactive_L_v2"
class NativeObserverContract(unittest.TestCase):
    def test_dedicated_native_supervisor_and_c11_core(self):
        code=(DIR/"progression_reactive_L_v2.c").read_text(encoding="utf-8")
        make=(DIR/"Makefile").read_text(encoding="utf-8")
        oracle=(DIR/"reactive_core_v2.h").read_text(encoding="utf-8")
        self.assertIn("C_SOURCES = progression_reactive_L_v2.c",make)
        self.assertIn("resources/Makefile.include",make)
        for needle in (
            '#include <webots/supervisor.h>',
            '#include <webots/contact_point.h>',
            "wb_supervisor_node_get_contact_points(craft,true,&count)",
            "wb_supervisor_node_enable_contact_points_tracking(craft,step,true)",
            "wb_supervisor_node_get_velocity(craft)",
            "wb_supervisor_node_get_orientation(craft)",
            "wb_rl2_sample_mission(&mission,&s)",
            "wb_rl2_boxes(*variant,boxes)",
            "wb_supervisor_field_get_sf_node(boundary)",
            "wb_supervisor_node_get_orientation(node)",
            "const double expected=(i%4==0)?1.0:0.0;",
            "if(!close_native(orientation[i],expected))return 0;",
            "WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=%llu oracle=%s",
            "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=%s",
            "WEBEEBLOCKS_A5_V2_NATIVE_C_READY",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle,code)
        code_without_comments=re.sub(r"/\*.*?\*/|//[^\n]*", "", code, flags=re.S)
        for forbidden in (
            "wb_supervisor_node_reset_physics",
            "wb_supervisor_field_set_sf_vec3f",
            "wb_motor_set_velocity",
            "wb_motor_set_position",
            "wb_supervisor_node_set_velocity",
            "wb_supervisor_node_set_position",
            "blockly", "ast_json", "Blockly", "physical_send",
            "crazyflie_runtime_v2.c",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden,code_without_comments)
        self.assertIn("WB_RL2_BODY 0.09",oracle)
        self.assertIn("WB_RL2_LAND_DWELL 0.25",oracle)
        self.assertIn("WB_RL2_LAND_TIMEOUT 1.50",oracle)
        self.assertIn("WB_RL2_LAND_MAX_SAMPLE_GAP 0.048",oracle)
        self.assertIn("observation_gap>WB_RL2_LAND_MAX_SAMPLE_GAP",oracle)
        self.assertIn("m->origin_z<WB_RL2_START_MIN_Z",oracle)
        self.assertIn("m->origin_z>WB_RL2_START_MAX_Z",oracle)
        self.assertIn("start[2]<WB_RL2_START_MIN_Z",code)
        self.assertIn("start[2]>WB_RL2_START_MAX_Z",code)
        self.assertIn("if(step!=32||!attest_scene(&variant))",code)
        world=(ROOT/"worlds/crazyflie_classroom_start.wbt").read_text(encoding="utf-8")
        self.assertIn("basicTimeStep 32",world)

    def test_native_observation_never_makes_variant_a_completion_magic(self):
        core=(DIR/"reactive_core_v2.h").read_text(encoding="utf-8")
        native=(DIR/"progression_reactive_L_v2.c").read_text(encoding="utf-8")
        self.assertNotIn("variables_set",core)
        self.assertNotIn("controls_repeat_ext",core)
        self.assertNotIn("controls_if",core)
        self.assertIn("s.completed=parse_completion(value,mission.attempt)",native)
        self.assertIn("if(!last_attempt||mission.verdict!=WB_RL2_WAIT)continue;",native)
        self.assertIn("wb_supervisor_field_set_sf_string(channel,marker)",native)
        self.assertIn("wb_rl2_segment_hits_box",core)
        self.assertIn("!wb_rl2_on_leg(m->variant,m->stage,s->x,s->y)",core)

if __name__=="__main__":
    unittest.main()

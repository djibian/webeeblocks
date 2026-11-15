#!/usr/bin/env python3
"""Draft A7 native witness source/negative import contract (not a flight PASS)."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/ci"))
import run_classroom_mini_gp_geometry as witness  # noqa: E402
import run_classroom_mini_gp_native_observer as observer  # noqa: E402
import run_classroom_mini_gp_ground_start as ground_start  # noqa: E402
import run_classroom_mini_gp_foreign_scene as foreign_scene  # noqa: E402
import run_classroom_mini_gp_wrong_timestep as wrong_step  # noqa: E402


class MiniGrandPrixNativeContract(unittest.TestCase):
    def test_separate_genuine_school_worlds_and_native_witness_only(self):
        l = witness.compose("L")
        r = witness.compose("R")
        self.assertNotEqual(l, r)
        for letter, world in (("L", l), ("R", r)):
            self.assertTrue(world.startswith("#VRML_SIM R2025a utf8\n"))
            self.assertEqual(world.count('controller "progression_mini_gp_geometry_probe"'), 1)
            self.assertNotIn('controller "crazyflie_runtime_v2"', world)
            self.assertNotIn('controller "crazyflie_classroom_v2"', world)
            self.assertEqual(world.count(witness.MARKER), 1)
            self.assertEqual(world.count(" Robot {"), 1)
            self.assertEqual(world.count(" Solid {"), 9)
            self.assertEqual(world.count("boundingObject Box"), 9)
            self.assertEqual(world.count(f"DEF WEBEEBLOCKS_MINI_GP_{letter}_SCENE Group"), 1)
            self.assertNotIn(f"DEF WEBEEBLOCKS_MINI_GP_{'R' if letter=='L' else 'L'}_SCENE", world)

    def test_invalid_or_ambiguous_scene_fails_closed_before_launch(self):
        for value in (None, 1, "", "B", "l", "LR"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                witness.compose(value)
        valid = (ROOT / "worlds/scenes/mini-grand-prix-l-v1.wbo").read_text(encoding="utf-8")
        for corrupt in (valid+valid, valid.replace("boundingObject Box", "geometry Box", 1),
                        valid.replace("ACTIVITY7_L_CLOSED_PANEL Solid", "ACTIVITY7_L_GHOST Solid"),
                        valid.replace('controller "progression_mini_grand_prix_v1"',
                                      'controller "crazyflie_runtime_v2"'),
                        valid.replace("supervisor TRUE", "supervisor FALSE", 1),
                        valid.replace(" Robot {", " Group {", 1),
                        valid+'\nDEF WEBEEBLOCKS_MINI_GP_R_SCENE Group {}\n'):
            # Replacing the panel label is structurally still 9 colliders,
            # but the exact native C attestation refuses it; the other bad
            # compositions must be rejected before even reaching Webots.
            if "_GHOST" not in corrupt:
                with self.assertRaises(ValueError):
                    witness.compose("L", scene=corrupt)
        with self.assertRaises(ValueError):
            witness.compose("L", source="#VRML_SIM R2025a utf8\n")

    def test_native_observer_has_contact_positive_controls_and_no_student_authority(self):
        native = (ROOT / "controllers/progression_mini_gp_geometry_probe/"
                  "progression_mini_gp_geometry_probe.c").read_text(encoding="utf-8")
        for token in ("wb_supervisor_node_get_from_def", "wb_supervisor_node_get_contact_points",
                      "wb_supervisor_node_enable_contact_points_tracking",
                      "wb_supervisor_node_reset_physics", "range_front",
                      "OPEN_BAR", "CLOSED_PANEL", "gravity_contact",
                      "WEBEEBLOCKS_A7_NATIVE_PASS", "pupil_wbb=UNPROVEN"):
            self.assertIn(token, native)
        self.assertNotIn("wb_motor_set_velocity", native)
        self.assertNotIn("Blockly.", native)
        self.assertNotIn("wb_robot_set_mode", native)

    def test_real_supervisor_requires_correct_native_scene_and_rejects_false_start(self):
        for letter in "LR":
            with self.subTest(variant=letter):
                source = observer.compose(letter)
                self.assertEqual(source.count(observer.MARKER), 1)
                self.assertEqual(source.count('controller "progression_mini_grand_prix_v1"'), 1)
                self.assertEqual(source.count('controller "progression_mini_gp_geometry_probe"'), 1)
                self.assertEqual(source.count('customData "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1"'), 1)
                self.assertEqual(source.count("Mini Grand Prix native evaluator"), 1)
                self.assertEqual(source.count(" Robot {"), 1)
                self.assertIn('Pose { translation -1.40 0 0.002 children [\n    Shape', source)
                self.assertNotIn('controller "crazyflie_runtime_v2"', source)
                self.assertNotIn('controller "crazyflie_classroom_v2"', source)
                self.assertEqual(source.count(" Solid {"), 9)
        for bad in (None, "", "B", "LR", 1):
            with self.subTest(untrusted=bad), self.assertRaises(ValueError):
                observer.compose(bad)
        native = (ROOT / "controllers/progression_mini_grand_prix_v1/"
                  "progression_mini_grand_prix_v1.c").read_text(encoding="utf-8")
        for token in ("WB_A7_SCENE_CHILDREN 29", "attest_scene(&variant)",
                      "solid_at(&check)", "unique_vehicle()",
                      "wb_supervisor_node_get_contact_points",
                      "wb_supervisor_node_enable_contact_points_tracking",
                      "wb_supervisor_node_get_orientation",
                      "attempt_token(data,&attempt)",
                      "completed_token(data,mission.attempt)",
                      "wb_mini_sample_mission(&mission,&sample)",
                      "WB_MINI_NATIVE_FIRST", "WB_MINI_NATIVE_RESULT",
                      "WB_MINI_NATIVE_FATAL"):
            self.assertIn(token, native)
        for forbidden in ("wb_motor_set_", "wb_supervisor_node_reset_physics",
                          "radio_link", "Blockly.", "wb_robot_set_mode"):
            self.assertNotIn(forbidden, native)
        runner = (ROOT / "tools/ci/run_classroom_mini_gp_native_observer.py").read_text(
            encoding="utf-8")
        self.assertIn('"motorized_flight": False', runner)
        self.assertIn('"pupil_program_tested": False', runner)
        self.assertIn('"status=achieved" in data', runner)
        workflow = (ROOT / ".github/workflows/ci-progression-a7-draft.yml").read_text(
            encoding="utf-8")
        self.assertIn("run_classroom_mini_gp_native_observer.py", workflow)
        self.assertIn("test -s progression_mini_grand_prix_v1", workflow)
        self.assertNotIn("name: CI Gate\n", workflow)

    def test_native_a7_observer_rejects_both_merged_a4_scene_families(self):
        """The native oracle cannot admit A7 with another mission's colliders."""
        native = (ROOT / "controllers/progression_mini_grand_prix_v1/"
                  "progression_mini_grand_prix_v1.c").read_text(encoding="utf-8")
        admission = native.split("static int attest_scene(char *variant) {", 1)[1]
        admission = admission.split("static WbNodeRef unique_vehicle(void)", 1)[0]
        for identity in ("WEBEEBLOCKS_DECISION_A_SCENE",
                         "WEBEEBLOCKS_DECISION_B_SCENE"):
            with self.subTest(identity=identity):
                self.assertIn(
                    'wb_supervisor_node_get_from_def("' + identity + '")',
                    admission)
        for letter in "LR":
            with self.subTest(variant=letter):
                school = witness.compose(letter)
                self.assertNotIn("DEF WEBEEBLOCKS_DECISION_A_SCENE", school)
                self.assertNotIn("DEF WEBEEBLOCKS_DECISION_B_SCENE", school)


    def test_four_native_mixed_worlds_use_real_six_collider_a4_assets(self):
        for letter in "LR":
            for a4 in "AB":
                with self.subTest(a7=letter, a4=a4):
                    world=foreign_scene.compose(letter,a4)
                    self.assertEqual(world.count(foreign_scene.MARKER),1)
                    self.assertEqual(world.count(" Solid {"),15)
                    self.assertEqual(world.count("boundingObject Box"),15)
                    self.assertEqual(world.count(
                        "DEF WEBEEBLOCKS_MINI_GP_"+letter+"_SCENE Group"),1)
                    self.assertEqual(world.count(
                        "DEF WEBEEBLOCKS_DECISION_"+a4+"_SCENE Group"),1)
                    self.assertEqual(world.count(
                        'controller "progression_mini_grand_prix_v1"'),1)
                    self.assertEqual(world.count(
                        'controller "progression_mini_gp_geometry_probe"'),1)
                    self.assertEqual(world.count('controller "<none>"'),1)
                    self.assertNotIn("WB_MINI_NATIVE_READY",world)
                    self.assertNotIn("WB_MINI_NATIVE_RESULT",world)
        for invalid in ((None,"A"),("L",None),("L","C"),("l","A")):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                foreign_scene.compose(*invalid)
        run=(ROOT/"tools/ci/run_classroom_mini_gp_foreign_scene.py").read_text(
            encoding="utf-8")
        self.assertIn("A7_FOREIGN_A4_NATIVE_ALL_REJECTED",run)
        self.assertIn("data.count(FATAL) != 1",run)
        self.assertIn('"WB_MINI_NATIVE_READY" in data',run)
        self.assertIn('"WB_MINI_NATIVE_RESULT" in data',run)

    def test_wrong_physics_cadence_is_rejected_before_a7_ready(self):
        """The 40-ms landing sample gap must not admit a 64-ms native world."""
        native = (ROOT / "controllers/progression_mini_grand_prix_v1/"
                  "progression_mini_grand_prix_v1.c").read_text(encoding="utf-8")
        admission = native.split("int main(void) {", 1)[1].split(
            "WbNodeRef craft=unique_vehicle();", 1)[0]
        self.assertIn("if(step!=32)", admission)
        self.assertIn("WB_MINI_NATIVE_FATAL invalid timestep=%d expected=32", admission)
        self.assertLess(admission.index("if(step!=32)"),
                        admission.index("if(!attest_scene(&variant))"))
        self.assertNotIn("WB_MINI_NATIVE_READY", admission)
        for letter in "LR":
            with self.subTest(variant=letter):
                original = observer.compose(letter)
                mutant = wrong_step.compose(letter)
                self.assertEqual(original.count("basicTimeStep 32"), 1)
                self.assertEqual(mutant.count("basicTimeStep 64"), 1)
                self.assertEqual(mutant.count(wrong_step.MARKER), 1)
                self.assertEqual(
                    mutant.replace("basicTimeStep 64", "basicTimeStep 32").replace(
                        "\n" + wrong_step.MARKER + "\n", "\n"),
                    original)
                self.assertEqual(mutant.count(" Solid {"), 9)
                self.assertEqual(mutant.count("boundingObject Box"), 9)
        for invalid in (None, "", "l", "X", 1):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                wrong_step.compose(invalid)
        runner = (ROOT / "tools/ci/run_classroom_mini_gp_wrong_timestep.py").read_text(
            encoding="utf-8")
        self.assertIn("data.count(FATAL) != 1", runner)
        self.assertIn('"WB_MINI_NATIVE_READY" in data', runner)
        self.assertIn('"WB_MINI_NATIVE_RESULT" in data', runner)
        workflow = (ROOT / ".github/workflows/ci-progression-a7-draft.yml").read_text(
            encoding="utf-8")
        self.assertIn("python3 tools/ci/run_classroom_mini_gp_wrong_timestep.py", workflow)

    def test_near_floor_obstacle_contacts_cannot_be_mistaken_for_floor(self):
        native=(ROOT/"controllers/progression_mini_grand_prix_v1/"
                "progression_mini_grand_prix_v1.c").read_text(encoding="utf-8")
        self.assertIn("wb_supervisor_node_get_id(obstacle)",native)
        self.assertIn(
            "wb_supervisor_node_get_contact_points(colliders[j],false,&n)",native)
        self.assertIn(
            "wb_supervisor_node_enable_contact_points_tracking(obstacle,step,false)",
            native)
        self.assertIn("WB_MINI_NATIVE_COLLIDER_CONTACT",native)
        self.assertIn("sample.contact=native_contact(craft,colliders)",native)
        self.assertLess(
            native.index("wb_supervisor_node_get_contact_points(colliders[j],false,&n)"),
            native.index("if(fabs(p[2])>0.025)return 1;"))
        # This was empirically falsified: point.node_id on a queried obstacle
        # was the obstacle ID (277), not the actual craft ID (59).
        self.assertNotIn("points[i].node_id==collider_ids[j]",native)
        self.assertLess(native.index("WB_MINI_NATIVE_COLLIDER_CONTACT"),
                        native.index("WB_MINI_NATIVE_FIRST"))
        import run_classroom_mini_gp_low_contact as low
        for letter in "LR":
            for part in ("CORNER_FRONT","CLOSED_PANEL"):
                with self.subTest(letter=letter,part=part):
                    world=low.compose(letter,part)
                    self.assertEqual(world.count(low.MARKER),1)
                    self.assertEqual(world.count(" Solid {"),9)
                    self.assertEqual(world.count("boundingObject Box"),9)
                    self.assertEqual(world.count(
                        'controller "progression_mini_gp_geometry_probe"'),1)
                    self.assertEqual(world.count(
                        'controller "progression_mini_grand_prix_v1"'),1)
                    self.assertEqual(world.count(
                        f'customData "WEBEEBLOCKS_A7_LOW_CONTACT_{part}_V1"'),1)
                    self.assertNotIn('customData "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1"',world)
        for args in ((None,"CORNER_FRONT"),("L","OPEN_BAR"),
                     ("Z","CLOSED_PANEL"),("R",None)):
            with self.subTest(invalid=args),self.assertRaises(ValueError):
                low.compose(*args)
        wf=(ROOT/".github/workflows/ci-progression-a7-draft.yml").read_text(
            encoding="utf-8")
        self.assertIn("run_classroom_mini_gp_low_contact.py",wf)
        self.assertIn("ci-artifacts/progression-mini-gp-low-contact/",wf)

    def test_grounded_start_is_a_real_native_observation_not_a_teleport(self):
        for letter in "LR":
            with self.subTest(variant=letter):
                world = ground_start.compose(letter)
                self.assertEqual(world.count(ground_start.MARKER), 1)
                self.assertEqual(world.count(
                    'customData "WEBEEBLOCKS_A7_GROUND_PREFLIGHT_V1"'), 1)
                self.assertEqual(world.count(
                    '  translation -1.4 0 0.015\n'), 1)
                self.assertEqual(world.count(
                    'controller "progression_mini_gp_geometry_probe"'), 1)
                self.assertEqual(world.count(
                    'controller "progression_mini_grand_prix_v1"'), 1)
                self.assertNotIn('controller "crazyflie_runtime_v2"', world)
                self.assertNotIn('controller "crazyflie_classroom_v2"', world)
        for bad in ("", "B", "LR", None, 7):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                ground_start.compose(bad)
        native_probe = (ROOT /
            "controllers/progression_mini_gp_geometry_probe/"
            "progression_mini_gp_geometry_probe.c").read_text(encoding="utf-8")
        for token in ("WEBEEBLOCKS_A7_GROUND_PREFLIGHT_V1",
                      "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2",
                      "A7_NATIVE_GROUND_TOKEN_RELEASED",
                      "A7_NATIVE_GROUND_VALID", "floor_hits<1",
                      "ground-control not physically settled"):
            self.assertIn(token, native_probe)
        self.assertNotIn("wb_motor_set_", native_probe)
        runner = (ROOT / "tools/ci/run_classroom_mini_gp_ground_start.py"
                  ).read_text(encoding="utf-8")
        for token in ("WB_MINI_NATIVE_FIRST", "WB_MINI_NATIVE_ATTEMPT",
                      "A7_NATIVE_GROUND_VALID",
                      "release_t < 1.0", "math.hypot(vx, vy) > .120",
                      '"WB_MINI_NATIVE_RESULT " in text',
                      '\"motorized_flight\": False',
                      '\"pupil_program_tested\": False'):
            self.assertIn(token, runner)


if __name__ == "__main__":
    unittest.main()

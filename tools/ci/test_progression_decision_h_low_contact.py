#!/usr/bin/env python3
"""Fail closed if A4 again labels genuine near-floor Solids as plain Floor.

The native R2025a physical oracle is tools/ci/run_classroom_decision_h_low_contact.py.
A source test alone does NOT prove the Webots contact event occurred.
"""
from pathlib import Path
import ast
import unittest

ROOT = Path(__file__).resolve().parents[2]
OBSERVER = ROOT / "controllers/progression_decision_h_v1/progression_decision_h_v1.c"
PROBE = ROOT / "controllers/progression_decision_h_range_probe/progression_decision_h_range_probe.c"
RUNNER = ROOT / "tools/ci/run_classroom_decision_h_low_contact.py"
DRAFT = ROOT / ".github/workflows/ci-progression-a4-draft.yml"
CANONICAL = ROOT / ".github/workflows/ci-runtime.yml"


class A4LowContactTests(unittest.TestCase):
    def test_observer_checks_six_real_solids_before_floor_fallback(self):
        source = OBSERVER.read_text(encoding="utf-8")
        self.assertIn("#define WB_DH_COLLIDERS 6", source)
        for part in ("H_LEFT", "H_RIGHT", "H_BAR", "THRESHOLD",
                     "CORRIDOR_LEFT", "CORRIDOR_RIGHT"):
            self.assertIn('"' + part + '"', source)
        self.assertIn("wb_supervisor_node_get_from_def(def)", source)
        self.assertIn("wb_supervisor_node_enable_contact_points_tracking(obstacle, step, false)", source)
        self.assertIn("wb_supervisor_node_get_contact_points(colliders[j], false, &n)", source)
        self.assertIn("WEBEEBLOCKS_DECISION_H_COLLIDER_CONTACT type=%s", source)
        self.assertIn("obstacle_contact(craft, colliders,", source)
        self.assertIn("&sample.floor_contact);", source)
        self.assertIn("*floor_contact = floor_seen;", source)
        self.assertIn("return -1;", source)
        native = source.split("static int obstacle_contact(", 1)[1].split(
            "static void publish(", 1)[0]
        self.assertLess(
            native.index("wb_supervisor_node_get_contact_points(colliders[j], false, &n)"),
            native.index("wb_supervisor_node_get_contact_points(craft, true, &count)"))
        self.assertLess(native.index("return 1;"), native.index("if (fabs(p[2]) > 0.025)"))
        self.assertNotIn("wb_supervisor_node_set_velocity", source)
        self.assertNotIn("wb_motor_set_", source)
        self.assertNotIn("radio_link", source)

    def test_genuine_unpowered_r2025a_physical_witness_is_required(self):
        probe = PROBE.read_text(encoding="utf-8")
        src = RUNNER.read_text(encoding="utf-8")
        ast.parse(src, filename=str(RUNNER))
        for token in (
            "WEBEEBLOCKS_A4_LOW_CONTACT_V1",
            "wb_supervisor_node_get_contact_points(colliders[j],false,&n)",
            "wb_supervisor_field_set_sf_vec3f(position_field,p)",
            "wb_supervisor_node_reset_physics(self)",
            "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %d",
            "WEBEEBLOCKS_DECISION_H_LOW_PHYSICAL variant=%c",
            "WEBEEBLOCKS_DECISION_H_LOW_END variant=%c",
            "WEBEEBLOCKS_DECISION_H_FLOOR_ONLY variant=%c",
            "floor_contacts=%d center_z=%.9f motors=OFF",
            "for(int tick=0;tick<65;++tick)",
            "last_contact_count=nf",
            "++floor_contacts",
            "no actual Floor contacts during settling",
        ):
            self.assertIn(token, probe)
        for token in (
            "run_classroom_decision_h_range as range_witness",
            'source.count(" Solid {") != 6',
            'source.count("boundingObject Box") != 6',
            "WEBEEBLOCKS_DECISION_H_COLLIDER_CONTACT",
            "WEBEEBLOCKS_DECISION_H_FIRST_SAMPLE attempt=1",
            '"floor_only_first_sample": True',
            '"native_floor_contacts": int(ground[0][1])',
            "ground_ok = (len(ground) == 1",
            "floor_only_accepted=true",
            "if not p or not n or len(stop) != 1",
            "no_pupil_flight_or_mission_success_claim",
            "refusing cleanup of altered physical world",
        ):
            self.assertIn(token, src)
        # This previously failed despite genuine contacts: double-escaped \d
        # erroneously matched a literal slash rather than the native count.
        self.assertIn(r"floor_contacts=(\d+) center_z=", src)
        self.assertNotIn(r"floor_contacts=(\\d+) center_z=", src)
        self.assertNotIn("wb_motor_set_", probe)

    def test_draft_and_ready_native_gates_both_execute_contact_witness(self):
        for path in (DRAFT, CANONICAL):
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn("python3 tools/ci/run_classroom_decision_h_low_contact.py", text)
                self.assertIn("python3 -m unittest tools.ci.test_progression_decision_h_low_contact", text)
                self.assertIn("ci-artifacts/progression-decision-h-low-contact/", text)
                self.assertIn("if: always()", text)


if __name__ == "__main__":
    unittest.main()

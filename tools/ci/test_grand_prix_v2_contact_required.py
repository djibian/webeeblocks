"""Host-schema counterexamples for mandatory FOUR-L-arm native contact evidence.

All samples in these tests are synthetic: they test the validator's refusal
boundary only. Only the separate R2025a runner can establish a physical PASS.
"""
import copy
import unittest

from tools.ci.run_grand_prix_v2_contact_native import CLAIM, check_native
from tools.grand_prix.route_courses_v2 import reference_course
from tools.grand_prix.route_solid_v2 import corner_boxes, HEIGHT


class FourArmNativeContactSchemaTests(unittest.TestCase):
    def setUp(self):
        self.course = reference_course(5)
        arms = corner_boxes(self.course.route)
        witnesses = []
        for index, box in enumerate(arms):
            node_id = 100 + index
            coords = [box.x, box.y, HEIGHT / 2]
            # Six 8-ms ticks per arm: three free, then three with a real-hit
            # *shape*. This is schema-only data, never a Webots observation.
            free = [dict(time_ms=8 * (index * 6 + tick),
                         contacts=[], target_contacts=[])
                    for tick in (1, 2, 3)]
            collision = [dict(time_ms=8 * (index * 6 + tick),
                              contacts=[dict(node_id=1, point=coords)],
                              target_contacts=[dict(node_id=node_id, point=coords)])
                         for tick in (4, 5, 6)]
            witnesses.append(dict(target=box.name, target_node_id=node_id,
                                  free=free, collision=collision))
        first = witnesses[0]
        self.record = dict(
            claim=CLAIM, configuration=self.course.identifier,
            webots="R2025a", timestep_ms=8,
            source="Robot.getContactPoints(includeDescendants=True)",
            target_source="Solid.getContactPoints(includeDescendants=False)",
            **first, additional=witnesses[1], second_corner=witnesses[2:])

    def test_all_four_distinct_fresh_reciprocal_records_are_required(self):
        # Structural acceptance is NOT a native or mission success.
        check_native(self.record, self.course)

    def test_missing_or_truncated_second_corner_is_rejected(self):
        for mutation in ("missing", "truncated", "wrong-schema"):
            with self.subTest(mutation=mutation):
                record = copy.deepcopy(self.record)
                if mutation == "missing":
                    record.pop("second_corner")
                elif mutation == "truncated":
                    record["second_corner"].pop()
                else:
                    record["second_corner"][0].pop("target_contacts", None)
                    record["second_corner"][0].pop("collision")
                with self.assertRaises(RuntimeError):
                    check_native(record, self.course)

    def test_second_corner_reused_id_and_wrong_arm_are_rejected(self):
        for field in ("target_node_id", "target"):
            with self.subTest(field=field):
                record = copy.deepcopy(self.record)
                record["second_corner"][0][field] = record["additional"][field]
                with self.assertRaises(RuntimeError):
                    check_native(record, self.course)

    def test_cross_corner_stale_time_is_rejected(self):
        record = copy.deepcopy(self.record)
        for phase in ("free", "collision"):
            for observation in record["second_corner"][0][phase]:
                observation["time_ms"] -= 48
        with self.assertRaisesRegex(RuntimeError, "stale|clock"):
            check_native(record, self.course)

    def test_second_corner_without_reciprocal_contact_is_rejected(self):
        record = copy.deepcopy(self.record)
        for observation in record["second_corner"][1]["collision"]:
            observation["target_contacts"] = []
        with self.assertRaisesRegex(RuntimeError, "reciprocal"):
            check_native(record, self.course)

    def test_contact_in_free_baseline_or_outside_arm_is_rejected(self):
        for mode in ("free", "outside"):
            with self.subTest(mode=mode):
                record = copy.deepcopy(self.record)
                arm = record["second_corner"][1]
                if mode == "free":
                    arm["free"][0]["contacts"] = [copy.deepcopy(
                        arm["collision"][0]["contacts"][0])]
                else:
                    for observation in arm["collision"]:
                        for contact in observation["target_contacts"]:
                            contact["point"][2] = HEIGHT + 1
                with self.assertRaises(RuntimeError):
                    check_native(record, self.course)


if __name__ == "__main__":
    unittest.main()

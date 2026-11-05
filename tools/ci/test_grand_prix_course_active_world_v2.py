"""Host-only active-scene contract tests: never a native Webots/GUI PASS."""
from dataclasses import replace
import itertools
import unittest
from unittest.mock import patch

from tools.grand_prix import course_active_world_v2 as active
from tools.grand_prix.course_static_world_v2 import (
    course_physical_boxes, static_course_world,
)
from tools.grand_prix.route_courses_v2 import plan_course, reference_course


class ActiveCourseWorldTests(unittest.TestCase):
    def test_twelve_reference_scenes_preserve_all_physics_and_host_identities(self):
        for index in range(12):
            course = reference_course(index)
            with self.subTest(index=index, course=course.identifier):
                static = static_course_world(course)
                scene = active.active_course_world(course)
                args = f'controllerArgs [ "{course.identifier}" ]'
                self.assertEqual(scene.count(args), 2)
                self.assertEqual(scene.count("controllerArgs"), 2)
                self.assertEqual(scene.count('DEF GP_ROUTE_EVALUATOR Robot {'), 1)
                self.assertEqual(scene.count('controller "grand_prix_route_flight"'), 1)
                self.assertEqual(scene.count('window "grand_prix_route_v2"'), 1)
                self.assertEqual(scene.count('controller "grand_prix_route_evaluator"'), 1)
                self.assertEqual(scene.count('description ""'), 1)
                self.assertEqual(scene.count("basicTimeStep 8"), 1)
                self.assertEqual(scene.count(
                    f'DEF {active.DEDICATED_WORLD_DEF} WorldInfo {{'), 1)
                self.assertNotIn(active.DEDICATED_WORLD_DEF, static)
                self.assertNotIn('controller "grand_prix_u_flight"', scene)
                self.assertNotIn('controller "<none>"', scene)
                self.assertEqual(scene.count('boundingObject Box { size'),
                                 len(course_physical_boxes(course)))
                for box in course_physical_boxes(course):
                    self.assertEqual(scene.count(f'DEF {box.name} Solid'), 1)
                before, separator, evaluator = scene.partition(
                    'DEF GP_ROUTE_EVALUATOR Robot {')
                self.assertTrue(separator)
                self.assertNotIn('boundingObject', evaluator,
                                 "route evaluator must not introduce a new physical body")
                self.assertNotIn('children [', evaluator)
                self.assertIn('synchronization TRUE', evaluator)
                restored = before.replace(
                    f'DEF {active.DEDICATED_WORLD_DEF} WorldInfo {{', 'WorldInfo {', 1
                ).replace(
                    "Grand Prix variable EXPERIMENTAL " + course.identifier,
                    "Grand Prix STATIC " + course.identifier, 1
                ).replace(
                    f'  controller "{active.FLIGHT_CONTROLLER}"\n'
                    f'  window "{active.ROBOT_WINDOW}"\n'
                    f'  controllerArgs [ "{course.identifier}" ]\n'
                    '  supervisor TRUE\n', active._INERT_FLIGHT, 1
                )
                self.assertEqual(restored, static,
                                 "active scene must preserve every static collider/guide byte")

    def test_every_length_turn_gate_combination_keeps_two_equal_arguments(self):
        checked = 0
        for lengths in itertools.product((2., 2.5, 3.), repeat=3):
            for turns in itertools.product(("G", "D"), repeat=2):
                for gates in (1, 2, 3):
                    course = plan_course(17, lengths, turns, gates)
                    scene = active.active_course_world(course)
                    with self.subTest(course=course.identifier):
                        self.assertEqual(scene.count(
                            f'controllerArgs [ "{course.identifier}" ]'), 2)
                        self.assertEqual(scene.count('DEF GP_V2_H_'), 3*gates)
                        self.assertEqual(scene.count('DEF GP_V2_L_'), 4)
                        self.assertEqual(scene.count('DEF GP_V2_FINAL_'), 4)
                        self.assertEqual(scene.count(
                            f'DEF {active.DEDICATED_WORLD_DEF} WorldInfo {{'), 1)
                    checked += 1
        self.assertEqual(checked, 324)

    def test_invalid_or_forged_course_never_creates_a_scene(self):
        course = reference_course(5)
        for invalid in (
            None, True, (), replace(course, count=course.count + 1),
            replace(course, gates=course.gates[:-1]),
            replace(course, route=reference_course(6).route),
        ):
            with self.subTest(invalid=str(invalid)[:80]):
                with self.assertRaises((TypeError, ValueError)):
                    active.active_course_world(invalid)

    def test_changed_static_anchors_and_hidden_evaluator_fail_closed(self):
        course = reference_course(5)
        inert = static_course_world(course)
        title = "Grand Prix STATIC " + course.identifier
        variants = (
            inert.replace('  controller "<none>"\n', '  controller "other"\n', 1),
            inert.replace('  window "<none>"\n', '  window "other"\n', 1),
            inert.replace('  supervisor TRUE\n', '  supervisor FALSE\n', 1),
            inert.replace(title, "unexpected title", 1),
            inert + 'DEF GP_ROUTE_EVALUATOR Robot { }\n',
            inert.replace('  controller "<none>"\n',
                          '  controller "<none>"\n  controller "<none>"\n', 1),
            inert.replace('  controller "<none>"\n',
                          '  controller "<none>"\n  controllerArgs [ "injected" ]\n', 1),
            inert + '# unexpected trailing content\n',
            inert.replace('WorldInfo {', 'Group {', 1),
            inert.replace('WorldInfo {',
                          f'DEF {active.DEDICATED_WORLD_DEF} WorldInfo {{', 1),
        )
        for index, forged in enumerate(variants):
            with self.subTest(index=index):
                with patch.object(active, "static_course_world", return_value=forged):
                    with self.assertRaises(RuntimeError):
                        active.active_course_world(course)


if __name__ == "__main__":
    unittest.main()

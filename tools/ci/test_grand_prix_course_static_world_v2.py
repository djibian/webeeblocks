"""Host-only full variable course static scene checks; no Webots PASS."""
from dataclasses import replace
import itertools
import unittest

from tools.grand_prix.route_courses_v2 import plan_course, reference_course
from tools.grand_prix.route_solid_v2 import visual_guides
from tools.grand_prix.course_footprint_v2 import red_boundary_marks
from tools.grand_prix.course_static_world_v2 import (
    course_physical_boxes, static_course_world,
)


class StaticCourseWorldTests(unittest.TestCase):
    def test_324_courses_have_all_physical_solids_and_single_boundary(self):
        cases = 0
        for lengths in itertools.product((2., 2.5, 3.), repeat=3):
            for turns in itertools.product(('G', 'D'), repeat=2):
                for count in (1, 2, 3):
                    course = plan_course(17, lengths, turns, count)
                    world = static_course_world(course)
                    manifest = course_physical_boxes(course)
                    with self.subTest(course=course.identifier):
                        cases += 1
                        self.assertEqual(len(manifest), 8 + 3*count)
                        self.assertEqual(len({box.name for box in manifest}), len(manifest))
                        self.assertEqual(
                            world.count('boundingObject Box { size'),
                            len(manifest))
                        self.assertEqual(world.count('locked TRUE'), len(manifest))
                        self.assertEqual(world.count('DEF GP_V2_L_'), 4)
                        self.assertEqual(world.count('DEF GP_V2_H_'), 3*count)
                        self.assertEqual(world.count('DEF GP_V2_FINAL_'), 4)
                        self.assertEqual(world.count('DEF GP_V2_WHITE_'), 3)
                        self.assertEqual(
                            world.count('DEF GP_V2_COURSE_RED_'),
                            len(red_boundary_marks(course.route)))
                        self.assertEqual(world.count('controller "<none>"'), 1)
                        self.assertEqual(world.count('window "<none>"'), 1)
                        self.assertEqual(world.count('EXTERNPROTO '), 4)
                        self.assertIn('basicTimeStep 8', world)
                        self.assertIn('Grand Prix STATIC ' + course.identifier, world)
                        self.assertNotIn('DEF GP_ROUTE_EVALUATOR', world)
                        self.assertNotIn('controller "grand_prix_u_flight"', world)
                        self.assertNotIn('controller "grand_prix_route_v2"', world)
                        self.assertEqual(world, static_course_world(course))
                        for box in manifest:
                            self.assertEqual(world.count('DEF ' + box.name + ' Solid'), 1)
        self.assertEqual(cases, 324)

    def test_no_historic_corridor_red_guides_survive_or_collide(self):
        course = reference_course(5)
        world = static_course_world(course)
        old = visual_guides(course.route)
        for guide in old:
            if guide.startswith('DEF GP_V2_RED_'):
                self.assertNotIn(guide, world)
        for index, (x, y, sx, sy) in enumerate(red_boundary_marks(course.route)):
            red = f'DEF GP_V2_COURSE_RED_{index} Pose'
            self.assertIn(red, world)
        # All course boundary marks are purely decorative: Pose/Shape,
        # without colliders; physical solids remain a separate manifest.
        self.assertEqual(world.count('boundingObject Box { size'),
                         len(course_physical_boxes(course)))

    def test_one_manifest_order_for_canonical_course_and_forgery_refusal(self):
        for index in range(12):
            course = reference_course(index)
            manifest = course_physical_boxes(course)
            names = tuple(box.name for box in manifest)
            self.assertEqual(names[:4], (
                'GP_V2_L_0_0', 'GP_V2_L_0_1',
                'GP_V2_L_1_0', 'GP_V2_L_1_1'))
            gate_names = tuple(
                f'GP_V2_H_{gate.leg_index}_{part}'
                for gate in course.gates
                for part in ('LEFT', 'RIGHT', 'BEAM'))
            self.assertEqual(names[4:4+3*course.count], gate_names)
            self.assertEqual(names[-4:], tuple('GP_V2_FINAL_' + part
                             for part in ('LEFT', 'RIGHT', 'BEAM', 'PANEL')))
        course = reference_course(3)
        for invalid in (None, (), True, replace(course, count=course.count + 1),
                        replace(course, gates=course.gates[:-1])):
            with self.subTest(invalid=type(invalid).__name__):
                with self.assertRaises((TypeError, ValueError)):
                    course_physical_boxes(invalid)
                with self.assertRaises((TypeError, ValueError)):
                    static_course_world(invalid)


if __name__ == '__main__':
    unittest.main()

"""Counterexamples for provisional, non-active physical open H geometry."""
from dataclasses import replace
import itertools
import unittest

from tools.grand_prix.route_courses_v2 import CoursePlan, plan_course
from tools.grand_prix.route_open_h_v2 import (
    BEAM_BOTTOM, BEAM_SPAN, HEIGHT, POST_LENGTH, POST_OFFSET,
    POST_THICKNESS, open_h_boxes,
)


class VariableOpenHTests(unittest.TestCase):
    def test_324_course_plans_three_visible_colliders_per_open_h(self):
        cases = 0
        for lengths in itertools.product((2., 2.5, 3.), repeat=3):
            for turns in itertools.product(('G', 'D'), repeat=2):
                for count in (1, 2, 3):
                    course = plan_course(17, lengths, turns, count)
                    boxes = open_h_boxes(course)
                    cases += 1
                    self.assertEqual(len(boxes), 3 * count)
                    self.assertEqual(len({b.name for b in boxes}), 3 * count)
                    self.assertEqual(boxes, open_h_boxes(course))
                    for gate, (left, right, beam) in zip(
                            course.gates,
                            (boxes[i:i + 3] for i in range(0, len(boxes), 3))):
                        leg = course.route.legs[gate.leg_index]
                        self.assertEqual(
                            [b.name for b in (left, right, beam)],
                            [f'GP_V2_H_{leg.index}_{part}'
                             for part in ('LEFT', 'RIGHT', 'BEAM')])
                        self.assertEqual((left.x, left.y),
                                         leg.at(gate.along, POST_OFFSET))
                        self.assertEqual((right.x, right.y),
                                         leg.at(gate.along, -POST_OFFSET))
                        self.assertEqual((beam.x, beam.y),
                                         leg.at(gate.along))
                        self.assertEqual((left.z, right.z), (HEIGHT / 2,) * 2)
                        self.assertEqual(beam.z - beam.sz / 2, BEAM_BOTTOM)
                        self.assertAlmostEqual(beam.z + beam.sz / 2, HEIGHT)
                        self.assertEqual((left.sz, right.sz, beam.sz),
                                         (HEIGHT, HEIGHT, HEIGHT - BEAM_BOTTOM))
                        dimensions = ((POST_LENGTH, POST_THICKNESS)
                                      if leg.direction % 2 == 0 else
                                      (POST_THICKNESS, POST_LENGTH))
                        self.assertEqual((left.sx, left.sy), dimensions)
                        self.assertEqual((right.sx, right.sy), dimensions)
                        self.assertEqual((beam.sx, beam.sy),
                                         ((.04, BEAM_SPAN) if leg.direction % 2 == 0
                                          else (BEAM_SPAN, .04)))
                        for part in (left, right, beam):
                            vrml = part.vrml()
                            self.assertIn('Solid {', vrml)
                            self.assertIn('locked TRUE', vrml)
                            self.assertEqual(vrml.count('geometry Box'), 1)
                            self.assertEqual(vrml.count('boundingObject Box'), 1)
                            self.assertNotIn('controller', vrml)
        self.assertEqual(cases, 324)

    def test_invalid_or_relabelled_gate_and_forged_course_fail_closed(self):
        course = plan_course(11, (2., 2.5, 3.), ('D', 'G'), 3)
        original = course.gates[0]
        broken = (
            replace(original, direction=(original.direction + 1) % 4),
            replace(original, along=float('nan')),
            replace(original, along=.2),
            replace(original, leg_index=3),
            replace(original, position=(99., 99.)),
        )
        for gate in broken:
            with self.assertRaises(ValueError):
                open_h_boxes(replace(course, gates=(gate,) + course.gates[1:]))
        with self.assertRaises(ValueError):
            open_h_boxes(replace(course, gates=course.gates[:2]))
        with self.assertRaises(ValueError):
            open_h_boxes(replace(course, gates=(original, original, course.gates[2])))
        with self.assertRaises(ValueError):
            open_h_boxes(CoursePlan(course.route, course.gates, 0))
        with self.assertRaises(ValueError):
            open_h_boxes(None)


if __name__ == '__main__':
    unittest.main()

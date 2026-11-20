"""Pure geometry invariants (no claim of native Webots validation)."""
from dataclasses import replace
import hashlib
import itertools
import math
import re
import unittest

from tools.grand_prix.course_active_world_v2 import active_course_world
from tools.grand_prix.course_static_world_v2 import course_physical_boxes, static_course_world
from tools.grand_prix.oracle_attempt_v2 import _hits_mission_body
from tools.grand_prix.oracle_gate_progress_v2 import FRAME_CLEAR
from tools.grand_prix.oracle_low_v2 import low_segment_allowed_v2
from tools.grand_prix.oracle_terminal_dwell_v2 import LANDING_TOL
from tools.grand_prix.progression_courses import progression_course
from tools.grand_prix.route_courses_v2 import reference_course
from tools.grand_prix.route_v2 import WIDTH, VERSION, build_route


class VariableRouteTests(unittest.TestCase):
    def test_a8_reference_scenes_match_the_original_bytes(self):
        baseline = hashlib.sha256()
        for index in range(12):
            course = reference_course(index)
            static = hashlib.sha256(static_course_world(course).encode()).hexdigest()
            active = hashlib.sha256(active_course_world(course).encode()).hexdigest()
            baseline.update(f'{course.identifier} {static} {active}\n'.encode())
        # All twelve static and active UTF-8 outputs at 0bdac3f108d8.
        self.assertEqual(baseline.hexdigest(),
                         'ca65d0eb304889dc83bc548d2ec64675a59115d6693f7353e9c21eec5abbbe3c')

    def test_progression_scenes_share_physical_components_and_all_lessons_can_compose(self):
        identifiers = set()
        for activity, count in enumerate((1, 1, 1, 3, 5, 5, 7), start=1):
            for variant in range(1, count + 1):
                course = progression_course(activity, variant)
                with self.subTest(course=course.identifier):
                    scene = static_course_world(course)
                    identifiers.add(course.identifier)
                    boxes = course_physical_boxes(course)
                    self.assertEqual(len(boxes), 2 * len(course.route.turns) + 3 * course.count + 4)
                    self.assertEqual(scene.count('boundingObject Box { size'), len(boxes))
                    self.assertTrue(all(f'DEF {box.name} Solid' in scene for box in boxes))
                    self.assertEqual(scene.count('DEF GP_V2_FINAL_PANEL Solid'), 1)
                    self.assertEqual(scene.count('DEF GP_ROUTE_BAND_MARKS Pose'), int(bool(course.gates)))
                    self.assertEqual(scene.count('DEF GP_V2_COURSE_RED_MARKS Pose'), 1)
                    self.assertEqual(tuple(map(int, re.findall(r'DEF GP_ROUTE_TARGET_(\d) Pose', scene))),
                                     course.pads)
                    self.assertIn('basicTimeStep 8', scene)
                    self.assertEqual(scene.count('controller "<none>"'), 1)
                    self.assertNotIn('controllerArgs', scene)
                    self.assertNotIn('GP_ROUTE_EVALUATOR', scene)
                    active = active_course_world(course)
                    self.assertEqual(active.count(f'controllerArgs [ "{course.identifier}" ]'), 2)
                    self.assertIn('controller "grand_prix_route_flight"', active)
                    self.assertIn('controller "grand_prix_route_evaluator"', active)
            with self.assertRaises(ValueError):
                progression_course(activity, count + 1)
        self.assertEqual(len(identifiers), 23)
        with self.assertRaises(ValueError):
            progression_course(8)
        with self.assertRaises(ValueError):
            static_course_world(replace(progression_course(5), required_pad=1))

    def test_progression_lengths_orientations_gates_and_pads(self):
        a1, a2, a3 = (progression_course(activity) for activity in (1, 2, 3))
        self.assertEqual((a1.route.lengths, a1.route.turns, a1.gates),
                         ((1.4, 1.8, 1.6), ('G', 'D'), ()))
        self.assertEqual(a2.route.lengths, (2.5,))
        self.assertEqual([(g.leg_index, g.along) for g in a2.gates], [(0, .8)])
        self.assertEqual(a3.route.lengths, (1.5, 1.5, 1.5))
        self.assertEqual([leg.direction for leg in a3.route.legs], [1, 2, 3])
        self.assertEqual([(g.leg_index, g.along) for g in a3.gates],
                         [(0, .75), (1, .75), (2, .75)])
        last = a3.route.legs[-1]
        pad_along, _ = last.local(a3.landing_position(a3.required_pad))
        self.assertGreater(pad_along, a3.gates[-1].along + FRAME_CLEAR)
        a4_targets = []
        for variant, length in enumerate((1., 1.4, 1.8), start=1):
            a4 = progression_course(4, variant)
            self.assertEqual(a4.route.lengths, (length,))
            self.assertEqual(a4.pads, (2,))
            along, lateral = a4.route.legs[-1].local(a4.landing_goal())
            self.assertEqual(lateral, .5)
            a4_targets.append(along)
        # One fixed longitudinal endpoint cannot land on all three courses.
        for left, right in itertools.pairwise(a4_targets):
            self.assertGreater(right - left, 2 * LANDING_TOL)
        for variant in range(1, 6):
            a5 = progression_course(5, variant)
            self.assertEqual(a5.route.lengths[-1], 2.5)
            self.assertEqual(a5.pads, (2, 3))
            leg = a5.route.legs[-1]
            along, offset = leg.local(a5.landing_position(a5.required_pad))
            self.assertEqual(offset, -.5 if a5.route.turns == ('G',) else .5)
            # Even the longitudinal lower bound is past the 2 m native ray
            # range. Verify it against the physical L extents, not its label.
            for box in course_physical_boxes(a5)[:2]:
                centre, _ = leg.local(box.position[:2])
                half_span = box.size[leg.direction % 2] / 2
                self.assertGreater(along - centre - half_span, 2.)
        self.assertEqual([progression_course(6, v).count for v in range(1, 6)],
                         [1, 1, 1, 0, 0])
        a7 = [progression_course(7, v) for v in range(1, 8)]
        self.assertEqual({c.route.turns for c in a7}, {('G',), ('D',)})
        self.assertEqual({tuple(g.leg_index for g in c.gates) for c in a7}, {(), (0,), (1,)})
        # Each direction must independently cover no H, first-leg H and
        # second-leg H: an aggregate-only set could conceal a missing case.
        for turn in ('G', 'D'):
            patterns = {tuple(g.leg_index for g in c.gates)
                        for c in a7 if c.route.turns == (turn,)}
            self.assertEqual(patterns, {(), (0,), (1,)})
        self.assertEqual(len({(c.route.lengths, c.route.turns,
                               tuple((g.leg_index, g.along) for g in c.gates))
                              for c in a7}), 7)
        self.assertGreater(len({c.route.lengths[0] for c in a7}), 1)
        self.assertGreater(len({c.route.lengths[1] for c in a7}), 1)
        for index, course in enumerate(a7, start=1):
            with self.subTest(a7_variant=index):
                self.assertEqual(len(course.route.legs), 2)
                self.assertEqual(len(course.route.turns), 1)
                self.assertLessEqual(len(course.gates), 1)
                self.assertEqual(course.pads, (1,))
                self.assertEqual(course.required_pad, 1)
                self.assertEqual(course.pad_distance_from_h, .70)
                self.assertEqual(course.landing_goal(), course.landing_position(1))
                for gate in course.gates:
                    leg = course.route.legs[gate.leg_index]
                    self.assertEqual(gate.position, leg.at(gate.along))
                    self.assertGreater(gate.along, .55)
                    self.assertLess(gate.along + .55, leg.length)

    def test_a2_altitude_and_physical_collision_refute_constant_height(self):
        course = progression_course(2)
        solids = course_physical_boxes(course)
        # Same GP thresholds for the entire allowed airborne altitude domain:
        # below 0.62 m outside the yellow band fails, at or above it the real
        # beam occupies the centreline up to 1.30 m.
        for z in (.1, .4, .619):
            self.assertFalse(low_segment_allowed_v2((.2, 0, z), (.3, 0, z),
                                                    course.route, course.gates))
        for z in (.62, .9, 1.165):
            self.assertTrue(_hits_mission_body((.45, 0, z), (1.15, 0, z), solids))
        # One admissible spatial sequence, without pilot/Blockly simulation.
        waypoints = ((.2, 0, .75), (.4, 0, .75), (.4, 0, .4),
                     (1.2, 0, .4), (1.2, 0, .75), (1.5, 0, .75))
        for before, after in zip(waypoints, waypoints[1:]):
            self.assertTrue(low_segment_allowed_v2(before, after, course.route, course.gates))
            self.assertFalse(_hits_mission_body(before, after, solids))

    def test_entire_length_turn_matrix(self):
        identifiers = set()
        for lengths in itertools.product((2, 2.5, 3), repeat=3):
            for turns in itertools.product(('G', 'D'), repeat=2):
                route = build_route(17, lengths, turns)
                self.assertEqual(route.identifier, build_route(17, lengths, turns).identifier)
                identifiers.add(route.identifier)
                self.assertEqual(route.lengths, tuple(float(v) for v in lengths))
                self.assertEqual(route.turns, turns)
                self.assertEqual(len(route.corners), 2)
                for i, leg in enumerate(route.legs):
                    self.assertAlmostEqual(math.dist(leg.start, leg.end), lengths[i])
                    self.assertEqual(leg.at(0), leg.start)
                    self.assertEqual(leg.at(leg.length), leg.end)
                    self.assertEqual(leg.local(leg.at(leg.length/2, .25)), (leg.length/2, .25))
                    if i < 2:
                        self.assertEqual(leg.end, route.legs[i+1].start)
                for i, corner in enumerate(route.corners):
                    self.assertEqual(corner.junction, route.legs[i].end)
                    for start, end in corner.arms:
                        self.assertEqual(start, corner.outer)
                        self.assertAlmostEqual(math.dist(start, end), WIDTH)
                    # Face of L is outside both incoming and outgoing half-width bands.
                    inc, out = route.legs[i:i+2]
                    self.assertAlmostEqual(abs(inc.local(corner.outer)[1]), WIDTH/2)
                    self.assertAlmostEqual(abs(out.local(corner.outer)[1]), WIDTH/2)
                center = route.landing_target(1)
                left = route.landing_target(2)
                right = route.landing_target(3)
                self.assertAlmostEqual(math.dist(center, left), .5)
                self.assertAlmostEqual(math.dist(center, right), .5)
                self.assertEqual(route.legs[-1].local(left)[1], .5)
                self.assertEqual(route.legs[-1].local(right)[1], -.5)
                self.assertLess(route.legs[-1].local(center)[0], route.legs[-1].length)
        self.assertEqual(len(identifiers), 3**3 * 2**2)

    def test_reproducible_identity_and_fail_closed_inputs(self):
        a = build_route(0, (2, 2.5, 3), ('G', 'D'))
        self.assertEqual(a.identifier, 'gp-route-v2-L2000-2500-3000-TGD-s0')
        self.assertEqual(a, build_route(0, [2., 2.5, 3.], ['G', 'D']))
        self.assertNotEqual(a.identifier, build_route(1, (2, 2.5, 3), ('G', 'D')).identifier)
        for seed in (True, -1, 65536, 1.2):
            with self.assertRaises(ValueError): build_route(seed, (2, 2, 2), ('G', 'G'))
        for lengths in ((2, 2), (2, 2, 2, 2), (2, float('nan'), 3), (True, 2, 3),
                        (2, 2.0001, 3), (1.5, 2, 3)):
            with self.assertRaises(ValueError): build_route(0, lengths, ('G', 'G'))
        for turns in (('G',), ('G', 'G', 'G'), ('G', 'X'), ('g', 'D'), (True, 'D')):
            with self.assertRaises(ValueError): build_route(0, (2, 2, 2), turns)
        for count in (0, 4, 2.0, True):
            with self.assertRaises(ValueError): a.landing_target(count)
        for value in (float('nan'), float('inf'), True):
            with self.assertRaises(ValueError): a.legs[0].at(value)
        with self.assertRaises(ValueError): a.legs[0].local((0., float('nan')))


    def test_provisional_gate_placements_are_directed_and_reproducible(self):
        from tools.grand_prix.route_courses_v2 import (
            LOW_BEFORE, LOW_AFTER, plan_course,
        )
        for lengths in itertools.product((2, 2.5, 3), repeat=3):
            for turns in itertools.product(('G', 'D'), repeat=2):
                for count in (1, 2, 3):
                    course = plan_course(17, lengths, turns, count)
                    self.assertEqual(course, plan_course(17, lengths, turns, count))
                    self.assertEqual(len(course.gates), count)
                    self.assertEqual(len({g.leg_index for g in course.gates}), count)
                    self.assertEqual(tuple(g.leg_index for g in course.gates),
                                     tuple(sorted(g.leg_index for g in course.gates)))
                    self.assertTrue(course.identifier.endswith('-H'+str(count)))
                    for g in course.gates:
                        leg = course.route.legs[g.leg_index]
                        self.assertEqual(g.direction, leg.direction)
                        self.assertEqual(g.position, leg.at(g.along))
                        self.assertEqual(leg.local(g.position), (g.along, 0.0))
                        self.assertGreater(g.along, LOW_BEFORE)
                        self.assertLess(g.along + LOW_AFTER, leg.length)
                        if g.leg_index < 2:
                            self.assertGreaterEqual(g.along - LOW_BEFORE, 0.35 - 1e-9)
                            self.assertGreaterEqual(leg.length - g.along - LOW_AFTER,
                                                    0.35 - 1e-9)
                        else:
                            # At least one band edge remains before the final
                            # nominal centre, but no swept clearance is claimed.
                            self.assertLess(g.along + LOW_AFTER,
                                            leg.length - 0.70)

    def test_twelve_pure_course_examples_cover_turns_counts_and_mixed_legs(self):
        from tools.grand_prix.route_courses_v2 import reference_course
        examples = [reference_course(i) for i in range(12)]
        self.assertEqual(len({c.identifier for c in examples}), 12)
        self.assertEqual({c.route.turns for c in examples},
                         {('G','G'), ('G','D'), ('D','G'), ('D','D')})
        self.assertEqual({c.count for c in examples}, {1, 2, 3})
        self.assertTrue(any(len(set(c.route.lengths)) > 1 for c in examples))
        for turns in {('G','G'), ('G','D'), ('D','G'), ('D','D')}:
            self.assertEqual({c.count for c in examples if c.route.turns == turns},
                             {1, 2, 3})
        for bad in (-1, 12, 1.2, True):
            with self.assertRaises(ValueError): reference_course(bad)

    def test_plan_rejects_out_of_domain_gate_counts(self):
        from tools.grand_prix.route_courses_v2 import plan_course
        for count in (-1, 0, 4, 1.0, True, "2"):
            with self.assertRaises(ValueError):
                plan_course(0, (2, 2, 2), ('G', 'D'), count)

    def test_host_identifier_reconstructs_the_exact_course(self):
        from tools.grand_prix.route_courses_v2 import (
            course_from_identifier, plan_course, reference_course,
        )
        for seed in (0, 65535):
            for lengths in itertools.product((2, 2.5, 3), repeat=3):
                for turns in itertools.product(('G', 'D'), repeat=2):
                    for count in (1, 2, 3):
                        course = plan_course(seed, lengths, turns, count)
                        self.assertEqual(course_from_identifier(course.identifier), course)
        for index in range(12):
            course = reference_course(index)
            self.assertEqual(course_from_identifier(course.identifier), course)

    def test_host_identifier_rejects_aliases_old_versions_and_malformed_input(self):
        from tools.grand_prix.route_courses_v2 import course_from_identifier
        valid = 'gp-route-v2-L2000-2500-3000-TGD-s17-H2'
        invalid = (
            None, True, 17, '', valid+'\n', ' '+valid, valid+' ',
            valid.replace('route-v2', 'u-v1'), valid.replace('v2', 'v3'),
            valid.replace('2000', '2.000'), valid.replace('2000', '2100'),
            valid.replace('TGD', 'Tgd'), valid.replace('TGD', 'TGGD'),
            valid.replace('s17', 's017'), valid.replace('s17', 's-1'),
            valid.replace('s17', 's65536'), valid.replace('H2', 'H0'),
            valid.replace('H2', 'H4'), valid.replace('H2', 'H02'),
            valid+';anything', valid.replace('s17', 's'+'9'*10000),
        )
        for identifier in invalid:
            with self.subTest(identifier=str(identifier)[:80]):
                with self.assertRaises(ValueError):
                    course_from_identifier(identifier)

    def test_static_full_course_world_banc_in_canonical_geometry_suite(self):
        from tools.ci.test_grand_prix_course_static_world_v2 import StaticCourseWorldTests
        case = unittest.defaultTestLoader.loadTestsFromTestCase(StaticCourseWorldTests)
        result = unittest.TestResult()
        case.run(result)
        if result.errors or result.failures:
            self.fail('Static complete-course counterexamples failed: ' +
                      repr(result.errors + result.failures))
        self.assertEqual(result.testsRun, 3)

    def test_active_course_world_contract_in_canonical_geometry_suite(self):
        from tools.ci.test_grand_prix_course_active_world_v2 import ActiveCourseWorldTests
        case = unittest.defaultTestLoader.loadTestsFromTestCase(ActiveCourseWorldTests)
        result = unittest.TestResult()
        case.run(result)
        if result.errors or result.failures:
            self.fail('Active host scene counterexamples failed: ' +
                      repr(result.errors + result.failures))
        self.assertEqual(result.testsRun, 4)

    def test_physical_open_h_geometry_matrix(self):
        from tools.ci.test_grand_prix_open_h_v2 import VariableOpenHTests
        case = unittest.defaultTestLoader.loadTestsFromTestCase(VariableOpenHTests)
        result = unittest.TestResult()
        case.run(result)
        if result.errors or result.failures:
            self.fail('Open-H geometry counterexamples failed: ' + repr(result.errors + result.failures))
        self.assertEqual(result.testsRun, 2)



if __name__ == '__main__':
    unittest.main()

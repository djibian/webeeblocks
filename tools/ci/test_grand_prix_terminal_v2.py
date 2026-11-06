"""Static geometry and fail-closed tests, not native Webots R2025a evidence."""
import itertools
import math
import unittest
from tools.grand_prix.route_v2 import build_route
from tools.grand_prix.route_terminal_v2 import (
    ARRIVAL_LENGTH, ARRIVAL_WIDTH, CLOSURE_SPAN, HEIGHT, LANDING_TILE,
    landing_footprint, landing_targets, terminal_boxes,
)


class VariableTerminalTests(unittest.TestCase):
    def test_108_routes_have_four_visible_physical_terminal_parts(self):
        cases = 0
        for lengths in itertools.product((2., 2.5, 3.), repeat=3):
            for turns in itertools.product(('G', 'D'), repeat=2):
                route = build_route(17, lengths, turns)
                leg = route.legs[-1]
                cases += 1
                boxes = terminal_boxes(route)
                self.assertEqual(len(boxes), 4)
                self.assertEqual(len({b.name for b in boxes}), 4)
                self.assertEqual([b.name for b in boxes], [
                    'GP_V2_FINAL_LEFT', 'GP_V2_FINAL_RIGHT',
                    'GP_V2_FINAL_BEAM', 'GP_V2_FINAL_PANEL',
                ])
                for b in boxes:
                    node = b.vrml()
                    self.assertIn(f'DEF {b.name} Solid', node)
                    self.assertIn('locked TRUE', node)
                    self.assertIn('boundingObject Box', node)
                    self.assertIn('geometry Box', node)
                    self.assertAlmostEqual(b.z-b.sz/2, 0. if b.name !=
                        'GP_V2_FINAL_BEAM' else .69)
                    self.assertLessEqual(b.z+b.sz/2, HEIGHT)
                panel = boxes[-1]
                self.assertTrue(panel.translucent)
                self.assertIn('transparency .65', panel.vrml())
                self.assertEqual((panel.x, panel.y), leg.end)
                self.assertEqual(panel.sz, HEIGHT)
                if leg.direction % 2 == 0:
                    self.assertEqual((panel.sx, panel.sy), (.04, CLOSURE_SPAN))
                else:
                    self.assertEqual((panel.sx, panel.sy), (CLOSURE_SPAN, .04))
                self.assertEqual(boxes[2].sz, .12)
                for sign, box in ((-1, boxes[0]), (1, boxes[1])):
                    self.assertEqual((box.x, box.y), leg.at(leg.length, sign*.87))
        self.assertEqual(cases, 108)

    def test_108_routes_keep_all_three_tiles_inside_widened_arrival(self):
        cases = 0
        for lengths in itertools.product((2., 2.5, 3.), repeat=3):
            for turns in itertools.product(('G', 'D'), repeat=2):
                route = build_route(18, lengths, turns)
                leg = route.legs[-1]
                cases += 1
                footprint = landing_footprint(route)
                self.assertEqual(footprint, tuple(leg.at(a, b) for a, b in (
                    (leg.length-ARRIVAL_LENGTH, -ARRIVAL_WIDTH/2),
                    (leg.length, -ARRIVAL_WIDTH/2),
                    (leg.length, ARRIVAL_WIDTH/2),
                    (leg.length-ARRIVAL_LENGTH, ARRIVAL_WIDTH/2),
                )))
                targets = landing_targets(route)
                self.assertEqual(targets, tuple(route.landing_target(n)
                                                 for n in (1, 2, 3)))
                for n, target in enumerate(targets, start=1):
                    along, lateral = leg.local(target)
                    self.assertAlmostEqual(along, leg.length-.70)
                    self.assertAlmostEqual(lateral, {1: 0., 2: .50, 3: -.50}[n])
                    # The entire 28cm landing tile fits, not only its centre.
                    self.assertGreaterEqual(along-LANDING_TILE/2,
                                            leg.length-ARRIVAL_LENGTH)
                    self.assertLessEqual(along+LANDING_TILE/2, leg.length)
                    self.assertLessEqual(abs(lateral)+LANDING_TILE/2,
                                         ARRIVAL_WIDTH/2)
        self.assertEqual(cases, 108)

    def test_native_variable_collider_preflight_is_fail_closed(self):
        # Additive to the existing, selected Grand Prix geometry suite.
        from tools.ci.test_grand_prix_native_collider_contract_v2 import (
            NativeColliderContractTests,
        )
        tests = unittest.defaultTestLoader.loadTestsFromTestCase(
            NativeColliderContractTests)
        result = unittest.TestResult()
        tests.run(result)
        self.assertEqual(result.testsRun, 12)
        if result.errors or result.failures:
            self.fail('native collider preflight contract: ' +
                      repr(result.errors + result.failures))

    def test_static_course_composite_has_all_colliders_but_no_mission(self):
        # Native probe input only: real R2025a sensor/contact and admission
        # remain separate obligations, independent of VRML-string assertions.
        import re
        from tools.grand_prix.route_courses_v2 import CoursePlan, reference_course
        from tools.grand_prix.course_static_world_v2 import static_course_world
        from tools.grand_prix.native_collider_contract_v2 import required_box_names
        from tools.grand_prix.course_footprint_v2 import red_boundary_marks

        for index in range(12):
            with self.subTest(reference=index):
                plan = reference_course(index)
                text = static_course_world(plan)
                self.assertEqual(text, static_course_world(plan))
                self.assertIn(plan.identifier, text)
                self.assertIn('basicTimeStep 8', text)
                self.assertEqual(text.count('controller "<none>"'), 1)
                self.assertEqual(text.count('window "<none>"'), 1)
                self.assertNotIn('GP_ROUTE_EVALUATOR', text)
                self.assertNotIn('grand_prix_route_flight', text)
                self.assertNotIn('grand_prix_u_flight', text)
                self.assertNotIn('controllerArgs', text)
                physical = re.findall(r'^DEF (\S+) Solid ', text, re.MULTILINE)
                self.assertEqual(tuple(physical), required_box_names(plan))
                self.assertEqual(text.count('boundingObject Box { size'), len(physical))
                self.assertIn('DEF GP_ROUTE_START Pose', text)
                for number in (1, 2, 3):
                    self.assertIn(f'DEF GP_ROUTE_TARGET_{number} Pose', text)
                for leg in plan.route.legs:
                    self.assertIn(f'DEF GP_V2_WHITE_{leg.index} Pose', text)
                self.assertEqual(text.count('DEF GP_V2_COURSE_RED_'),
                                 len(red_boundary_marks(plan.route)))
                self.assertEqual(text.count('DEF GP_ROUTE_BAND_'), 16 * plan.count)

        plan = reference_course(1)
        with self.assertRaises(ValueError):
            static_course_world(None)
        with self.assertRaises(ValueError):
            static_course_world(CoursePlan(plan.route, plan.gates[:-1],
                                           plan.count))

    def test_variable_landing_targets_have_accepted_checkered_visuals(self):
        # Reuse the historical U's green-bordered black/white 4x4 mark,
        # independently of the final leg heading. This is host-only geometry.
        from tools.grand_prix.course_static_world_v2 import static_course_world
        from tools.grand_prix.route_courses_v2 import reference_course

        for index in range(12):
            course = reference_course(index)
            lines = static_course_world(course).splitlines()
            with self.subTest(configuration=course.identifier):
                self.assertEqual(sum(
                    line.startswith('DEF GP_ROUTE_TARGET_') for line in lines), 51)
                for number, (x, y) in enumerate(landing_targets(course.route), start=1):
                    tiles = [line for line in lines if line.startswith(
                        f'DEF GP_ROUTE_TARGET_{number}_CELL_')]
                    self.assertEqual(len(tiles), 16)
                    self.assertEqual(sum('baseColor .06 .06 .06' in line
                                         for line in tiles), 8)
                    self.assertEqual(sum('baseColor .96 .96 .96' in line
                                         for line in tiles), 8)
                    for col in range(4):
                        for row in range(4):
                            prefix = f'DEF GP_ROUTE_TARGET_{number}_CELL_{col}_{row} Pose'
                            expected = [line for line in tiles
                                        if line.startswith(prefix + ' {')]
                            self.assertEqual(len(expected), 1)
                            tile = expected[0]
                            tx = x - .125 + (col + .5) * .0625
                            ty = y - .125 + (row + .5) * .0625
                            self.assertIn(
                                f'translation {tx:.6f} {ty:.6f} .0042', tile)
                            self.assertIn('size .0625 .0625 .0002', tile)
                            self.assertNotIn('boundingObject', tile)

    def test_unrelated_objects_cannot_be_mistaken_for_routes(self):
        for value in (None, False, (), object()):
            with self.assertRaises(TypeError):
                terminal_boxes(value)
            with self.assertRaises(TypeError):
                landing_footprint(value)
            with self.assertRaises(TypeError):
                landing_targets(value)


if __name__ == '__main__':
    unittest.main()

"""Pure negative/preparation tests, NOT a substitute for Webots R2025a."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from tools.ci import run_grand_prix_v2_l_native as runner
from tools.ci import run_grand_prix_v2_h_native as h_runner
from tools.grand_prix.route_courses_v2 import reference_course
from tools.ci.run_grand_prix_v2_l_native import (
    DEFAULT_INDICES, probe_scene, check_native,
)


class NativeLProbePreparationTests(unittest.TestCase):
    def test_four_turn_directions_prepared_without_mission(self):
        self.assertEqual(
            [reference_course(i).route.turns for i in DEFAULT_INDICES],
            [('G', 'G'), ('G', 'D'), ('D', 'G'), ('D', 'D')])
        for index in DEFAULT_INDICES:
            with self.subTest(index=index):
                scene = probe_scene(index)
                self.assertEqual(scene.count('controller "grand_prix_v2_l_probe"'), 1)
                self.assertIn('window "<none>"', scene)
                course = reference_course(index)
                self.assertEqual(scene.count('DEF GP_V2_L_'), 4)
                self.assertEqual(scene.count('DEF GP_V2_H_'), 3 * course.count)
                self.assertEqual(scene.count('DEF GP_V2_FINAL_'), 4)
                self.assertEqual(scene.count('boundingObject Box { size '),
                                 8 + 3 * course.count)
                self.assertNotIn('GP_ROUTE_EVALUATOR', scene)
                self.assertNotIn('controllerArgs', scene)
                self.assertNotIn('grand_prix_route_flight', scene)

    def test_missing_full_course_body_refuses_probe_preparation(self):
        # A historical four-L-only static world is no longer a valid probe
        # source. This is a host-side guard, NOT native contact evidence.
        from tools.grand_prix.route_solid_v2 import static_world
        course = reference_course(5)
        incomplete = static_world(course.route)
        with patch.object(runner, 'static_course_world', return_value=incomplete):
            with self.assertRaisesRegex(RuntimeError, 'full static course'):
                probe_scene(5)

    def test_synthetic_result_never_qualifies_native(self):
        course = reference_course(5)
        with self.assertRaisesRegex(RuntimeError, 'identity'):
            check_native({'claim': 'static-only', 'configuration': course.identifier},
                         course)
        with self.assertRaisesRegex(RuntimeError, 'incomplete'):
            check_native(dict(claim='L-only-native-teleport-perception-not-flight',
                              configuration=course.identifier, webots='R2025a',
                              timestep_ms=8, samples=[]), course)

    def test_failure_after_previous_summary_does_not_publish_stale_success(self):
        # Pure simulated subprocess failure: never a native sensor PASS.
        with TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / 'webots'
            (home / 'resources').mkdir(parents=True)
            (home / 'resources/version.txt').write_text('R2025a\n')
            (home / 'webots').touch()
            out = root / 'evidence'
            out.mkdir()
            summary = out / 'summary.json'
            summary.write_text('{"claim": "old success"}\n')
            with patch.object(runner, 'OUT', out), patch.object(
                    runner.subprocess, 'Popen') as spawned:
                spawned.return_value.wait.return_value = 1
                spawned.return_value.poll.return_value = 1
                with self.assertRaisesRegex(RuntimeError, 'native Webots failure'):
                    runner.native_run(home, (0,))
            # Historical global evidence is untouched, but a failed invocation
            # has no summary at its own announced per-run location.
            self.assertEqual(summary.read_text(), '{"claim": "old success"}\n')
            self.assertEqual(len(list(out.glob('invocation-*'))), 1)
            self.assertFalse(list(out.glob('invocation-*/summary.json')))
            self.assertFalse(list(out.glob('invocation-*/.summary-*.tmp')))

    def test_interleaved_invocations_never_borrow_other_native_bytes(self):
        # Interleave mock B, which produces valid-shaped fake data, while mock
        # A exits zero without writing sensor evidence. A must fail closed.
        # These synthetic records are NOT native R2025a qualification.
        with TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / 'webots'
            (home / 'resources').mkdir(parents=True)
            (home / 'resources/version.txt').write_text('R2025a\n')
            (home / 'webots').touch()
            out = root / 'evidence'
            course = reference_course(0)
            nearby = {'front': .20, 'back': 2., 'left': 2., 'right': 2.}
            distant = {'front': .60, 'back': 2., 'left': 2., 'right': 2.}
            mock_result = dict(
                claim='L-only-native-teleport-perception-not-flight',
                configuration=course.identifier, webots='R2025a',
                timestep_ms=8,
                samples=[dict(box=f'GP_V2_L_{i}_{part}', near=nearby, far=distant)
                         for i in range(2) for part in range(2)])

            def b_process(*args, **kwargs):
                target = Path(kwargs['env']['GP_V2_L_NATIVE_OUT'])
                target.write_text(json.dumps(mock_result))
                kwargs['stdout'].write(
                    'GP_V2_L_NATIVE ' + json.dumps(mock_result, sort_keys=True) + '\n')
                process = Mock()
                process.wait.return_value = 0
                process.poll.return_value = 0
                return process

            def a_process(*args, **kwargs):
                process = Mock()

                def wait(*, timeout):
                    with patch.object(runner.subprocess, 'Popen',
                                      side_effect=b_process):
                        runner.native_run(home, (0,))
                    return 0

                process.wait.side_effect = wait
                process.poll.return_value = 0
                return process

            with patch.object(runner, 'OUT', out), patch.object(
                    runner.subprocess, 'Popen', side_effect=a_process):
                with self.assertRaisesRegex(RuntimeError, 'no native output'):
                    runner.native_run(home, (0,))
            run_dirs = list(out.glob('invocation-*'))
            self.assertEqual(len(run_dirs), 2)
            self.assertEqual(len(list(out.glob('invocation-*/summary.json'))), 1)
            self.assertEqual(len(list(out.glob('invocation-*/*/native.json'))), 1)
            self.assertFalse((out / 'summary.json').exists())

    def test_full_H_native_probe_uses_canonical_course_without_evaluator(self):
        # Scene preparation only. Native sensor/contact evidence is not claimed.
        self.assertEqual([reference_course(i).route.turns
                          for i in h_runner.DEFAULT_INDICES],
                         [('G', 'G'), ('G', 'D'), ('D', 'G'), ('D', 'D')])
        for i in h_runner.DEFAULT_INDICES:
            with self.subTest(index=i):
                course = reference_course(i)
                scene = h_runner.probe_scene(i)
                self.assertEqual(scene.count('controller "grand_prix_v2_h_probe"'), 1)
                self.assertEqual(scene.count('window "<none>"'), 1)
                self.assertEqual(scene.count('DEF GP_V2_L_'), 4)
                self.assertEqual(scene.count('DEF GP_V2_H_'), 3 * course.count)
                self.assertEqual(scene.count('DEF GP_V2_FINAL_'), 4)
                self.assertNotIn('GP_ROUTE_EVALUATOR', scene)
                self.assertNotIn('controllerArgs', scene)

    def test_full_H_native_proof_rejects_static_and_incomplete_records(self):
        course = reference_course(5)
        with self.assertRaisesRegex(RuntimeError, 'identity'):
            h_runner.check_native({'claim': 'static-only',
                                   'configuration': course.identifier}, course)
        with self.assertRaisesRegex(RuntimeError, 'incomplete'):
            h_runner.check_native({'claim': h_runner.CLAIM,
                                   'configuration': course.identifier,
                                   'webots': 'R2025a',
                                   'timestep_ms': 8, 'opened': []}, course)
        for index in (-1, 12, None, '5'):
            with self.subTest(index=index), self.assertRaises(ValueError):
                h_runner.probe_scene(index)

    def test_native_contact_full_course_scene_uses_unpowered_proto(self):
        from tools.ci import run_grand_prix_v2_contact_native as contact
        for index in contact.DEFAULT_INDICES:
            with self.subTest(index=index):
                course = reference_course(index)
                world = contact.probe_scene(index)
                self.assertEqual(world.count('controller "grand_prix_v2_contact_probe"'), 1)
                self.assertIn('window "<none>"', world)
                self.assertNotIn('GP_ROUTE_EVALUATOR', world)
                self.assertNotIn('grand_prix_route_flight', world)
                self.assertEqual(world.count('DEF GP_V2_L_'), 4)
                self.assertEqual(world.count('DEF GP_V2_H_'), 3 * course.count)
                self.assertEqual(world.count('DEF GP_V2_FINAL_'), 4)
        for invalid in (-1, 12, True, '5'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                contact.probe_scene(invalid)

    def test_native_contact_output_requires_real_node_id_hit_and_clock(self):
        from tools.ci import run_grand_prix_v2_contact_native as contact
        from tools.grand_prix.route_solid_v2 import corner_boxes
        course = reference_course(5)
        box = corner_boxes(course.route)[0]
        def tick(ms, points, target_points=None):
            return dict(time_ms=ms, contacts=points,
                        target_contacts=[] if target_points is None else target_points)
        hit = dict(node_id=23, point=[box.x, box.y, .65])
        own = dict(node_id=8, point=[box.x, box.y, .65])
        other = corner_boxes(course.route)[1]
        other_hit = dict(node_id=24, point=[other.x, other.y, .65])
        other_own = dict(node_id=8, point=[other.x, other.y, .65])
        base = dict(claim=contact.CLAIM, configuration=course.identifier,
                    webots='R2025a', timestep_ms=8,
                    source='Robot.getContactPoints(includeDescendants=True)',
                    target_source='Solid.getContactPoints(includeDescendants=False)',
                    target=box.name, target_node_id=23,
                    free=[tick(8, []), tick(16, []), tick(24, [])],
                    collision=[tick(32, [own], [hit]), tick(40, []), tick(48, [])],
                    additional=dict(
                        target=other.name, target_node_id=24,
                        free=[tick(56, []), tick(64, []), tick(72, [])],
                        collision=[tick(80, [other_own], [other_hit]),
                                   tick(88, []), tick(96, [])]))
        # Host-shaped fakes are only parser tests; they are never native proof.
        contact.check_native(base, course)
        import copy
        for mutation in ('missing', 'stale', 'spoofed', 'nan', 'wrong-course',
                         'wrong-source', 'free-hit', 'free-foreign-contact',
                         'missing-reciprocal', 'unmatched-point', 'old-partner-id-assumption',
                         'no-second', 'second-missing-hit', 'second-mismatched-id',
                         'second-stale', 'second-same-node'):
            with self.subTest(mutation=mutation):
                bad = copy.deepcopy(base)
                if mutation == 'missing':
                    bad['collision'][0]['contacts'] = []
                elif mutation == 'stale':
                    bad['collision'][0]['time_ms'] = 24
                elif mutation == 'spoofed':
                    bad['collision'][0]['target_contacts'][0]['node_id'] = 9
                elif mutation == 'nan':
                    bad['collision'][0]['contacts'][0]['point'][0] = float('nan')
                elif mutation == 'wrong-course':
                    bad['configuration'] = reference_course(1).identifier
                elif mutation == 'wrong-source':
                    bad['source'] = 'synthetic geometry'
                elif mutation == 'free-hit':
                    bad['free'][0]['contacts'].append(hit)
                elif mutation == 'free-foreign-contact':
                    bad['free'][0]['contacts'].append(
                        dict(node_id=99, point=[0., 0., .65]))
                elif mutation == 'missing-reciprocal':
                    bad['collision'][0]['target_contacts'] = []
                elif mutation == 'unmatched-point':
                    bad['collision'][0]['contacts'][0]['point'][0] += .01
                elif mutation == 'old-partner-id-assumption':
                    # The old impossible proof accepted partner IDs on the
                    # vehicle alone; it must not substitute for a Solid read.
                    bad['collision'][0]['contacts'] = [hit]
                    bad['collision'][0]['target_contacts'] = []
                elif mutation == 'no-second':
                    del bad['additional']
                elif mutation == 'second-missing-hit':
                    bad['additional']['collision'][0]['target_contacts'] = []
                elif mutation == 'second-mismatched-id':
                    bad['additional']['collision'][0]['target_contacts'][0]['node_id'] = 25
                elif mutation == 'second-stale':
                    bad['additional']['free'][0]['time_ms'] = 48
                elif mutation == 'second-same-node':
                    bad['additional']['target_node_id'] = 23
                with self.assertRaises(RuntimeError):
                    contact.check_native(bad, course)

    def test_native_contact_runner_refuses_zero_exit_without_native_bytes(self):
        from tools.ci import run_grand_prix_v2_contact_native as contact
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / 'webots'
            (home / 'resources').mkdir(parents=True)
            (home / 'resources/version.txt').write_text('R2025a\n')
            (home / 'webots').write_text('stub')
            (home / 'webots').chmod(0o755)
            out = base / 'evidence'
            with patch.object(contact, 'OUT', out), \
                 patch.object(contact.subprocess, 'Popen') as spawned:
                spawned.return_value.wait.return_value = 0
                spawned.return_value.poll.return_value = 0
                with self.assertRaisesRegex(RuntimeError, 'missing native contact output'):
                    contact.native_run(home, (5,))
            self.assertEqual(len(list(out.glob('invocation-*'))), 1)
            self.assertFalse(list(out.glob('invocation-*/summary.json')))

    def test_contact_producer_reads_both_arms_with_native_own_ids(self):
        # API-shaped mocks test Python composition, not R2025a contact physics.
        import contextlib
        import io
        import runpy
        import sys
        from types import SimpleNamespace
        from tools.ci import run_grand_prix_v2_contact_native as contact
        from tools.grand_prix.route_solid_v2 import corner_boxes
        course = reference_course(5)
        boxes = corner_boxes(course.route)[:2]
        state = dict(time_ms=0, position=[0., 0., .65], target=boxes[0])
        translation, rotation = Mock(), Mock()
        translation.setSFVec3f.side_effect = lambda value: state.update(position=value)
        vehicle, robot = Mock(), Mock()
        vehicle.getTypeName.return_value = 'Crazyflie'
        vehicle.getPosition.side_effect = lambda: state['position']
        vehicle.getVelocity.return_value = [0.] * 6
        cylinder, radius, height, physics = Mock(), Mock(), Mock(), Mock()
        cylinder.getTypeName.return_value = 'Cylinder'
        radius.getSFFloat.return_value = .05
        height.getSFFloat.return_value = .03
        cylinder.getField.side_effect = lambda key: {
            'radius': radius, 'height': height}[key]
        physics.getTypeName.return_value = 'Physics'
        bound_field, physics_field = Mock(), Mock()
        bound_field.getSFNode.return_value = cylinder
        physics_field.getSFNode.return_value = physics
        vehicle.getBaseNodeField.side_effect = lambda key: {
            'boundingObject': bound_field, 'physics': physics_field}[key]
        vehicle.getField.side_effect = lambda key: {
            'translation': translation, 'rotation': rotation}[key]

        def collision_position(box):
            face = min(box.sx, box.sy) / 2 + .05 - .015
            return ([box.x, box.y + face, .65] if box.sy < box.sx
                    else [box.x + face, box.y, .65])

        def contacts(node_id):
            box = state['target']
            if state['position'] == collision_position(box):
                return [SimpleNamespace(point=[box.x, box.y, .65], node_id=node_id)]
            return []

        vehicle.getContactPoints.side_effect = lambda **kw: contacts(8)
        colliders = {}
        for index, box in enumerate(boxes):
            collider = Mock()
            collider.getTypeName.return_value = 'Solid'
            collider.getId.return_value = 23 + index
            collider.getContactPoints.side_effect = (
                lambda index=index, **kw: contacts(23 + index))
            colliders[box.name] = collider

        def get_target(name):
            state['target'] = next(box for box in boxes if box.name == name)
            return colliders[name]

        robot.getFromDef.side_effect = get_target
        robot.getBasicTimeStep.return_value = 8
        robot.getSelf.return_value = vehicle
        def step(period):
            state['time_ms'] += period
            return 0
        robot.step.side_effect = step
        robot.getTime.side_effect = lambda: state['time_ms'] / 1000
        captured = io.StringIO()
        with TemporaryDirectory() as temp:
            output = Path(temp) / 'native.json'
            with (
                patch.dict(sys.modules, {'controller': SimpleNamespace(Supervisor=lambda: robot)}),
                patch.dict('os.environ', GP_V2_CONTACT_INDEX='5', GP_V2_CONTACT_OUT=str(output)),
                patch('tools.grand_prix.native_collider_contract_v2.verify_native_boxes'),
                contextlib.redirect_stdout(captured),
            ):
                producer = runpy.run_path(str(contact.ROOT /
                    'controllers/grand_prix_v2_contact_probe/grand_prix_v2_contact_probe.py'))
                producer['witness']()
            record = json.loads(output.read_text())
            contact.check_native(record, course)
            self.assertEqual([record['target'], record['additional']['target']],
                             [box.name for box in boxes])
            self.assertEqual([record['target_node_id'], record['additional']['target_node_id']],
                             [23, 24])
            diagnostics = [json.loads(line.removeprefix('GP_V2_CONTACT_DIAG '))
                           for line in captured.getvalue().splitlines()
                           if line.startswith('GP_V2_CONTACT_DIAG ')]
            self.assertEqual(len(diagnostics), 16)
            expected = ([('free', 'after_reset', 0)] +
                        [('free', 'after_step', i) for i in (1, 2, 3)] +
                        [('collision', 'after_reset', 0)] +
                        [('collision', 'after_step', i) for i in (1, 2, 3)])
            self.assertEqual(
                [(row['phase'], row['event'], row['tick']) for row in diagnostics],
                expected + expected)
            self.assertEqual(diagnostics[4]['vehicle_position'], collision_position(boxes[0]))
            self.assertEqual(diagnostics[12]['vehicle_position'], collision_position(boxes[1]))
            self.assertEqual(diagnostics[-1]['time_ms'], 96)
            self.assertEqual(vehicle.getContactPoints.call_count, 12)
            for collider in colliders.values():
                self.assertEqual(collider.getContactPoints.call_count, 6)
                collider.getContactPoints.assert_called_with(includeDescendants=False)
            robot.simulationQuit.assert_called_once_with(0)

    def test_required_native_contact_matrix_covers_all_turn_pairs(self):
        # Four native courses, each requiring both first-L arms, not synthetic rays.
        # Each candidate is still required to pass real R2025a independently.
        from tools.ci import run_grand_prix_v2_contact_native as contact
        self.assertEqual(contact.DEFAULT_INDICES, (0, 5, 6, 11))
        courses = [reference_course(index) for index in contact.DEFAULT_INDICES]
        self.assertEqual([course.count for course in courses], [1, 2, 2, 3])
        self.assertEqual(
            [course.identifier.split("-T", 1)[1][:2] for course in courses],
            ["GG", "GD", "DG", "DD"])
        self.assertEqual(
            {leg.length for course in courses for leg in course.route.legs},
            {2., 2.5, 3.})

    def test_native_contact_failure_refutes_required_geometry_campaign(self):
        # Actual campaign orchestration with only native executors replaced:
        # any missing mandatory route contact must fail after the historical probes,
        # before the campaign digest can be published. No native PASS claimed.
        from tools.ci import run_grand_prix_u_geometry as geometry
        from tools.ci import run_grand_prix_v2_contact_native as contact
        import sys
        from types import SimpleNamespace
        with TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / 'webots'
            (home / 'resources').mkdir(parents=True)
            (home / 'resources/version.txt').write_text('R2025a\n')
            (home / 'bin').mkdir()
            (home / 'bin/webots-bin').write_bytes(b'host fake, not Webots')
            out = root / 'evidence'
            deadline = Mock()
            with patch.object(geometry, 'OUT', out), \
                 patch.object(geometry, 'cases', return_value=[]), \
                 patch.dict(sys.modules, {'run_grand_prix_u_deadline_native':
                            SimpleNamespace(run_native=deadline)}), \
                 patch.object(contact, 'native_run', side_effect=RuntimeError(
                     'real L collider node-ID contact not observed')) as native:
                with self.assertRaisesRegex(RuntimeError, 'contact not observed'):
                    geometry.run_native(home)
            deadline.assert_called_once_with(home)
            native.assert_called_once_with(home, contact.DEFAULT_INDICES)
            self.assertFalse((out / 'sha256.json').exists())
        self.assertEqual(contact.OUT.parent, geometry.OUT)

    def test_contact_producer_seals_native_failure_before_simulation_quit(self):
        # A native non-zero exit may retire the controller before Webots
        # forwards stderr. Keep the original exception in a host-readable
        # failure artifact, but NEVER write a successful native witness.
        import contextlib
        import io
        import runpy
        import sys
        from types import SimpleNamespace
        from tools.ci import run_grand_prix_v2_contact_native as contact
        with TemporaryDirectory() as temp:
            output = Path(temp) / 'case' / 'native.json'
            robot = Mock()
            robot.getBasicTimeStep.side_effect = RuntimeError('forced native probe fault')
            with patch.dict(sys.modules, {'controller': SimpleNamespace(Supervisor=lambda: robot)}), \
                 patch.dict('os.environ', GP_V2_CONTACT_INDEX='5', GP_V2_CONTACT_OUT=str(output)), \
                 contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, 'forced native probe fault'):
                    runpy.run_path(str(contact.ROOT /
                        'controllers/grand_prix_v2_contact_probe/grand_prix_v2_contact_probe.py'),
                        run_name='__main__')
            failure = output.with_suffix('.failure.log')
            self.assertTrue(failure.is_file())
            self.assertIn('RuntimeError: forced native probe fault', failure.read_text())
            self.assertFalse(output.exists(), 'fatal trace must not count as native evidence')
            robot.simulationQuit.assert_called_once_with(1)

    def test_index_outside_reference_set_rejected(self):
        for index in (-1, 12, None, '5'):
            with self.subTest(index=index), self.assertRaises(ValueError):
                probe_scene(index)


if __name__ == '__main__':
    unittest.main()

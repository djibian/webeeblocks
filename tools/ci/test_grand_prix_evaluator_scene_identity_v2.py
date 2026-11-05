"""Host fakes for the native scene identity contract, never Webots READY/PASS."""
import unittest
from unittest.mock import patch

from tools.grand_prix.evaluator_scene_identity_v2 import check_native_evaluator_scene
from tools.grand_prix.route_courses_v2 import reference_course


class Field:
    def __init__(self, value):
        self.value = value

    def getSFString(self):
        return self.value

    def getSFBool(self):
        return self.value

    def getCount(self):
        return len(self.value)

    def getMFString(self, index):
        return self.value[index]

    def getMFNode(self, index):
        return self.value[index]


class Node:
    def __init__(self, tag, kind, base, fields, proto=False):
        self.tag, self.kind, self.base, self.fields, self.proto = (
            tag, kind, base, fields, proto)

    def getId(self):
        return self.tag

    def getDef(self):
        return 'GP_ROUTE_EVALUATOR' if self.tag == 7 else ''

    def getTypeName(self):
        return self.kind

    def getBaseTypeName(self):
        return self.base

    def isProto(self):
        return self.proto

    def getField(self, name):
        value = self.fields.get(name)
        return Field(value) if value is not None else None

    def getPosition(self):
        return getattr(self, 'position', [0., 0., .65])

    def getOrientation(self):
        return getattr(self, 'orientation', [1., 0., 0., 0., 1., 0., 0., 0., 1.])

    def getVelocity(self):
        return getattr(self, 'velocity', [0.] * 6)


class Supervisor:
    def __init__(self, course):
        self.vehicle = Node(8, 'Crazyflie', 'Robot', {
            'name': 'Crazyflie WebeeBlocks',
            'controllerArgs': [course.identifier],
            'controller': 'grand_prix_route_flight',
            'window': 'grand_prix_route_v2',
            'supervisor': True,
        }, True)
        self.evaluator = Node(7, 'Robot', 'Robot', {
            'controllerArgs': [course.identifier],
            'controller': 'grand_prix_route_evaluator',
            'supervisor': True,
        })
        self.root = Node(0, 'Group', 'Group', {'children': [self.vehicle, self.evaluator]})
        self.timestep = 8
        self.time = 0.

    def getTime(self):
        return self.time

    def getFromId(self, identity):
        return self.vehicle if identity == self.vehicle.getId() else None

    def getBasicTimeStep(self):
        return self.timestep

    def getSelf(self):
        return self.evaluator

    def getFromDef(self, name):
        return self.evaluator if name == 'GP_ROUTE_EVALUATOR' else None

    def getRoot(self):
        return self.root


class NativeEvaluatorSceneIdentityTests(unittest.TestCase):
    def setUp(self):
        self.course = reference_course(5)
        self.native = Supervisor(self.course)
        self.boxes = patch('tools.grand_prix.evaluator_scene_identity_v2.canonical_native_boxes',
                           return_value=('locked-native-colliders',))
        self.verify = patch('tools.grand_prix.evaluator_scene_identity_v2.verify_native_boxes')
        self.boxes.start()
        self.check = self.verify.start()
        self.addCleanup(self.boxes.stop)
        self.addCleanup(self.verify.stop)

    def run_check(self):
        return check_native_evaluator_scene(self.native, self.course.identifier)

    def test_unique_identical_native_identities_and_full_collider_check(self):
        self.assertIsNone(self.run_check(), 'a scene-only check must grant no authority')
        self.check.assert_called_once()
        args = self.check.call_args.args
        self.assertIs(args[0], self.native)
        self.assertEqual(args[1], self.course)
        self.assertEqual(args[2], ('locked-native-colliders',))

    def test_reject_mismatched_host_course_and_wrong_runtime(self):
        other = reference_course(6).identifier
        with self.assertRaisesRegex(RuntimeError, 'identity'):
            check_native_evaluator_scene(self.native, other)
        with self.assertRaises(ValueError):
            check_native_evaluator_scene(self.native, None)
        self.native.timestep = 16
        with self.assertRaisesRegex(RuntimeError, 'timestep'):
            self.run_check()
        self.check.assert_not_called()

    def test_reject_missing_duplicate_or_wrong_vehicle(self):
        self.native.root.fields['children'] = [self.native.evaluator]
        with self.assertRaisesRegex(RuntimeError, 'Crazyflie'):
            self.run_check()
        self.native.root.fields['children'] = [self.native.vehicle] * 2 + [self.native.evaluator]
        with self.assertRaisesRegex(RuntimeError, 'Crazyflie'):
            self.run_check()
        self.native.root.fields['children'] = [self.native.vehicle, self.native.evaluator]
        self.native.vehicle.proto = False
        with self.assertRaisesRegex(RuntimeError, 'PROTO'):
            self.run_check()
        self.check.assert_not_called()

    def test_reject_forged_evaluator_identity_and_authority(self):
        self.native.evaluator.fields['controller'] = 'grand_prix_u_evaluator'
        with self.assertRaisesRegex(RuntimeError, 'evaluator identity'):
            self.run_check()
        self.native.evaluator.fields['controller'] = 'grand_prix_route_evaluator'
        self.native.evaluator.fields['supervisor'] = False
        with self.assertRaisesRegex(RuntimeError, 'supervisor authority'):
            self.run_check()
        self.native.evaluator.fields['supervisor'] = True
        self.native.evaluator.fields['controllerArgs'] = [self.course.identifier, 'extra']
        with self.assertRaisesRegex(RuntimeError, 'one controllerArgs'):
            self.run_check()
        self.check.assert_not_called()

    def test_reject_changed_flight_identity_and_profile(self):
        self.native.vehicle.fields['controllerArgs'] = [reference_course(6).identifier]
        with self.assertRaisesRegex(RuntimeError, 'flight identity'):
            self.run_check()
        self.native.vehicle.fields['controllerArgs'] = [self.course.identifier]
        self.native.vehicle.fields['window'] = 'grand_prix_u'
        with self.assertRaisesRegex(RuntimeError, 'flight identity'):
            self.run_check()
        self.native.vehicle.fields['window'] = 'grand_prix_route_v2'
        self.native.vehicle.fields['supervisor'] = False
        with self.assertRaisesRegex(RuntimeError, 'supervisor authority'):
            self.run_check()
        self.check.assert_not_called()

    def test_native_scene_readback_failure_is_not_a_pass(self):
        self.check.side_effect = RuntimeError('extra hidden physical Solid')
        with self.assertRaisesRegex(RuntimeError, 'extra hidden'):
            self.run_check()
        self.check.assert_called_once()


    def test_preflight_bootstrap_rejects_stale_or_forged_ready_during_steps(self):
        from tools.grand_prix.evaluator_preflight_v2 import serve_fail_closed

        class Description:
            value = 'GP_ROUTE_READY_V1 forged stale'
            writes = []
            def setSFString(self, value):
                self.value = value
                self.writes.append(value)

        description = Description()
        original_field = self.native.evaluator.getField
        calls = []

        def field(name):
            return description if name == 'description' else original_field(name)

        def step(milliseconds):
            calls.append(milliseconds)
            self.native.time = len(calls) * .008
            if len(calls) == 1:
                description.value = 'GP_ROUTE_READY_V1 injected between native steps'
                return 0
            if len(calls) == 2:
                return 0
            return -1

        with patch.object(self.native.evaluator, 'getField', side_effect=field):
            with patch.object(self.native, 'step', side_effect=step, create=True):
                self.assertIsNone(serve_fail_closed(self.native, self.course.identifier))
        self.assertEqual(calls, [8, 8, 8])
        self.assertEqual(description.writes, ['', '', ''])
        self.assertEqual(description.value, '')
        self.check.assert_called_once()

    def test_preflight_failure_clears_prior_claim_before_native_verification(self):
        from tools.grand_prix.evaluator_preflight_v2 import serve_fail_closed

        class Description:
            value = 'GP_ROUTE_READY_V1 old claim'
            def setSFString(self, value):
                self.value = value

        description = Description()
        original_field = self.native.evaluator.getField
        self.check.side_effect = RuntimeError('hidden native collider')
        with patch.object(self.native.evaluator, 'getField',
                          side_effect=lambda name: (
                              description if name == 'description' else original_field(name))):
            with self.assertRaisesRegex(RuntimeError, 'hidden native collider'):
                serve_fail_closed(self.native, self.course.identifier)
        self.assertEqual(description.value, '')
        self.check.assert_called_once()

    def test_preflight_rejects_missing_authority_field(self):
        from tools.grand_prix.evaluator_preflight_v2 import serve_fail_closed
        original_field = self.native.evaluator.getField
        with patch.object(self.native.evaluator, 'getField',
                          side_effect=lambda name: (
                              None if name == 'description' else original_field(name))):
            with self.assertRaisesRegex(RuntimeError, 'description field absent'):
                serve_fail_closed(self.native, self.course.identifier)
        self.check.assert_not_called()



    def test_native_kinematics_sampler_produces_data_not_authority(self):
        from tools.grand_prix.evaluator_native_kinematics_v2 import NativeKinematicsSampler
        reader = NativeKinematicsSampler(self.native, self.course.identifier)
        self.native.time = .008
        snapshot = reader.snapshot()
        self.assertEqual(snapshot.time_ms, 8)
        self.assertEqual(snapshot.position, (0., 0., .65))
        self.assertEqual(snapshot.velocity, (0.,) * 6)
        self.assertFalse(hasattr(snapshot, 'ready'))
        self.assertFalse(hasattr(snapshot, 'native_validated'))
        with self.assertRaisesRegex(RuntimeError, 'replayed'):
            reader.snapshot()
        self.native.time = .016
        self.native.vehicle.position = [.15, 0., .65]
        self.assertEqual(reader.snapshot().position, (.15, 0., .65))

    def test_native_kinematics_rejects_invalid_pose_velocity_clock_and_provenance(self):
        from tools.grand_prix.evaluator_native_kinematics_v2 import NativeKinematicsSampler
        cases = (
            ('position', [0., 0., float('nan')]),
            ('position', [True, 0., 0.]),
            ('orientation', [0.] * 9),
            ('orientation', [1.,0.,0., 0.,1.,0., 0.,0.,-1.]),
            ('velocity', [0.] * 5),
            ('velocity', [0.,0.,0.,0.,0.,float('inf')]),
        )
        for name, value in cases:
            with self.subTest(name=name, value=value):
                setattr(self.native.vehicle, name, value)
                reader = NativeKinematicsSampler(self.native, self.course.identifier)
                self.native.time = .008
                with self.assertRaises(RuntimeError):
                    reader.snapshot()
                delattr(self.native.vehicle, name)
        reader = NativeKinematicsSampler(self.native, self.course.identifier)
        for invalid_time in (-.008, .009, float('nan'), True):
            with self.subTest(time=invalid_time):
                self.native.time = invalid_time
                with self.assertRaises(RuntimeError):
                    reader.snapshot()
        self.native.time = .008
        self.native.vehicle.kind = 'Robot'
        with self.assertRaisesRegex(RuntimeError, 'disappeared'):
            reader.snapshot()
        self.native.vehicle.kind = 'Crazyflie'
        self.assertEqual(reader.snapshot().time_ms, 8)

    def test_native_kinematics_rejects_live_source_drift_after_binding(self):
        from tools.grand_prix.evaluator_native_kinematics_v2 import NativeKinematicsSampler
        reader = NativeKinematicsSampler(self.native, self.course.identifier)
        self.native.time = .008
        self.assertEqual(reader.snapshot().time_ms, 8)
        self.native.time = .016
        drift = (
            ('name', 'Other Robot'),
            ('supervisor', False),
            ('controller', 'other_controller'),
            ('window', 'other_window'),
            ('controllerArgs', [reference_course(1).identifier]),
        )
        for name, replacement in drift:
            with self.subTest(field=name):
                prior = self.native.vehicle.fields[name]
                self.native.vehicle.fields[name] = replacement
                try:
                    with self.assertRaisesRegex(RuntimeError, 'native vehicle .* changed'):
                        reader.snapshot()
                finally:
                    self.native.vehicle.fields[name] = prior
        self.native.vehicle.proto = False
        try:
            with self.assertRaisesRegex(RuntimeError, 'native vehicle provenance changed'):
                reader.snapshot()
        finally:
            self.native.vehicle.proto = True
        # Invalid observations must not consume the next legitimate tick.
        self.assertEqual(reader.snapshot().time_ms, 16)

    def test_preflight_invalid_native_velocity_rejects_and_erases_stale_ready(self):
        from tools.grand_prix.evaluator_preflight_v2 import serve_fail_closed
        class Description:
            value = 'GP_ROUTE_READY_V1 stale'
            def setSFString(self, value):
                self.value = value

        description = Description()
        original_field = self.native.evaluator.getField
        self.native.vehicle.velocity = [0.,0.,0.,0.,0.,float('nan')]

        def step(milliseconds):
            self.native.time = .008
            return 0

        with patch.object(self.native.evaluator, 'getField', side_effect=lambda key: (
                description if key == 'description' else original_field(key))):
            with patch.object(self.native, 'step', side_effect=step, create=True):
                with self.assertRaisesRegex(RuntimeError, 'native linear/angular velocity'):
                    serve_fail_closed(self.native, self.course.identifier)
        self.assertEqual(description.value, '')
        self.check.assert_called_once()



if __name__ == '__main__':
    unittest.main()

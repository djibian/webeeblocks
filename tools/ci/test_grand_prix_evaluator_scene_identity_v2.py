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


if __name__ == '__main__':
    unittest.main()

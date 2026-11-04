"""Adversarial fake-Supervisor tests, never native R2025a qualification."""
from dataclasses import replace
import unittest

from tools.grand_prix.route_courses_v2 import reference_course
from tools.grand_prix.native_collider_attestation_v2 import (
    ColliderAttestationError, attest_native_course_colliders,
    expected_course_colliders,
)


class Field:
    def __init__(self, value):
        self.value = value

    def getSFBool(self):
        return self.value

    def getSFVec3f(self):
        return self.value

    def getSFRotation(self):
        return self.value

    def getSFNode(self):
        return self.value


class FakeBox:
    def __init__(self, size):
        self.fields = {'size': Field(list(size))}
        self.kind = 'Box'

    def getTypeName(self):
        return self.kind

    def getField(self, key):
        return self.fields.get(key)


class FakeSolid:
    def __init__(self, expected):
        self.kind = 'Solid'
        self.world_position = list(expected.position)
        self.fields = {
            'locked': Field(True),
            'translation': Field(list(expected.position)),
            'rotation': Field([0, 0, 1, 0]),
            'boundingObject': Field(FakeBox(expected.size)),
        }

    def getTypeName(self):
        return self.kind

    def getField(self, key):
        return self.fields.get(key)

    def getPosition(self):
        return self.world_position


class FakeSupervisor:
    def __init__(self, expected):
        self.nodes = {item.name: FakeSolid(item) for item in expected}

    def getFromDef(self, name):
        return self.nodes.get(name)


class NativeColliderAttestationTests(unittest.TestCase):
    def test_twelve_host_plans_yield_all_expected_static_colliders(self):
        for index in range(12):
            course = reference_course(index)
            expected = expected_course_colliders(course)
            with self.subTest(index=index):
                self.assertEqual(len(expected), 8 + 3 * course.count)
                self.assertEqual(len({item.name for item in expected}), len(expected))
                self.assertEqual(
                    attest_native_course_colliders(FakeSupervisor(expected), course),
                    tuple(item.name for item in expected),
                )

    def test_single_missing_or_modified_native_object_refuses_attestation(self):
        course = reference_course(5)
        expected = expected_course_colliders(course)
        for index in (0, 4, len(expected)-1):  # L, open H, terminal closure
            name = expected[index].name
            for mutation in ('missing', 'wrong_type', 'unlocked', 'moved',
                             'displaced_in_parent', 'rotated', 'no_rotation',
                             'no_bounding', 'wrong_shape', 'wrong_size',
                             'nan_size', 'bool_position'):
                with self.subTest(name=name, mutation=mutation):
                    supervisor = FakeSupervisor(expected)
                    node = supervisor.nodes[name]
                    box = node.fields['boundingObject'].value
                    if mutation == 'missing':
                        del supervisor.nodes[name]
                    elif mutation == 'wrong_type':
                        node.kind = 'Pose'
                    elif mutation == 'unlocked':
                        node.fields['locked'].value = False
                    elif mutation == 'moved':
                        node.fields['translation'].value[0] += .02
                    elif mutation == 'displaced_in_parent':
                        node.world_position[0] += .02
                    elif mutation == 'rotated':
                        node.fields['rotation'].value[-1] = .1
                    elif mutation == 'no_rotation':
                        del node.fields['rotation']
                    elif mutation == 'no_bounding':
                        node.fields['boundingObject'].value = None
                    elif mutation == 'wrong_shape':
                        box.kind = 'Sphere'
                    elif mutation == 'wrong_size':
                        box.fields['size'].value[0] += .03
                    elif mutation == 'nan_size':
                        box.fields['size'].value[2] = float('nan')
                    elif mutation == 'bool_position':
                        node.fields['translation'].value[0] = True
                    with self.assertRaises(ColliderAttestationError):
                        attest_native_course_colliders(supervisor, course)

    def test_forged_or_incomplete_host_identity_is_rejected_first(self):
        course = reference_course(0)
        supervisor = FakeSupervisor(expected_course_colliders(course))
        for invalid in (None, True, 'route', replace(course, count=2),
                        replace(course, gates=()),
                        replace(course, gates=(object(),))):
            with self.subTest(invalid=str(invalid)[:32]):
                with self.assertRaises(ColliderAttestationError):
                    attest_native_course_colliders(supervisor, invalid)
        with self.assertRaises(ColliderAttestationError):
            attest_native_course_colliders(None, course)


if __name__ == '__main__':
    unittest.main()

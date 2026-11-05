"""Host-only negative tests for native route contact readback; no Webots PASS."""
import unittest
from types import SimpleNamespace

from tools.grand_prix.route_courses_v2 import reference_course
from tools.grand_prix.evaluator_native_contacts_v2 import NativeContactSampler


class Field:
    def __init__(self, value):
        self.value = value

    def getSFString(self):
        return self.value

    def getSFBool(self):
        return self.value

    def getCount(self):
        return len(self.value)

    def getMFNode(self, index):
        return self.value[index]

    def getMFString(self, index):
        return self.value[index]


class Node:
    def __init__(self, identity, fields, proto=True):
        self.identity, self.fields, self.proto = identity, fields, proto
        self.contacts = []
        self.contact_args = []

    def getId(self):
        return self.identity

    def getField(self, key):
        return Field(self.fields[key]) if key in self.fields else None

    def isProto(self):
        return self.proto

    def getTypeName(self):
        return "Crazyflie"

    def getBaseTypeName(self):
        return "Robot"

    def getContactPoints(self, *, includeDescendants):
        self.contact_args.append(includeDescendants)
        return self.contacts


class Supervisor:
    def __init__(self, course):
        self.vehicle = Node(9, {
            "name": "Crazyflie WebeeBlocks",
            "supervisor": True,
            "controller": "grand_prix_route_flight",
            "window": "grand_prix_route_v2",
            "controllerArgs": [course.identifier],
        })
        self.root = Node(2, {"children": [self.vehicle]})
        self.time = .008
        self.step_ms = 8

    def getBasicTimeStep(self):
        return self.step_ms

    def getRoot(self):
        return self.root

    def getFromId(self, identity):
        return self.vehicle if identity == 9 else None

    def getTime(self):
        return self.time


class NativeRouteContactReadbackTests(unittest.TestCase):
    def setUp(self):
        self.course = reference_course(5)
        self.native = Supervisor(self.course)

    def test_data_only_with_descendant_contacts_and_monotonic_clock(self):
        sample = NativeContactSampler(self.native, self.course.identifier)
        first = sample.snapshot()
        self.assertEqual(first.time_ms, 8)
        self.assertEqual(first.points, ())
        self.assertFalse(hasattr(first, "collision_free"))
        self.assertFalse(hasattr(first, "ready"))
        self.native.time = .016
        self.native.vehicle.contacts = [
            SimpleNamespace(point=(.12, -.3, .52), node_id=5),
            SimpleNamespace(point=[.14, -.2, .5], node_id=-1),
        ]
        second = sample.snapshot()
        self.assertEqual(len(second.points), 2)
        self.assertEqual(second.points[0].point, (.12, -.3, .52))
        self.assertEqual(second.points[1].node_id, -1)
        self.assertEqual(self.native.vehicle.contact_args, [True, True])
        with self.assertRaisesRegex(RuntimeError, "replayed"):
            sample.snapshot()

    def test_invalid_contact_values_fail_without_authority(self):
        invalid = [
            SimpleNamespace(point=(0, 0, float("nan")), node_id=3),
            SimpleNamespace(point=(True, 0, 0), node_id=3),
            SimpleNamespace(point=(0, 0), node_id=3),
            SimpleNamespace(point=(0, 0, 0), node_id=True),
            SimpleNamespace(point=(0, 0, 0), node_id=2**40),
        ]
        for item in invalid:
            with self.subTest(item=item):
                self.native.vehicle.contacts = [item]
                with self.assertRaises(RuntimeError):
                    NativeContactSampler(self.native, self.course.identifier).snapshot()
        self.native.vehicle.contacts = None
        with self.assertRaisesRegex(RuntimeError, "collection"):
            NativeContactSampler(self.native, self.course.identifier).snapshot()

    def test_binding_rejects_duplicate_missing_or_forged_source(self):
        self.native.root.fields["children"] = [self.native.vehicle, self.native.vehicle]
        with self.assertRaisesRegex(RuntimeError, "duplicate"):
            NativeContactSampler(self.native, self.course.identifier)
        self.native.root.fields["children"] = []
        with self.assertRaisesRegex(RuntimeError, "root inventory"):
            NativeContactSampler(self.native, self.course.identifier)
        self.native.root.fields["children"] = [self.native.vehicle]
        self.native.vehicle.fields["controller"] = "wrong"
        with self.assertRaisesRegex(RuntimeError, "identity"):
            NativeContactSampler(self.native, self.course.identifier)
        self.native.vehicle.fields["controller"] = "grand_prix_route_flight"
        self.native.vehicle.fields["controllerArgs"] = [reference_course(1).identifier]
        with self.assertRaisesRegex(RuntimeError, "course mismatch"):
            NativeContactSampler(self.native, self.course.identifier)

    def test_live_identity_and_timestamp_revalidated_every_sample(self):
        reader = NativeContactSampler(self.native, self.course.identifier)
        self.native.step_ms = 16
        with self.assertRaisesRegex(RuntimeError, "timestep"):
            reader.snapshot()
        self.native.step_ms = 8
        for invalid in (-.008, .009, float("nan"), True):
            with self.subTest(invalid=invalid):
                self.native.time = invalid
                with self.assertRaises(RuntimeError):
                    reader.snapshot()
        self.native.time = .008
        self.native.vehicle.proto = False
        with self.assertRaisesRegex(RuntimeError, "identity"):
            reader.snapshot()
        self.native.vehicle.proto = True
        self.assertEqual(reader.snapshot().time_ms, 8)
        self.native.time = .016
        self.native.vehicle.fields["window"] = "grand_prix_u"
        with self.assertRaisesRegex(RuntimeError, "identity"):
            reader.snapshot()


if __name__ == "__main__":
    unittest.main()

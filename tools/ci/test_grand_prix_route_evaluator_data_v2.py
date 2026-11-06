"""Cross-Robot evaluator data boundary: host fakes, never native/READY PASS."""
import unittest
from types import SimpleNamespace

from tools.grand_prix.route_courses_v2 import reference_course
from tools.grand_prix.evaluator_live_data_v2 import NativeRouteDataReader


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
    def __init__(self, node_id, definition, kind, fields, proto=False):
        self.identity = node_id
        self.definition = definition
        self.kind = kind
        self.fields = fields
        self.proto = proto
        self.contact_points = ()

    def getId(self):
        return self.identity

    def getDef(self):
        return self.definition

    def getTypeName(self):
        return self.kind

    def getBaseTypeName(self):
        return "Robot" if self.kind in ("Robot", "Crazyflie") else "Group"

    def isProto(self):
        return self.proto

    def getField(self, name):
        return Field(self.fields[name]) if name in self.fields else None

    def getContactPoints(self, includeDescendants=False):
        if not includeDescendants:
            raise AssertionError("must read PROTO descendants")
        return self.contact_points


class FakeSupervisor:
    def __init__(self, identifier):
        self.now = 2.112
        self.vehicle = Node(8, "", "Crazyflie", {
            "name": "Crazyflie WebeeBlocks",
            "supervisor": True,
            "controller": "grand_prix_route_flight",
            "window": "grand_prix_route_v2",
            "controllerArgs": [identifier]}, proto=True)
        self.evaluator = Node(7, "GP_ROUTE_EVALUATOR", "Robot", {
            "supervisor": True,
            "controller": "grand_prix_route_evaluator",
            "controllerArgs": [identifier],
            "customData": (f"GP_ROUTE_CHALLENGE_V1 attempt=1 config={identifier} "
                           + "epoch=" + "ab"*16),
            "model": (f"GP_ROUTE_SAMPLE_V1 attempt=1 config={identifier} "
                      + "epoch=" + "ab"*16
                      + " time_ms=2112 period_ms=32 ground=1 ranges_um=0,200000,1234567,2000000,2001000"),
            "description": "FORGED_READY"})
        self.root = Node(0, "", "Group",
                         {"children": [self.vehicle, self.evaluator]})

    def getSelf(self):
        return self.evaluator

    def getFromDef(self, definition):
        return self.evaluator if definition == "GP_ROUTE_EVALUATOR" else None

    def getFromId(self, identity):
        return {7: self.evaluator, 8: self.vehicle}.get(identity)

    def getRoot(self):
        return self.root

    def getBasicTimeStep(self):
        return 8

    def getTime(self):
        return self.now


class NativeRouteDataTests(unittest.TestCase):
    def setUp(self):
        self.course = reference_course(5)
        self.native = FakeSupervisor(self.course.identifier)

    def test_same_tick_real_field_and_contact_readers_never_issue_authority(self):
        reader = NativeRouteDataReader(self.native, self.course.identifier)
        one = reader.snapshot()
        self.assertEqual(one.time_ms, 2112)
        self.assertEqual(one.flight.time_ms, 2112)
        self.assertEqual(one.flight.ranges_m[1], .2)
        self.assertEqual(one.contacts.time_ms, one.time_ms)
        self.assertEqual(one.contacts.points, ())
        self.assertFalse(hasattr(one, "ready"))
        self.assertFalse(hasattr(one, "native_validated"))
        self.assertEqual(self.native.evaluator.fields["description"], "FORGED_READY")
        self.native.now = 2.120
        self.native.vehicle.contact_points = (
            SimpleNamespace(point=[.1, .2, .3], node_id=42),)
        two = reader.snapshot()
        self.assertEqual(two.time_ms, 2120)
        self.assertEqual(two.flight.time_ms, 2112,
                         "field receipt must not invent a new sensor sample")
        self.assertEqual(two.contacts.points[0].node_id, 42)
        with self.assertRaisesRegex(RuntimeError, "replayed"):
            reader.snapshot()

    def test_no_context_or_stale_sample_refuses_without_authorization(self):
        for wrong in ("", "GP_ROUTE_READY_V1", "x" * 384):
            with self.subTest(wrong=wrong):
                self.native.evaluator.fields["customData"] = wrong
                with self.assertRaises(ValueError):
                    NativeRouteDataReader(self.native, self.course.identifier).snapshot()
        self.native = FakeSupervisor(self.course.identifier)
        reader = NativeRouteDataReader(self.native, self.course.identifier)
        self.native.now = 2.152
        with self.assertRaisesRegex(ValueError, "stale"):
            reader.snapshot()
        self.assertEqual(self.native.evaluator.fields["description"], "FORGED_READY")

    def test_bad_nonce_and_sensor_field_are_rejected(self):
        reader = NativeRouteDataReader(self.native, self.course.identifier)
        self.native.evaluator.fields["model"] = self.native.evaluator.fields["model"].replace("epoch=" + "ab"*16, "epoch=" + "cd"*16)
        with self.assertRaisesRegex(ValueError, "identity"):
            reader.snapshot()

    def test_mutated_source_and_contact_provenance_refuse(self):
        reader = NativeRouteDataReader(self.native, self.course.identifier)
        self.native.vehicle.fields["controller"] = "grand_prix_u_flight"
        with self.assertRaisesRegex(RuntimeError, "source identity"):
            reader.snapshot()
        self.native.vehicle.fields["controller"] = "grand_prix_route_flight"
        self.native.evaluator.fields["controllerArgs"] = [reference_course(0).identifier]
        with self.assertRaisesRegex(RuntimeError, "course changed"):
            reader.snapshot()
        self.native.evaluator.fields["controllerArgs"] = [self.course.identifier]
        self.native.vehicle.contact_points = (SimpleNamespace(point=[float("nan"), 0, 0], node_id=42),)
        with self.assertRaisesRegex(RuntimeError, "contact coordinates"):
            reader.snapshot()

    def test_missing_or_replaced_evaluator_field_refuses(self):
        del self.native.evaluator.fields["model"]
        with self.assertRaisesRegex(RuntimeError, "field model"):
            NativeRouteDataReader(self.native, self.course.identifier)
        self.native = FakeSupervisor(self.course.identifier)
        reader = NativeRouteDataReader(self.native, self.course.identifier)
        self.native.evaluator.identity = 9
        with self.assertRaisesRegex(RuntimeError, "source changed"):
            reader.snapshot()


if __name__ == "__main__":
    unittest.main()

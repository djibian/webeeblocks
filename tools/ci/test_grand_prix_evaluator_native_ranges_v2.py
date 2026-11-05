"""Host-shaped negative tests; they are not native Webots R2025a evidence."""
import unittest
from unittest.mock import patch

from tools.grand_prix.evaluator_native_ranges_v2 import NativeFlightRangeReader

CONFIG = 'gp-route-v2-L2000-2500-3000-TGD-s17-H2'
EPOCH = 'ab' * 16
CHALLENGE = f'GP_ROUTE_CHALLENGE_V1 attempt=1 config={CONFIG} epoch={EPOCH}'
SAMPLE = (f'GP_ROUTE_SAMPLE_V1 attempt=1 config={CONFIG} epoch={EPOCH} '
          'time_ms=2112 period_ms=32 ground=1 ranges_um=0,200000,1234567,2000000,2001000')


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
    def __init__(self, identity, kind, fields, proto=False):
        self.identity = identity
        self.kind = kind
        self.fields = {key: Field(value) for key, value in fields.items()}
        self.proto = proto

    def getId(self):
        return self.identity

    def getTypeName(self):
        return self.kind

    def getBaseTypeName(self):
        return 'Robot'

    def isProto(self):
        return self.proto

    def getField(self, name):
        return self.fields.get(name)


class Supervisor:
    def __init__(self):
        self.evaluator = Node(11, 'Robot', {
            'controller': 'grand_prix_route_evaluator',
            'controllerArgs': [CONFIG], 'supervisor': True, 'model': SAMPLE,
        })
        self.flight = Node(23, 'Crazyflie', {
            'name': 'Crazyflie WebeeBlocks', 'controller': 'grand_prix_route_flight',
            'window': 'grand_prix_route_v2', 'controllerArgs': [CONFIG],
            'supervisor': True, 'customData': CHALLENGE,
        }, proto=True)
        self.root = Node(5, 'Group', {'children': [self.evaluator, self.flight]})
        self.time = 2.120

    def getBasicTimeStep(self):
        return 8

    def getSelf(self):
        return self.evaluator

    def getFromDef(self, name):
        return self.evaluator if name == 'GP_ROUTE_EVALUATOR' else None

    def getFromId(self, identity):
        return {11: self.evaluator, 23: self.flight}.get(identity)

    def getRoot(self):
        return self.root

    def getTime(self):
        return self.time


class NativeFlightRangeReaderTests(unittest.TestCase):
    def setUp(self):
        self.native = Supervisor()
        self.checker = patch(
            'tools.grand_prix.evaluator_native_ranges_v2.check_native_evaluator_scene')
        self.scene = self.checker.start()
        self.addCleanup(self.checker.stop)
        self.reader = NativeFlightRangeReader(self.native, CONFIG)

    def test_bound_live_fields_return_data_only_and_do_not_refresh_sample_age(self):
        data = self.reader.read()
        self.scene.assert_called_once_with(self.native, CONFIG)
        self.assertEqual(data.time_ms, 2112)
        self.assertEqual(data.ranges_m, (0., .2, 1.234567, 2., 2.001))
        self.assertTrue(data.ground_confirmed)
        self.assertFalse(hasattr(data, 'ready'))
        self.assertFalse(hasattr(data, 'native_validated'))
        self.native.time = 2.128
        self.assertEqual(self.reader.read().time_ms, 2112)
        with self.assertRaisesRegex(RuntimeError, 'replayed native evaluator'):
            self.reader.read()

    def test_native_source_drift_refused_without_consuming_valid_tick(self):
        mutations = (
            (self.native.flight, 'controller', 'wrong_controller'),
            (self.native.flight, 'name', 'Other Robot'),
            (self.native.flight, 'window', 'wrong_window'),
            (self.native.flight, 'controllerArgs', ['gp-u-v1']),
            (self.native.evaluator, 'controller', 'wrong_evaluator'),
            (self.native.evaluator, 'controllerArgs', ['gp-u-v1']),
            (self.native.evaluator, 'supervisor', False),
            (self.native.flight, 'supervisor', False),
        )
        for node, name, replacement in mutations:
            with self.subTest(name=name, replacement=replacement):
                prior = node.fields[name].value
                node.fields[name].value = replacement
                try:
                    with self.assertRaises(RuntimeError):
                        self.reader.read()
                finally:
                    node.fields[name].value = prior
        self.native.flight.proto = False
        with self.assertRaisesRegex(RuntimeError, 'source identity'):
            self.reader.read()
        self.native.flight.proto = True
        self.assertEqual(self.reader.read().time_ms, 2112)

    def test_missing_stale_wrong_epoch_or_attempt_rejected(self):
        for changed in ('', 'untrusted', SAMPLE.replace('attempt=1', 'attempt=2'),
                        SAMPLE.replace('time_ms=2112', 'time_ms=2048')):
            with self.subTest(payload=changed):
                self.native.evaluator.fields['model'].value = changed
                with self.assertRaises(ValueError):
                    self.reader.read()
        self.native.evaluator.fields['model'].value = SAMPLE
        self.native.flight.fields['customData'].value = ''
        with self.assertRaisesRegex(RuntimeError, 'without live attempt'):
            self.reader.read()
        self.native.flight.fields['customData'].value = CHALLENGE.replace('attempt=1', 'attempt=2')
        with self.assertRaises(ValueError):
            self.reader.read()
        self.native.flight.fields['customData'].value = CHALLENGE
        self.assertEqual(self.reader.read().time_ms, 2112)
        self.native.time = 2.152
        with self.assertRaises(ValueError):
            self.reader.read()

    def test_replaced_robot_and_evaluator_identity_refused(self):
        self.native.flight.identity = 44
        with self.assertRaisesRegex(RuntimeError, 'source identity'):
            self.reader.read()
        self.native.flight.identity = 23
        self.native.evaluator.identity = 44
        with self.assertRaisesRegex(RuntimeError, 'source identity'):
            self.reader.read()


if __name__ == '__main__':
    unittest.main()

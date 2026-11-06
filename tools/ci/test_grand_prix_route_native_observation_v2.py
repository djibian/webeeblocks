"""Pure host-side tests of same-tick native data composition, never Webots PASS."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tools.ci.test_grand_prix_route_evaluator_data_v2 import FakeSupervisor
from tools.grand_prix.evaluator_native_kinematics_v2 import NativeKinematics
from tools.grand_prix.evaluator_native_observation_v2 import (
    NativeRouteObservationSampler,
)
from tools.grand_prix.route_courses_v2 import reference_course


class NativeRouteObservationTests(unittest.TestCase):
    def setUp(self):
        self.course = reference_course(5)
        self.native = FakeSupervisor(self.course.identifier)
        self.native.vehicle.getPosition = lambda: [0., 0., .65]
        self.native.vehicle.getOrientation = lambda: [
            1., 0., 0., 0., 1., 0., 0., 0., 1.]
        self.native.vehicle.getVelocity = lambda: [0.] * 6
        self.patcher = patch(
            'tools.grand_prix.evaluator_native_observation_v2.check_native_evaluator_scene')
        self.scene = self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def sampler(self):
        return NativeRouteObservationSampler(self.native, self.course.identifier)

    def test_same_real_samplers_read_pose_native_ranges_and_contacts_at_one_tick(self):
        reader = self.sampler()
        self.scene.assert_called_once_with(self.native, self.course.identifier)
        first = reader.snapshot()
        self.assertEqual(first.time_ms, 2112)
        self.assertEqual(first.kinematics.time_ms, first.time_ms)
        self.assertEqual(first.contacts.time_ms, first.time_ms)
        self.assertEqual(first.flight.time_ms, first.time_ms)
        self.assertEqual(first.flight.ranges_m[1], .2)
        self.assertEqual(first.kinematics.position, (0., 0., .65))
        self.assertEqual(first.contacts.points, ())
        self.assertFalse(hasattr(first, 'ready'))
        self.assertFalse(hasattr(first, 'authority'))
        self.assertEqual(self.native.evaluator.fields['description'], 'FORGED_READY')
        self.native.now = 2.120
        self.native.vehicle.contact_points = (
            SimpleNamespace(point=[.1, .2, .3], node_id=42),)
        second = reader.snapshot()
        self.assertEqual(second.time_ms, 2120)
        self.assertEqual(second.flight.time_ms, 2112,
                         'receipt must not invent a fresh range sample')
        self.assertEqual(second.contacts.points[0].node_id, 42)
        self.assertEqual(self.native.evaluator.fields['description'], 'FORGED_READY')
        self.scene.assert_called_once()

    def test_scene_preflight_failure_prevents_any_native_reader(self):
        self.scene.side_effect = RuntimeError('extra native collider')
        with patch(
            'tools.grand_prix.evaluator_native_observation_v2.NativeKinematicsSampler'
        ) as kinematics, patch(
            'tools.grand_prix.evaluator_native_observation_v2.NativeRouteDataReader'
        ) as data:
            with self.assertRaisesRegex(RuntimeError, 'extra native collider'):
                self.sampler()
            kinematics.assert_not_called()
            data.assert_not_called()

    def test_mismatched_native_kinematics_clock_poison_is_irreversible(self):
        reader = self.sampler()
        reader._kinematics.snapshot = Mock(return_value=NativeKinematics(
            2104, (0., 0., .65), (1., 0., 0., 0., 1., 0., 0., 0., 1.),
            (0.,) * 6))
        with self.assertRaisesRegex(RuntimeError, 'tick mismatch'):
            reader.snapshot()
        self.native.now = 2.120
        with self.assertRaisesRegex(RuntimeError, 'poisoned'):
            reader.snapshot()
        reader._kinematics.snapshot.assert_called_once()

    def test_replayed_tick_poisoned_even_after_clock_advance(self):
        reader = self.sampler()
        self.assertEqual(reader.snapshot().time_ms, 2112)
        with self.assertRaisesRegex(RuntimeError, 'replayed'):
            reader.snapshot()
        self.native.now = 2.120
        with self.assertRaisesRegex(RuntimeError, 'poisoned'):
            reader.snapshot()

    def test_expired_real_range_packet_rejected_without_fallback(self):
        reader = self.sampler()
        self.native.now = 2.152  # flight message still stamped 2112 (>32ms)
        with self.assertRaisesRegex(ValueError, 'stale'):
            reader.snapshot()
        self.native.now = 2.120
        with self.assertRaisesRegex(RuntimeError, 'poisoned'):
            reader.snapshot()

    def test_corrupted_real_contact_rejected_without_fallback(self):
        reader = self.sampler()
        self.native.vehicle.contact_points = (
            SimpleNamespace(point=[float('nan'), 0., 0.], node_id=42),)
        with self.assertRaisesRegex(RuntimeError, 'contact coordinates'):
            reader.snapshot()
        self.native.vehicle.contact_points = ()
        self.native.now = 2.120
        with self.assertRaisesRegex(RuntimeError, 'poisoned'):
            reader.snapshot()

    def test_forged_flight_context_never_grants_authority(self):
        reader = self.sampler()
        raw = self.native.evaluator.fields['model']
        self.native.evaluator.fields['model'] = raw.replace(
            'epoch=' + 'ab' * 16, 'epoch=' + 'cd' * 16)
        with self.assertRaisesRegex(ValueError, 'identity'):
            reader.snapshot()
        self.assertEqual(self.native.evaluator.fields['description'], 'FORGED_READY')
        with self.assertRaisesRegex(RuntimeError, 'poisoned'):
            reader.snapshot()


if __name__ == '__main__':
    unittest.main()

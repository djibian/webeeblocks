"""Host-fake coherence and negative proofs, never native R2025a qualification."""
import unittest
from unittest.mock import patch

from tools.ci.test_grand_prix_route_evaluator_data_v2 import FakeSupervisor
from tools.grand_prix.route_courses_v2 import reference_course
from tools.grand_prix.evaluator_observation_v2 import NativeCourseObservationSampler


class NativeCourseObservationTests(unittest.TestCase):
    def setUp(self):
        self.course = reference_course(5)
        self.native = FakeSupervisor(self.course.identifier)
        self.native.vehicle.getPosition = lambda: [0., 0., .65]
        self.native.vehicle.getOrientation = lambda: [1., 0., 0.,
                                                       0., 1., 0.,
                                                       0., 0., 1.]
        self.native.vehicle.getVelocity = lambda: [0.] * 6
        self.scene = patch(
            "tools.grand_prix.evaluator_observation_v2.check_native_evaluator_scene")
        self.checked = self.scene.start()
        self.addCleanup(self.scene.stop)

    def test_exact_tick_with_real_reader_contract_and_no_authority(self):
        reader = NativeCourseObservationSampler(self.native, self.course.identifier)
        self.checked.assert_called_once_with(self.native, self.course.identifier)
        first = reader.snapshot()
        self.assertEqual(first.time_ms, 2112)
        self.assertEqual(first.kinematics.time_ms, first.time_ms)
        self.assertEqual(first.contacts.time_ms, first.time_ms)
        self.assertEqual(first.flight.time_ms, first.time_ms)
        self.assertEqual(first.flight.ranges_m[1], .2)
        self.assertEqual(first.kinematics.position, (0., 0., .65))
        for key in ("ready", "alive", "native_validated", "success", "admitted"):
            self.assertFalse(hasattr(first, key))
        self.assertEqual(self.native.evaluator.fields["description"], "FORGED_READY")
        self.native.now = 2.120
        second = reader.snapshot()
        self.assertEqual(second.time_ms, 2120)
        self.assertEqual(second.kinematics.time_ms, second.contacts.time_ms)
        self.assertEqual(second.flight.time_ms, 2112,
                         "receiving a 32-ms sample twice must not forge acquisition")
        with self.assertRaisesRegex(RuntimeError, "replayed"):
            reader.snapshot()
        self.assertEqual(self.native.evaluator.fields["description"], "FORGED_READY")

    def test_scene_refutation_prevents_any_reader_construction(self):
        self.checked.side_effect = RuntimeError("extra hidden native collider")
        with patch("tools.grand_prix.evaluator_observation_v2.NativeRouteDataReader") as data:
            with self.assertRaisesRegex(RuntimeError, "hidden native collider"):
                NativeCourseObservationSampler(self.native, self.course.identifier)
            data.assert_not_called()

    def test_disagreeing_valid_timestamps_are_not_combined(self):
        reader = NativeCourseObservationSampler(self.native, self.course.identifier)
        original = reader._data.snapshot

        def advance_during_composition():
            self.native.now = 2.120
            return original()

        reader._data.snapshot = advance_during_composition
        with self.assertRaisesRegex(RuntimeError, "tick mismatch"):
            reader.snapshot()
        self.assertEqual(self.native.evaluator.fields["description"], "FORGED_READY")

    def test_invalid_pose_or_flight_observation_never_returns_partial_success(self):
        reader = NativeCourseObservationSampler(self.native, self.course.identifier)
        self.native.vehicle.getVelocity = lambda: [0., 0., 0., 0., 0., float("nan")]
        with self.assertRaisesRegex(RuntimeError, "native linear/angular velocity"):
            reader.snapshot()
        self.native.vehicle.getVelocity = lambda: [0.] * 6
        self.native.now = 2.120
        with self.assertRaisesRegex(RuntimeError, "terminal after failure"):
            reader.snapshot()
        # Distinct fresh sampler: isolate and verify the flight-identity
        # negative rather than reusing the poisoned reader.
        reader = NativeCourseObservationSampler(self.native, self.course.identifier)
        self.native.evaluator.fields["model"] = self.native.evaluator.fields["model"].replace(
            "epoch=" + "ab" * 16, "epoch=" + "cd" * 16)
        with self.assertRaisesRegex(ValueError, "identity"):
            reader.snapshot()
        self.native.now = 2.128
        with self.assertRaisesRegex(RuntimeError, "terminal after failure"):
            reader.snapshot()
        self.assertEqual(self.native.evaluator.fields["description"], "FORGED_READY")

    def test_failed_tick_cannot_be_recovered_by_later_valid_data(self):
        reader = NativeCourseObservationSampler(self.native, self.course.identifier)
        original = reader._data.snapshot

        def advance_between_readers():
            self.native.now = 2.120
            return original()

        reader._data.snapshot = advance_between_readers
        with self.assertRaisesRegex(RuntimeError, "tick mismatch"):
            reader.snapshot()
        reader._data.snapshot = original
        self.native.now = 2.128
        with self.assertRaisesRegex(RuntimeError, "terminal after failure"):
            reader.snapshot()
        self.assertEqual(self.native.evaluator.fields["description"], "FORGED_READY")
        # A fresh read-only reader may be built, but this cannot create READY.
        fresh = NativeCourseObservationSampler(self.native, self.course.identifier)
        self.assertEqual(fresh.snapshot().time_ms, 2128)
        self.assertEqual(self.native.evaluator.fields["description"], "FORGED_READY")

    def test_changed_vehicle_provenance_is_not_a_fresh_snapshot(self):
        reader = NativeCourseObservationSampler(self.native, self.course.identifier)
        reader.snapshot()
        self.native.now = 2.120
        self.native.vehicle.fields["window"] = "grand_prix_u"
        with self.assertRaisesRegex(RuntimeError, "native vehicle provenance changed"):
            reader.snapshot()


if __name__ == "__main__":
    unittest.main()

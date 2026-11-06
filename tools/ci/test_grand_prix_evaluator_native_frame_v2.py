"""Host-only falsification of the evaluator's synchronized data frame.

These API-shaped fakes do NOT establish a Webots R2025a native PASS, a fresh
RESET, collision clearance, READY/ALIVE or acceptance of a pupil mission.
"""
import unittest
from unittest.mock import patch

from tools.ci.test_grand_prix_route_evaluator_data_v2 import FakeSupervisor
from tools.grand_prix.evaluator_native_frame_v2 import NativeRouteFrameReader
from tools.grand_prix.route_courses_v2 import reference_course


class NativeRouteFrameTests(unittest.TestCase):
    def setUp(self):
        self.identifier = reference_course(5).identifier
        self.robot = FakeSupervisor(self.identifier)
        flight = self.robot.vehicle
        flight.getPosition = lambda: [0., 0., .65]
        flight.getOrientation = lambda: [1., 0., 0., 0., 1., 0., 0., 0., 1.]
        flight.getVelocity = lambda: [0.] * 6

    def test_one_tick_composes_native_readers_without_issuing_authority(self):
        reader = NativeRouteFrameReader(self.robot, self.identifier)
        first = reader.snapshot()
        self.assertEqual(first.time_ms, 2112)
        self.assertEqual(first.kinematics.time_ms, first.data.time_ms)
        self.assertEqual(first.data.contacts.time_ms, first.time_ms)
        self.assertEqual(first.data.flight.challenge.config, self.identifier)
        self.assertEqual(first.range_age_upper_ms, 32)
        self.assertEqual(first.kinematics.position, (0., 0., .65))
        self.assertFalse(hasattr(first, "ready"))
        self.assertFalse(hasattr(first, "native_validated"))
        self.assertEqual(self.robot.evaluator.fields["description"], "FORGED_READY")
        self.robot.now = 2.120
        second = reader.snapshot()
        self.assertEqual(second.time_ms, 2120)
        self.assertEqual(second.data.flight.time_ms, 2112)
        self.assertEqual(second.range_age_upper_ms, 40)
        with self.assertRaisesRegex(RuntimeError, "replayed"):
            reader.snapshot()
        self.assertEqual(self.robot.evaluator.fields["description"], "FORGED_READY")

    def test_native_step_between_sources_rejects_instead_of_mixing(self):
        reader = NativeRouteFrameReader(self.robot, self.identifier)
        sample = reader._data.snapshot
        def shifted():
            self.robot.now = 2.120
            return sample()
        with patch.object(reader._data, "snapshot", side_effect=shifted):
            with self.assertRaisesRegex(RuntimeError, "not from the same tick"):
                reader.snapshot()
        self.assertEqual(self.robot.evaluator.fields["description"], "FORGED_READY")

    def test_invalid_pose_and_stale_or_spoofed_sensor_fail_closed(self):
        self.robot.vehicle.getVelocity = lambda: [0.] * 5
        reader = NativeRouteFrameReader(self.robot, self.identifier)
        with self.assertRaisesRegex(RuntimeError, "velocity"):
            reader.snapshot()
        self.robot.vehicle.getVelocity = lambda: [0.] * 6
        reader = NativeRouteFrameReader(self.robot, self.identifier)
        self.robot.now = 2.152  # 40ms after the real flight sample: stale
        with self.assertRaisesRegex(ValueError, "stale"):
            reader.snapshot()
        self.robot.now = 2.112
        self.robot.evaluator.fields["model"] = (
            self.robot.evaluator.fields["model"].replace("epoch=" + "ab" * 16,
                                                         "epoch=" + "cd" * 16))
        with self.assertRaisesRegex(ValueError, "identity"):
            NativeRouteFrameReader(self.robot, self.identifier).snapshot()
        self.assertEqual(self.robot.evaluator.fields["description"], "FORGED_READY")


if __name__ == "__main__":
    unittest.main()

"""Strict native evaluator wire contract; no fabricated Webots qualification."""
import unittest

from tools.grand_prix.route_courses_v2 import reference_course
from tools.grand_prix.route_evaluator_wire_v2 import (
    Challenge, EvaluatorHandshake, Start, parse_flight_channel
)

EPOCH = "0123456789abcdef0123456789abcdef"


def challenge(course, attempt=1, epoch=EPOCH):
    return (f"GP_ROUTE_CHALLENGE_V1 attempt={attempt} "
            f"config={course.identifier} epoch={epoch}")


def start(course, *, attempt=1, epoch=EPOCH, time=1016, state="admitted"):
    return (f"GP_ROUTE_START_V1 attempt={attempt} "
            f"config={course.identifier} epoch={epoch} "
            f"start_ms={time} state={state}")


class VariableEvaluatorWireTests(unittest.TestCase):
    def test_all_reference_ids_accept_canonical_same_course_only(self):
        for index in range(12):
            course = reference_course(index)
            ch = parse_flight_channel(challenge(course), course.identifier)
            self.assertEqual(ch, Challenge(1, course.identifier, EPOCH))
            st = parse_flight_channel(start(course), course.identifier)
            self.assertEqual(st, Start(ch, 1016, "admitted"))
            self.assertIsNone(parse_flight_channel("", course.identifier))
            other = reference_course((index + 1) % 12)
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                parse_flight_channel(challenge(other), course.identifier)

    def test_malformed_wire_fails_closed(self):
        course = reference_course(5)
        valid = challenge(course)
        bad = (
            valid + " ", valid + "\n", valid.replace("attempt=1", "attempt=01"),
            valid.replace("attempt=1", "attempt=0"),
            valid.replace("attempt=1", "attempt=18446744073709551616"),
            valid.replace(EPOCH, EPOCH.upper()),
            valid.replace("config=", "config=GP_"),
            "GP_ROUTE_READY_V1 attempt=1 config=" + course.identifier,
            start(course, time=1016).replace("start_ms=1016", "start_ms=+1016"),
            start(course, time=1016).replace("start_ms=1016", "start_ms=01016"),
            start(course).replace("state=admitted", "state=success"),
            start(course).replace("start_ms=1016", "start_ms=1000000000000001"),
            "X" * 384,
        )
        for raw in bad:
            with self.subTest(raw=raw[:80]):
                with self.assertRaises(ValueError):
                    parse_flight_channel(raw, course.identifier)
        with self.assertRaises(ValueError):
            parse_flight_channel(valid, "gp-route-v2-L2000-2500-3000-TGG-s017-H2")
        with self.assertRaises(ValueError):
            parse_flight_channel(None, course.identifier)

    def test_ready_requires_native_verification_then_fresh_matching_start(self):
        course = reference_course(5)
        wire = EvaluatorHandshake(course.identifier)
        ch = challenge(course)
        st = start(course)
        self.assertEqual(wire.observe(ch, 1000), "")
        self.assertEqual(wire.observe(st, 1008, native_validated=True), "")
        self.assertIn("READY_V1 attempt=1", wire.observe(ch, 1016, native_validated=True))
        self.assertIn("ALIVE_V1 attempt=1", wire.observe(st, 1024, native_validated=True))
        self.assertEqual(wire.observe(st, 1024, native_validated=True), "")
        self.assertIn("ALIVE_V1 attempt=1", wire.observe(st, 1032, native_validated=True))
        self.assertEqual(wire.observe(start(course, state="deadline"), 1040, native_validated=True), "")
        self.assertEqual(wire.observe(st, 1048, native_validated=True), "")

    def test_start_stale_epoch_clock_and_lost_scene_fail_closed(self):
        course = reference_course(1)
        wire = EvaluatorHandshake(course.identifier)
        ch = challenge(course)
        self.assertIn("READY_V1", wire.observe(ch, 1000, native_validated=True))
        self.assertEqual(wire.observe(start(course, time=960), 1008, native_validated=True), "")
        self.assertEqual(wire.observe(start(course), 1016, native_validated=True), "")
        self.assertIn("READY_V1", wire.observe(ch, 1024, native_validated=True))
        self.assertEqual(wire.observe(start(course, epoch="f"*32), 1032, native_validated=True), "")
        self.assertIn("READY_V1", wire.observe(ch, 1040, native_validated=True))
        self.assertEqual(wire.observe(start(course, time=1000), 1048, native_validated=True), "")
        self.assertIn("READY_V1", wire.observe(ch, 1056, native_validated=True))
        self.assertEqual(wire.observe(start(course, time=1065), 1064, native_validated=True), "")
        self.assertIn("READY_V1", wire.observe(ch, 1072, native_validated=True))
        self.assertEqual(wire.observe(ch, 1080, native_validated=False), "")
        self.assertEqual(wire.observe(start(course, time=1080), 1088, native_validated=True), "")

    def test_native_clock_rollback_invalidates_epoch(self):
        course = reference_course(0)
        wire = EvaluatorHandshake(course.identifier)
        ch = challenge(course)
        self.assertIn("READY_V1", wire.observe(ch, 1000, native_validated=True))
        self.assertEqual(wire.observe(ch, 900, native_validated=True), "")
        self.assertEqual(wire.observe(start(course, time=900), 908, native_validated=True), "")
        self.assertIn("READY_V1", wire.observe(ch, 916, native_validated=True))


if __name__ == "__main__":
    unittest.main()

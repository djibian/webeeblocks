"""Discriminate the A7 rear sweep from a frontal range or a terminal cause alone."""
from dataclasses import replace
from types import SimpleNamespace
import unittest

from tools.grand_prix.a7_retreat import retreat_direction
from tools.grand_prix.native_collider_contract_v2 import NativeBox
from tools.grand_prix.oracle_attempt_v2 import start_pure_attempt
from tools.grand_prix.progression_courses import progression_course


class A7RetreatTests(unittest.TestCase):
    def setUp(self):
        course = progression_course(7, 2)
        self.last_leg = course.route.legs[-1]
        previous = SimpleNamespace(leg=SimpleNamespace(active_leg=1),
                                   pose=(2.011, -1.389, .914))
        self.attempt = replace(start_pure_attempt(course, 1, .015, 1000),
                               last_ms=4992, progress=previous)
        self.observation = SimpleNamespace(
            time_ms=5000, contacts=SimpleNamespace(points=()),
            kinematics=SimpleNamespace(position=(2.011, -1.391, .914),
                                       velocity=(.002, -.140, -.001)))

    def test_only_clear_native_rear_sweep_can_arm_retreat(self):
        self.assertEqual(retreat_direction(self.attempt, self.observation),
                         self.last_leg.direction)
        blocked = NativeBox('rear-box', (2.011, -1.271, .25), (.05, .05, .4))
        attempt = replace(self.attempt, boxes=(*self.attempt.boxes, blocked))
        self.assertIsNone(retreat_direction(attempt, self.observation))
        self.observation.time_ms += 8
        self.assertIsNone(retreat_direction(self.attempt, self.observation))

    def test_closed_h_alone_or_actual_contact_never_arms_retreat(self):
        self.observation.kinematics.position = (2.011, -1.36, .914)
        self.attempt.progress.pose = (2.011, -1.359, .914)
        self.assertIsNone(retreat_direction(self.attempt, self.observation))
        self.observation.kinematics.position = (2.011, -1.391, .914)
        self.observation.contacts.points = ('contact',)
        self.assertIsNone(retreat_direction(self.attempt, self.observation))

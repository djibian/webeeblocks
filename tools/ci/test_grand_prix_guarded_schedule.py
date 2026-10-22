#!/usr/bin/env python3
"""Preserve the #665 historical startup control and every added native trial."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.ci.run_grand_prix_u_prototype import suite_cases


# Native control from main@ec2401e, before adding guarded movement probes.
# In particular, wrong-landing is launch 4 and s17-witness is launch 16.
HISTORICAL = [
    (4, 'short'), (4, 'timeout'), (0, 'timeout-gate'), (1, 'wrong-landing'),
    (0, 'low-outside'), (0, 'collision'), (0, 'reverse'), (0, 'unavailable'),
    (0, 'reset'), (0, 'witness'), (1, 'witness'), (3, 'witness'),
    (4, 'witness'), (14, 'witness'), (15, 'witness'), (17, 'witness'),
]
ADDITIONAL = [(0, 'guarded-approach'), (0, 'guarded-single-h')]


class ScheduleTests(unittest.TestCase):
    def test_historical_control_precedes_both_required_additions(self):
        for side in (2., 3.):
            cases = suite_cases('all', 99, side)
            self.assertEqual(len(cases), 18)
            self.assertTrue(all(size == side for _, size, _ in cases))
            identifiers = [(seed, mode) for seed, _, mode in cases]
            self.assertEqual(identifiers[:16], HISTORICAL)
            self.assertEqual(identifiers[16:], ADDITIONAL)
            self.assertEqual(identifiers[3], (1, 'wrong-landing'))
            self.assertEqual(identifiers[15], (17, 'witness'))

    def test_each_guarded_trial_remains_independently_selectable(self):
        for _, mode in ADDITIONAL:
            self.assertEqual(suite_cases(mode, 17, 3.), [(17, 3., mode)])

    def test_existing_single_and_size_campaigns_are_unchanged(self):
        self.assertEqual(suite_cases('reset', 3, 2.), [(3, 2., 'reset')])
        self.assertEqual(suite_cases('sizes', 99, 99),
                         [(4, size, 'witness') for size in (2., 3., 4., 5., 6.)])


if __name__ == '__main__':
    unittest.main()

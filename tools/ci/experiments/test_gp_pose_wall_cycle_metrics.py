"""Adversarial tests for wall-cycle timing, separate from step+tick timings."""
import copy
import unittest

from tools.ci.experiments.gp_pose_wall_cycle_metrics import measure_wall_cycles


def rows():
    return [dict(time_ms=t, phase='active', wall_elapsed_s=(t - 4000) / 800,
                 step_wall_s=.001, tick_wall_s=.008)
            for t in range(4000, 7001, 8)]


class WallCycleMetricsTests(unittest.TestCase):
    def test_full_cycle_is_not_only_step_plus_tick(self):
        actual = measure_wall_cycles(rows(), 4008, 7000)
        self.assertEqual(actual['count'], 375)
        self.assertEqual(actual['wall_cycle_mean_ms'], 10)
        self.assertEqual(actual['wall_cycle_p95_ms'], 10)
        self.assertEqual(actual['wall_cycle_p99_ms'], 10)
        self.assertEqual(actual['step_plus_tick_p99_ms'], 9)
        self.assertEqual(actual['outside_step_tick_mean_ms'], 1)
        self.assertEqual(actual['wall_speed_x'], .8)

    def test_missing_previous_timestamp_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'predecessor'):
            measure_wall_cycles(rows()[1:], 4008, 7000)

    def test_duplicate_timestamp_is_refused(self):
        sample = rows()
        sample.append(copy.deepcopy(sample[10]))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            measure_wall_cycles(sample, 4008, 7000)

    def test_nonmonotone_clock_is_refused(self):
        sample = rows()
        sample[18]['wall_elapsed_s'] = sample[17]['wall_elapsed_s']
        with self.assertRaisesRegex(ValueError, 'nonmonotone'):
            measure_wall_cycles(sample, 4008, 7000)

    def test_wrong_step_budget_cannot_be_hidden(self):
        sample = rows()
        sample[18]['tick_wall_s'] = .030
        with self.assertRaisesRegex(ValueError, 'duration'):
            measure_wall_cycles(sample, 4008, 7000)

    def test_missing_active_tick_is_refused(self):
        sample = rows()
        sample[200]['phase'] = 'failed'
        with self.assertRaisesRegex(ValueError, 'non-active'):
            measure_wall_cycles(sample, 4008, 7000)


if __name__ == '__main__':
    unittest.main()

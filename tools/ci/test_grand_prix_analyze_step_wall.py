"""Fail-closed analyzer regression tests (diagnostic only, no native PASS)."""
import json
import unittest
from tools.grand_prix.analyze_step_wall import PREFIX, analyze, parse_windows


def window(i, count=125, start=8, step=8_000_000, wall=10_000_000):
    first = i * 1250_000_000
    return {
        'schema': 1, 'course': 'route-5', 'window': i, 'reason': 'complete',
        'count': count, 'start_sim_ms': start + i * 1000,
        'end_sim_ms': start + i * 1000 + (count - 1) * 8,
        'simulated_ms': count * 8, 'first_start_wall_ns': first,
        'last_end_wall_ns': first + count * wall, 'wall_ns': count * wall,
        'step_ns': [step] * count, 'tick_ns': [1_000_000] * count,
        'step_p99_ns': step, 'step_max_ns': step, 'tick_p99_ns': 1_000_000,
    }


class AnalyzePhaseTests(unittest.TestCase):
    def test_thirty_seconds_preserves_gaps_and_never_claims_gui(self):
        data = [window(i) for i in range(30)]
        logs = ['unrelated Webots line\n'] + ['debug: ' + PREFIX + json.dumps(w) + '\n' for w in data]
        report = analyze(parse_windows(logs), 'route-5', 0, None)
        self.assertEqual(report['status'], 'MEASURED_ONLY')
        self.assertEqual(report['step_count'], 3750)
        self.assertEqual(report['simulated_ms'], 30000)
        self.assertAlmostEqual(report['elapsed_wall_ms'], 37500)
        self.assertAlmostEqual(report['speed_x'], .8)
        self.assertEqual(report['step_p99_ms'], 8)
        self.assertIsNone(report['display_fps'])
        self.assertEqual(report['overall_product_acceptance'], 'UNPROVEN')

    def test_only_29_seconds_is_unproven(self):
        report = analyze([window(i) for i in range(29)], 'route-5', 0, None)
        self.assertEqual(report['status'], 'UNPROVEN_TOO_SHORT')
        self.assertFalse(report['speed_target_0_95_met'])

    def test_window_gap_rejected_even_if_phase_would_look_fast(self):
        with self.assertRaisesRegex(ValueError, 'discontinuous'):
            analyze([window(0), window(2)], 'route-5', 0, None)

    def test_simulated_clock_reset_rejected(self):
        data = [window(0), window(1)]
        data[1]['start_sim_ms'] = 8
        data[1]['end_sim_ms'] = 1000
        with self.assertRaisesRegex(ValueError, 'discontinuous'):
            analyze(data, 'route-5', 0, None)

    def test_reject_mixed_course(self):
        data = [window(0), window(1)]
        data[1]['course'] = 'another'
        with self.assertRaisesRegex(ValueError, 'mixed course'):
            analyze(data, 'route-5', 0, None)

    def test_malformed_prefixed_log_cannot_be_ignored(self):
        with self.assertRaisesRegex(ValueError, 'line 2'):
            parse_windows(['unrelated\n', PREFIX + '{bad json\n'])

    def test_inconsistent_raw_p99_rejected(self):
        bad = window(0)
        bad['step_p99_ns'] = 1
        with self.assertRaisesRegex(ValueError, 'percentiles'):
            parse_windows([PREFIX + json.dumps(bad)])

    def test_impossible_wall_duration_rejected(self):
        # Valid 8-ms clocks and raw p99, but 1 ns cannot contain 125
        # measured steps of 8 ms plus their evaluator ticks.
        forged = window(0)
        forged['last_end_wall_ns'] = forged['first_start_wall_ns'] + 1
        forged['wall_ns'] = 1
        with self.assertRaisesRegex(ValueError, 'impossible wall duration'):
            parse_windows([PREFIX + json.dumps(forged)])

    def test_negative_monotonic_wall_bound_refused(self):
        forged = window(0)
        forged['first_start_wall_ns'] = -forged['wall_ns']
        forged['last_end_wall_ns'] = 0
        with self.assertRaisesRegex(ValueError, 'impossible wall duration'):
            parse_windows([PREFIX + json.dumps(forged)])

    def test_partial_window_rejected(self):
        data = [window(0)]
        data[0]['reason'] = 'clock-discontinuity'
        with self.assertRaisesRegex(ValueError, 'partial'):
            analyze(data, 'route-5', 0, None)

    def test_selected_stable_segment_can_exclude_warmup(self):
        report = analyze([window(i) for i in range(35)], 'route-5', 5008, 34000)
        self.assertEqual(report['phase_start_sim_ms'], 5008)
        self.assertEqual(report['simulated_ms'], 29000)
        self.assertEqual(report['status'], 'UNPROVEN_TOO_SHORT')

    def test_reversed_wall_time_detected(self):
        data = [window(0), window(1)]
        data[1]['first_start_wall_ns'] = 10
        data[1]['last_end_wall_ns'] = 1250000010
        with self.assertRaisesRegex(ValueError, 'discontinuous'):
            analyze(data, 'route-5', 0, None)


if __name__ == '__main__':
    unittest.main()

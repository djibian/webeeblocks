"""Host-only, adversarial checks for a non-authority phase breakdown."""
import json
import unittest

from tools.grand_prix.analyze_evaluator_phase import PREFIX, analyze, parse_windows


def window(index, *, total=50_000_000, export=30_000_000):
    rows = []
    for step in range(125):
        rows.append({'sim_ms': 8 + index * 1000 + step * 8,
                     'durations_ns': {
                         'tick_total': total, 'scene_and_colliders': 40_000_000,
                         'exportString': export, 'kinematics': 1_000_000,
                         'contacts': 1_000_000, 'flight_observation': 1_000_000,
                         'mission_oracle': 1_000_000, 'liveness_wire': 1_000_000,
                     }})
    return {'schema': 1, 'course': 'route-5', 'window': index, 'rows': rows}


class PhaseAnalysisTests(unittest.TestCase):
    def test_thirty_seconds_and_exclusive_same_tick_durations(self):
        logs = ['Webots unrelated\n'] + [
            'INFO: ' + PREFIX + json.dumps(window(i)) + '\n' for i in range(30)]
        report = analyze(parse_windows(logs), 'route-5')
        self.assertEqual(report['status'], 'MEASURED_ONLY')
        self.assertEqual(report['steps'], 3750)
        self.assertEqual(report['phases']['exportString']['mean_ms'], 30)
        self.assertEqual(report['phases']['scene_and_colliders']['mean_ms'], 40)
        self.assertEqual(report['phases']['scene_without_exportString']['mean_ms'], 10)
        self.assertEqual(report['phases']['unattributed_tick']['mean_ms'], 5)
        self.assertEqual(report['phases']['scene_without_exportString']['slow_tick_tail_mean_ms'], 10)
        self.assertIsNone(report['speed_x'])
        self.assertEqual(report['overall_product_acceptance'], 'UNPROVEN')

    def test_conditional_stages_not_falsely_zero_filled(self):
        data = [window(0)]
        for row in data[0]['rows']:
            del row['durations_ns']['mission_oracle']
        report = analyze(data, 'route-5', minimum_sim_ms=8)
        self.assertEqual(report['phases']['mission_oracle']['observed'], 0)
        self.assertEqual(report['phases']['mission_oracle']['missing'], 125)
        self.assertIsNone(report['phases']['mission_oracle']['p99_ms'])
        self.assertEqual(report['phases']['unattributed_tick']['mean_ms'], 6)

    def test_per_step_exclusivity_not_subtracted_percentiles(self):
        data = [window(0)]
        data[0]['rows'][0]['durations_ns']['exportString'] = 39_000_000
        data[0]['rows'][1]['durations_ns']['scene_and_colliders'] = 31_000_000
        # Scene-only time = 1ms on step 0 and 1ms on step 1,
        # although p99(scene) - p99(export) would be a wrong estimate.
        data[0]['rows'][1]['durations_ns']['exportString'] = 30_000_000
        result = analyze(data, 'route-5', minimum_sim_ms=8)
        self.assertEqual(result['phases']['scene_without_exportString']['p50_ms'], 10)
        self.assertEqual(result['phases']['scene_without_exportString']['p99_ms'], 10)

    def test_missing_window_and_reset_are_rejected(self):
        for inp in ([window(0), window(2)], [window(0), window(1), window(0)]):
            with self.subTest(data=len(inp)), self.assertRaisesRegex(ValueError, 'discontinuous'):
                analyze(inp, 'route-5', minimum_sim_ms=8)

    def test_short_segment_is_not_a_pass(self):
        out = analyze([window(i) for i in range(7)], 'route-5')
        self.assertEqual(out['status'], 'UNPROVEN_TOO_SHORT')

    def test_truncated_record_rejected(self):
        with self.assertRaisesRegex(ValueError, 'line 2'):
            parse_windows(['noise\n', PREFIX + '{not-json}\n'])
        bad = window(0)
        bad['rows'][0]['durations_ns']['tick_total'] = 1
        with self.assertRaisesRegex(ValueError, 'overlapping'):
            parse_windows([PREFIX + json.dumps(bad)])

    def test_missing_total_unknown_phase_and_export_outside_scene(self):
        for replacement in ({'unknown': 1}, {'exportString': 1}):
            bad = window(0)
            bad['rows'][0]['durations_ns'] = replacement
            with self.assertRaises(ValueError):
                parse_windows([PREFIX + json.dumps(bad)])

    def test_no_fake_zero_for_unavailable_export(self):
        data = [window(0)]
        for row in data[0]['rows']:
            del row['durations_ns']['exportString']
        result = analyze(data, 'route-5', minimum_sim_ms=8)
        self.assertEqual(result['phases']['exportString']['observed'], 0)
        self.assertIsNone(result['phases']['scene_without_exportString']['mean_ms'])


    def test_nested_colliders_and_protocol_are_not_double_counted(self):
        data = [window(0)]
        for row in data[0]['rows']:
            t = row['durations_ns']
            t['scene_root_inventory'] = 1_000_000
            t['scene_vehicle_identity'] = 1_000_000
            t['scene_collider_traversal'] = 3_000_000
            t['scene_collider_values'] = 2_000_000
            t['protocol_request'] = 1_000_000
            t['protocol_model'] = 1_000_000
            t['protocol_channel'] = 1_000_000
        result = analyze(parse_windows([PREFIX + json.dumps(data[0])]), 'route-5',
                         minimum_sim_ms=8)
        phases = result['phases']
        self.assertEqual(phases['scene_collider_total']['mean_ms'], 5)
        self.assertEqual(phases['scene_exclusive_residual']['mean_ms'], 3)
        self.assertEqual(phases['protocol_total']['mean_ms'], 3)
        self.assertEqual(phases['unattributed_tick']['mean_ms'], 2)
        self.assertEqual(phases['scene_and_colliders']['slow_tick_tail_share_of_tick_pct'], 80)
        self.assertEqual(phases['exportString']['slow_tick_tail_share_of_tick_pct'], 60)

    def test_nested_sum_exceeding_scene_is_refused(self):
        data = window(0)
        t = data['rows'][0]['durations_ns']
        t['scene_collider_traversal'] = 20_000_000
        with self.assertRaisesRegex(ValueError, 'overlapping'):
            parse_windows([PREFIX + json.dumps(data)])

    def test_orphan_native_collider_phase_is_refused(self):
        data = window(0)
        t = data['rows'][0]['durations_ns']
        del t['scene_and_colliders']
        del t['exportString']
        t['scene_collider_values'] = 1
        with self.assertRaisesRegex(ValueError, 'orphan'):
            parse_windows([PREFIX + json.dumps(data)])


if __name__ == '__main__':
    unittest.main()

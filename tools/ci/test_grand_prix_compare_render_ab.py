"""Deterministic oracle for non-authoritative native render A/B diagnostics."""
import json
from pathlib import Path
import tempfile
import unittest

from tools.grand_prix.compare_render_ab import compare


class RenderABTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = {
            'schema': 1, 'source_sha': 'a' * 40, 'webots_executable_sha256': 'b' * 64,
            'program_sha256': 'c' * 64, 'course': 'route-5', 'host_id': 'machine-1',
            'display_mode': 'visible, hardware GL, same viewport',
            'phase_ms': [3200, 6400], 'render_fps': {'A': 60, 'B': 25},
            'trials': [],
        }
        for index, arm in enumerate('ABBAAB'):
            log = f'run-{index}.log'
            self.manifest['trials'].append({'arm': arm, 'log': log})
            records = []
            for window in range(3):
                # 125 physical samples per 1 s window, with distinct tick costs.
                first = 3200 + window * 1000
                steps = [4_000_000 if arm == 'A' else 2_000_000] * 125
                ticks = [1_000_000] * 125
                payload = dict(schema=1, course='route-5', window=window,
                               count=125, reason='complete', start_sim_ms=first,
                               end_sim_ms=first + 992, simulated_ms=1000,
                               step_ns=steps, tick_ns=ticks,
                               wall_ns=125 * (steps[0] + ticks[0]))
                # Distinct trials have distinct host-monotonic epochs, even if costs coincide.
                payload['first_start_wall_ns'] = index * 10_000_000_000 + window * 1_000_000_000
                payload['last_end_wall_ns'] = payload['first_start_wall_ns'] + payload['wall_ns']
                payload.update(speed_x=round(125 * 8 * 1e6 / payload['wall_ns'], 6),
                               step_p50_ns=steps[0], step_p95_ns=steps[0],
                               step_p99_ns=steps[0], step_max_ns=steps[0],
                               tick_p99_ns=ticks[0])
                records.append('prefix ' + 'GP_STEP_WALL_V1 ' + json.dumps(payload))
            (self.root / log).write_text('\n'.join(records) + '\n', encoding='utf-8')
        self.write()

    def write(self):
        (self.root / 'trial.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def test_valid_alternated_pairs_and_raw_p99(self):
        report = compare(self.root / 'trial.json')
        self.assertEqual(report['pair_count'], 3)
        self.assertEqual(report['arms']['A']['median_speed_in_windows_x'], 1.6)
        self.assertEqual(report['arms']['B']['median_speed_in_windows_x'], round(8 / 3, 6))
        self.assertEqual(report['arms']['A']['median_step_p99_ms'], 4)
        self.assertEqual(report['arms']['B']['median_step_p99_ms'], 2)
        self.assertEqual(report['arms']['A']['median_speed_observed_envelope_x'],
                         round(3 / 2.625, 6))
        self.assertEqual(report['arms']['B']['median_speed_observed_envelope_x'],
                         round(3 / 2.375, 6))
        # The requested 3.2 s phase contains only 3.0 s of full windows.
        self.assertEqual(report['observed_complete_window_phase_ms'], [3200, 6200])
        self.assertEqual(report['phase_ms'], [3200, 6400])
        self.assertEqual(report['arms']['A']['per_trial'][0]['simulated_ms'], 3000)
        self.assertIn('DIAGNOSTIC_ONLY', report['interpretation'])

    def test_window_only_speed_cannot_claim_complete_phase_gain(self):
        report = compare(self.root / 'trial.json')
        self.assertEqual(report['measurement_scope'],
                         'WINDOW_DURATION_ONLY_INTER_WINDOW_GAPS_NOT_MEASURED')
        self.assertNotIn('candidate_speed_change_percent', report)
        self.assertNotIn('median_speed_x', report['arms']['A'])
        self.assertTrue(report['arms']['B']['median_speed_in_windows_x'] >
                        report['arms']['A']['median_speed_in_windows_x'])
        self.assertIn('excludes inter-window stalls', report['interpretation'])
        self.assertEqual(report['envelope_measurement_scope'],
                         'FIRST_TO_LAST_COMPLETE_WINDOW_INCLUDING_GAPS')
        self.assertNotIn('median_speed_x', report['arms']['A'])
        self.assertNotIn('speed_x', report['arms']['A']['per_trial'][0])
        self.assertIn('speed_in_windows_x', report['arms']['A']['per_trial'][0])

    def test_inter_window_pause_reduces_envelope_speed_but_not_window_speed(self):
        before = compare(self.root / 'trial.json')['arms']['B']['per_trial'][0]
        path = self.root / 'run-1.log'
        changed = []
        for i, line in enumerate(path.read_text(encoding='utf-8').splitlines()):
            header, payload = line.split('GP_STEP_WALL_V1 ', 1)
            row = json.loads(payload)
            if i > 0:
                # Delay all later windows while keeping both simulated clock
                # and each window's complete raw step/tick durations intact.
                row['first_start_wall_ns'] += 400_000_000
                row['last_end_wall_ns'] += 400_000_000
            changed.append(header + 'GP_STEP_WALL_V1 ' + json.dumps(row))
        path.write_text('\n'.join(changed) + '\n', encoding='utf-8')
        after = compare(self.root / 'trial.json')['arms']['B']['per_trial'][0]
        self.assertEqual(after['speed_in_windows_x'], before['speed_in_windows_x'])
        self.assertEqual(after['step_p99_ms'], before['step_p99_ms'])
        self.assertLess(after['speed_observed_envelope_x'],
                        before['speed_observed_envelope_x'])
        self.assertEqual(after['speed_observed_envelope_x'], round(3 / 2.775, 6))

    def test_non_alternating_or_incomplete_pairs_are_refused(self):
        self.manifest['trials'][2]['arm'] = 'A'
        self.write()
        with self.assertRaisesRegex(ValueError, 'pair'):
            compare(self.root / 'trial.json')
        self.manifest['trials'][2]['arm'] = 'B'
        self.manifest['trials'][2], self.manifest['trials'][3] = self.manifest['trials'][3], self.manifest['trials'][2]
        self.write()
        with self.assertRaisesRegex(ValueError, 'alternate'):
            compare(self.root / 'trial.json')

    def test_duplicate_native_log_is_refused(self):
        self.manifest['trials'][1]['log'] = self.manifest['trials'][0]['log']
        self.write()
        with self.assertRaisesRegex(ValueError, 'same log reused'):
            compare(self.root / 'trial.json')

    def test_copied_observations_under_distinct_paths_are_refused(self):
        source = self.root / 'run-0.log'
        copy = self.root / 'run-4.log'
        self.assertNotEqual(copy.read_bytes(), source.read_bytes())
        copy.write_bytes(source.read_bytes())
        with self.assertRaisesRegex(ValueError, 'duplicate native observations'):
            compare(self.root / 'trial.json')

    def test_replayed_timings_cannot_hide_behind_changed_summaries_or_metadata(self):
        original = (self.root / 'run-0.log').read_text(encoding='utf-8').splitlines()
        destination = self.root / 'run-4.log'
        for field in ('speed_x', 'step_p50_ns', 'step_p95_ns',
                      'step_p99_ns', 'step_max_ns', 'tick_p99_ns'):
            changed = []
            for line in original:
                header, payload = line.split('GP_STEP_WALL_V1 ', 1)
                row = json.loads(payload)
                row[field] += 1
                changed.append(header + 'GP_STEP_WALL_V1 ' + json.dumps(row))
            destination.write_text('\n'.join(changed) + '\n', encoding='utf-8')
            with self.subTest(field=field), self.assertRaisesRegex(
                    ValueError, 'inconsistent native probe summary'):
                compare(self.root / 'trial.json')

        # Unknown/unused metadata must not alter the raw-observation digest.
        changed = []
        for line in original:
            header, payload = line.split('GP_STEP_WALL_V1 ', 1)
            row = json.loads(payload)
            row['annotation'] = 'independent run'
            changed.append(header + 'GP_STEP_WALL_V1 ' + json.dumps(row))
        destination.write_text('\n'.join(changed) + '\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'duplicate native observations'):
            compare(self.root / 'trial.json')

    def test_different_coverage_is_refused(self):
        path = self.root / 'run-0.log'
        lines = path.read_text().splitlines()
        path.write_text('\n'.join(lines[1:]) + '\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'different simulated coverage'):
            compare(self.root / 'trial.json')

    def test_changed_course_or_invalid_raw_wall_is_refused(self):
        path = self.root / 'run-1.log'
        lines = path.read_text().splitlines()
        data = json.loads(lines[0].split('GP_STEP_WALL_V1 ')[1])
        data['course'] = 'another-route'
        lines[0] = 'GP_STEP_WALL_V1 ' + json.dumps(data)
        path.write_text('\n'.join(lines), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'mixed course'):
            compare(self.root / 'trial.json')
        data['course'] = 'route-5'
        data['wall_ns'] = 1
        lines[0] = 'GP_STEP_WALL_V1 ' + json.dumps(data)
        path.write_text('\n'.join(lines), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'inconsistent monotonic wall'):
            compare(self.root / 'trial.json')

    def test_untrusted_manifest_and_changed_binary_are_refused(self):
        for bad in ('0', 'f' * 40):
            self.manifest['webots_executable_sha256'] = bad
            self.write()
            with self.assertRaisesRegex(ValueError, 'digests'):
                compare(self.root / 'trial.json')

    def test_reset_overlap_is_not_aggregated_as_one_flight(self):
        path = self.root / 'run-0.log'
        lines = path.read_text().splitlines()
        payload = json.loads(lines[-1].split('GP_STEP_WALL_V1 ')[1])
        payload['window'] = 3
        payload['start_sim_ms'] = 3200
        payload['end_sim_ms'] = 4192
        path.write_text('\n'.join(lines + ['GP_STEP_WALL_V1 ' + json.dumps(payload)]), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'gapped/overlapping|overlapping monotonic wall'):
            compare(self.root / 'trial.json')

    def test_partial_window_and_gapped_trace_refused(self):
        path = self.root / 'run-0.log'
        lines = path.read_text().splitlines()
        payload = json.loads(lines[1].split('GP_STEP_WALL_V1 ')[1])
        payload['reason'] = 'partial'
        lines[1] = 'GP_STEP_WALL_V1 ' + json.dumps(payload)
        path.write_text('\n'.join(lines), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'partial'):
            compare(self.root / 'trial.json')

    def test_native_monotonic_envelope_cannot_contradict_wall_or_overlap(self):
        path = self.root / 'run-0.log'
        lines = path.read_text(encoding='utf-8').splitlines()
        first = json.loads(lines[0].split('GP_STEP_WALL_V1 ')[1])
        first['last_end_wall_ns'] += 100_000_000
        lines[0] = 'GP_STEP_WALL_V1 ' + json.dumps(first)
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'inconsistent monotonic wall'):
            compare(self.root / 'trial.json')
        first['last_end_wall_ns'] -= 100_000_000
        lines[0] = 'GP_STEP_WALL_V1 ' + json.dumps(first)
        second = json.loads(lines[1].split('GP_STEP_WALL_V1 ')[1])
        second['first_start_wall_ns'] = 0
        second['last_end_wall_ns'] = second['wall_ns']
        lines[1] = 'GP_STEP_WALL_V1 ' + json.dumps(second)
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'overlapping monotonic wall'):
            compare(self.root / 'trial.json')
    def test_native_complete_windows_must_have_125_steps(self):
        path = self.root / 'run-0.log'
        lines = path.read_text(encoding='utf-8').splitlines()
        whole = json.loads(lines[0].split('GP_STEP_WALL_V1 ')[1])
        first = dict(whole)
        first['count'] = 63
        first['end_sim_ms'] = first['start_sim_ms'] + 62 * 8
        first['simulated_ms'] = 63 * 8
        first['step_ns'] = whole['step_ns'][:63]
        first['tick_ns'] = whole['tick_ns'][:63]
        first['wall_ns'] = sum(first['step_ns']) + sum(first['tick_ns'])
        first['last_end_wall_ns'] = first['first_start_wall_ns'] + first['wall_ns']
        tail = dict(whole)
        tail['window'] = 1
        tail['count'] = 62
        tail['start_sim_ms'] = first['end_sim_ms'] + 8
        tail['simulated_ms'] = 62 * 8
        tail['step_ns'] = whole['step_ns'][63:]
        tail['tick_ns'] = whole['tick_ns'][63:]
        tail['wall_ns'] = sum(tail['step_ns']) + sum(tail['tick_ns'])
        tail['first_start_wall_ns'] = first['last_end_wall_ns']
        tail['last_end_wall_ns'] = tail['first_start_wall_ns'] + tail['wall_ns']
        rows = [first, tail]
        for index, line in enumerate(lines[1:], 2):
            item = json.loads(line.split('GP_STEP_WALL_V1 ')[1])
            item['window'] = index
            rows.append(item)
        path.write_text('\n'.join('GP_STEP_WALL_V1 ' + json.dumps(x) for x in rows) + '\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'non-native complete window size'):
            compare(self.root / 'trial.json')

    def test_native_window_index_gap_and_unaligned_clock_rejected(self):
        path = self.root / 'run-0.log'
        lines = path.read_text(encoding='utf-8').splitlines()
        middle = json.loads(lines[1].split('GP_STEP_WALL_V1 ')[1])
        last = json.loads(lines[2].split('GP_STEP_WALL_V1 ')[1])
        middle['window'] = 4
        last['window'] = 5
        lines[1] = 'GP_STEP_WALL_V1 ' + json.dumps(middle)
        lines[2] = 'GP_STEP_WALL_V1 ' + json.dumps(last)
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'discontinuous native window index'):
            compare(self.root / 'trial.json')
        middle['window'] = 1
        last['window'] = 2
        lines[1] = 'GP_STEP_WALL_V1 ' + json.dumps(middle)
        lines[2] = 'GP_STEP_WALL_V1 ' + json.dumps(last)
        first = json.loads(lines[0].split('GP_STEP_WALL_V1 ')[1])
        first['start_sim_ms'] += 1
        first['end_sim_ms'] += 1
        lines[0] = 'GP_STEP_WALL_V1 ' + json.dumps(first)
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'unaligned native 8-ms window'):
            compare(self.root / 'trial.json')

if __name__ == '__main__':
    unittest.main()

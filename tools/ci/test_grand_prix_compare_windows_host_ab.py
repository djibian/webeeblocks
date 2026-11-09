"""Offline regression fixtures for passive Windows engine A/B comparisons."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

from tools.grand_prix.compare_windows_host_ab import compare


class PassiveWindowsHostABTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = {
            'schema': 1, 'host_id': 'operator-declared-not-verified',
            'phase': 'declared same route and controller activity', 'trials': []}
        for i, arm in enumerate(('reference', 'candidate', 'candidate',
                                 'reference', 'reference', 'candidate')):
            directory = f'trial-{i}'
            self.manifest['trials'].append({'variant': arm, 'directory': directory})
            self.write_capture(i, arm)
        self.write_manifest()

    def write_manifest(self):
        (self.root / 'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def write_capture(self, i, arm, **overrides):
        p = self.root / f'trial-{i}'
        p.mkdir(exist_ok=True)
        meta = {
            'schema': 'webeeblocks.windows-passive-host-v1',
            'source_sha': 'a' * 40, 'course_id': 'route-5', 'variant': arm,
            'webots_version': 'R2025a',
            'webots_executable_sha256': ('b' if arm == 'reference' else 'c') * 64,
            'external_browser': None,
            'process_name': 'webots-bin', 'webots_pid': i + 1,
            'process_start_utc': '2026-11-09T00:00:00Z',
            'requested_duration_s': 30, 'requested_period_ms': 1000,
            'actual_duration_s': 30.005, 'sample_count': 30,
            'operating_system': {'build': '26100', 'ram_bytes': 16000000000},
            'cpus': [{'model': 'sample', 'logical_processors': 8}],
            'video_devices': [{'model': 'sample', 'driver_version': '1'}],
            'sampling_scope': 'single Webots engine PID; no children, GPU utilization or simulation clock',
            'performance_acceptance': 'NOT_MEASURED',
        }
        meta.update(overrides)
        (p / 'metadata.json').write_text(json.dumps(meta), encoding='utf-8')
        with (p / 'samples.csv').open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=[
                'elapsed_ms', 'utc', 'period_ms', 'cpu_percent_one_core',
                'process_cpu_total_s', 'working_set_bytes',
                'private_memory_bytes', 'thread_count'])
            w.writeheader()
            for j in range(30):
                w.writerow({'elapsed_ms': 1000 * (j + 1), 'utc': '2026-11-09T00:00:00Z',
                            'period_ms': 1000, 'cpu_percent_one_core':
                            50 if arm == 'reference' else 25,
                            'process_cpu_total_s': (j + 1) * (0.5 if arm == 'reference' else 0.25),
                            'working_set_bytes': 1000000 + i,
                            'private_memory_bytes': 500000 + i,
                            'thread_count': 5})

    def compare(self):
        return compare(self.root / 'manifest.json')

    def test_valid_ab_ba_ab_paired_engine_measurements_only(self):
        report = self.compare()
        self.assertEqual(report['status'], 'PASSIVE_HOST_DIAGNOSTIC_ONLY')
        self.assertEqual(report['pair_count'], 3)
        self.assertEqual(report['arms']['reference']['median_cpu_one_core_percent'], 50)
        self.assertEqual(report['arms']['candidate']['median_cpu_one_core_percent'], 25)
        self.assertIn('Cannot establish same physical host', report['limitations'])
        self.assertNotIn('speed_x', json.dumps(report))
        self.assertNotIn('acceptance_met', json.dumps(report))

    def test_wrong_pair_order_refused(self):
        self.manifest['trials'][2], self.manifest['trials'][3] = (
            self.manifest['trials'][3], self.manifest['trials'][2])
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'alternate'):
            self.compare()

    def test_duplicate_capture_path_refused(self):
        self.manifest['trials'][5]['directory'] = 'trial-1'
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'reused'):
            self.compare()

    def test_wrong_engine_process_or_variant_refused(self):
        self.write_capture(0, 'reference', process_name='webotsw')
        with self.assertRaisesRegex(ValueError, 'engine-only'):
            self.compare()
        self.write_capture(0, 'candidate')
        with self.assertRaisesRegex(ValueError, 'variant mismatch'):
            self.compare()

    def test_mismatched_engine_within_arm_refused(self):
        self.write_capture(4, 'reference', webots_executable_sha256='d' * 64)
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            self.compare()

    def test_mismatched_hardware_or_course_refused(self):
        self.write_capture(4, 'reference', course_id='route-6')
        with self.assertRaisesRegex(ValueError, 'different hardware/software/course'):
            self.compare()

    def test_less_than_thirty_seconds_refused(self):
        self.write_capture(0, 'reference', requested_duration_s=10)
        with self.assertRaisesRegex(ValueError, 'shorter than 30'):
            self.compare()

    def test_broken_clock_and_truncated_sample_refused(self):
        p = self.root / 'trial-0' / 'samples.csv'
        lines = p.read_text(encoding='utf-8-sig').splitlines()
        p.write_text('\n'.join(lines[:-1]) + '\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'missing host samples'):
            self.compare()
        self.write_capture(0, 'reference')
        with p.open(encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f))
        rows[1]['elapsed_ms'] = rows[0]['elapsed_ms']
        with p.open('w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        with self.assertRaisesRegex(ValueError, 'non-monotonic sample clock'):
            self.compare()

    def test_unsafe_nonfinite_sample_refused(self):
        p = self.root / 'trial-0' / 'samples.csv'
        with p.open(encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f))
        rows[0]['cpu_percent_one_core'] = 'NaN'
        with p.open('w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        with self.assertRaisesRegex(ValueError, 'finite nonnegative'):
            self.compare()

    def test_cpu_percentage_must_match_consecutive_cumulative_cpu(self):
        # R2025a PowerShell computes the one-core % from CPU-total delta.
        # A plausible 25% label on a true 50% sample must be rejected.
        p = self.root / 'trial-0' / 'samples.csv'
        with p.open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
        rows[10]['cpu_percent_one_core'] = '25'
        with p.open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        with self.assertRaisesRegex(ValueError, 'CPU percentage contradicts'):
            self.compare()

    def test_cumulative_cpu_cannot_disagree_with_declared_percentage(self):
        # Alter the CPU total while preserving monotonicity and the % label.
        p = self.root / 'trial-0' / 'samples.csv'
        with p.open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
        rows[10]['process_cpu_total_s'] = str(float(rows[10]['process_cpu_total_s']) + 0.2)
        with p.open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        with self.assertRaisesRegex(ValueError, 'CPU percentage contradicts'):
            self.compare()

    def test_sparse_capture_with_hidden_twenty_five_second_gap_refused(self):
        # Two rows can cover nominal 30 s but not a declared 500 ms cadence.
        p = self.root / 'trial-0'
        meta = json.loads((p / 'metadata.json').read_text())
        meta.update(sample_count=2, requested_period_ms=500, actual_duration_s=30)
        (p / 'metadata.json').write_text(json.dumps(meta))
        rows = [
            dict(elapsed_ms=5000, period_ms=5000, cpu_percent_one_core=100,
                 process_cpu_total_s=5),
            dict(elapsed_ms=30000, period_ms=25000, cpu_percent_one_core=0,
                 process_cpu_total_s=5)]
        with (p / 'samples.csv').open('w', encoding='utf-8-sig', newline='') as f:
            columns = ['elapsed_ms', 'period_ms', 'cpu_percent_one_core',
                       'process_cpu_total_s', 'working_set_bytes',
                       'private_memory_bytes', 'thread_count']
            w = csv.DictWriter(f, fieldnames=columns)
            w.writeheader()
            for sample in rows:
                sample.update(working_set_bytes=1000000,
                              private_memory_bytes=500000, thread_count=5)
                w.writerow(sample)
        with self.assertRaisesRegex(ValueError, 'observed sampling interval'):
            self.compare()

    def test_first_sample_clock_must_match_its_observed_period(self):
        p = self.root / 'trial-0' / 'samples.csv'
        with p.open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
        rows[0]['elapsed_ms'] = '1500'
        with p.open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        with self.assertRaisesRegex(ValueError, 'inconsistent host sampling interval'):
            self.compare()

    def test_unequal_valid_intervals_use_time_weighted_cpu_mean(self):
        # 15 x 100% over 1000ms and 15 x 0% over 1100ms: the temporal
        # mean is 47.619%, not the unweighted per-row mean of 50%.
        p = self.root / 'trial-0'
        meta = json.loads((p / 'metadata.json').read_text())
        meta['actual_duration_s'] = 31.505
        (p / 'metadata.json').write_text(json.dumps(meta))
        elapsed_ms = 0
        cumulative = 0.0
        rows = []
        for i in range(30):
            dt = 1000 if i % 2 == 0 else 1100
            pct = 100 if i % 2 == 0 else 0
            elapsed_ms += dt
            cumulative += dt * pct / 100000
            rows.append(dict(elapsed_ms=elapsed_ms, period_ms=dt,
                             cpu_percent_one_core=pct, process_cpu_total_s=cumulative,
                             working_set_bytes=1000000, private_memory_bytes=500000,
                             thread_count=5))
        with (p / 'samples.csv').open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        report = self.compare()
        self.assertEqual(report['arms']['reference']['trials'][0]['cpu_one_core_mean_percent'],
                         round(14 * 1000 * 100 / (14 * 1000 + 15 * 1100), 4))

    def test_first_cpu_percentage_unverifiable_and_excluded_from_aggregation(self):
        # The collector retains no pre-capture CPU total, so the first %
        # can change without contradicting any retained cumulative delta.
        report = self.compare()
        first = report['arms']['reference']['trials'][0]
        self.assertEqual(first['cpu_verified_duration_ms'], 29000)
        p = self.root / 'trial-0' / 'samples.csv'
        with p.open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
        rows[0]['cpu_percent_one_core'] = '300'
        with p.open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        changed = self.compare()['arms']['reference']['trials'][0]
        self.assertEqual(changed['cpu_one_core_mean_percent'],
                         first['cpu_one_core_mean_percent'])
        self.assertEqual(changed['cpu_verified_duration_ms'],
                         first['cpu_verified_duration_ms'])

    def test_five_sparse_6s_periods_rejected_as_insufficient_cpu_evidence(self):
        # Five rows span 30 seconds but only four CPU deltas (24s)
        # are independently checkable. First 100% is not evidence.
        p = self.root / 'trial-0'
        meta = json.loads((p / 'metadata.json').read_text())
        meta.update(sample_count=5, requested_period_ms=5000, actual_duration_s=30)
        (p / 'metadata.json').write_text(json.dumps(meta))
        with (p / 'samples.csv').open('w', encoding='utf-8-sig', newline='') as f:
            columns = ['elapsed_ms', 'period_ms', 'cpu_percent_one_core',
                       'process_cpu_total_s', 'working_set_bytes',
                       'private_memory_bytes', 'thread_count']
            w = csv.DictWriter(f, fieldnames=columns)
            w.writeheader()
            for i in range(5):
                w.writerow(dict(elapsed_ms=6000 * (i + 1), period_ms=6000,
                                cpu_percent_one_core=100 if i == 0 else 0,
                                process_cpu_total_s=10,
                                working_set_bytes=1000000,
                                private_memory_bytes=500000, thread_count=5))
        with self.assertRaisesRegex(ValueError, 'insufficient CPU-verified'):
            self.compare()

    def test_distinct_source_shas_between_arms_are_allowed_and_preserved(self):
        for i in (1, 2, 5):
            self.write_capture(i, 'candidate', source_sha='d' * 40)
        report = self.compare()
        self.assertEqual(report['arms']['reference']['source_sha'], 'a' * 40)
        self.assertEqual(report['arms']['candidate']['source_sha'], 'd' * 40)

    def test_source_sha_change_inside_arm_is_refused(self):
        self.write_capture(5, 'candidate', source_sha='d' * 40)
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            self.compare()

    def test_same_binary_not_a_meaningful_a_b(self):
        for i in (1, 2, 5):
            self.write_capture(i, 'candidate', webots_executable_sha256='b' * 64)
        with self.assertRaisesRegex(ValueError, 'identical engine'):
            self.compare()


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""Fail-closed, offline tests for passive Windows A/B host comparison (#914)."""

import csv
import json
from pathlib import Path
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location

SOURCE = Path(__file__).resolve().parents[1] / 'grand_prix' / 'compare_windows_host_ab.py'
spec = spec_from_file_location('compare_windows_host_ab', SOURCE)
compare_ab = module_from_spec(spec)
spec.loader.exec_module(compare_ab)


class WindowsHostABTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = tempfile.TemporaryDirectory()
        self.addCleanup(self.sandbox.cleanup)
        self.root = Path(self.sandbox.name)
        self.manifest = {
            'schema': 1, 'course_id': 'gp-route-v2-L2000-2500-3000-TGD-s17-H2',
            'declared_host': 'portable-windows-controlled-A', 'trials': [],
        }
        for i, arm in enumerate('ABBAAB'):
            directory = self.root / f'trial-{i}'
            directory.mkdir()
            self.manifest['trials'].append({'arm': arm, 'directory': directory.name})
            self.write_trial(directory, i, arm)
        self.save_manifest()

    def save_manifest(self):
        (self.root / 'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def write_trial(self, path, n, arm, *, duration=30):
        meta = {
            'schema': 'webeeblocks.windows-passive-host-v1',
            'sampling_scope': compare_ab.EXPECTED_SCOPE,
            'performance_acceptance': 'NOT_MEASURED',
            'course_id': self.manifest['course_id'],
            'webots_version': 'R2025a', 'process_name': 'webots-bin',
            'variant': 'reference' if arm == 'A' else 'candidate',
            'source_sha': ('a' if arm == 'A' else 'b') * 40,
            'webots_executable_sha256': ('c' if arm == 'A' else 'd') * 64,
            'webots_pid': 900 + n, 'process_start_utc': '2026-11-08T10:00:00Z',
            'actual_duration_s': duration, 'requested_duration_s': duration,
            'requested_period_ms': 10000, 'sample_count': duration // 10,
            'operating_system': {'caption': 'Windows 11', 'version': '10.0',
                                 'build': '26100', 'ram_bytes': 16 * 1024 ** 3},
            'cpus': [{'model': 'CPU fixture', 'logical_processors': 8}],
            'video_devices': [{'model': 'GPU fixture', 'driver_version': '2.4'}],
            'external_browser': {'exe_sha256': 'f' * 64, 'used_in_gui': 'UNVERIFIED'},
        }
        (path / 'metadata.json').write_text(json.dumps(meta), encoding='utf-8')
        with (path / 'samples.csv').open('w', encoding='utf-8-sig', newline='') as out:
            writer = csv.DictWriter(out, fieldnames=[
                'elapsed_ms', 'utc', 'period_ms', 'cpu_percent_one_core',
                'process_cpu_total_s', 'working_set_bytes', 'private_memory_bytes', 'thread_count'])
            writer.writeheader()
            for k in range(1, duration // 10 + 1):
                writer.writerow({
                    'elapsed_ms': 10000 * k, 'utc': '2026-11-08T10:00:00Z',
                    'period_ms': 10000, 'cpu_percent_one_core': (20 if arm == 'A' else 12) + n,
                    'process_cpu_total_s': 50 + n + k,
                    'working_set_bytes': 200000000 + 1000 * n + 100 * k,
                    'private_memory_bytes': 150000000 + 1000 * n + 100 * k,
                    'thread_count': 7,
                })
        return meta

    def compare(self):
        return compare_ab.compare(self.root / 'manifest.json')

    def test_three_alternating_pairs_only_host_metrics(self):
        result = self.compare()
        self.assertEqual(result['status'], 'HOST_ONLY_DIAGNOSTIC')
        self.assertEqual(len(result['pairs']), 3)
        self.assertEqual(result['source_identity']['A']['engine_sha256'], 'c' * 64)
        self.assertEqual(result['source_identity']['B']['engine_sha256'], 'd' * 64)
        self.assertIn('no measured Webots simulation speed', result['limitations'])
        self.assertNotIn('overall_product_acceptance', result)

    def test_short_but_consistent_captures_are_never_qualified(self):
        for n in range(6):
            self.write_trial(self.root / f'trial-{n}', n, 'ABBAAB'[n], duration=20)
        self.assertEqual(self.compare()['status'], 'INSUFFICIENT_CAPTURE_DURATION')

    def test_refuse_unpaired_or_reused_evidence(self):
        self.manifest['trials'][2]['arm'] = 'A'
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'AB/BA'):
            self.compare()
        self.manifest['trials'][2]['arm'] = 'B'
        self.manifest['trials'][3]['directory'] = self.manifest['trials'][2]['directory']
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'reused'):
            self.compare()

    def test_refuse_mixed_candidate_identity_and_host(self):
        path = self.root / 'trial-3' / 'metadata.json'
        meta = json.loads(path.read_text())
        meta['webots_executable_sha256'] = 'e' * 64
        path.write_text(json.dumps(meta))
        with self.assertRaisesRegex(ValueError, 'candidate identity changed'):
            self.compare()
        meta['webots_executable_sha256'] = 'c' * 64
        meta['video_devices'][0]['driver_version'] = '3.0'
        path.write_text(json.dumps(meta))
        with self.assertRaisesRegex(ValueError, 'inconsistent Windows'):
            self.compare()

    def test_refuse_corrupt_host_samples(self):
        path = self.root / 'trial-0' / 'samples.csv'
        content = path.read_text(encoding='utf-8-sig')
        path.write_text(content.replace('10000,2026-', '10001,2026-', 1), encoding='utf-8-sig')
        with self.assertRaisesRegex(ValueError, 'sample period'):
            self.compare()

    def test_refuse_launcher_pid_and_missing_digest(self):
        path = self.root / 'trial-0' / 'metadata.json'
        meta = json.loads(path.read_text())
        meta['process_name'] = 'webotsw'
        path.write_text(json.dumps(meta))
        with self.assertRaisesRegex(ValueError, 'engine PID'):
            self.compare()
        meta['process_name'] = 'webots-bin'
        meta['source_sha'] = None
        path.write_text(json.dumps(meta))
        with self.assertRaisesRegex(ValueError, 'digests'):
            self.compare()


if __name__ == '__main__':
    unittest.main()

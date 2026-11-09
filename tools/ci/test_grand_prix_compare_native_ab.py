"""Refute false native Webots A/B wins without requiring a Windows host."""
import json
from pathlib import Path
import tempfile
import unittest

from tools.grand_prix.compare_native_ab import compare


class NativeEngineABTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for arm, engine in (('A', 'b' * 64), ('B', 'c' * 64)):
            inventory = dict(
                schema='webeeblocks-grand-prix-windows-host-v1',
                source_sha='a' * 40,
                os={'version': '10', 'build': '26100'},
                physical_memory_bytes=16 * 1024**3,
                cpu=[{'model': 'test CPU'}],
                display_adapters=[{'model': 'test GPU', 'driver': '1'}],
                browser=None,
                webots=dict(release='R2025a', exe_relative_path='msys64/mingw64/bin/webots-bin.exe',
                            exe_sha256=engine),
                measurement_state='INVENTORY_ONLY_NOT_A_PERFORMANCE_OR_ACCEPTANCE_RESULT')
            (self.root / f'inventory-{arm}.json').write_text(json.dumps(inventory))
        self.manifest = dict(
            schema=1, source_sha='a' * 40, program_sha256='d' * 64,
            course='route-5', host_id='same-host-operator-declared',
            display_mode='visible same viewport', render_fps=25,
            phase_ms=[0, 30000],
            inventories={'A': 'inventory-A.json', 'B': 'inventory-B.json'}, trials=[])
        for run, arm in enumerate('ABBAAB'):
            path = f'run-{run}.log'
            self.manifest['trials'].append({'arm': arm, 'log': path})
            self.write_native_log(path, run, arm)
        self.save()

    def save(self):
        (self.root / 'manifest.json').write_text(json.dumps(self.manifest))

    def write_native_log(self, name, run, arm, count=30):
        rows = []
        step = 6_000_000 if arm == 'A' else 4_000_000
        wall = 125 * (step + 1_000_000)
        for i in range(count):
            start = run * 100_000_000_000 + i * (wall + 1_000_000)
            rec = dict(schema=1, course='route-5', window=i, reason='complete', count=125,
                       start_sim_ms=1000 * i, end_sim_ms=1000 * i + 992,
                       simulated_ms=1000, step_ns=[step] * 125,
                       tick_ns=[1_000_000] * 125, wall_ns=wall,
                       first_start_wall_ns=start, last_end_wall_ns=start + wall,
                       step_p50_ns=step, step_p95_ns=step, step_p99_ns=step,
                       step_max_ns=step, tick_p99_ns=1_000_000,
                       speed_x=round(1_000_000_000 / wall, 6))
            rows.append('Webots GP_STEP_WALL_V1 ' + json.dumps(rec))
        (self.root / name).write_text('\n'.join(rows) + '\n')

    def compare(self):
        return compare(self.root / 'manifest.json')

    def test_three_pairs_distinct_engines_only_diagnostic(self):
        result = self.compare()
        self.assertEqual(result['pair_count'], 3)
        self.assertEqual(result['observed_simulated_phase_ms'], [0, 30000])
        self.assertGreater(result['arms']['B']['median_speed_observed_envelope_x'],
                           result['arms']['A']['median_speed_observed_envelope_x'])
        self.assertNotIn('overall_product_acceptance', result)
        self.assertIn('not tied to the actually running PID', result['interpretation'])

    def test_same_engine_bytes_refused(self):
        p = self.root / 'inventory-B.json'
        data = json.loads(p.read_text())
        data['webots']['exe_sha256'] = 'b' * 64
        p.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'distinct native engines'):
            self.compare()

    def test_different_gpu_driver_refused(self):
        p = self.root / 'inventory-B.json'
        data = json.loads(p.read_text())
        data['display_adapters'][0]['driver'] = 'different'
        p.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'inventory differs'):
            self.compare()

    def test_partial_phase_refused(self):
        self.write_native_log('run-0.log', 0, 'A', count=29)
        with self.assertRaisesRegex(ValueError, '30 consecutive simulated seconds'):
            self.compare()

    def test_replayed_native_observations_refused(self):
        (self.root / 'run-4.log').write_bytes((self.root / 'run-0.log').read_bytes())
        with self.assertRaisesRegex(ValueError, 'replayed native observations'):
            self.compare()

    def test_inconsistent_raw_step_summary_refused(self):
        p = self.root / 'run-0.log'
        rows = p.read_text().splitlines()
        first = json.loads(rows[0].split('GP_STEP_WALL_V1 ')[1])
        first['step_p99_ns'] = 999
        rows[0] = 'GP_STEP_WALL_V1 ' + json.dumps(first)
        p.write_text('\n'.join(rows) + '\n')
        with self.assertRaisesRegex(ValueError, 'inconsistent native probe summary'):
            self.compare()


if __name__ == '__main__':
    unittest.main()

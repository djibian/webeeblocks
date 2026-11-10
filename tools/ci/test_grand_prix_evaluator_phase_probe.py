"""Refutable, host-only semantics of the optional phase-probe."""
import json
import unittest

from tools.grand_prix.evaluator_phase_probe import EvaluatorPhaseProbe, PREFIX


class EvaluatorPhaseProbeTests(unittest.TestCase):
    def test_raw_windows_and_missing_stages(self):
        log = []
        probe = EvaluatorPhaseProbe('route-5', log.append, window_steps=2)
        probe.begin()
        probe.record('exportString', 10)
        probe.record('exportString', 20)
        with probe.phase('scene_and_colliders'):
            pass
        probe.end(8)
        self.assertEqual(log, [])
        probe.begin()
        probe.end(16)
        self.assertEqual(len(log), 1)
        self.assertTrue(log[0].startswith(PREFIX))
        data = json.loads(log[0][len(PREFIX):])
        self.assertEqual([r['sim_ms'] for r in data['rows']], [8, 16])
        self.assertEqual(data['rows'][0]['durations_ns']['exportString'], 30)
        self.assertIn('scene_and_colliders', data['rows'][0]['durations_ns'])
        self.assertNotIn('exportString', data['rows'][1]['durations_ns'])
        self.assertTrue(all(row['durations_ns']['tick_total'] >= 0 for row in data['rows']))

    def test_reject_overlapping_timing(self):
        probe = EvaluatorPhaseProbe('route-5', lambda _: None)
        probe.begin()
        with self.assertRaises(RuntimeError):
            probe.begin()
        with self.assertRaises(RuntimeError):
            probe.flush()
        probe.end(8)


if __name__ == '__main__':
    unittest.main()

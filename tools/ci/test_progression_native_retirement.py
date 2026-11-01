#!/usr/bin/env python3
"""Deterministic fail-closed checks for M1b; no Webots process is launched."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from progression_native_retirement import (
    COMPLETE, SUMMARY, complete_evidence, required_events, verify_native_report,
)

def witness(mode):
    rows = []
    for name in required_events(mode):
        if name == COMPLETE[mode]:
            detail = copy.deepcopy(SUMMARY[mode])
        elif name.endswith('_FRESH') or name.endswith('_UNAVAILABLE'):
            detail = {'code': 'OUTCOME_UNAVAILABLE'}
        elif name.endswith('_NOT_ACHIEVED'):
            detail = {'status': 'not-achieved'}
        elif name.endswith('_ACHIEVED'):
            detail = {'status': 'achieved'}
        elif name.endswith('_PROBE_READY'):
            detail = {'ready': True}
        elif name == 'AUTONOMOUS_DEPARTURE_SMALL_RANGE':
            detail = {'meters': 1.5}
        elif name == 'AUTONOMOUS_DEPARTURE_LARGE_RANGE':
            detail = {'meters': 0.3}
        else:
            detail = {}
        rows.append({'event': name, 'detail': detail})
    return rows

def write_events(path, rows):
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')

class RetirementGuards(unittest.TestCase):
    def test_complete_requires_original_negative_oracles(self):
        for mode in ('memory', 'autonomous'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / 'events.jsonl'
                rows = witness(mode)
                write_events(path, rows)
                self.assertEqual(complete_evidence(mode, path, required_events(mode)),
                                 hashlib.sha256(path.read_bytes()).hexdigest())
                changed = copy.deepcopy(rows)
                target = next(row for row in changed if row['event'].endswith('_NOT_ACHIEVED'))
                target['detail'] = {'status': 'achieved'}
                write_events(path, changed)
                with self.assertRaises(RuntimeError):
                    complete_evidence(mode, path, required_events(mode))
                changed = rows + [{'event': COMPLETE[mode], 'detail': SUMMARY[mode]}]
                write_events(path, changed)
                with self.assertRaises(RuntimeError):
                    complete_evidence(mode, path, required_events(mode))
                changed = rows + [{'event': 'ERROR', 'detail': {'message': 'late browser error'}}]
                write_events(path, changed)
                with self.assertRaises(RuntimeError):
                    complete_evidence(mode, path, required_events(mode))
                write_events(path, rows[:-1])
                self.assertIsNone(complete_evidence(mode, path, required_events(mode)))

    def test_native_report_cannot_be_replaced_by_wrapper_status(self):
        for mode in ('memory', 'autonomous'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                payload = 'hello native\n'
                (root / 'webots.log').write_text(payload)
                events = root / 'browser-events.jsonl'
                write_events(events, witness(mode))
                request = mode + ' ' + 'a' * 32 + '\n'
                (root / 'normal-quit.request').write_text(request)
                (root / 'normal-quit.ack').write_text(request)
                original = {
                    'schema': 1, 'kind': mode, 'normal_success': True,
                    'browser_complete': True, 'requested': True,
                    'acknowledged': True, 'stdout_eof': True,
                    'native_exit_code': 0, 'proofs_unchanged': True,
                    'fallback_used': False, 'native_pid': 42,
                    'native_binary': '/usr/local/webots/bin/webots-bin',
                    'owned_group_state': {'status': 'empty', 'evidence': 'kernel-pgid-esrch'},
                    'frozen_events_sha256': hashlib.sha256(events.read_bytes()).hexdigest(),
                }
                report = root / 'normal-quit.json'
                def write(obj):
                    report.write_text(json.dumps(obj))
                write(original)
                self.assertEqual(verify_native_report(root, mode), original)
                for field, value in [('native_exit_code', -11), ('stdout_eof', False),
                                     ('acknowledged', False), ('fallback_used', True),
                                     ('native_binary', '/usr/bin/xvfb-run'),
                                     ('owned_group_state', {'status': 'unknown'})]:
                    mutant = copy.deepcopy(original)
                    mutant[field] = value
                    with self.subTest(field=field):
                        write(mutant)
                        with self.assertRaises(RuntimeError):
                            verify_native_report(root, mode)
                write(original)
                (root / 'normal-quit.ack').write_text(mode + ' ' + 'b' * 32 + '\n')
                with self.assertRaises(RuntimeError):
                    verify_native_report(root, mode)
                (root / 'normal-quit.ack').write_text(request)
                (root / 'webots.log').write_text('Segmentation fault\n')
                with self.assertRaises(RuntimeError):
                    verify_native_report(root, mode)

    def test_original_runners_do_not_synthesize_zero_after_complete(self):
        scripts = ('run_progression_memory_overwrite.py',
                   'run_progression_autonomous_mission.py')
        for script in scripts:
            source = (Path(__file__).parent / script).read_text()
            with self.subTest(script=script):
                self.assertNotIn('kill "$webots_runner"', source)
                self.assertNotIn('exit "$runner_rc"', source)
                self.assertIn('verify_native_report(ARTIFACT_ROOT,', source)
                self.assertIn('ci_progression_retirement', source)

if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""Deterministic fail-closed checks for M1b; no Webots process is launched."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from autonomous_incident_evidence import (
    SCHEMA, record_prelaunch, run_host_streamed, record_completion,
)
from progression_native_retirement import finish_failed_autonomous_log
from progression_native_retirement import (
    COMPLETE, SUMMARY, complete_evidence, required_events, verify_native_report,
    require_container_processes_retired,
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

def process_inventory(*processes):
    return {'status': 'ok', 'pid_namespace': 'pid:[123]', 'membership': '0::/trial',
            'truncated': False, 'task_truncated': False,
            'processes': [{'pid': pid, 'start_ticks': start,
                           'pid_namespace': 'pid:[123]'} for pid, start in processes]}

class RetirementGuards(unittest.TestCase):
    def test_detached_process_cannot_hide_behind_native_exit_eof_and_empty_pgid(self):
        before = process_inventory((1, 10), (7, 20))
        require_container_processes_retired(before, copy.deepcopy(before))
        # The namespace is private: a new Chrome identity belongs to this trial,
        # regardless of its reparenting, different PGID, or redirected pipes.
        with self.assertRaises(RuntimeError):
            require_container_processes_retired(before,
                                                process_inventory((1, 10), (7, 20), (99, 30)))
        # Reusing a baseline PID must not exempt a different process.
        with self.assertRaises(RuntimeError):
            require_container_processes_retired(before, process_inventory((1, 10), (7, 21)))

    def test_missing_partial_or_changed_process_scope_is_not_absence(self):
        before = process_inventory((1, 10), (7, 20))
        for field, value in [('status', 'partial'), ('truncated', True),
                             ('task_truncated', True), ('membership', '0::/other'),
                             ('pid_namespace', 'pid:[456]'), ('processes', [])]:
            after = copy.deepcopy(before)
            after[field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                require_container_processes_retired(before, after)
        with self.assertRaises(RuntimeError):
            require_container_processes_retired(None, before)

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
                    'container_processes_before': process_inventory((1, 10), (7, 20)),
                    'container_processes_after': process_inventory((1, 10), (7, 20)),
                }
                report = root / 'normal-quit.json'
                def write(obj):
                    report.write_text(json.dumps(obj))
                write(original)
                self.assertEqual(verify_native_report(root, mode), original)
                for field, value in [('native_exit_code', -11), ('stdout_eof', False),
                                     ('acknowledged', False), ('fallback_used', True),
                                     ('native_binary', '/usr/bin/xvfb-run'),
                                     ('owned_group_state', {'status': 'unknown'}),
                                     ('container_processes_after',
                                      process_inventory((1, 10), (7, 20), (99, 30))),
                                     ('container_processes_before', None)]:
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


class IncidentEvidenceP1(unittest.TestCase):
    def test_prelaunch_provenance_is_observed_not_assumed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            world = root / 'world.wbt'
            world.write_bytes(b'world-bytes')
            envelope = record_prelaunch(
                root, image='webots@sha256:fixed', command=['docker', 'run'],
                inner_script='native test', head='a' * 40,
                input_files={'world': world, 'unknown': root / 'missing.c'})
            self.assertEqual(envelope['schema'], SCHEMA)
            self.assertEqual(envelope['inputs']['world']['sha256'],
                             hashlib.sha256(b'world-bytes').hexdigest())
            self.assertEqual(envelope['inputs']['unknown']['status'], 'unknown')
            self.assertEqual(envelope['webots_bin_and_libode_mappings'], 'unknown')
            self.assertEqual(envelope['native_result'], 'unobserved')
            with self.assertRaises(FileExistsError):
                record_prelaunch(root, image='webots@sha256:fixed',
                                 command=['docker'], inner_script='', head='a' * 40,
                                 input_files={})

    def test_streamed_host_log_keeps_prefix_after_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'native-host.log'
            def interrupted(_argv, **kwargs):
                kwargs['stdout'].write(b'partial native output\n')
                kwargs['stdout'].flush()
                raise OSError('host interrupted')
            with mock.patch('autonomous_incident_evidence.subprocess.run',
                            side_effect=interrupted):
                with self.assertRaises(OSError):
                    run_host_streamed(['docker', 'run'], path, cwd=Path(temp), env={})
            self.assertEqual(path.read_bytes(), b'partial native output\n')
            with self.assertRaises(FileExistsError):
                run_host_streamed(['docker'], path, cwd=Path(temp), env={})

    def test_partial_jsonl_and_unknown_exit_cannot_claim_a_native_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'native-reset-state.jsonl').write_bytes(b'{"type":"header"}\n{"partial":')
            (root / 'native-host.log').write_bytes(b'partial')
            result = record_completion(root, docker_returncode=None)
            self.assertEqual(result['docker_returncode'], 'unknown')
            self.assertEqual(result['native_report']['status'], 'unknown')
            self.assertFalse(result['files']['native-reset-state.jsonl']['newline_terminated'])
            self.assertEqual(result['files']['browser-events.jsonl']['status'], 'unknown')
            self.assertEqual(result['oracle_verdict'], 'not_assigned_by_diagnostics')
            self.assertEqual(result['causal_attribution'], 'UNPROVEN')
            with self.assertRaises(FileExistsError):
                record_completion(root, docker_returncode=0)

    def test_failed_native_report_stays_failed_even_with_clean_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'normal-quit.json').write_text(json.dumps({
                'normal_success': False, 'fallback_used': True,
                'failure_log_capture': 'stdout_eof', 'stdout_eof': False,
            }))
            result = record_completion(root, docker_returncode=1)
            self.assertIs(result['native_report']['normal_success_reported'], False)
            self.assertIs(result['native_report']['fallback_used'], True)
            self.assertEqual(result['docker_returncode'], 1)
            self.assertEqual(result['native_report']['failure_log_capture'], 'stdout_eof')
            self.assertEqual(result['oracle_verdict'], 'not_assigned_by_diagnostics')

    def test_autonomous_error_drain_is_bounded_and_never_overrides_original(self):
        for error in (None, RuntimeError('EOF absent'), OSError('disk read failed')):
            report = {'normal_success': False, 'fallback_used': True,
                      'error': 'initial native failure'}
            log = mock.Mock()
            log.finish.side_effect = error
            finish_failed_autonomous_log('autonomous', log, report)
            log.finish.assert_called_once_with(timeout=8)
            self.assertEqual(report['normal_success'], False)
            self.assertEqual(report['error'], 'initial native failure')
            self.assertEqual(report['failure_log_capture'],
                             'stdout_eof' if error is None else 'partial_or_unknown')
        report = {'normal_success': False}
        log = mock.Mock()
        finish_failed_autonomous_log('memory', log, report)
        log.finish.assert_not_called()
        self.assertEqual(report, {'normal_success': False})


if __name__ == '__main__':
    unittest.main()

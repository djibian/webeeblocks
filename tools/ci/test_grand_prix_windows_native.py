"""Ensure installed-campaign evidence never turns incomplete execution into PASS."""
import copy
import json
import linecache
import os
import signal
from pathlib import Path
import sys
import subprocess
import time
from unittest import mock
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.ci import run_grand_prix_windows_native as harness
from tools.ci.run_grand_prix_windows_native import captured_engine, engine_environment, validate, stop, _filter_windows_tree
from tools.grand_prix.layout_u import generate
from tools.grand_prix.package_windows_u import local_world


class EvidenceTests(unittest.TestCase):
    def test_owned_pid_preexited_crash_refused_without_taskkill(self):
        for code in (1, -1073741819):
            with self.subTest(code=code):
                process = mock.Mock(pid=123)
                process.poll.return_value = code
                with mock.patch('tools.ci.run_grand_prix_windows_native.subprocess.run') as run:
                    with self.assertRaisesRegex(RuntimeError, f'process={code}'):
                        stop(process)
                    run.assert_not_called()
                process.wait.assert_not_called()

    def test_intentional_taskkill_success_does_not_misclassify_forced_exit(self):
        process = mock.Mock(pid=123)
        process.poll.return_value = None
        process.wait.return_value = 1
        with mock.patch('tools.ci.run_grand_prix_windows_native.subprocess.run') as run:
            stop(process)
            self.assertEqual(run.call_args.args[0], ['taskkill', '/PID', '123', '/T', '/F'])
        process.wait.assert_called_once_with(timeout=20)

    def test_owned_pid_cleanup_race_refuses_nonzero_or_still_running(self):
        command = ['taskkill', '/PID', '123', '/T', '/F']
        for after in (1, -1073741819):
            process = mock.Mock(pid=123)
            process.poll.side_effect = [None, after]
            error = subprocess.CalledProcessError(255, command, output=b'PID not found')
            with mock.patch('tools.ci.run_grand_prix_windows_native.subprocess.run',
                            side_effect=error) as run:
                with self.assertRaisesRegex(RuntimeError, 'cleanup unproven') as raised:
                    stop(process)
                self.assertIn(f'process={after}', str(raised.exception))
                self.assertIn('PID not found', str(raised.exception))
                self.assertEqual(run.call_args.args[0], command)
                self.assertTrue(run.call_args.kwargs['check'])
            process.wait.assert_not_called()

        # taskkill failed and the owned process is still alive after the
        # bounded grace period: never turn the missing exit into a PASS.
        process = mock.Mock(pid=123)
        process.poll.side_effect = [None, None]
        process.wait.side_effect = subprocess.TimeoutExpired(command, 5)
        with mock.patch('tools.ci.run_grand_prix_windows_native.subprocess.run',
                        side_effect=subprocess.CalledProcessError(255, command)):
            with self.assertRaisesRegex(RuntimeError, 'process=None'):
                stop(process)
        process.wait.assert_called_once_with(timeout=5)

    def test_owned_pid_cleanup_race_refuses_ambiguous_taskkill_even_after_exit_zero(self):
        command = ['taskkill', '/PID', '123', '/T', '/F']
        process = mock.Mock(pid=123)
        process.poll.side_effect = [None, 0]
        with mock.patch('tools.ci.run_grand_prix_windows_native.subprocess.run',
                        side_effect=subprocess.CalledProcessError(128, command)) as run:
            with self.assertRaisesRegex(RuntimeError, 'taskkill=128, process=0'):
                stop(process)
            self.assertEqual(run.call_args.args[0], command)
        process.wait.assert_not_called()

        # A delayed zero exit also cannot excuse an ambiguous taskkill result.
        delayed = mock.Mock(pid=123)
        delayed.poll.side_effect = [None, None]
        delayed.wait.side_effect = [0, 0]
        with mock.patch('tools.ci.run_grand_prix_windows_native.subprocess.run',
                        side_effect=subprocess.CalledProcessError(255, command)):
            with self.assertRaisesRegex(RuntimeError, 'taskkill=255, process=0'):
                stop(delayed)
        self.assertEqual(delayed.wait.call_args_list, [mock.call(timeout=5)])

        # The auxiliary Node probe (no diagnostic/descendant attestation)
        # is legitimately reaped by its own successful wait contract.
        already_stopped = mock.Mock(pid=123)
        already_stopped.poll.return_value = 0
        with mock.patch('tools.ci.run_grand_prix_windows_native.subprocess.run') as run:
            stop(already_stopped)
            run.assert_not_called()

    def test_poll_zero_surviving_qtwebengine_or_late_child_is_refused(self):
        root = dict(pid=2232, parent=50, created='root-start',
                    name='webots-bin.exe')
        child = dict(pid=4520, parent=2232, created='child-start',
                     name='QtWebEngineProcess.exe')
        for known_at_launch in (True, False):
            with self.subTest(known_at_launch=known_at_launch), tempfile.TemporaryDirectory() as tmp:
                process = mock.Mock(pid=2232)
                process.poll.return_value = 0
                early = dict(available=True, root_present=True,
                             owned=[root, child] if known_at_launch else [root])
                # The root is gone. A new CIM census still exposes surviving
                # children by ParentProcessId; it cannot prove their ancestry
                # retroactively, so an untracked candidate must also veto PASS.
                raw = [dict(ProcessId=4520, ParentProcessId=2232,
                            CreationDate='child-start', Name='QtWebEngineProcess.exe')]
                watched = [p['pid'] for p in early['owned']]
                after = _filter_windows_tree(raw, 2232, watched)
                self.assertFalse(after['root_present'])
                self.assertEqual([p['pid'] for p in after['owned']], [4520])
                evidence = Path(tmp) / 'cleanup.json'
                with mock.patch(
                        'tools.ci.run_grand_prix_windows_native._windows_process_snapshot',
                        return_value=after) as snap, mock.patch(
                        'tools.ci.run_grand_prix_windows_native.subprocess.run') as run:
                    expected = ('same-identity descendants survived' if known_at_launch
                                else 'post-census descendants still present')
                    with self.assertRaisesRegex(RuntimeError, expected):
                        stop(process, diagnostic_path=evidence, launch_snapshot=early)
                    snap.assert_called_once_with(2232, watched)
                    run.assert_not_called()
                actual = json.loads(evidence.read_text(encoding='utf-8'))
                self.assertEqual(actual['root_exit_at_stop'], 0)
                self.assertNotIn('taskkill_returncode', actual)
                self.assertEqual(len(
                    actual['still_present_same_pid_and_creation'] if known_at_launch
                    else actual['untracked_owned_after_cleanup']), 1)
                process.wait.assert_not_called()

    def test_poll_zero_without_positive_early_root_identity_is_refused(self):
        root = dict(pid=2232, parent=50, created='root-start',
                    name='webots-bin.exe')
        child = dict(pid=4520, parent=2232, created='child-start',
                     name='QtWebEngineProcess.exe')
        cases = [
            (None, 'before-snapshot-unavailable'),
            (dict(available=False, error='CIM unavailable'), 'before-snapshot-unavailable'),
            (dict(available=True, root_present=False, owned=[]),
             'before-root-identity-unavailable'),
            (dict(available=True, root_present=True, owned=[dict(root, created=None)]),
             'creation-identity-unavailable'),
            (dict(available=True, root_present=True, owned=[root, dict(child, created=None)]),
             'creation-identity-unavailable'),
        ]
        for early, reason in cases:
            with self.subTest(reason=reason, early=early), tempfile.TemporaryDirectory() as tmp:
                process = mock.Mock(pid=2232)
                process.poll.return_value = 0
                diagnostic = Path(tmp) / 'cleanup.json'
                after = dict(available=True, root_present=False, owned=[], watched=[])
                with mock.patch(
                        'tools.ci.run_grand_prix_windows_native._windows_process_snapshot',
                        return_value=after), mock.patch(
                        'tools.ci.run_grand_prix_windows_native.subprocess.run') as run:
                    with self.assertRaisesRegex(RuntimeError, 'observation unavailable'):
                        stop(process, diagnostic_path=diagnostic, launch_snapshot=early)
                    run.assert_not_called()
                record = json.loads(diagnostic.read_text(encoding='utf-8'))
                self.assertIn(reason, record['cleanup_observation_gaps'])
                self.assertNotIn('taskkill_returncode', record)

    def test_poll_zero_genuinely_attested_retirement_and_after_cim_refusal(self):
        root = dict(pid=2232, parent=50, created='root-start',
                    name='webots-bin.exe')
        child = dict(pid=4520, parent=2232, created='child-start',
                     name='QtWebEngineProcess.exe')
        early = dict(available=True, root_present=True, owned=[root, child])
        for after_available in (True, False):
            with self.subTest(after_available=after_available), tempfile.TemporaryDirectory() as tmp:
                process = mock.Mock(pid=2232)
                process.poll.return_value = 0
                process.active_job_processes.return_value = 0
                diagnostic = Path(tmp) / 'cleanup.json'
                after = (dict(available=True, root_present=False, owned=[], watched=[])
                         if after_available else dict(available=False, error='CIM failed'))
                with mock.patch(
                        'tools.ci.run_grand_prix_windows_native._windows_process_snapshot',
                        return_value=after) as snap, mock.patch(
                        'tools.ci.run_grand_prix_windows_native.subprocess.run') as run:
                    if after_available:
                        stop(process, diagnostic_path=diagnostic, launch_snapshot=early)
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'after-snapshot-unavailable'):
                            stop(process, diagnostic_path=diagnostic, launch_snapshot=early)
                    snap.assert_called_once_with(2232, [2232, 4520])
                    run.assert_not_called()
                actual = json.loads(diagnostic.read_text(encoding='utf-8'))
                self.assertEqual(actual['before'], early)
                self.assertEqual(actual['after'], after)
                self.assertEqual(actual['root_exit_at_stop'], 0)
                self.assertNotIn('taskkill_returncode', actual)
                if after_available:
                    self.assertEqual(actual['still_present_same_pid_and_creation'], [])
                    self.assertEqual(actual['untracked_owned_after_cleanup'], [])
                    self.assertEqual(actual['cleanup_observation_gaps'], [])
                    self.assertEqual(actual['job_active_processes'], 0)
                process.wait.assert_not_called()

    def test_poll_zero_late_grandchild_requires_job_accounting(self):
        early = _filter_windows_tree([
            dict(ProcessId=2232, ParentProcessId=50, CreationDate='t0', Name='webots-bin.exe')
        ], 2232)
        final_rows = [dict(ProcessId=4520, ParentProcessId=3333, CreationDate='t2',
                           Name='QtWebEngineProcess.exe')]
        after = _filter_windows_tree(final_rows, 2232, watched=[2232])
        self.assertFalse(after['root_present'])
        self.assertEqual(after['owned'], [])
        self.assertEqual(after['watched'], [])
        for active in (1, None):
            with self.subTest(active=active), tempfile.TemporaryDirectory() as tmp:
                process = mock.Mock(pid=2232)
                process.poll.return_value = 0
                if active is None:
                    process.active_job_processes.side_effect = OSError('Job query unavailable')
                else:
                    process.active_job_processes.return_value = active
                diagnostic = Path(tmp) / 'webots-process-cleanup.json'
                with mock.patch('tools.ci.run_grand_prix_windows_native._windows_process_snapshot',
                                return_value=after), mock.patch(
                        'tools.ci.run_grand_prix_windows_native.subprocess.run') as run:
                    with self.assertRaisesRegex(RuntimeError, f'job cleanup unproven: active processes={active}'):
                        stop(process, diagnostic_path=diagnostic, launch_snapshot=early)
                    run.assert_not_called()
                evidence = json.loads(diagnostic.read_text(encoding='utf-8'))
                self.assertEqual(evidence['cleanup_observation_gaps'], [])
                self.assertEqual(evidence['job_active_processes'], active)
                if active is None:
                    self.assertEqual(evidence['job_accounting_error'], 'Job query unavailable')

    def test_cim_interruption_closes_handles_before_caller_resumes(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            command = [sys.executable, '-c', 'import time; time.sleep(60)']
            with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as child:
                process = mock.Mock(pid=child.pid, stdout=child.stdout, stderr=child.stderr)
                process.poll.side_effect = child.poll
                process.close_job.side_effect = child.kill
                before = _filter_windows_tree([
                    dict(ProcessId=child.pid, ParentProcessId=os.getpid(),
                         CreationDate='t0', Name='webots-bin.exe')
                ], child.pid)
                interruption = KeyboardInterrupt('during stop CIM')
                try:
                    with mock.patch.object(sys, 'platform', 'win32'), mock.patch.object(
                            harness, 'WindowsJobProcess', return_value=process, create=True), mock.patch.object(
                            harness, '_windows_process_snapshot', side_effect=[before, interruption]) as snapshot, mock.patch.object(
                            harness.subprocess, 'run') as run:
                        with self.assertRaises(KeyboardInterrupt) as raised:
                            with captured_engine(command, directory, {},
                                                 directory / 'stdout', directory / 'stderr'):
                                self.assertIsNone(child.poll())
                    self.assertIs(raised.exception, interruption)
                    self.assertEqual(snapshot.call_args_list, [mock.call(child.pid), mock.call(child.pid)])
                    run.assert_not_called()
                    process.close_job.assert_called_once_with()
                    process.close_process.assert_called_once_with()
                    self.assertNotEqual(child.wait(timeout=5), 0)
                    evidence = json.loads((directory / 'webots-process-cleanup.json').read_text(encoding='utf-8'))
                    self.assertEqual(evidence['primary_exception'], 'KeyboardInterrupt: during stop CIM')
                    self.assertNotIn('job_active_processes', evidence)
                finally:
                    if child.poll() is None:
                        child.kill()

    def test_taskkill_128_remains_primary_when_capture_pipe_stays_open(self):
        root = dict(pid=2232, parent=50, created='t0', name='webots-bin.exe')
        before = dict(available=True, root_present=True, owned=[root])
        after = dict(available=True, root_present=False, owned=[], watched=[])
        process = mock.Mock(pid=2232)
        process.poll.side_effect = [None, None, None, 0]
        process.active_job_processes.return_value = 1
        failed = subprocess.CalledProcessError(128, ['taskkill'], output=b'SUCCESS: terminated root')
        thread = mock.Mock()
        thread.is_alive.return_value = True
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with mock.patch.object(sys, 'platform', 'win32'), mock.patch(
                    'tools.ci.run_grand_prix_windows_native.WindowsJobProcess',
                    return_value=process, create=True), mock.patch(
                    'tools.ci.run_grand_prix_windows_native._windows_process_snapshot',
                    side_effect=[before, before, after]), mock.patch(
                    'tools.ci.run_grand_prix_windows_native.threading.Thread', return_value=thread), mock.patch(
                    'tools.ci.run_grand_prix_windows_native.subprocess.run', side_effect=failed):
                with self.assertRaisesRegex(RuntimeError, 'taskkill=128, process=0') as raised:
                    with captured_engine(['webots-bin.exe'], directory, {},
                                         directory / 'stdout', directory / 'stderr'):
                        pass
            self.assertIs(raised.exception.__cause__, failed)
            self.assertIn('pipes did not close', raised.exception.__notes__[0])
            evidence = json.loads((directory / 'webots-process-cleanup.json').read_text(encoding='utf-8'))
            self.assertEqual(evidence['taskkill_returncode'], 128)
            self.assertIn('taskkill=128', evidence['exception'])
            self.assertIn('pipes did not close', evidence['secondary_errors'][0])
            process.close_job.assert_called_once_with()

    def test_capture_preserves_primary_when_cleanup_operations_fail(self):
        for stop_fails in (False, True):
            with self.subTest(stop_fails=stop_fails), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                process = mock.Mock(pid=2232)
                stop_error = OSError('stop failed') if stop_fails else None
                job_error = OSError('CloseHandle(job) failed')
                process.close_job.side_effect = job_error
                process.close_process.side_effect = OSError('CloseHandle(process) failed')
                thread = mock.Mock()
                thread.join.side_effect = [KeyboardInterrupt('joining capture pipe'), None]
                thread.is_alive.return_value = False
                expected = stop_error or job_error
                with mock.patch.object(sys, 'platform', 'win32'), mock.patch.object(
                        harness, 'WindowsJobProcess', return_value=process, create=True), mock.patch.object(
                        harness, 'stop', side_effect=stop_error), mock.patch.object(
                        harness.threading, 'Thread', return_value=thread):
                    with self.assertRaises(OSError) as raised:
                        with captured_engine(['webots-bin.exe'], directory, {},
                                             directory / 'stdout', directory / 'stderr'):
                            pass
                self.assertIs(raised.exception, expected)
                process.close_job.assert_called_once_with()
                process.close_process.assert_called_once_with()
                self.assertEqual(thread.join.call_args_list, [mock.call(timeout=20)] * 2)
                evidence = json.loads((directory / 'webots-process-cleanup.json').read_text(encoding='utf-8'))
                self.assertEqual(evidence['primary_exception'], f'OSError: {expected}')
                secondary = ['OSError: CloseHandle(process) failed', 'KeyboardInterrupt: joining capture pipe']
                if stop_fails:
                    secondary.insert(0, 'OSError: CloseHandle(job) failed')
                self.assertEqual(evidence['secondary_errors'], secondary)
                self.assertEqual(raised.exception.__notes__, secondary)

    def test_pre_call_interrupts_are_bounded_but_uncertain_native_call_is_not_retried(self):
        process = mock.Mock()
        process._job_close_state = 'owned'
        failures = []
        calls = []

        def before_kernel():
            calls.append('entry')
            if len(calls) <= 2:
                raise KeyboardInterrupt('before CloseHandle')
            process._job_close_state = 'closed'

        harness._attempt_owned_win32_close(
            failures, process, before_kernel, '_job_close_state')
        self.assertEqual(calls, ['entry'] * 3)
        self.assertEqual(len(failures), 2)
        self.assertTrue(all(isinstance(err, KeyboardInterrupt) for err in failures))

        process._job_close_state = 'owned'
        failures.clear()
        calls.clear()

        def uncertain_kernel():
            calls.append('kernel')
            process._job_close_state = 'uncertain'
            raise OSError('CloseHandle returned an unverified outcome')

        harness._attempt_owned_win32_close(
            failures, process, uncertain_kernel, '_job_close_state')
        self.assertEqual(calls, ['kernel'])  # No retry of possibly closed value.
        self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], OSError)

    def test_sigint_guard_installed_before_ownership_and_replays_after_release(self):
        # The guard is installed before either Win32 handle can be acquired.
        # Outside the close section the existing SIGINT handler still fires.
        previous = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, signal.default_int_handler)
        guard = None
        try:
            guard = harness._Win32CloseSigintGuard()
            with self.assertRaises(KeyboardInterrupt):
                signal.raise_signal(signal.SIGINT)
            self.assertEqual(guard._pending, [])
            guard.arm()
            released = []
            signal.raise_signal(signal.SIGINT)
            released.append('job')
            signal.raise_signal(signal.SIGINT)
            released.append('process')
            self.assertEqual(released, ['job', 'process'])
            self.assertEqual(len(guard._pending), 2)
            with self.assertRaises(KeyboardInterrupt):
                guard.restore()
            self.assertTrue(guard._restored)
            self.assertIs(signal.getsignal(signal.SIGINT), signal.default_int_handler)
        finally:
            if guard is not None and not guard._restored:
                guard.restore()
            signal.signal(signal.SIGINT, previous)

    def test_failed_sigint_handler_restoration_fails_explicitly_without_silencing_sigint(self):
        previous = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, signal.default_int_handler)
        guard = harness._Win32CloseSigintGuard()
        try:
            guard.arm()
            signal.raise_signal(signal.SIGINT)
            with mock.patch.object(harness.signal, 'signal',
                                   side_effect=OSError('restore failed')):
                with self.assertRaisesRegex(OSError, 'restore failed') as raised:
                    guard.restore()
            self.assertFalse(guard._armed)
            self.assertFalse(guard._restored)
            self.assertIn('KeyboardInterrupt', ' '.join(raised.exception.__notes__))
            with self.assertRaises(KeyboardInterrupt):
                signal.raise_signal(signal.SIGINT)  # Forwarding still works.
            guard.restore()
            self.assertTrue(guard._restored)
        finally:
            if not guard._restored:
                guard.restore()
            signal.signal(signal.SIGINT, previous)

    def test_taskkill_128_remains_primary_with_sigint_deferred_in_close(self):
        root_error = subprocess.CalledProcessError(128, ['taskkill'])
        primary = RuntimeError('Owned Windows PID 2232 cleanup unproven: taskkill=128')
        primary.__cause__ = root_error
        previous = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, signal.default_int_handler)
        guard = None
        try:
            guard = harness._Win32CloseSigintGuard()
            process = mock.Mock(pid=2232)
            process.poll.return_value = 0
            process._close_sigint = guard
            closed = []

            def close_job():
                guard.arm()
                signal.raise_signal(signal.SIGINT)  # Before the native close.
                closed.append('job')

            def close_process():
                closed.append('process')

            process.close_job.side_effect = close_job
            process.close_process.side_effect = close_process
            thread = mock.Mock()
            thread.is_alive.return_value = False
            with tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                with mock.patch.object(sys, 'platform', 'win32'), mock.patch.object(
                        harness, 'WindowsJobProcess', return_value=process, create=True), mock.patch.object(
                        harness, 'stop', side_effect=primary), mock.patch.object(
                        harness.threading, 'Thread', return_value=thread):
                    with self.assertRaises(RuntimeError) as raised:
                        with captured_engine(['webots-bin.exe'], directory, {},
                                             directory / 'stdout', directory / 'stderr'):
                            pass
                self.assertIs(raised.exception, primary)
                self.assertIs(primary.__cause__, root_error)
                self.assertEqual(closed, ['job', 'process'])
                self.assertTrue(any('KeyboardInterrupt' in n for n in primary.__notes__))
                record = json.loads((directory / 'webots-process-cleanup.json').read_text())
                self.assertIn('taskkill=128', record['primary_exception'])
                self.assertTrue(any('KeyboardInterrupt' in n for n in record['secondary_errors']))
        finally:
            if guard is not None and not guard._restored:
                guard.restore()
            signal.signal(signal.SIGINT, previous)

    def test_taskkill_128_remains_primary_when_post_cim_raises(self):
        process = mock.Mock(pid=2232)
        process.poll.side_effect = [None, None, None, 0]
        before = _filter_windows_tree([
            dict(ProcessId=2232, ParentProcessId=50, CreationDate='t0', Name='webots-bin.exe')
        ], 2232)
        failed = subprocess.CalledProcessError(128, ['taskkill'], output=b'SUCCESS: terminated root')
        thread = mock.Mock()
        thread.is_alive.return_value = False
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            post_cim_error = KeyboardInterrupt('during post-taskkill CIM')
            with mock.patch.object(sys, 'platform', 'win32'), mock.patch.object(
                    harness, 'WindowsJobProcess', return_value=process, create=True), mock.patch.object(
                    harness, '_windows_process_snapshot', side_effect=[before, before, post_cim_error]), mock.patch.object(
                    harness.threading, 'Thread', return_value=thread), mock.patch.object(
                    harness.subprocess, 'run', side_effect=failed):
                with self.assertRaisesRegex(RuntimeError, 'taskkill=128, process=0') as raised:
                    with captured_engine(['webots-bin.exe'], directory, {},
                                         directory / 'stdout', directory / 'stderr'):
                        pass
            self.assertIs(raised.exception.__cause__, failed)
            process.close_job.assert_called_once_with()
            process.close_process.assert_called_once_with()
            evidence = json.loads((directory / 'webots-process-cleanup.json').read_text(encoding='utf-8'))
            self.assertEqual(evidence['taskkill_returncode'], 128)
            self.assertIn('taskkill=128', evidence['primary_exception'])
            self.assertEqual(evidence['secondary_errors'], ['KeyboardInterrupt: during post-taskkill CIM'])
            self.assertEqual(raised.exception.__notes__, evidence['secondary_errors'])
            self.assertNotIn('job_active_processes', evidence)

    def test_cleanup_snapshot_preserves_child_creation_identity_and_bounds(self):
        rows = [
            dict(ProcessId=77, ParentProcessId=2, CreationDate='20261117T200000',
                 Name='webots-bin.exe'),
            dict(ProcessId=78, ParentProcessId=77, CreationDate='20261117T200001',
                 Name='QtWebEngineProcess.exe'),
            dict(ProcessId=79, ParentProcessId=78, CreationDate='20261117T200002',
                 Name='robot.exe'),
            dict(ProcessId=80, ParentProcessId=4, CreationDate='20261117T200003',
                 Name='unrelated.exe')
        ]
        seen = _filter_windows_tree(rows, 77)
        self.assertTrue(seen['root_present'])
        self.assertEqual([p['pid'] for p in seen['owned']], [77, 78, 79])
        self.assertEqual(seen['watched'], [])
        # After root disappears, a surviving descendant keeps its original
        # identity even if its parent is no longer listed in the snapshot.
        surviving = _filter_windows_tree(rows[2:], 77, watched=[77, 78, 79])
        self.assertFalse(surviving['root_present'])
        self.assertEqual(surviving['owned'], [])
        self.assertEqual([p['pid'] for p in surviving['watched']], [79])
        with self.assertRaises(ValueError):
            _filter_windows_tree([dict(ProcessId=True, ParentProcessId=77)], 77)
        with self.assertRaises(ValueError):
            _filter_windows_tree(rows * 1025, 77)
        with self.assertRaises(ValueError):
            _filter_windows_tree(rows, 77, watched=list(range(65)))

    def test_reused_parent_pid_does_not_adopt_preexisting_system_tree(self):
        # Exact identities from checkpoint 46159336447 / artifact 15268874691.
        # A new conhost reused a PID retained in old system-process metadata.
        rows = [
            (2736, 7328, 1795879755681, 'webots-bin.exe'),
            (1164, 2736, 1795879766350, 'webeeblocks-gp-python.exe'),
            (6332, 1164, 1795879766386, 'conhost.exe'),
            (6344, 6332, 1795878283554, 'csrss.exe'),
            (6392, 6332, 1795878283565, 'winlogon.exe'),
            (6440, 6392, 1795878283593, 'fontdrvhost.exe'),
            (6472, 6392, 1795878283608, 'dwm.exe'),
        ]
        def raw(row):
            pid, parent, created, name = row
            return dict(ProcessId=pid, ParentProcessId=parent,
                        CreationDate=f'/Date({created})/' if created is not None else None,
                        Name=name)
        before = _filter_windows_tree(list(map(raw, rows)), 2736)
        self.assertEqual({p['pid'] for p in before['owned']}, {2736, 1164, 6332})
        self.assertEqual({p['child']['pid'] for p in before['rejected_older_parent_links']},
                         {6344, 6392})
        watched = [p['pid'] for p in before['owned']]
        after = _filter_windows_tree(list(map(raw, rows[3:])), 2736, watched)
        self.assertEqual(after['owned'], [])
        self.assertEqual(after['watched'], [])
        # The same names confer no exemption: newer/equal/unknown dates remain
        # candidates, as does a late child of a vanished parent.
        for created in (1795879766386, 1795879766387, None):
            child = raw((6344, 6332, created, 'csrss.exe'))
            result = _filter_windows_tree(list(map(raw, rows[:3])) + [child], 2736)
            self.assertIn(6344, {p['pid'] for p in result['owned']})
        late = _filter_windows_tree([raw((6344, 2736, None, 'csrss.exe'))], 2736)
        self.assertEqual([p['pid'] for p in late['owned']], [6344])
        # Full stop contract: even with no CIM survivors, an active or unknown
        # Job count cannot be converted into success by the chronology filter.
        for count in (0, 1, None):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as tmp:
                process = mock.Mock(pid=2736)
                process.poll.return_value = 0
                process.active_job_processes.return_value = count
                diagnostic = Path(tmp) / 'cleanup.json'
                with mock.patch.object(harness, '_windows_process_snapshot', return_value=after):
                    if count == 0:
                        stop(process, diagnostic_path=diagnostic, launch_snapshot=before)
                    else:
                        with self.assertRaises(RuntimeError):
                            stop(process, diagnostic_path=diagnostic, launch_snapshot=before)
                self.assertEqual(json.loads(diagnostic.read_text())['job_active_processes'], count)

    def test_cim_blank_or_duplicate_creation_identity_is_not_valid_evidence(self):
        root = dict(ProcessId=77, ParentProcessId=4,
                    CreationDate=' ', Name='webots-bin.exe')
        sample = _filter_windows_tree([root], 77)
        self.assertIsNone(sample['owned'][0]['created'])
        with self.assertRaisesRegex(ValueError, 'Duplicate process PID'):
            _filter_windows_tree([root, dict(root, CreationDate='t2')], 77)

    def test_system_idle_pid_zero_is_excluded_only_when_unrelated(self):
        # Windows Win32_Process may include System Idle Process as PID 0,
        # with ParentProcessId 0 or null. It is never an owned child of a
        # positive PID and must not invalidate every useful CIM snapshot.
        root = dict(ProcessId=77, ParentProcessId=4,
                    CreationDate='20261117T201000', Name='webots-bin.exe')
        child = dict(ProcessId=78, ParentProcessId=77,
                     CreationDate='20261117T201001', Name='robot.exe')
        for idle_parent in (0, None):
            idle = dict(ProcessId=0, ParentProcessId=idle_parent,
                        CreationDate=None, Name='System Idle Process')
            before = _filter_windows_tree([idle, root, child], 77)
            self.assertTrue(before['available'])
            self.assertTrue(before['root_present'])
            self.assertEqual(before['excluded_system_idle_rows'], 1)
            self.assertEqual([p['pid'] for p in before['owned']], [77, 78])
            after = _filter_windows_tree([idle, child], 77, watched=[77, 78])
            self.assertFalse(after['root_present'])
            self.assertEqual([p['pid'] for p in after['watched']], [78])
            self.assertEqual(after['excluded_system_idle_rows'], 1)
        # A counterfeit PID 0 with a real parent is not silently ignored.
        for hostile in (77, True, '77'):
            invalid = dict(ProcessId=0, ParentProcessId=hostile,
                           Name='System Idle Process')
            with self.assertRaises(ValueError):
                _filter_windows_tree([invalid, root, child], 77)
        with self.assertRaises(ValueError):
            _filter_windows_tree([idle, idle, root], 77)
        with self.assertRaises(ValueError):
            _filter_windows_tree([idle, root], 0)
        with self.assertRaises(ValueError):
            _filter_windows_tree([idle, root], 77, watched=[0])
        # Unrelated positive-PID malformed entries must still fail closed.
        with self.assertRaises(ValueError):
            _filter_windows_tree([idle, root, dict(ProcessId=99,
                ParentProcessId=None, Name='unknown.exe')], 77)
        with self.assertRaises(ValueError):
            _filter_windows_tree([idle, root, dict(ProcessId=True,
                ParentProcessId=77, Name='spoof.exe')], 77)

    def test_taskkill_128_preserves_failure_and_full_evidence_not_just_tail(self):
        command = ['taskkill', '/PID', '2232', '/T', '/F']
        process = mock.Mock(pid=2232)
        process.poll.side_effect = [None, 1]
        failed = subprocess.CalledProcessError(
            128, command,
            output=b'ERROR: hypothetical missing child before successes\r\n'
                   + b'SUCCESS: terminated child\r\n' * 40)
        before = dict(available=True, owned=[
            dict(pid=2232, parent=100, name='webots-bin.exe',
                 created='t1'),
            dict(pid=4520, parent=2232, name='child.exe',
                 created='t2')])
        after = dict(available=True, owned=[], watched=[
            dict(pid=4520, parent=2232, name='child.exe', created='t2')])
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / 'webots-process-cleanup.json'
            with mock.patch(
                'tools.ci.run_grand_prix_windows_native._windows_process_snapshot',
                side_effect=[before, after]) as snap, mock.patch(
                'tools.ci.run_grand_prix_windows_native.subprocess.run',
                side_effect=failed) as invoked:
                with self.assertRaisesRegex(RuntimeError, 'cleanup unproven'):
                    stop(process, diagnostic_path=evidence)
                snap.assert_any_call(2232)
                snap.assert_any_call(2232, [2232, 4520])
                invoked.assert_called_once()
                self.assertTrue(invoked.call_args.kwargs['check'])
            record = json.loads(evidence.read_text(encoding='utf-8'))
            self.assertEqual(record['taskkill_returncode'], 128)
            self.assertEqual(record['process_after_taskkill'], 1)
            self.assertIn('ERROR: hypothetical missing child',
                          record['taskkill_output'])
            self.assertFalse(record['taskkill_output_truncated'])
            self.assertEqual(record['still_present_same_pid_and_creation'],
                             after['watched'])
            self.assertIn('cleanup unproven', record['exception'])
        process.wait.assert_not_called()

    def test_observed_surviving_descendant_vetoes_taskkill_success_or_race(self):
        # taskkill exit=0 or root exit=0 is not retirement proof when the
        # native CIM witness still observes the exact child incarnation.
        root = dict(pid=2232, parent=50, created='start', name='webots-bin.exe')
        child = dict(pid=4520, parent=2232, created='child-start',
                     name='QtWebEngineProcess.exe')
        before = dict(available=True, owned=[root, child])
        after = dict(available=True, owned=[], watched=[child])
        for taskkill_ok in (True, False):
            with self.subTest(taskkill_ok=taskkill_ok), tempfile.TemporaryDirectory() as tmp:
                evidence = Path(tmp) / 'cleanup.json'
                process = mock.Mock(pid=2232)
                process.poll.side_effect = [None, 0] if not taskkill_ok else [None]
                process.wait.return_value = 1 if taskkill_ok else 0
                if taskkill_ok:
                    action = dict(return_value=subprocess.CompletedProcess(
                        ['taskkill'], 0, stdout=b'SUCCESS: terminated'))
                else:
                    action = dict(side_effect=subprocess.CalledProcessError(
                        128, ['taskkill'], output=b'SUCCESS: terminated'))
                with mock.patch(
                        'tools.ci.run_grand_prix_windows_native._windows_process_snapshot',
                        side_effect=[before, after]), mock.patch(
                        'tools.ci.run_grand_prix_windows_native.subprocess.run',
                        **action):
                    expected = ('cleanup unproven: 1 same-identity descendants survived'
                                if taskkill_ok else 'taskkill=128, process=0')
                    with self.assertRaisesRegex(RuntimeError, expected):
                        stop(process, diagnostic_path=evidence)
                record = json.loads(evidence.read_text(encoding='utf-8'))
                self.assertEqual(record['still_present_same_pid_and_creation'], [child])
                self.assertIn('observed same-identity' if taskkill_ok else 'taskkill=128',
                              record['exception'])

        # PID reuse is not evidence the originally owned child survived.
        replaced = dict(child, created='new-incarnation')
        process = mock.Mock(pid=2232)
        process.poll.return_value = None
        process.wait.return_value = 1
        process.active_job_processes.return_value = 0
        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / 'cleanup.json'
            with mock.patch(
                    'tools.ci.run_grand_prix_windows_native._windows_process_snapshot',
                    side_effect=[before, dict(available=True, owned=[],
                                              watched=[replaced])]), mock.patch(
                    'tools.ci.run_grand_prix_windows_native.subprocess.run',
                    return_value=subprocess.CompletedProcess(
                        ['taskkill'], 0, stdout=b'SUCCESS: terminated')):
                stop(process, diagnostic_path=evidence)
            record = json.loads(evidence.read_text(encoding='utf-8'))
            self.assertEqual(record['still_present_same_pid_and_creation'], [])
            self.assertEqual(record['job_active_processes'], 0)

    def test_taskkill_128_with_success_text_and_clean_cim_still_refused(self):
        root = dict(pid=2232, parent=50, created='root-start',
                    name='webots-bin.exe')
        process = mock.Mock(pid=2232)
        process.poll.side_effect = [None, 0]
        with tempfile.TemporaryDirectory() as tmp:
            diagnostic = Path(tmp) / 'cleanup.json'
            with mock.patch(
                'tools.ci.run_grand_prix_windows_native._windows_process_snapshot',
                side_effect=[dict(available=True, owned=[root]),
                             dict(available=True, watched=[], owned=[])]), \
                mock.patch('tools.ci.run_grand_prix_windows_native.subprocess.run',
                           side_effect=subprocess.CalledProcessError(
                               128, ['taskkill'], output=b'SUCCESS: terminated')):
                with self.assertRaisesRegex(RuntimeError, 'taskkill=128, process=0'):
                    stop(process, diagnostic_path=diagnostic)
            record = json.loads(diagnostic.read_text(encoding='utf-8'))
            self.assertEqual(record['taskkill_returncode'], 128)
            self.assertEqual(record['cleanup_observation_gaps'], [])
            self.assertEqual(record['still_present_same_pid_and_creation'], [])
            self.assertIn('taskkill=128', record['exception'])
            self.assertIn('SUCCESS', record['taskkill_output'])

    def test_missing_cim_snapshot_or_creation_identity_vetoes_cleanup(self):
        root = dict(pid=2232, parent=50, created='root-start',
                    name='webots-bin.exe')
        child = dict(pid=4520, parent=2232, created='child-start',
                     name='QtWebEngineProcess.exe')
        before = dict(available=True, owned=[root, child])
        after = dict(available=True, owned=[], watched=[])
        cases = [
            ('before-snapshot-unavailable',
             dict(available=False, error='CIM startup failed'), after),
            ('after-snapshot-unavailable',
             before, dict(available=False, error='CIM teardown failed')),
            ('creation-identity-unavailable',
             dict(available=True, owned=[dict(root, created=None), child]),
             after),
            ('after-creation-identity-unavailable', before,
             dict(available=True, owned=[], watched=[dict(child, created=None)])),
            # An available CIM response can omit the owned root even when
            # the Popen handle was live at the start of stop().
            ('before-root-identity-unavailable',
             dict(available=True, root_present=False, owned=[]), after),
        ]
        for reason, first, last in cases:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as tmp:
                diagnostic = Path(tmp) / 'cleanup.json'
                process = mock.Mock(pid=2232)
                process.poll.return_value = None
                process.wait.return_value = 1
                with mock.patch(
                    'tools.ci.run_grand_prix_windows_native._windows_process_snapshot',
                    side_effect=[first, last]), mock.patch(
                    'tools.ci.run_grand_prix_windows_native.subprocess.run',
                    return_value=subprocess.CompletedProcess(
                        ['taskkill'], 0, stdout=b'SUCCESS: terminated')):
                    with self.assertRaisesRegex(RuntimeError,
                                                'cleanup observation unavailable'):
                        stop(process, diagnostic_path=diagnostic)
                record = json.loads(diagnostic.read_text(encoding='utf-8'))
                self.assertIn(reason, record['cleanup_observation_gaps'])
                self.assertIn('observation unavailable', record['exception'])
                self.assertEqual(record['taskkill_returncode'], 0)

        # Never mask an earlier causal taskkill failure with the later
        # diagnostic inability to observe CIM.
        process = mock.Mock(pid=2232)
        process.poll.side_effect = [None, 1]
        failed = subprocess.CalledProcessError(
            128, ['taskkill'], output=b'ERROR: failed to terminate')
        with tempfile.TemporaryDirectory() as tmp:
            diagnostic = Path(tmp) / 'cleanup.json'
            with mock.patch(
                'tools.ci.run_grand_prix_windows_native._windows_process_snapshot',
                side_effect=[dict(available=False), dict(available=False)]), \
                mock.patch('tools.ci.run_grand_prix_windows_native.subprocess.run',
                           side_effect=failed):
                with self.assertRaisesRegex(RuntimeError, 'cleanup unproven'):
                    stop(process, diagnostic_path=diagnostic)
            record = json.loads(diagnostic.read_text(encoding='utf-8'))
            self.assertIn('cleanup unproven', record['exception'])
            self.assertEqual(len(record['cleanup_observation_gaps']), 2)

    def test_successful_taskkill_is_only_observed_not_manufactured(self):
        process = mock.Mock(pid=456)
        process.poll.return_value = None
        process.wait.return_value = 1  # taskkill intentionally terminates process
        process.active_job_processes.return_value = 0
        before = dict(available=True, owned=[
            dict(pid=456, parent=100, created='t1', name='native.exe')])
        after = dict(available=True, owned=[], watched=[])
        with tempfile.TemporaryDirectory() as tmp:
            diagnostic = Path(tmp) / 'cleanup.json'
            with mock.patch(
                'tools.ci.run_grand_prix_windows_native._windows_process_snapshot',
                side_effect=[before, after]), mock.patch(
                'tools.ci.run_grand_prix_windows_native.subprocess.run',
                return_value=subprocess.CompletedProcess(
                    ['taskkill'], 0, stdout=b'SUCCESS: terminated')):
                stop(process, diagnostic_path=diagnostic)
            actual = json.loads(diagnostic.read_text(encoding='utf-8'))
            self.assertEqual(actual['taskkill_returncode'], 0)
            self.assertEqual(actual['wait_returncode'], 1)
            self.assertEqual(actual['still_present_same_pid_and_creation'], [])
            self.assertEqual(actual['job_active_processes'], 0)
        process.wait.assert_called_once_with(timeout=20)

    def test_offline_world_uses_exact_webots_floor_plane_not_box(self):
        # Upstream R2025a Floor.proto has a locked Solid/Plane collider.
        # An offline 5-cm Box substitutes a different contact dynamics.
        for seed in (0, 1, 4):
            world = local_world(seed, 'grand_prix_u')
            side = generate(seed).side + 2.5
            self.assertIn('Solid { translation 1.0 1.0 0\n  name "floor"\n  locked TRUE', world)
            self.assertEqual(world.count(f'boundingObject Plane {{ size {side} {side} }}'), 1)
            self.assertIn('coordIndex [ 2 0 1 3 -1 ]', world)
            self.assertNotIn(f'boundingObject Box {{ size {side} {side} 0.05 }}', world)
            self.assertNotIn('Floor { translation', world)
            self.assertNotIn('rollingFriction', world)
            self.assertIn('basicTimeStep 8', world)

    def test_native_capture_uses_pipes_and_drains_both_channels(self):
        # Exercise R2025a's FILE_TYPE_PIPE discriminator on Windows too.
        code = '''
import os, sys
if sys.platform == 'win32':
 import ctypes
 kernel = ctypes.WinDLL('kernel32', use_last_error=True)
 kernel.GetStdHandle.restype = ctypes.c_void_p
 kernel.GetFileType.argtypes = [ctypes.c_void_p]
 assert kernel.GetFileType(kernel.GetStdHandle(-11)) == 3
 assert kernel.GetFileType(kernel.GetStdHandle(-12)) == 3
for i in range(128):
 os.write(1, b'R' * 4096)
 os.write(2, b'E' * 4096)
print('WEBEEBLOCKS_RUNTIME_V2 READY', flush=True)
'''
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stdout, stderr = root / 'stdout', root / 'stderr'
            with captured_engine([sys.executable, '-c', code], root, os.environ.copy(), stdout, stderr) as process:
                self.assertEqual(process.wait(timeout=20), 0)
            self.assertEqual(stdout.read_bytes(), b'R' * (128 * 4096) + b'WEBEEBLOCKS_RUNTIME_V2 READY' + os.linesep.encode())
            self.assertEqual(stderr.read_bytes(), b'E' * (128 * 4096))
            if sys.platform == 'win32':
                evidence = json.loads((root / 'webots-process-cleanup.json').read_text(encoding='utf-8'))
                self.assertEqual(evidence['job_active_processes'], 0)

    @unittest.skipUnless(sys.platform == 'win32', 'requires Win32 Job disposal')
    def test_native_job_close_kills_live_root_and_child_after_stop_cim_interrupt(self):
        import _winapi

        root_code = '''
from pathlib import Path
import subprocess, sys, time

child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
Path('child.pid.tmp').write_text(str(child.pid), encoding='ascii')
Path('child.pid.tmp').replace('child.pid')
time.sleep(60)
'''
        command = [sys.executable, '-c', root_code]
        interruption = KeyboardInterrupt('in stop CIM subprocess')
        run = subprocess.run
        handles = []
        process = None
        snapshots = []

        def interrupt_second_cim(command, *args, **kwargs):
            self.assertEqual(command[0], 'powershell.exe')
            if not snapshots:
                snapshot = run(command, *args, **kwargs)
                snapshots.append(snapshot)
                return snapshot
            self.assertEqual(len(handles), 2)
            for handle in handles:
                self.assertEqual(_winapi.WaitForSingleObject(handle, 0), _winapi.WAIT_TIMEOUT)
            snapshots.append(interruption)
            raise interruption

        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            try:
                with mock.patch.object(harness.subprocess, 'run', side_effect=interrupt_second_cim), mock.patch.object(
                        harness, '_windows_process_snapshot', wraps=harness._windows_process_snapshot) as cim, mock.patch.object(
                        harness.WindowsJobProcess, 'close_job', autospec=True,
                        side_effect=harness.WindowsJobProcess.close_job) as close_job, mock.patch.object(
                        harness.WindowsJobProcess, 'close_process', autospec=True,
                        side_effect=harness.WindowsJobProcess.close_process) as close_process:
                    with self.assertRaises(KeyboardInterrupt) as raised:
                        with captured_engine(command, directory, os.environ.copy(),
                                             directory / 'stdout', directory / 'stderr') as process:
                            child_pid = directory / 'child.pid'
                            deadline = time.monotonic() + 10
                            while not child_pid.is_file() and time.monotonic() < deadline:
                                time.sleep(.02)
                            for pid in (process.pid, int(child_pid.read_text(encoding='ascii'))):
                                handles.append(_winapi.OpenProcess(0x100000, False, pid))  # SYNCHRONIZE
                            self.assertIsNone(process.poll())
                            self.assertEqual(process.active_job_processes(), 2)
                    self.assertIs(raised.exception, interruption)
                    close_job.assert_called_once_with(process)
                    close_process.assert_called_once_with(process)
                    self.assertEqual(cim.call_args_list, [mock.call(process.pid)] * 2)
                self.assertIsNone(process._job)
                self.assertIsNone(process._process)
                rows = json.loads(snapshots[0].stdout.decode('utf-8-sig'))
                initial = _filter_windows_tree(rows, process.pid)
                self.assertTrue(initial['root_present'])
                self.assertTrue(all(row['created'] for row in initial['owned']))
                for handle in handles:
                    self.assertEqual(_winapi.WaitForSingleObject(handle, 5000), _winapi.WAIT_OBJECT_0)
                evidence = json.loads((directory / 'webots-process-cleanup.json').read_text(encoding='utf-8'))
                self.assertEqual(evidence['primary_exception'], 'KeyboardInterrupt: in stop CIM subprocess')
                self.assertNotIn('job_active_processes', evidence)
                print('Win32 CIM interruption: both owned handles closed and both live members signaled after Job close')
            finally:
                try:
                    if process is not None:
                        try:
                            if process._job is not None:
                                process.close_job()
                        finally:
                            if process._process is not None:
                                process.close_process()
                finally:
                    for handle in handles:
                        _winapi.CloseHandle(handle)

    @unittest.skipUnless(sys.platform == 'win32', 'requires Win32 native SIGINT and handles')
    def test_native_sigint_exactly_before_each_closehandle_and_double_interrupt(self):
        import _winapi

        # An independent SYNCHRONIZE handle for each living member survives
        # the owner's two CloseHandle calls and establishes actual termination.
        root_code = """
from pathlib import Path
import subprocess, sys, time
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
Path('child.pid').write_text(str(child.pid), encoding='ascii')
time.sleep(60)
"""
        for target, count in (('_job', 1), ('_process', 1), ('_job', 2)):
            with self.subTest(target=target, count=count), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                process = None
                handles = []
                close_calls = []
                injected = []
                real_close = _winapi.CloseHandle
                try:
                    process = harness.WindowsJobProcess(
                        [sys.executable, '-c', root_code], directory, os.environ.copy())
                    pidfile = directory / 'child.pid'
                    deadline = time.monotonic() + 10
                    while not pidfile.exists() and time.monotonic() < deadline:
                        time.sleep(.02)
                    self.assertTrue(pidfile.is_file(), 'Child handshake missing')
                    for pid in (process.pid, int(pidfile.read_text())):
                        handles.append(_winapi.OpenProcess(0x100000, False, pid))
                    for handle in handles:
                        self.assertEqual(_winapi.WaitForSingleObject(handle, 0), _winapi.WAIT_TIMEOUT)
                    job_handle, process_handle = process._job, process._process

                    def trace(frame, event, arg):
                        if (event == 'line' and not injected and
                                frame.f_code is harness.WindowsJobProcess._close_once.__code__ and
                                frame.f_locals.get('attribute') == target and
                                '_winapi.CloseHandle(handle)' in linecache.getline(
                                    frame.f_code.co_filename, frame.f_lineno)):
                            injected.append(target)
                            if target == '_job':
                                for handle in handles:
                                    self.assertEqual(
                                        _winapi.WaitForSingleObject(handle, 0), _winapi.WAIT_TIMEOUT)
                            for _ in range(count):
                                signal.raise_signal(signal.SIGINT)
                        return trace

                    def counted_close(handle):
                        close_calls.append(handle)
                        return real_close(handle)

                    try:
                        with mock.patch.object(_winapi, 'CloseHandle', side_effect=counted_close):
                            sys.settrace(trace)
                            with self.assertRaises(KeyboardInterrupt):
                                process.close_job()
                                process.close_process()
                                process._close_sigint.restore()
                    finally:
                        sys.settrace(None)
                    self.assertEqual(injected, [target])
                    self.assertEqual(close_calls.count(job_handle), 1)
                    self.assertEqual(close_calls.count(process_handle), 1)
                    self.assertEqual(process._job_close_state, 'closed')
                    self.assertEqual(process._process_close_state, 'closed')
                    self.assertIsNone(process._job)
                    self.assertIsNone(process._process)
                    for handle in handles:
                        self.assertEqual(
                            _winapi.WaitForSingleObject(handle, 5000), _winapi.WAIT_OBJECT_0)
                finally:
                    sys.settrace(None)
                    if process is not None:
                        # A failed assertion must still retire the test's Job.
                        if process._job_close_state == 'owned':
                            process.close_job()
                        if process._process_close_state == 'owned':
                            process.close_process()
                        if not process._close_sigint._restored:
                            process._close_sigint.restore()
                    for handle in handles:
                        real_close(handle)

    @unittest.skipUnless(sys.platform == 'win32', 'requires Win32 native close failures')
    def test_native_failed_close_is_uncertain_and_never_retried(self):
        import _winapi
        real_close = _winapi.CloseHandle
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            process = harness.WindowsJobProcess(
                [sys.executable, '-c', 'import time; time.sleep(60)'],
                directory, os.environ.copy())
            job = process._job
            calls = []
            try:
                def injected_close(handle):
                    if handle == job:
                        calls.append(handle)
                        raise OSError('simulated Win32 CloseHandle failure')
                    return real_close(handle)

                with mock.patch.object(_winapi, 'CloseHandle', side_effect=injected_close):
                    with self.assertRaisesRegex(RuntimeError, 'outcome unverified'):
                        process.close_job()
                self.assertEqual(calls, [job])
                self.assertEqual(process._job_close_state, 'uncertain')
                with self.assertRaisesRegex(RuntimeError, 'no retry'):
                    process.close_job()
                self.assertEqual(calls, [job])
                process.close_process()
            finally:
                # The injected exception occurred before the real API call;
                # this test alone can safely retire its still-open Job.
                real_close(job)
                if not process._close_sigint._restored:
                    process._close_sigint.restore()

    @unittest.skipUnless(sys.platform == 'win32', 'requires Win32 job inheritance')
    def test_native_job_keeps_late_grandchild_after_both_ancestors_exit(self):
        import _winapi

        grandchild_code = 'import time; time.sleep(60)'
        intermediate_code = '''
from pathlib import Path
import subprocess, sys
child = subprocess.Popen([sys.executable, '-c', sys.argv[1]],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
Path('grandchild.pid').write_text(str(child.pid), encoding='ascii')
'''
        root_code = '''
from pathlib import Path
import subprocess, sys, time
deadline = time.monotonic() + 20
while not Path('spawn').exists():
    if time.monotonic() > deadline:
        sys.exit('missing parent handshake')
    time.sleep(.02)
try:
    subprocess.run([sys.executable, '-c', 'pass'], creationflags=0x01000000, check=True)
except OSError as error:
    if error.winerror != 5:
        raise
else:
    sys.exit('CREATE_BREAKAWAY_FROM_JOB unexpectedly succeeded')
subprocess.run([sys.executable, '-c', sys.argv[1], sys.argv[2]], check=True)
'''
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            command = [sys.executable, '-c', root_code, intermediate_code, grandchild_code]
            grandchild = None
            try:
                with self.assertRaisesRegex(RuntimeError, 'job cleanup unproven: active processes=1'):
                    with captured_engine(command, directory, os.environ.copy(),
                                         directory / 'stdout', directory / 'stderr') as process:
                        self.assertEqual(process.active_job_processes(), 1)
                        (directory / 'spawn').touch()
                        self.assertEqual(process.wait(timeout=20), 0)
                        pid = int((directory / 'grandchild.pid').read_text(encoding='ascii'))
                        grandchild = _winapi.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
                        self.assertEqual(_winapi.WaitForSingleObject(grandchild, 0), _winapi.WAIT_TIMEOUT)
                self.assertEqual(_winapi.WaitForSingleObject(grandchild, 5000), _winapi.WAIT_OBJECT_0)
            finally:
                if grandchild is not None:
                    _winapi.CloseHandle(grandchild)
            evidence = json.loads((directory / 'webots-process-cleanup.json').read_text(encoding='utf-8'))
            self.assertEqual(evidence['cleanup_observation_gaps'], [])
            self.assertEqual(evidence['untracked_owned_after_cleanup'], [])
            self.assertEqual(evidence['job_active_processes'], 1)

    def test_real_windows_uppercase_copy_and_mixed_case_inputs(self):
        for root_key in ('SYSTEMROOT', 'SystemRoot'):
            ambient = {root_key: '/Windows', 'Path': '/ambient',
                       'qt_qpa_platform_plugin_path': '/foreign-qt'}
            env = engine_environment(Path('/Webots'), ambient)
            self.assertEqual(env['SYSTEMROOT'], '/Windows')
            self.assertNotIn('/ambient', env['PATH'])
            self.assertIn(str(Path('/Windows') / 'System32'), env['PATH'])
            self.assertNotIn('QT_QPA_PLATFORM_PLUGIN_PATH', env)
            self.assertEqual(env['QT_ENABLE_HIGHDPI_SCALING'], '1')
            self.assertIn('qt_qpa_platform_plugin_path', ambient)
        with self.assertRaises(ValueError):
            engine_environment(Path('/Webots'), {'PATH': '/ambient'})

    def fixture(self, root):
        layout = generate(0)
        result = dict(status='achieved', configuration=layout.identifier, attempt=1,
                      crossings=1, seconds=100, reason=None)
        rows = [dict(event='program', detail={'program': []}),
                dict(event='outcome', detail={'status': 'achieved'})]
        (root / 'native_trace.csv').write_text('time,attempt,x,y,z\n' + '1,1,0,0,0\n' * 20, encoding='utf-8')
        (root / 'native-diagnostic-1.json').write_text(json.dumps(dict(crossings=1,
            landing_target=layout.landing_target(1))), encoding='utf-8')
        self.write(root, rows, result)
        return rows, result

    def write(self, root, rows, result, logged=None):
        (root / 'events.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
        (root / 'native-result-1.json').write_text(json.dumps(result), encoding='utf-8')
        (root / 'webots.stdout.log').write_text('GP_U_RESULT ' + json.dumps(result if logged is None else logged) + '\n', encoding='utf-8')

    def test_missing_failed_wrong_subject_or_ambiguous_evidence_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows, result = self.fixture(root)
            self.assertEqual(validate(root, 0)['status'], 'achieved')
            for field, bad in [('status', 'not-achieved'), ('configuration', 'foreign'),
                               ('attempt', 2), ('crossings', 2), ('seconds', 210),
                               ('seconds', float('nan'))]:
                with self.subTest(field=field, bad=bad):
                    changed = dict(result, **{field: bad})
                    self.write(root, rows, changed)
                    with self.assertRaises(ValueError): validate(root, 0)
            for event in ('error', 'transport-error', 'wall-timeout'):
                self.write(root, rows + [dict(event=event, detail={})], result)
                with self.assertRaises(ValueError): validate(root, 0)
            for changed in (rows[:1], rows[1:], rows + [copy.deepcopy(rows[0])]):
                self.write(root, changed, result)
                with self.assertRaises(ValueError): validate(root, 0)
            self.write(root, rows, result, dict(result, seconds=101))
            with self.assertRaises(ValueError): validate(root, 0)
            self.write(root, rows, result)
            (root / 'webots.stderr.log').write_text('ERROR: controller failed\n', encoding='utf-8')
            with self.assertRaises(ValueError): validate(root, 0)
            (root / 'webots.stderr.log').unlink()
            (root / 'native_trace.csv').unlink()
            with self.assertRaises(ValueError): validate(root, 0)


if __name__ == '__main__':
    unittest.main()

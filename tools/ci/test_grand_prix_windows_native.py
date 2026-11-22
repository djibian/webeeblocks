"""Ensure installed-campaign evidence never turns incomplete execution into PASS."""
import copy
import json
import os
from pathlib import Path
import sys
import subprocess
from unittest import mock
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
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

        already_stopped = mock.Mock(pid=123)
        already_stopped.poll.return_value = 0
        with mock.patch('tools.ci.run_grand_prix_windows_native.subprocess.run') as run:
            if sys.platform == 'win32':
                with self.assertRaisesRegex(RuntimeError, 'cleanup unproven'):
                    stop(already_stopped)
            else:
                stop(already_stopped)  # Portable, non-Windows capture smoke test.
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
                process.wait.assert_not_called()

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

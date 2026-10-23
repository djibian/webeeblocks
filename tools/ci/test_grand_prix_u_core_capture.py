#!/usr/bin/env python3
"""Falsify private-core routing, restoration and post-mortem boundaries."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tools.ci.run_grand_prix_u_core_capture as capture


class CoreCaptureTests(unittest.TestCase):
    def test_no_capture_preserves_original_docker_arguments(self):
        self.assertEqual(capture.core_mount(None), [])
        self.assertEqual(capture.core_mount(''), [])

    def test_private_mount_and_symlink_rejection(self):
        with tempfile.TemporaryDirectory(prefix='gp-u-core-', dir='/tmp') as tmp:
            options = capture.core_mount(tmp)
            self.assertEqual(options, ['--ulimit', 'core=1073741824', '-v', tmp+':'+tmp])
            Path(tmp, 'alias').symlink_to(tmp, target_is_directory=True)
            with self.assertRaises(ValueError):
                capture.core_mount(str(Path(tmp, 'alias')))
            os.chmod(tmp, 0o755)
            with self.assertRaises(ValueError):
                capture.core_mount(tmp)

    @contextmanager
    def fake_kernel(self, directory):
        pattern = Path(directory) / 'pattern'
        pattern.write_text('|original-handler')
        with (patch.object(capture, 'PATTERN_FILE', pattern),
              patch.object(capture, 'set_pattern', side_effect=pattern.write_text),
              patch.dict(os.environ, GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted')):
            yield pattern

    def test_restore_on_exception_and_interruption(self):
        for error in (RuntimeError('subject failed'), InterruptedError('TERM')):
            with self.subTest(error=error), tempfile.TemporaryDirectory(prefix='gp-u-core-', dir='/tmp') as tmp:
                record = {}
                with self.fake_kernel(tmp) as pattern:
                    with self.assertRaises(type(error)):
                        with capture.kernel_capture(Path(tmp), record):
                            self.assertIn('core.%e.%p.%t', pattern.read_text())
                            raise error
                    self.assertEqual(pattern.read_text(), '|original-handler')
                    self.assertTrue(record['restored'])

    def test_unknown_pattern_is_not_overwritten(self):
        with tempfile.TemporaryDirectory(prefix='gp-u-core-', dir='/tmp') as tmp:
            record = {}
            with self.fake_kernel(tmp) as pattern:
                with self.assertRaisesRegex(RuntimeError, 'changed externally'):
                    with capture.kernel_capture(Path(tmp), record):
                        pattern.write_text('|external-handler')
                self.assertEqual(pattern.read_text(), '|external-handler')
                self.assertFalse(record['restored'])

    def test_ambiguous_setting_failure_still_restores_observed_write(self):
        with tempfile.TemporaryDirectory(prefix='gp-u-core-', dir='/tmp') as tmp:
            record = {}
            with self.fake_kernel(tmp) as pattern:
                def ambiguous(value):
                    pattern.write_text(value)
                    if value != '|original-handler':
                        raise subprocess.TimeoutExpired('sysctl', 10)
                with patch.object(capture, 'set_pattern', side_effect=ambiguous):
                    with self.assertRaises(subprocess.TimeoutExpired):
                        with capture.kernel_capture(Path(tmp), record):
                            self.fail('unestablished route was used')
                self.assertEqual(pattern.read_text(), '|original-handler')

    def test_refuses_self_hosted_runner_before_sysctl(self):
        with patch.dict(os.environ, GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='self-hosted'), \
                patch.object(capture, 'set_pattern') as setter:
            with self.assertRaisesRegex(RuntimeError, 'disposable'):
                with capture.kernel_capture(Path('/tmp/unused'), {}):
                    self.fail('self-hosted route was used')
            setter.assert_not_called()

    def test_core_inventory_refuses_symlinks_and_foreign_executables(self):
        with tempfile.TemporaryDirectory(prefix='gp-u-core-', dir='/tmp') as tmp:
            path = Path(tmp)
            good = path / 'core.webots-bin.123.456'
            good.write_bytes(b'ELF fixture')
            (path/'core.other.123.456').write_bytes(b'other')
            (path/'core.webots-bin.124.456').symlink_to(good)
            self.assertEqual(capture.cores(path, 'webots-bin'), [good])
            good.write_bytes(b'')
            with self.assertRaisesRegex(RuntimeError, 'empty'):
                capture.cores(path, 'webots-bin')

    def test_debugger_refuses_mutated_original_sysroot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            binary, core, output = path/'binary', path/'core', path/'out'
            binary.write_bytes(b'exact binary'); core.write_bytes(b'fake core')
            roots = []
            original_snapshot = capture.snapshot_inputs
            def snapshot(binary, root):
                roots.append(root)
                return original_snapshot(binary, root)
            def run(command, **kwargs):
                saved = roots[0] / binary.relative_to('/')
                saved.write_bytes(b'corrupted')
                return subprocess.CompletedProcess(command, 0)
            with (patch.object(capture, 'LIBRARY_ROOTS', ()),
                  patch.object(capture, 'snapshot_inputs', side_effect=snapshot),
                  patch.object(capture, 'package_versions', side_effect=[{'libc6':'1'}, {'libc6':'2'}]),
                  patch.object(capture.subprocess, 'run', side_effect=run) as called):
                self.assertEqual(capture.container_backtrace(core, binary, output), 1)
            self.assertEqual(called.call_count, 2)  # preparation only; never GDB
            self.assertFalse(output.with_suffix('.txt').exists())
            self.assertEqual(json.loads(output.with_suffix('.json').read_text())['status'], 'UNPROVEN')

    def test_stack_has_no_frame_arguments_or_auto_loaded_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            binary, core, output = path/'binary', path/'core', path/'out'
            binary.write_bytes(b'exact binary'); core.write_bytes(b'fake core')
            def run(command, **kwargs):
                if command[0] == 'gdb':
                    self.assertIn('set print frame-arguments none', command)
                    self.assertIn('set auto-load off', command)
                    self.assertIn('set auto-load libthread-db on', command)
                    self.assertLess(command.index('set auto-load off'),
                                    command.index('set auto-load libthread-db on'))
                    path_setting = next(x for x in command if x.startswith('set auto-load safe-path '))
                    self.assertTrue(path_setting.startswith('set auto-load safe-path /tmp/gp-u-sysroot-'))
                    self.assertEqual(path_setting.count(':'), 1)
                    self.assertNotIn('*', path_setting)
                    self.assertEqual(command[command.index('set auto-load libthread-db on')-1], '-iex')
                    self.assertIn('set debuginfod enabled off', command)
                    self.assertEqual(command[command.index('set print frame-arguments none')-1], '-iex')
                    self.assertEqual(command[command.index('set print entry-values no')-1], '-iex')
                    self.assertTrue(any(x.startswith('set libthread-db-search-path /tmp/gp-u-sysroot-') for x in command))
                    self.assertLess(command.index('bt 24'), command.index('thread apply all bt 24'))
                    self.assertNotIn('full', command)
                    self.assertIn('set sysroot ', ' '.join(command))
                    self.assertIn('set debug-file-directory ', ' '.join(command))
                    self.assertNotEqual(Path(command[-2]), binary)
                    self.assertEqual(Path(command[-2]).read_bytes(), b'exact binary')
                    kwargs['stdout'].write(b'WBB_PRIMARY_BEGIN\n#0 wbb_expected_crash ()\nWBB_PRIMARY_END\n' + b'x'*70000)
                else:
                    binary.write_bytes(b'changed by debugger dependencies')
                return subprocess.CompletedProcess(command, 0)
            with (patch.object(capture, 'LIBRARY_ROOTS', ()),
                  patch.object(capture, 'package_versions', side_effect=[{'libc6':'1'}, {'libc6':'2'}]),
                  patch.object(capture.subprocess, 'run', side_effect=run)):
                self.assertEqual(capture.container_backtrace(core, binary, output), 0)
            self.assertEqual(output.with_suffix('.txt').stat().st_size, capture.TEXT_LIMIT)
            self.assertTrue(json.loads(output.with_suffix('.json').read_text())['text_truncated'])

    def test_thread_helper_warning_refuses_a_seemingly_complete_primary_stack(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            binary, core, output = path/'binary', path/'core', path/'out'
            binary.write_bytes(b'fixture'); core.write_bytes(b'fixture')
            def run(command, **kwargs):
                if command[0] == 'gdb':
                    kwargs['stdout'].write(
                        b'WBB_PRIMARY_BEGIN\n#0 wbb_expected_crash ()\nWBB_PRIMARY_END\n'
                        b'warning: Unable to find libthread_db matching inferior'
                        b"'s thread library, thread debugging will not be available\n")
                return subprocess.CompletedProcess(command, 0)
            with (patch.object(capture, 'LIBRARY_ROOTS', ()),
                  patch.object(capture, 'package_versions', return_value={}),
                  patch.object(capture.subprocess, 'run', side_effect=run)):
                self.assertEqual(capture.container_backtrace(core, binary, output), 1)
            result = json.loads(output.with_suffix('.json').read_text())
            self.assertTrue(result['primary_stack_complete'])
            self.assertTrue(result['stack_incomplete'])
            self.assertEqual(result['status'], 'UNPROVEN')

    def test_worker_frame_cannot_qualify_missing_primary_stack(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            binary, core, output = path/'binary', path/'core', path/'out'
            binary.write_bytes(b'fixture'); core.write_bytes(b'fixture')
            def run(command, **kwargs):
                if command[0] == 'gdb':
                    kwargs['stdout'].write(b'#0 worker ()\n' + b'x'*70000 +
                        b'WBB_PRIMARY_BEGIN\n#0 actual_fault ()\nWBB_PRIMARY_END\n')
                return subprocess.CompletedProcess(command, 0)
            with (patch.object(capture, 'LIBRARY_ROOTS', ()),
                  patch.object(capture, 'package_versions', return_value={}),
                  patch.object(capture.subprocess, 'run', side_effect=run)):
                self.assertEqual(capture.container_backtrace(core, binary, output), 1)
            result = json.loads(output.with_suffix('.json').read_text())
            self.assertEqual(result['status'], 'UNPROVEN')
            self.assertFalse(result['primary_stack_complete'])

    def test_absolute_library_symlink_becomes_verified_original_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            libs, saved = directory/'libraries', directory/'saved'
            libs.mkdir(); saved.mkdir()
            original, link = libs/'libfixture.so.1', libs/'libfixture.so'
            original.write_bytes(b'\x7fELF original library')
            link.symlink_to(original)
            binary = directory/'binary'
            binary.write_bytes(b'original binary')
            with patch.object(capture, 'LIBRARY_ROOTS', (libs,)):
                manifest = capture.snapshot_inputs(binary, saved)
            copied = saved/link.relative_to('/')
            self.assertFalse(copied.is_symlink())
            original.write_bytes(b'changed library')
            capture.verify_snapshot(saved, manifest)
            self.assertEqual(copied.read_bytes(), b'\x7fELF original library')
            copied.write_bytes(b'changed snapshot')
            with self.assertRaisesRegex(RuntimeError, 'sysroot changed'):
                capture.verify_snapshot(saved, manifest)

    def test_thread_stack_proof_requires_distinct_real_thread_frames(self):
        diagnostic = ('[Thread debugging using libthread_db enabled]\n'
                      'WBB_PRIMARY_BEGIN\n#0 wbb_expected_crash\n'
                      'WBB_PRIMARY_END\n'
                      'Thread 2 (LWP 2):\n#0 wbb_worker_wait\n'
                      'Thread 1 (LWP 1):\n#0 wbb_expected_crash\n')
        self.assertTrue(capture.control_threads_verified(diagnostic))
        negatives = (
            diagnostic.replace('#0 wbb_worker_wait',
                               'warning: wbb_worker_wait symbol unavailable'),
            diagnostic.replace('Thread 2 (LWP 2):\n#0 wbb_worker_wait',
                               'Thread 2 (LWP 2):\n#0 something_else\n'
                               'Thread 1 (LWP 1):\n#1 wbb_worker_wait'),
            diagnostic.replace('Thread 1 (LWP 1):\n#0 wbb_expected_crash',
                               'Thread 1 (LWP 1):\n#0 something_else'),
            diagnostic.replace('[Thread debugging using libthread_db enabled]', ''),
            diagnostic.replace('WBB_PRIMARY_BEGIN', 'WBB_UNKNOWN_BEGIN'),
        )
        for broken in negatives:
            with self.subTest(broken=broken):
                self.assertFalse(capture.control_threads_verified(broken))

    def test_threaded_control_preflight_builds_one_synchronized_pthread_probe(self):
        with tempfile.TemporaryDirectory(prefix='gp-u-core-', dir='/tmp') as tmp:
            directory = Path(tmp)
            commands = []
            def run(command, **kwargs):
                commands.append(command)
                if command[0] == 'docker':
                    (directory/'core.gp-core-probe.123.456').write_bytes(b'core fixture')
                    return subprocess.CompletedProcess(command, 139)
                return subprocess.CompletedProcess(command, 0)
            with (patch.object(capture.subprocess, 'run', side_effect=run),
                  patch.object(capture, 'retire_container')):
                core, binary = capture.preflight(directory)
            self.assertEqual(core.name, 'core.gp-core-probe.123.456')
            self.assertEqual(binary, directory/'gp-core-probe')
            self.assertEqual(len(commands), 2)
            self.assertIn('-pthread', commands[0])
            self.assertEqual(commands[1][0:3], ['docker', 'run', '--rm'])
            self.assertEqual(commands[1].count('--cidfile'), 1)
            code = (directory/'probe.c').read_text()
            self.assertIn('pthread_create', code)
            self.assertIn('while (!worker_ready) pthread_cond_wait', code)
            self.assertIn('for (;;) pthread_cond_wait', code)
            self.assertIn('wbb_expected_crash();', code)

    def test_missing_secondary_stack_or_thread_helper_blocks_subject(self):
        positive = ('[Thread debugging using libthread_db enabled]\n'
                    '#0 wbb_expected_crash\nThread 2 (LWP 2):\n'
                    '#0 wbb_worker_wait\n')
        cases = (positive.replace('wbb_worker_wait', 'worker_unavailable'),
                 positive.replace('[Thread debugging using libthread_db enabled]', ''))
        for diagnostic in cases:
            with self.subTest(diagnostic=diagnostic), tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp)/'evidence'
                @contextmanager
                def route(directory, record):
                    yield
                def fake_probe(directory):
                    core = directory/'core.gp-core-probe.1.1'
                    core.write_bytes(b'core')
                    return core, directory/'gp-core-probe'
                def analyse(core, binary, label):
                    (out/(label+'.txt')).write_text(diagnostic)
                    return 0
                subject_invocations = []
                def run(command, **kwargs):
                    if command[0] == sys.executable:
                        subject_invocations.append(command)
                    return subprocess.CompletedProcess(command, 0)
                with (patch.object(capture, 'OUT', out),
                      patch.object(capture, 'kernel_capture', side_effect=route),
                      patch.object(capture, 'preflight', side_effect=fake_probe),
                      patch.object(capture, 'analyse', side_effect=analyse),
                      patch.object(capture.subprocess, 'run', side_effect=run)):
                    self.assertEqual(capture.host_main(), 1)
                self.assertEqual(subject_invocations, [])
                result = json.loads((out/'core-capture-host.json').read_text())
                self.assertEqual(result['status'], 'UNPROVEN')
                self.assertIn('multi-thread core', result['reason'])

    def test_native_failure_is_preserved_without_retry_even_with_a_stack(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'evidence'
            @contextmanager
            def route(directory, record):
                record['restored'] = False
                try:
                    yield
                finally:
                    record['restored'] = True
            def preflight(directory):
                core, binary = directory/'core.gp-core-probe.1.1', directory/'gp-core-probe'
                core.write_bytes(b'core'); binary.write_bytes(b'binary')
                return core, binary
            subjects = []
            def run(command, **kwargs):
                if command[0] == sys.executable:
                    subjects.append(command)
                    directory = Path(kwargs['env']['WEBEEBLOCKS_GP_CORE_DIR'])
                    (directory/'core.webots-bin.2.2').write_bytes(b'native core')
                    return subprocess.CompletedProcess(command, 17)
                return subprocess.CompletedProcess(command, 0)
            def analyse(core, binary, label):
                if label == 'core-capture-preflight':
                    (out/(label+'.txt')).write_text(
                        '[Thread debugging using libthread_db enabled]\n'
                        'WBB_PRIMARY_BEGIN\n#0 wbb_expected_crash\nWBB_PRIMARY_END\n'
                        'Thread 2 (LWP 2):\n#0 wbb_worker_wait\n'
                        'Thread 1 (LWP 1):\n#0 wbb_expected_crash\n')
                return 0
            with (patch.object(capture, 'OUT', out),
                  patch.object(capture, 'kernel_capture', side_effect=route),
                  patch.object(capture, 'preflight', side_effect=preflight),
                  patch.object(capture, 'analyse', side_effect=analyse),
                  patch.object(capture.subprocess, 'run', side_effect=run)):
                self.assertEqual(capture.host_main(), 17)
            self.assertEqual(subjects, [[sys.executable, str(capture.ROOT/
                'tools/ci/run_grand_prix_u_prototype.py')]])
            record = json.loads((out/'core-capture-host.json').read_text())
            self.assertEqual(record['subject_returncode'], 17)
            self.assertEqual(record['native_core_count'], 1)
            self.assertTrue(record['restored'])
            self.assertFalse(record['raw_core_uploaded'])

    def test_unknown_container_retirement_is_not_blindly_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            cid = Path(tmp)/'container.cid'
            cid.write_text('a'*64)
            observed = subprocess.CompletedProcess([], 1, '', 'Cannot connect to Docker')
            with patch.object(capture.subprocess, 'run', return_value=observed) as run:
                with self.assertRaisesRegex(RuntimeError, 'unproven'):
                    capture.retire_container(cid)
            self.assertEqual(run.call_count, 1)

    def test_post_ready_core_is_not_attributed_to_startup(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            trial = out/'witness'
            trial.mkdir()
            capture.write_json(trial/'startup-ready.json', dict(sequence_index=14,
                process_samples=[dict(processes=[dict(pid=811, comm='webots-bin')])]))
            core = Path('/tmp/core.webots-bin.811.12345')
            with patch.object(capture, 'OUT', out):
                self.assertEqual(capture.attribute(core)['phase'], 'AFTER_READY')
                capture.write_json(trial/'startup-failure.json', dict(sequence_index=14,
                    core=dict(native_sigsegv_pids_in_log=[811])))
                self.assertEqual(capture.attribute(core)['phase'], 'BEFORE_READY')


if __name__ == '__main__':
    unittest.main()

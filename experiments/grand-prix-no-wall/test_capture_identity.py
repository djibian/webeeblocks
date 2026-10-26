"""Injected procfs/syscall counterexamples; no model test sends a real signal."""
import ast
from contextlib import ExitStack
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch
import evidence_capture as c
from test_evidence_capture import sample

class ProcModel(unittest.TestCase):

    def put(self, pid, *, ppid=7, pgid=8, sid=8, state='S', birth=123, nspid=None):
        e = self.proc / str(pid)
        (e / 'ns').mkdir(parents=True, exist_ok=True)
        f = [state, str(ppid), str(pgid), str(sid)] + ['0'] * 15 + [str(birth)]
        (e / 'stat').write_text(f'{pid} (model (name)) ' + ' '.join(f))
        (e / 'status').write_text(f'NSpid: {nspid or pid}\nNSpgid: {pgid}\nNSsid: {sid}\nUid: 1000 1000 1000 1000\n')
        if not (e / 'ns/pid').is_symlink():
            (e / 'ns/pid').symlink_to('pid:[42]')
        (e / 'fd').mkdir(exist_ok=True)
        (e / 'fdinfo').mkdir(exist_ok=True)

    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.proc = self.root / 'proc'
        self.proc.mkdir()
        self.put(7, ppid=1, pgid=7, sid=7)
        (self.proc / 'self').symlink_to('7')
        (self.proc / '7/task/7').mkdir(parents=True)
        (self.proc / '1/ns').mkdir(parents=True)
        (self.proc / '1/ns/pid').symlink_to('pid:[42]')
        (self.proc / '7/ns/pid_for_children').symlink_to('pid:[42]')
        (self.proc / '7/mountinfo').write_text(f'1 0 0:1 / {self.proc} rw - proc proc rw\n')
        self.put(8)
        self.child = NS(pid=8, returncode=None, args=['model'])

        def reap(timeout):
            self.child.returncode = 0
            return 0
        self.child.wait = Mock(side_effect=reap)
        stack = ExitStack()
        self.addCleanup(stack.close)
        for obj, key, value in [(c, 'PROC', self.proc), (os, 'getpid', lambda: 7), (os, 'geteuid', lambda: 1000), (os, 'getpgrp', lambda: 7), (os, 'getsid', lambda p: 7 if p == 0 else c._stat(self.proc / str(p) / 'stat')['sid']), (os, 'getpgid', lambda p: c._stat(self.proc / str(p) / 'stat')['pgid']), (signal, 'getsignal', lambda sig: signal.SIG_DFL)]:
            stack.enter_context(patch.object(obj, key, value))

        def wait(*args):
            if c._stat(self.proc / '8/stat')['state'] == 'Z':
                return NS(si_pid=8, si_uid=1000, si_status=0, si_code=os.CLD_EXITED)
            return None
        self.waitid = stack.enter_context(patch.object(os, 'waitid', side_effect=wait))
        self.killpg = stack.enter_context(patch.object(os, 'killpg'))
        self.domain = c.qualify_procfs()
        self.child._capture_domain = self.domain
        self.child._capture_identity = c._leader_identity(self.child, self.domain)

    def test_coherent_namespace(self):
        self.assertEqual(c.qualify_procfs()['nspid'], [7])
        self.assertEqual(c._group_members(8), [8])
        self.assertEqual(self.child._capture_identity['birth'], 123)

    def divergence(self):
        self.put(13903, ppid=1, pgid=13903, sid=13903, nspid='13903 7')
        (self.proc / 'self').unlink()
        (self.proc / 'self').symlink_to('13903')

    def test_false_negative_13903_7(self):
        self.divergence()
        with self.assertRaisesRegex(c.EvidenceError, 'divergence'):
            c._group_members(7)
        self.killpg.assert_not_called()

    def test_false_positive_foreign_pid_7(self):
        self.divergence()
        with self.assertRaises(c.EvidenceError):
            c.stop_writer_groups([NS(pid=7, returncode=None)])
        self.killpg.assert_not_called()

    def test_reaped_pid(self):
        self.child.returncode = 0
        with self.assertRaisesRegex(c.EvidenceError, 'already reaped'):
            c.stop_writer_groups([self.child])
        self.killpg.assert_not_called()

    def test_reused_pid_not_child(self):
        self.waitid.side_effect = ChildProcessError('harvested')
        with self.assertRaisesRegex(c.EvidenceError, 'unreaped'):
            c.stop_writer_groups([self.child])
        self.killpg.assert_not_called()

    def test_birth_changed(self):
        self.put(8, birth=124)
        with self.assertRaisesRegex(c.EvidenceError, 'birth'):
            c.stop_writer_groups([self.child])
        self.killpg.assert_not_called()

    def test_foreign_parent_session(self):
        self.put(8, ppid=1, sid=99)
        with self.assertRaisesRegex(c.EvidenceError, 'identity'):
            c.stop_writer_groups([self.child])
        self.killpg.assert_not_called()

    def test_identity_rechecked_after_scan(self):
        original = c._group_members

        def change(*args):
            found = original(*args)
            self.put(8, birth=999)
            return found
        with patch.object(c, '_group_members', side_effect=change):
            with self.assertRaisesRegex(c.EvidenceError, 'signal identity'):
                c.stop_writer_groups([self.child])
        self.killpg.assert_not_called()
        self.child.wait.assert_not_called()

    def test_zombie_leader_descendant_alive(self):
        self.put(8, state='Z')
        self.put(9, ppid=1)

        def stop(pgid, sig):
            self.assertEqual((pgid, sig), (8, signal.SIGTERM))
            self.child.wait.assert_not_called()
            self.put(9, ppid=1, state='Z')
        self.killpg.side_effect = stop
        exits = c.stop_writer_groups([self.child], grace=0, kill_grace=0)
        self.assertEqual(exits[0]['identity']['pgid'], 8)
        self.child.wait.assert_called_once()
        self.assertTrue(all((x.args[2] & os.WNOWAIT for x in self.waitid.call_args_list)))

    def test_namespace_and_credentials_changed(self):
        (self.proc / '8/ns/pid').unlink()
        (self.proc / '8/ns/pid').symlink_to('pid:[999]')
        with self.assertRaises(c.EvidenceError):
            c.stop_writer_groups([self.child])
        self.killpg.assert_not_called()
        (self.proc / '8/ns/pid').unlink()
        (self.proc / '8/ns/pid').symlink_to('pid:[42]')
        f = self.proc / '8/status'
        f.write_text(f.read_text().replace('Uid: 1000 1000 1000 1000', 'Uid: 1000 0 1000 1000'))
        with self.assertRaises(c.EvidenceError):
            c.stop_writer_groups([self.child])
        self.killpg.assert_not_called()

    def test_escalation(self):

        def stop(pgid, sig):
            if sig == signal.SIGKILL:
                self.put(8, state='Z')
        self.killpg.side_effect = stop
        c.stop_writer_groups([self.child], grace=0, kill_grace=0)
        self.assertEqual([x.args[1] for x in self.killpg.call_args_list], [signal.SIGTERM, signal.SIGKILL])

    def test_failed_drain_never_reaps(self):
        with self.assertRaisesRegex(c.EvidenceError, 'still alive'):
            c.stop_writer_groups([self.child], grace=0, kill_grace=0)
        self.child.wait.assert_not_called()

    def test_permission_denied(self):
        self.waitid.side_effect = None
        self.waitid.return_value = None
        original = c._stat

        def read(path):
            if path == self.proc / '8/stat':
                raise PermissionError('hidden')
            return original(path)
        with patch.object(c, '_stat', side_effect=read):
            with self.assertRaises(c.EvidenceError):
                c.stop_writer_groups([self.child])
        self.killpg.assert_not_called()

    def test_hidepid(self):
        f = self.proc / '7/mountinfo'
        f.write_text(f.read_text().rstrip() + ',hidepid=2\n')
        with self.assertRaisesRegex(c.EvidenceError, 'visibility'):
            c.qualify_procfs()

    def test_other_reaper_or_threads(self):
        with patch.object(signal, 'getsignal', return_value=signal.SIG_IGN):
            with self.assertRaises(c.EvidenceError):
                c.qualify_procfs()
        (self.proc / '7/task/10').mkdir()
        with self.assertRaises(c.EvidenceError):
            c.qualify_procfs()

    def test_detached_fd(self):
        folder = self.root / 'trial'
        folder.mkdir()
        self.put(9, pgid=9, sid=9)
        (self.proc / '9/fd/4').symlink_to(folder / 'flight.log')
        (self.proc / '9/fdinfo/4').write_text('flags: 0100001\n')
        with patch.object(os, 'geteuid', return_value=os.stat(self.proc / '9').st_uid), patch.object(c, 'stop_writer_groups', return_value=[]):
            with self.assertRaisesRegex(c.EvidenceError, 'untracked writable'):
                c.close_capture([], [], folder)
        self.assertFalse((folder / 'capture-seal.json').exists())

class ErrorSafety(unittest.TestCase):

    def test_native_and_multiple_cleanup_errors(self):
        native = RuntimeError('native first')
        errors = [OSError('cleanup'), ValueError('close')]
        seen = []

        def fail(e):
            seen.append(e)
            raise e
        with self.assertRaises(RuntimeError) as caught:
            try:
                raise native
            finally:
                with c.preserve_errors(native) as attempt:
                    for e in errors:
                        attempt(lambda e=e: fail(e))
        self.assertIs(caught.exception, native)
        self.assertEqual(native.capture_cleanup_errors, tuple(errors))
        self.assertEqual(seen, errors)

    def test_group_and_close_errors(self):
        first = c.EvidenceError('group')
        second = OSError('close')
        stream = NS(close=Mock(side_effect=second))
        with patch.object(c, 'stop_writer_groups', side_effect=first):
            with self.assertRaises(c.EvidenceError) as caught:
                c.close_capture([], [stream], '/never-sealed')
        self.assertIs(caught.exception, first)
        self.assertEqual(first.capture_cleanup_errors, (second,))

    def test_nested_cleanup_preserves_existing_errors(self):
        first = c.EvidenceError('group')
        stream = OSError('stream')
        runtime = OSError('runtime')
        first.capture_cleanup_errors = (stream,)

        def fail(error):
            raise error
        with self.assertRaises(c.EvidenceError) as caught:
            with c.preserve_errors() as attempt:
                attempt(lambda: fail(first))
                attempt(lambda: fail(runtime))
        self.assertIs(caught.exception, first)
        self.assertEqual(first.capture_cleanup_errors, (stream, runtime))

    def test_handled_unrelated_exception_never_swallows_cleanup(self):
        try:
            raise RuntimeError('unrelated caller context')
        except RuntimeError:
            with self.assertRaises(OSError):
                with c.preserve_errors() as attempt:
                    attempt(lambda: (_ for _ in ()).throw(OSError('must propagate')))

    def test_python310_note_fallback(self):
        error = NS(add_note=None)
        with patch('sys.stderr', io.StringIO()) as log:
            c._note(error, 'retained diagnostic')
        self.assertEqual(error.capture_notes, ('retained diagnostic',))
        self.assertIn('retained diagnostic', log.getvalue())

    def test_actual_runner_lifecycle(self):
        for name in ['run_native.py', 'run_negative.py']:
            for native_failure, closure_failure in [(False, False), (True, True), (False, True)]:
                mod = ast.parse(Path(__file__).with_name(name).read_text())
                trial = next((x for x in mod.body if isinstance(x, ast.FunctionDef) and x.name == 'trial'))
                start = next((i for i, x in enumerate(trial.body) if isinstance(x, ast.Try)))
                suffix = ast.Module(body=trial.body[start:], type_ignores=[])
                suffix.body[0].body = ast.parse("raise RuntimeError('native first')" if native_failure else 'pass').body
                suffix.body[-1] = ast.parse('returned=result').body[0]
                runtime = NS(cleanup=Mock())
                target = NS(unlink=Mock(), stem='world', with_name=Mock(return_value=NS(unlink=Mock())))
                close = Mock(side_effect=OSError('close') if closure_failure else None)
                scope = dict(close_capture=close, preserve_errors=c.preserve_errors, children=[], streams=[], out='model', native_error=None, runtime_state=runtime, target=target, json=json, result={})
                output = io.StringIO()
                with patch('sys.stdout', output):
                    if native_failure or closure_failure:
                        with self.assertRaises(RuntimeError if native_failure else OSError):
                            exec(compile(ast.fix_missing_locations(suffix), name, 'exec'), scope)
                        self.assertNotIn('GP_U_NATIVE', output.getvalue())
                    else:
                        exec(compile(ast.fix_missing_locations(suffix), name, 'exec'), scope)
                        self.assertIn('GP_U_CAPTURE_CLOSED', output.getvalue())
                runtime.cleanup.assert_called_once()
                target.unlink.assert_called_once()

class PublicationSafety(unittest.TestCase):

    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.source = sample(self.root)
        self.dest = self.root / 'result.tar.xz'

    def test_fsync_after_link_uncertain(self):
        original = os.fsync

        def fail(fd):
            if self.dest.exists():
                raise OSError('directory fsync')
            return original(fd)
        with patch.object(os, 'fsync', side_effect=fail):
            with self.assertRaises(OSError) as caught:
                c.archive_capture(self.source, self.dest)
        self.assertTrue(caught.exception.publication_uncertain)
        self.assertTrue(self.dest.exists())
        with self.assertRaises(c.EvidenceError):
            c.archive_capture(self.source, self.dest)

    def interrupt(self, stage):
        if stage == 'after_link':
            raise KeyboardInterrupt('publication interrupted')

    def test_old_unqualified_seal_refused(self):
        seal = self.source / 'capture-seal.json'
        value = json.loads(seal.read_text())
        value['schema'] = 1
        seal.write_text(json.dumps(value))
        with self.assertRaisesRegex(c.EvidenceError, 'not attested'):
            c.archive_capture(self.source, self.dest)
        self.assertFalse(self.dest.exists())

    def test_interrupt_after_link(self):
        with self.assertRaises(KeyboardInterrupt) as caught:
            c.archive_capture(self.source, self.dest, hook=self.interrupt)
        self.assertTrue(caught.exception.publication_uncertain)
        self.assertTrue(self.dest.exists())
        self.assertFalse(list(self.root.glob('*.partial')))

    def test_cleanup_does_not_mask_publication(self):
        original = Path.unlink

        def fail(p, *args, **kw):
            if str(p).endswith('.partial'):
                raise OSError('unlink refused')
            return original(p, *args, **kw)
        with patch.object(Path, 'unlink', fail):
            with self.assertRaises(KeyboardInterrupt) as caught:
                c.archive_capture(self.source, self.dest, hook=self.interrupt)
        self.assertTrue(caught.exception.publication_uncertain)
        self.assertEqual(str(caught.exception.capture_cleanup_errors[0]), 'unlink refused')

class RealKernelBoundary(unittest.TestCase):

    def test_wnowait_retains_actual_child(self):
        child = subprocess.Popen([sys.executable, '-c', 'pass'], start_new_session=True)
        try:
            self.assertEqual(c.wait_writer(child, 3), 0)
            self.assertIsNone(child.returncode)
            self.assertEqual(c.observe_exit(child), 0)
            self.assertEqual(os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOWAIT).si_pid, child.pid)
        finally:
            child.wait(timeout=3)
        with self.assertRaises(c.EvidenceError):
            c.observe_exit(child)

    def test_actual_host_refuses_before_spawn(self):
        try:
            c.qualify_procfs()
        except c.EvidenceError:
            with patch.object(subprocess, 'Popen') as popen:
                with self.assertRaises(c.EvidenceError):
                    c.spawn_writer(['never-executed'])
                popen.assert_not_called()
        else:
            self.assertEqual(c.qualify_procfs()['procfs_pid'], os.getpid())
if __name__ == '__main__':
    unittest.main()

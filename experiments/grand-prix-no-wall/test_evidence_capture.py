"""Adversarial synthetic evidence tests. Never starts Webots."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest

from evidence_capture import EvidenceError, archive_capture, close_capture, _group_members


def sample(root):
    folder = root / 'gp-u-synthetic-s5'
    folder.mkdir()
    (folder / 'node.log').write_text('mission status = achieved\n')
    (folder / 'flight.log').write_text('flight output\n')
    close_capture([], [], folder)
    return folder


def archive_worker(args):
    folder, dest = args
    try:
        archive_capture(folder, dest)
        return 'created'
    except (EvidenceError, FileExistsError):
        return 'refused'


class ArchiveSafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gp-proof-tests-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = sample(self.root)
        self.dest = self.root / 'export' / 'seed5.tar.xz'

    def test_valid_immutable_archive_and_reopen(self):
        result = archive_capture(self.folder, self.dest)
        self.assertEqual(result['members'], 4)
        self.assertEqual(self.dest.stat().st_mode & 0o222, 0)
        first = self.dest.read_bytes()
        self.assertEqual(hashlib.sha256(first).hexdigest(), result['sha256'])
        with tarfile.open(self.dest, 'r:xz') as tar:
            self.assertEqual(len(tar.getmembers()), 4)
            self.assertEqual(tar.extractfile(f'{self.folder.name}/flight.log').read(),
                             b'flight output\n')
        with self.assertRaises(EvidenceError):
            archive_capture(self.folder, self.dest)
        self.assertEqual(first, self.dest.read_bytes())

    def test_source_modified_since_manifest(self):
        (self.folder / 'flight.log').write_text('late bytes\n')
        with self.assertRaisesRegex(EvidenceError, 'manifest'):
            archive_capture(self.folder, self.dest)
        self.assertFalse(self.dest.exists())

    def test_source_missing(self):
        (self.folder / 'node.log').unlink()
        with self.assertRaisesRegex(EvidenceError, 'enumerate'):
            archive_capture(self.folder, self.dest)
        self.assertFalse(self.dest.exists())

    def test_manifest_incoherent(self):
        manifest = json.loads((self.folder / 'sha256.json').read_text())
        del manifest['node.log']
        (self.folder / 'sha256.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(EvidenceError, 'enumerate'):
            archive_capture(self.folder, self.dest)

    def test_late_write_during_archive(self):
        def mutation(stage):
            if stage == 'after_write':
                (self.folder / 'node.log').write_text('post-capture late writer\n')
        with self.assertRaises(EvidenceError):
            archive_capture(self.folder, self.dest, hook=mutation)
        self.assertFalse(self.dest.exists())
        self.assertFalse(list(self.dest.parent.glob('*.partial')))

    def test_archive_interrupted_before_publication(self):
        def interrupt(_):
            raise KeyboardInterrupt('forced interruption during packaging')
        with self.assertRaises(KeyboardInterrupt):
            archive_capture(self.folder, self.dest, hook=interrupt)
        self.assertFalse(self.dest.exists())
        self.assertFalse(list(self.dest.parent.glob('*.partial')))

    def test_temporary_archive_corruption(self):
        def corrupt(stage):
            if stage == 'after_write':
                next(self.dest.parent.glob('*.partial')).write_bytes(b'not a valid tar')
        with self.assertRaises((tarfile.TarError, EOFError, EvidenceError, OSError)):
            archive_capture(self.folder, self.dest, hook=corrupt)
        self.assertFalse(self.dest.exists())

    def test_concurrent_attempts_only_one_archive(self):
        with concurrent.futures.ProcessPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(archive_worker, [(self.folder, self.dest)] * 2))
        self.assertEqual(sorted(results), ['created', 'refused'])

    @unittest.skipUnless(Path('/proc/self/stat').is_file(), 'Linux process group evidence')
    def test_descendant_still_alive_after_leader_exits(self):
        folder = self.root / 'descendant'
        folder.mkdir()
        marker, late = self.root / 'grandchild_ready', self.root / 'grandchild_wrote'
        grandchild = ("import pathlib,time; pathlib.Path(%r).write_text('ready'); "
                      "time.sleep(0.75); pathlib.Path(%r).write_text('late')"
                      % (str(marker), str(late)))
        leader = ("import subprocess,sys; subprocess.Popen([sys.executable,'-c',%r], "
                  "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, "
                  "stderr=subprocess.DEVNULL)" % grandchild)
        proc = subprocess.Popen([sys.executable, '-c', leader], start_new_session=True)
        deadline = time.monotonic() + 3
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(marker.exists())
        self.assertTrue(_group_members(proc.pid))
        close_capture([proc], [], folder)
        self.assertEqual(_group_members(proc.pid), [])
        time.sleep(.9)
        self.assertFalse(late.exists(), 'descendant wrote after proof closure')
        self.assertTrue((folder / 'capture-seal.json').exists())

    @unittest.skipUnless(Path('/proc/self/stat').is_file(), 'Linux /proc required')
    def test_detached_writer_fd_refuses_seal(self):
        target = self.folder / 'flight.log'
        code = ("import pathlib,time; f=open(%r, 'a'); "
                "pathlib.Path(%r).write_text('ready'); time.sleep(1.2); "
                "f.write('delayed'); f.flush(); f.close()" %
                (str(target), str(self.root / 'writer_ready')))
        proc = subprocess.Popen([sys.executable, '-c', code], start_new_session=True)
        try:
            deadline = time.monotonic() + 2
            while not (self.root / 'writer_ready').exists() and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue((self.root / 'writer_ready').exists())
            with self.assertRaisesRegex(EvidenceError, 'untracked writable'):
                close_capture([], [], self.folder)
            self.assertFalse(self.dest.exists())
        finally:
            proc.terminate()
            proc.wait(timeout=3)

    def test_refuse_unsealed_directory(self):
        (self.folder / 'capture-seal.json').unlink()
        with self.assertRaisesRegex(EvidenceError, 'seal'):
            archive_capture(self.folder, self.dest)

    def test_failure_to_close_does_not_claim_result(self):
        class BrokenStream:
            closed = False
            def close(self):
                raise OSError('close failure')
        with self.assertRaises(OSError):
            close_capture([], [BrokenStream()], self.root / 'failed')
        self.assertFalse((self.root / 'failed' / 'capture-seal.json').exists())


if __name__ == '__main__':
    unittest.main()

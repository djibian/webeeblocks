#!/usr/bin/env python3
"""Offline negative contract for process-level Qt665 attestation (no fake PASS)."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import attest_running_consumer as probe


class RunningConsumerTests(unittest.TestCase):
    def test_stat_with_parentheses(self):
        with tempfile.TemporaryDirectory() as directory:
            proc = Path(directory)
            tail = ['S'] + ['0'] * 18 + ['123456'] + ['0'] * 4
            (proc/'stat').write_text('42 (webots (native)) ' + ' '.join(tail))
            self.assertEqual(probe.starttime(proc), '123456')
            (proc/'stat').write_text('42 broken')
            with self.assertRaises(ValueError):
                probe.starttime(proc)

    def test_mapped_qt_inode_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            lib = Path(directory)/'libQt6Core.so.6.5.3'
            lib.write_bytes(b'exact-qt-in-test')
            st = lib.stat()
            device = f'{__import__("os").major(st.st_dev):02x}:{__import__("os").minor(st.st_dev):02x}'
            line = f'7fb-8fb r-xp 00000000 {device} {st.st_ino} {lib}\n'
            self.assertEqual(probe.mapped_qt_files(line, lib.name, lib), {lib})
            # Native Webots /proc/maps exposes the SONAME alias rather than
            # the fully versioned filename checked by the SHA-256 policy.
            alias = lib.with_name('libQt6Core.so.6')
            alias.symlink_to(lib.name)
            alias_line = line.replace(str(lib), str(alias))
            self.assertEqual(probe.mapped_qt_files(alias_line, lib.name, lib), {lib})
            with self.assertRaisesRegex(ValueError, 'inode differs'):
                probe.mapped_qt_files(
                    alias_line.replace(str(st.st_ino), str(st.st_ino+1), 1), lib.name, lib)
            with self.assertRaisesRegex(ValueError, 'deleted'):
                probe.mapped_qt_files(alias_line.strip()+' (deleted)\\n', lib.name, lib)
            with self.assertRaisesRegex(ValueError, 'inode differs'):
                probe.mapped_qt_files(line.replace(str(st.st_ino), str(st.st_ino+1), 1), lib.name, lib)
            with self.assertRaisesRegex(ValueError, 'deleted'):
                probe.mapped_qt_files(line.strip()+ ' (deleted)\n', lib.name, lib)

    def test_self_process_cannot_be_mislabelled_webots(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)/'webots'
            (home/'bin').mkdir(parents=True)
            (home/'resources').mkdir()
            (home/'resources/version.txt').write_text('R2025a\n')
            (home/'bin/webots-bin').write_bytes(b'not-qualified-webots')
            manifest = Path(directory)/'manifest.json'
            cmd = [sys.executable, str(Path(probe.__file__)), '--runtime-home', str(home),
                   '--pid', str(__import__('os').getpid()), '--manifest', str(manifest)]
            run = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            self.assertNotEqual(run.returncode, 0)
            payload = json.loads(manifest.read_text())
            self.assertEqual(payload['verdict'], 'UNPROVEN')
            self.assertIn('not the installed Webots ELF', payload['error'])

    def test_pid_and_version_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home/'resources').mkdir()
            (home/'resources/version.txt').write_text('R2024b\n')
            for pid in [0, -1, 999999999]:
                with self.subTest(pid=pid), self.assertRaises(ValueError):
                    probe.attest(home, pid)


if __name__ == '__main__':
    unittest.main()

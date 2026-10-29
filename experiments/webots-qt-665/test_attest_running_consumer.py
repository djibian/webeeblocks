#!/usr/bin/env python3
"""Offline negative contract for process-level Qt665 attestation (no fake PASS)."""
import hashlib
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


    def test_rename_between_map_stat_and_digest_is_rejected(self):
        """The hash must come from the SAME open inode as /proc/PID/maps."""
        import os
        from unittest import mock

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / 'webots'
            libdir = home / 'lib/webots'
            libdir.mkdir(parents=True)
            original_open = Path.open

            def mapped(path):
                st = path.stat()
                return (f'7fb-8fb r-xp 00000000 '
                        f'{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x} '
                        f'{st.st_ino} {path}\n')

            def race(path, substitute, operation):
                swapped = [False]
                def open_after_swap(instance, *args, **kwargs):
                    if instance == path and not swapped[0]:
                        swapped[0] = True
                        os.replace(substitute, path)
                    return original_open(instance, *args, **kwargs)
                with mock.patch.object(Path, 'open', new=open_after_swap):
                    with self.assertRaisesRegex(ValueError, 'inode differs'):
                        operation()
                self.assertTrue(swapped[0], 'race injection was not exercised')

            pinned = libdir / 'libQt6Core.so.6.5.3'
            pinned.write_bytes(b'mapped-untrusted-contents')
            substitute = libdir / 'replacement-core'
            substitute.write_bytes(b'expected-verified-contents')
            maps = mapped(pinned)
            expected = hashlib.sha256(substitute.read_bytes()).hexdigest()
            race(pinned, substitute,
                 lambda: probe.mapped_qt_files(maps, pinned.name, pinned, expected))

            gui = libdir / 'libQt6Gui.so.6'
            gui.write_bytes(b'mapped-gui-contents')
            replacement_gui = libdir / 'replacement-gui'
            replacement_gui.write_bytes(b'new-gui-contents')
            maps = mapped(gui)
            race(gui, replacement_gui,
                 lambda: probe.observed_qt_family(maps, home))

    def test_mapped_qt_inode_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            lib = Path(directory)/'libQt6Core.so.6.5.3'
            lib.write_bytes(b'exact-qt-in-test')
            st = lib.stat()
            device = f'{__import__("os").major(st.st_dev):02x}:{__import__("os").minor(st.st_dev):02x}'
            line = f'7fb-8fb r-xp 00000000 {device} {st.st_ino} {lib}\n'
            expected = hashlib.sha256(lib.read_bytes()).hexdigest()
            self.assertEqual(probe.mapped_qt_files(line, lib.name, lib, expected), {lib})
            # Native Webots /proc/maps exposes the SONAME alias rather than
            # the fully versioned filename checked by the SHA-256 policy.
            alias = lib.with_name('libQt6Core.so.6')
            alias.symlink_to(lib.name)
            alias_line = line.replace(str(lib), str(alias))
            self.assertEqual(probe.mapped_qt_files(alias_line, lib.name, lib, expected), {alias})
            with self.assertRaisesRegex(ValueError, 'inode differs'):
                probe.mapped_qt_files(
                    alias_line.replace(str(st.st_ino), str(st.st_ino+1), 1), lib.name, lib, expected)
            with self.assertRaisesRegex(ValueError, 'deleted'):
                probe.mapped_qt_files(alias_line.strip()+' (deleted)\n', lib.name, lib, expected)
            # R2025a image uses a separate regular .so.6 file, not a symlink.
            alias.unlink()
            alias.write_bytes(lib.read_bytes())
            alias_st = alias.stat()
            separate_line = f'7fb-8fb r-xp 00000000 {device} {alias_st.st_ino} {alias}\n'
            self.assertEqual(probe.mapped_qt_files(
                separate_line, lib.name, lib, expected), {alias})
            alias.write_bytes(b'wrong-library')
            with self.assertRaisesRegex(ValueError, 'bytes differ'):
                probe.mapped_qt_files(separate_line, lib.name, lib, expected)
            alias.write_bytes(lib.read_bytes())
            with self.assertRaisesRegex(ValueError, 'inode differs'):
                probe.mapped_qt_files(
                    separate_line.replace(str(alias_st.st_ino), str(alias_st.st_ino+1), 1),
                    lib.name, lib, expected)
            with self.assertRaisesRegex(ValueError, 'inode differs'):
                probe.mapped_qt_files(line.replace(str(st.st_ino), str(st.st_ino+1), 1), lib.name, lib, expected)
            with self.assertRaisesRegex(ValueError, 'deleted'):
                probe.mapped_qt_files(line.strip()+ ' (deleted)\n', lib.name, lib, expected)



    def test_qtgui_digest_from_pinned_native_full_link_and_soname_negatives(self):
        """R2025a original/candidate hashes agree; map still needs real bytes."""
        import os
        qualified = 'f8396f49e2bcfb3e667ba17bd861f1f0be806153141cc3966e79f726818e24e9'
        self.assertEqual(probe.QT_SHA256['libQt6Gui.so.6.5.3'], qualified)
        self.assertEqual(set(probe.QT_SHA256),
                         {'libQt6Core.so.6.5.3', 'libQt6Gui.so.6.5.3',
                          'libQt6Widgets.so.6.5.3'})
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / 'webots/lib/webots'
            home.mkdir(parents=True)
            gui = home / 'libQt6Gui.so.6.5.3'
            gui.write_bytes(b'QtGui fixture, not an authentic distribution')
            alias = home / 'libQt6Gui.so.6'
            # The actual R2025a process may map a separate .so.6 inode.
            alias.write_bytes(gui.read_bytes())
            digest = hashlib.sha256(gui.read_bytes()).hexdigest()
            def mapped(path):
                st = path.stat()
                return (f'7fb-8fb r-xp 00000000 '
                        f'{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x} '
                        f'{st.st_ino} {path}\n')
            self.assertEqual(probe.mapped_qt_files(
                mapped(alias), gui.name, gui, digest), {alias})
            # Installed versioned file and actual mapped alias must both agree.
            alias.write_bytes(b'mapped GUI altered after install')
            with self.assertRaisesRegex(ValueError, 'bytes differ'):
                probe.mapped_qt_files(mapped(alias), gui.name, gui, digest)
            alias.write_bytes(gui.read_bytes())
            with self.assertRaisesRegex(ValueError, 'deleted'):
                probe.mapped_qt_files(mapped(alias).strip() + ' (deleted)\n',
                                      gui.name, gui, digest)
            old_inode = alias.stat().st_ino
            with self.assertRaisesRegex(ValueError, 'inode differs'):
                probe.mapped_qt_files(
                    mapped(alias).replace(f' {old_inode} ', f' {old_inode + 1} ', 1),
                    gui.name, gui, digest)
            foreign = Path(directory) / 'libQt6Gui.so.6'
            foreign.write_bytes(gui.read_bytes())
            with self.assertRaisesRegex(ValueError, 'outside pinned runtime'):
                probe.mapped_qt_files(mapped(foreign), gui.name, gui, digest)

    def test_observed_all_qt6_dso_origins_without_inventing_hash_qualification(self):
        import os
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / 'webots'
            libdir = home / 'lib/webots'
            libdir.mkdir(parents=True)
            outside = Path(directory) / 'foreign'
            outside.mkdir()
            core = libdir / 'libQt6Core.so.6.5.3'
            gui = libdir / 'libQt6Gui.so.6'
            network = libdir / 'libQt6Network.so.6'
            for file in (core, gui, network):
                file.write_bytes(file.name.encode())
            def row(file):
                st = file.stat()
                return (f'7fb-8fb r-xp 00000000 '
                        f'{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x} '
                        f'{st.st_ino} {file}\n')
            valid = row(core) + row(gui) + row(gui) + row(network)
            result = probe.observed_qt_family(valid, home)
            self.assertEqual(set(result), {'libQt6Core', 'libQt6Gui', 'libQt6Network'})
            self.assertEqual(result['libQt6Gui']['mapped_filename'], str(gui))
            self.assertEqual(result['libQt6Gui']['sha256_observed_only'],
                             hashlib.sha256(gui.read_bytes()).hexdigest())
            # The same-runtime result is a measurement, not a pinned digest.
            self.assertNotIn('qualified_digest_verified', result['libQt6Gui'])
            with self.assertRaisesRegex(ValueError, 'Qt6Gui mapping missing'):
                probe.observed_qt_family(row(core), home)
            foreign = outside / gui.name
            foreign.write_bytes(gui.read_bytes())
            with self.assertRaisesRegex(ValueError, 'outside bundled'):
                probe.observed_qt_family(row(core) + row(foreign), home)
            with self.assertRaisesRegex(ValueError, 'deleted'):
                probe.observed_qt_family(row(core) + row(gui).strip() + ' (deleted)\n', home)
            st = gui.stat()
            altered = row(gui).replace(f' {st.st_ino} ', f' {st.st_ino + 1} ', 1)
            with self.assertRaisesRegex(ValueError, 'inode differs'):
                probe.observed_qt_family(row(core) + altered, home)
            with self.assertRaisesRegex(ValueError, 'malformed Qt6'):
                probe.observed_qt_family(row(core) + 'incomplete libQt6Gui.so.6', home)
            wrong_version = libdir / 'libQt6Gui.so.6.6.0'
            wrong_version.write_bytes(gui.read_bytes())
            with self.assertRaisesRegex(ValueError, 'SONAME version'):
                probe.observed_qt_family(row(core) + row(wrong_version), home)
            other_gui = libdir / 'libQt6Gui.so.6.5.3'
            other_gui.write_bytes(gui.read_bytes())
            with self.assertRaisesRegex(ValueError, 'ambiguous Qt6 family'):
                probe.observed_qt_family(valid + row(other_gui), home)
            gui_alias = libdir / 'libQt6Gui.so.6.5.3-link'
            gui_alias.symlink_to(foreign)
            with self.assertRaisesRegex(ValueError, 'SONAME version'):
                probe.observed_qt_family(row(core) + row(gui_alias), home)
            gui.unlink()
            gui.symlink_to(foreign)
            with self.assertRaisesRegex(ValueError, 'outside bundled'):
                probe.observed_qt_family(row(core) + row(gui), home)


    def test_qt_platform_plugin_mapped_identity_is_restricted_and_observed_only(self):
        import os
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / 'webots'
            plugins = home / 'lib/webots/qt/plugins/platforms'
            plugins.mkdir(parents=True)
            foreign = Path(directory) / 'foreign'
            foreign.mkdir()
            xcb = plugins / 'libqxcb.so'
            xcb.write_bytes(b'qualified-location-only')
            def row(path):
                st = path.stat()
                return (f'7fb-8fb r-xp 00000000 '
                        f'{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x} '
                        f'{st.st_ino} {path}\n')
            self.assertEqual(probe.observed_qt_platform_plugins('', home), {},
                             'missing platform mapping is NOT_OBSERVED, not a fake PASS')
            mapped = probe.observed_qt_platform_plugins(row(xcb) * 2, home)
            self.assertEqual(set(mapped), {'libqxcb.so'})
            self.assertEqual(mapped['libqxcb.so']['mapped_filename'], str(xcb))
            self.assertEqual(mapped['libqxcb.so']['sha256_observed_only'],
                             hashlib.sha256(xcb.read_bytes()).hexdigest())
            self.assertNotIn('qualified_digest_verified', mapped['libqxcb.so'])
            outsider = foreign / 'libqxcb.so'
            outsider.write_bytes(xcb.read_bytes())
            with self.assertRaisesRegex(ValueError, 'outside bundled runtime'):
                probe.observed_qt_platform_plugins(row(outsider), home)
            with self.assertRaisesRegex(ValueError, 'deleted'):
                probe.observed_qt_platform_plugins(row(xcb).strip() + ' (deleted)\n', home)
            st = xcb.stat()
            with self.assertRaisesRegex(ValueError, 'mapped inode differs'):
                probe.observed_qt_platform_plugins(
                    row(xcb).replace(f' {st.st_ino} ', f' {st.st_ino + 1} ', 1), home)
            with self.assertRaisesRegex(ValueError, 'malformed Qt platform'):
                probe.observed_qt_platform_plugins('incomplete libqxcb.so', home)
            unknown = plugins / 'libqunknown.so'
            unknown.write_bytes(b'unqualified-platform')
            with self.assertRaisesRegex(ValueError, 'unknown Qt platform'):
                probe.observed_qt_platform_plugins(row(xcb) + row(unknown), home)
            second = plugins / 'libqoffscreen.so'
            second.write_bytes(b'other-plugin')
            self.assertEqual(
                set(probe.observed_qt_platform_plugins(row(xcb) + row(second), home)),
                {'libqxcb.so', 'libqoffscreen.so'})
            other = plugins / 'sub'
            other.mkdir()
            odd = other / 'libqxcb.so'
            odd.write_bytes(xcb.read_bytes())
            with self.assertRaisesRegex(ValueError, 'outside bundled runtime'):
                probe.observed_qt_platform_plugins(row(xcb) + row(odd), home)
            # A local SONAME alias resolving outside the bundled plugin tree
            # must not be accepted just because the text path is local.
            xcb.unlink()
            xcb.symlink_to(outsider)
            with self.assertRaisesRegex(ValueError, 'outside bundled runtime'):
                probe.observed_qt_platform_plugins(row(xcb), home)

    def test_self_process_cannot_be_mislabelled_webots(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)/'webots'
            (home/'bin').mkdir(parents=True)
            (home/'resources').mkdir()
            (home/'resources/version.txt').write_text('R2025a\n')
            (home/'bin/webots-bin').write_bytes(b'not-qualified-webots')
            manifest = Path(directory)/'manifest.json'
            # The child must attest ITS OWN PID, not its parent. Linux
            # ptrace/Yama policy may forbid reading /proc/<parent>/exe,
            # which would obscure this exact negative with PermissionError.
            launcher = (
                'import os, runpy, sys\\n'
                'script, home, manifest = sys.argv[1:]\\n'
                "sys.argv = [script, '--runtime-home', home, '--pid', "
                "str(os.getpid()), '--manifest', manifest]\\n"
                "runpy.run_path(script, run_name='__main__')\\n"
            )
            cmd = [sys.executable, '-c', launcher,
                   str(Path(probe.__file__)), str(home), str(manifest)]
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

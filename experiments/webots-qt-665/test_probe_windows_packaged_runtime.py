import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import probe_windows_packaged_runtime as probe
from probe_windows_packaged_runtime import attest_modules, engine_environment, process_role, sha256, verify_package


class ProbeTests(unittest.TestCase):
    def test_corrected_pe_requires_independent_sha256_anchor(self):
        self.assertEqual(probe.QUALIFIED_WINDOWS_PE_SHA256,
                         '52b8c047047094c30f0cd358456ca5a18c73209457c2129991068f5825c8a06e')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / 'artifact'
            artifact.mkdir()
            installed = root / 'installed-webots-bin.exe'
            candidate = artifact / 'webots-bin.exe'
            candidate.write_bytes(b'wrong-but-internally-consistent PE')
            installed.write_bytes(candidate.read_bytes())
            digest = sha256(candidate)
            record = artifact / 'pe.sha256'
            record.write_text(digest + '  webots-bin.exe\\n')
            # A self-consistent forged archive and installed binary cannot
            # masquerade as the already-qualified genuine Windows engine.
            with self.assertRaisesRegex(ValueError, 'independently qualified'):
                probe.attest_qualified_pe(artifact, installed)
            record.write_text(probe.QUALIFIED_WINDOWS_PE_SHA256 + '  webots-bin.exe\\n')
            with self.assertRaisesRegex(ValueError, 'artifact bytes'):
                probe.attest_qualified_pe(artifact, installed)
            record.write_text(digest + '  webots-bin.exe\\n')
            # Synthetic positive exercises both actual file hashes without
            # pretending that synthetic bytes are a qualified production PE.
            with mock.patch.object(probe, 'QUALIFIED_WINDOWS_PE_SHA256', digest):
                self.assertEqual(probe.attest_qualified_pe(artifact, installed), digest)
                installed.write_bytes(b'other bytes')
                with self.assertRaisesRegex(ValueError, 'Installed Webots'):
                    probe.attest_qualified_pe(artifact, installed)
                installed.write_bytes(candidate.read_bytes())
                candidate.write_bytes(b'other bytes')
                with self.assertRaisesRegex(ValueError, 'artifact bytes'):
                    probe.attest_qualified_pe(artifact, installed)
                candidate.write_bytes(b'wrong-but-internally-consistent PE')
                record.write_text(digest + '  webots-bin.exe\\n' + digest + '  duplicate\\n')
                with self.assertRaisesRegex(ValueError, 'Malformed'):
                    probe.attest_qualified_pe(artifact, installed)

    def test_windows_module_provenance_is_independent_of_external_sdk(self):
        # These retained native identities must describe the same process
        # closure. The source SDK cannot authorize a different Qt/GCC/OpenAL
        # build merely by supplying matching bytes to Webots.
        import json
        historic = json.loads((Path(__file__).with_name('windows-startup-native.json')).read_text())
        observed = {
            **{name: row['sha256'] for name, row in
               historic['processes']['webots-bin.exe']['modules'].items()
               if name in probe.QUALIFIED_WINDOWS_MODULE_SHA256},
            'Controller.dll': historic['processes']['runtime']['modules']['Controller.dll']['sha256'],
        }
        self.assertEqual(observed, probe.QUALIFIED_WINDOWS_MODULE_SHA256)
        self.assertEqual(set(observed), {
            'Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Widgets.dll', 'libstdc++-6.dll',
            'libgcc_s_seh-1.dll', 'libwinpthread-1.dll', 'libopenal-1.dll',
            'qwindows.dll', 'Controller.dll'})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdk = root / 'sdk/mingw64/bin'
            sdk.mkdir(parents=True)
            installed = root / 'installed/Qt6Core.dll'
            installed.parent.mkdir()
            sdk_file = sdk / 'Qt6Core.dll'
            sdk_file.write_bytes(b'foreign-but-SDK-and-installed-identical')
            installed.write_bytes(sdk_file.read_bytes())
            # The pre-fix self-consistency check would pass both files.
            self.assertEqual(sha256(sdk_file), sha256(installed))
            with self.assertRaisesRegex(ValueError, 'qualified native startup'):
                probe.require_pinned_component('Qt6Core.dll', sdk_file)
            with self.assertRaisesRegex(ValueError, 'Unqualified Windows module'):
                probe.require_pinned_component('foreign.dll', sdk_file)
            # Explicit synthetic positive tests the mechanism, not the
            # authenticity of a real Windows native component.
            synthetic_hash = sha256(sdk_file)
            with mock.patch.dict(probe.QUALIFIED_WINDOWS_MODULE_SHA256,
                                 {'Qt6Core.dll': synthetic_hash}):
                self.assertEqual(probe.require_pinned_component('Qt6Core.dll', sdk_file),
                                 synthetic_hash)
                # The native module observer must still reject installed
                # bytes that differ from their pinned source.
                installed.write_bytes(b'tampered-installed-component')
                with self.assertRaisesRegex(ValueError, 'Wrong mapped bytes'):
                    probe.attest_modules([str(installed)],
                                         {'Qt6Core.dll': (installed, synthetic_hash)}, sdk)

    def test_engine_process_argv_must_match_real_classroom_launcher(self):
        # The retained genuine Windows process did forward the exact launch
        # flags, port and classroom world to webots-bin.exe.
        import json
        historic = json.loads((Path(__file__).with_name('windows-startup-native.json')).read_text())
        historic_argv = historic['processes']['webots-bin.exe']['command_line']
        self.assertEqual(historic_argv[1:], historic['command'][1:])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bin_dir = root / 'Webots installation/bin'
            bin_dir.mkdir(parents=True)
            launcher = bin_dir / 'webots.exe'
            engine = bin_dir / 'webots-bin.exe'
            launcher.write_bytes(b'launcher')
            engine.write_bytes(b'qualified-engine-fixture')
            world = root / 'classroom with spaces/worlds/crazyflie_runtime_v2.wbt'
            world.parent.mkdir(parents=True)
            world.write_text('untouched-world-fixture')
            flags = ['--stdout', '--stderr', '--batch', '--mode=fast',
                     '--port=59229', str(world)]
            expected = [str(launcher), *flags]
            self.assertIsNone(probe.attest_native_engine_argv(
                [str(engine), *flags], expected, engine))
            mutations = [
                [str(engine), *flags[:-1], str(root / 'other-world.wbt')],
                [str(engine), '--stdout', '--stderr', '--batch',
                 '--mode=fast', '--port=59230', str(world)],
                [str(engine), '--stdout', '--stderr', '--batch',
                 '--mode=fast', '--port=59229', str(world), str(world)],
                [str(engine), '--stdout', '--stderr', '--batch',
                 '--mode=fast', '--port=59229'],
                [str(engine), '--stdout', '--stderr', '--batch',
                 '--mode=fast', '--no-rendering', '--port=59229', str(world)],
            ]
            for candidate in mutations:
                with self.subTest(argv=candidate), self.assertRaisesRegex(
                        ValueError, 'differ from classroom launch'):
                    probe.attest_native_engine_argv(candidate, expected, engine)
            another = bin_dir / 'other-engine.exe'
            another.write_bytes(engine.read_bytes())
            with self.assertRaisesRegex(ValueError, 'argv executable'):
                probe.attest_native_engine_argv(
                    [str(another), *flags], expected, engine)
            with self.assertRaisesRegex(ValueError, 'argv executable'):
                probe.attest_native_engine_argv([], expected, engine)


    def test_evaluator_cannot_substitute_for_main_runtime(self):
        exe = 'crazyflie_runtime_v2.exe'
        self.assertEqual(process_role(exe, [exe]), 'runtime')
        self.assertEqual(process_role(exe, [exe, 'sequence-evaluator-v1']), 'sequence-evaluator')
        for args in ([], [exe, 'unknown'], [exe, 'sequence-evaluator-v1', 'extra']):
            with self.assertRaises(ValueError):
                process_role(exe, args)

    def test_real_mapped_path_and_bytes_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / 'installed/Qt6Core.dll'
            expected.parent.mkdir()
            expected.write_bytes(b'qualified')
            sdk = root / 'sdk/mingw64/bin'
            required = {expected.name: (expected, sha256(expected))}
            self.assertEqual(attest_modules([str(expected)], required, sdk)[expected.name]['sha256'], sha256(expected))
            with self.assertRaises(LookupError):
                attest_modules([], required, sdk)
            foreign = root / expected.name
            foreign.write_bytes(expected.read_bytes())
            with self.assertRaises(ValueError):
                attest_modules([str(foreign)], required, sdk)
            with self.assertRaises(ValueError):
                attest_modules([str(expected), str(foreign)], required, sdk)
            expected.write_bytes(b'tampered')
            with self.assertRaises(ValueError):
                attest_modules([str(expected)], required, sdk)

    def test_native_abi_family_location_rejects_unlisted_foreign_qt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / 'Webots'
            native = home / 'msys64/mingw64/bin'
            native.mkdir(parents=True)
            qt = native / 'Qt6Core.dll'
            qt.write_bytes(b'pinned-fixture')
            extra = native / 'Qt6Network.dll'
            extra.write_bytes(b'additional-runtime-module')
            windows = root / 'Windows/System32'
            windows.mkdir(parents=True)
            opengl = windows / 'opengl32.dll'
            opengl.write_bytes(b'Windows OpenGL system module')
            # Without a verified digest, a known Qt DLL name is not evidence.
            with self.assertRaisesRegex(ValueError, 'bytes differ from qualified reference'):
                probe.attest_native_abi_family_locations([str(qt)], home)
            with mock.patch.dict(probe.QUALIFIED_WINDOWS_MODULE_SHA256,
                                 {'Qt6Core.dll': sha256(qt)}):
                family = probe.attest_native_abi_family_locations(
                    [str(qt), str(extra), str(opengl)], home)
                self.assertEqual(set(family), {'qt6core.dll', 'qt6network.dll'})
                self.assertTrue(family['qt6core.dll']['qualified_digest_verified'])
                self.assertFalse(family['qt6network.dll']['qualified_digest_verified'])
            foreign = root / 'Another Qt/bin/Qt6Network.dll'
            foreign.parent.mkdir(parents=True)
            foreign.write_bytes(extra.read_bytes())
            with self.assertRaisesRegex(ValueError, 'outside pinned Webots runtime'):
                probe.attest_native_abi_family_locations([str(foreign)], home)
            alternate = home / 'other/Qt6Network.dll'
            alternate.parent.mkdir()
            alternate.write_bytes(extra.read_bytes())
            with self.assertRaisesRegex(ValueError, 'Multiple native ABI-family'):
                probe.attest_native_abi_family_locations([str(extra), str(alternate)], home)

    def test_external_sdk_rejected_even_for_other_dependency(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdk = root / 'sdk/mingw64/bin'
            dll = sdk / 'libextra.dll'
            dll.parent.mkdir(parents=True)
            dll.write_bytes(b'sdk')
            with self.assertRaises(ValueError):
                attest_modules([str(dll)], {}, sdk)

    def test_ambient_sdk_and_qt_lookup_removed(self):
        root = Path('/installed')
        env = engine_environment(root, {'SystemRoot': '/Windows', 'Path': '/SDK/bin',
            'QT_PLUGIN_PATH': '/SDK/plugins', 'QT_QPA_PLATFORM': 'offscreen',
            'QML_IMPORT_PATH': '/SDK/qml', 'WEBOTS_CONTROLLER_URL': 'ipc://65535',
            'PYTHONPATH': '/ambient', 'QT665_MINGW_BIN': '/SDK/bin'})
        self.assertNotIn('/SDK', env['PATH'])
        for key in ('QT_PLUGIN_PATH', 'QT_QPA_PLATFORM', 'QML_IMPORT_PATH',
                    'WEBOTS_CONTROLLER_URL', 'PYTHONPATH', 'QT665_MINGW_BIN'):
            self.assertNotIn(key, env)
        self.assertEqual(env['WEBOTS_HOME'], str(root))

    def test_native_snapshot_rejects_duplicate_and_stale_roles(self):
        expected = {'webots-bin.exe', 'runtime', 'sequence-evaluator'}
        full = probe.unique_native_snapshot([
            ('webots-bin.exe', {'pid': 1}), ('runtime', {'pid': 2}),
            ('sequence-evaluator', {'pid': 3})])
        self.assertEqual(set(full), expected)
        # A later poll cannot inherit a role that was present in an earlier one.
        partial = probe.unique_native_snapshot([
            ('webots-bin.exe', {'pid': 1}), ('runtime', {'pid': 2})])
        self.assertNotIn('sequence-evaluator', partial)
        self.assertEqual(set(full), expected)
        with self.assertRaisesRegex(ValueError, 'Duplicate native process role: runtime'):
            probe.unique_native_snapshot([
                ('runtime', {'pid': 2}), ('runtime', {'pid': 4})])

    def test_two_second_startup_requires_same_process_generation(self):
        initial = {
            'webots-bin.exe': {'pid': 1, 'create_time': 10.0},
            'runtime': {'pid': 2, 'create_time': 11.0},
            'sequence-evaluator': {'pid': 3, 'create_time': 12.0},
        }
        advance = probe.advance_native_stability
        identity, start = advance(True, initial, None, None, 100.0)
        self.assertEqual(start, 100.0)
        identity, start = advance(True, dict(reversed(list(initial.items()))),
                                  identity, start, 101.9)
        self.assertEqual(start, 100.0)
        # All roles can remain present while a controller exits and respawns.
        changed = {**initial, 'sequence-evaluator': {'pid': 4, 'create_time': 12.5}}
        identity, start = advance(True, changed, identity, start, 102.1)
        self.assertEqual(start, 102.1)
        # PID reuse also resets continuity: creation time is part of identity.
        reused = {**initial, 'sequence-evaluator': {'pid': 4, 'create_time': 13.0}}
        identity, start = advance(True, reused, identity, start, 103.0)
        self.assertEqual(start, 103.0)
        identity, start = advance(False, {}, identity, start, 103.1)
        self.assertIsNone(identity)
        self.assertIsNone(start)
        identity, start = advance(True, initial, identity, start, 104.0)
        self.assertEqual(start, 104.0)

    def test_historical_ready_cannot_qualify_replacement_after_gap(self):
        initial = {
            'webots-bin.exe': {'pid': 1, 'create_time': 10.0},
            'runtime': {'pid': 2, 'create_time': 11.0},
            'sequence-evaluator': {'pid': 3, 'create_time': 12.0},
        }
        frozen = probe.require_unchanged_ready_generation(initial, None)
        # A temporary incomplete poll should invalidate the 2 s continuous
        # window but cannot authorize a different process with old READY logs.
        _ignored_identity, _ignored_start = probe.advance_native_stability(
            False, {}, frozen, 100.0, 101.0)
        self.assertIsNone(_ignored_identity)
        self.assertEqual(
            probe.require_unchanged_ready_generation(
                dict(reversed(list(initial.items()))), frozen), frozen)
        for replaced in (
            {**initial, 'runtime': {'pid': 4, 'create_time': 11.5}},
            {**initial, 'runtime': {'pid': 2, 'create_time': 11.5}},
            {**initial, 'webots-bin.exe': {'pid': 5, 'create_time': 10.5}},
            {**initial, 'sequence-evaluator': {'pid': 6, 'create_time': 12.5}},
        ):
            with self.subTest(replaced=replaced), self.assertRaisesRegex(
                    RuntimeError, 'stale READY'):
                probe.require_unchanged_ready_generation(replaced, frozen)


    def test_package_tamper_extra_missing_and_escape_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'package'
            (root / 'worlds').mkdir(parents=True)
            world = root / 'worlds/crazyflie_runtime_v2.wbt'
            world.write_text('DEF WEBEEBLOCKS_CLASSROOM_START_WORLD WorldInfo {\n}\n')
            manifest = root / 'MANIFEST.sha256'
            manifest.write_text(f'{sha256(world)}  worlds/crazyflie_runtime_v2.wbt\n')

            self.assertEqual(probe.QUALIFIED_CLASSROOM_MANIFEST_SHA256,
                             '000ac88a8f56e0337d9243c13faa226fcc2c8bc434b445899013d7df8ba8efc4')
            # The content of a self-signed fixture must NOT be accepted by the
            # production default; tests explicitly override only this anchor.
            with self.assertRaisesRegex(ValueError, 'canonical'):
                verify_package(root)

            def fixture_verify():
                with mock.patch.object(probe, 'QUALIFIED_CLASSROOM_MANIFEST_SHA256', sha256(manifest)):
                    return verify_package(root)

            # Rewriting a classroom world AND recomputing its own manifest is
            # insufficient to attest the unchanged canonical package.
            world.write_text('DEF WEBEEBLOCKS_CLASSROOM_START_WORLD WorldInfo {\n}\n# altered\n')
            manifest.write_text(f'{sha256(world)}  worlds/crazyflie_runtime_v2.wbt\n')
            with self.assertRaisesRegex(ValueError, 'canonical'):
                verify_package(root)
            world.write_text('DEF WEBEEBLOCKS_CLASSROOM_START_WORLD WorldInfo {\n}\n')
            manifest.write_text(f'{sha256(world)}  worlds/crazyflie_runtime_v2.wbt\n')
            self.assertEqual(fixture_verify()['files'], 1)
            extra = root / 'foreign.dll'
            extra.write_bytes(b'extra')
            with self.assertRaises(ValueError):
                fixture_verify()
            extra.unlink()
            world.write_text('tampered')
            with self.assertRaises(ValueError):
                fixture_verify()
            world.unlink()
            with self.assertRaises(FileNotFoundError):
                fixture_verify()
            foreign = root.parent / 'outside'
            foreign.write_bytes(b'outside')
            manifest.write_text(f'{sha256(foreign)}  ../outside\n')
            with self.assertRaises(ValueError):
                fixture_verify()


if __name__ == '__main__':
    unittest.main()

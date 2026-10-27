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

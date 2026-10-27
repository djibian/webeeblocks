import os
from pathlib import Path
import tempfile
import unittest

from probe_windows_packaged_runtime import attest_modules, engine_environment, process_role, sha256, verify_package


class ProbeTests(unittest.TestCase):
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

    def test_package_tamper_extra_missing_and_escape_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'package'
            (root / 'worlds').mkdir(parents=True)
            world = root / 'worlds/crazyflie_runtime_v2.wbt'
            world.write_text('DEF WEBEEBLOCKS_CLASSROOM_START_WORLD WorldInfo {\n}\n')
            manifest = root / 'MANIFEST.sha256'
            manifest.write_text(f'{sha256(world)}  worlds/crazyflie_runtime_v2.wbt\n')
            self.assertEqual(verify_package(root)['files'], 1)
            extra = root / 'foreign.dll'
            extra.write_bytes(b'extra')
            with self.assertRaises(ValueError):
                verify_package(root)
            extra.unlink()
            world.write_text('tampered')
            with self.assertRaises(ValueError):
                verify_package(root)
            world.unlink()
            with self.assertRaises(FileNotFoundError):
                verify_package(root)
            foreign = root.parent / 'outside'
            foreign.write_bytes(b'outside')
            manifest.write_text(f'{sha256(foreign)}  ../outside\n')
            with self.assertRaises(ValueError):
                verify_package(root)


if __name__ == '__main__':
    unittest.main()

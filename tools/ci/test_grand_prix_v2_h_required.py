"""Required CI R2025a H-ray campaign wiring; host tests prove no native PASS."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from tools.ci import run_grand_prix_v2_h_native as h_runner


class RequiredNativeHRayTests(unittest.TestCase):
    def test_required_native_h_mixed_gd_failure_refutes_geometry_digest(self):
        # A headless fake can only prove orchestration, never H sensor success.
        # Native GD H-ray acquisition is now a mandatory separate R2025a
        # witness after all legacy probes and four real contact configurations.
        from tools.ci import run_grand_prix_u_geometry as geometry
        from tools.ci import run_grand_prix_v2_contact_native as contact
        from tools.ci import run_grand_prix_v2_h_native as h_probe
        import sys
        from types import SimpleNamespace
        with TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / 'webots'
            (home / 'resources').mkdir(parents=True)
            (home / 'resources/version.txt').write_text('R2025a\n')
            (home / 'bin').mkdir()
            (home / 'bin/webots-bin').write_bytes(b'host fake, not Webots')
            out = root / 'evidence'
            deadline = Mock()
            with patch.object(geometry, 'OUT', out), \
                 patch.object(geometry, 'cases', return_value=[]), \
                 patch.dict(sys.modules, {'run_grand_prix_u_deadline_native':
                            SimpleNamespace(run_native=deadline)}), \
                 patch.object(contact, 'native_run') as contacts, \
                 patch.object(h_probe, 'native_run', side_effect=RuntimeError(
                     'native H ray missing')) as rays:
                with self.assertRaisesRegex(RuntimeError, 'native H ray missing'):
                    geometry.run_native(home)
            deadline.assert_called_once_with(home)
            contacts.assert_called_once_with(home, contact.DEFAULT_INDICES)
            rays.assert_called_once_with(home, (5,), output_root=out / 'route-h-native')
            self.assertFalse((out / 'sha256.json').exists())

    def test_h_native_ci_artifact_scope_refuses_zero_exit_without_evidence(self):
        # Probe execution isolated per invocation; a zero process exit
        # without exact native JSON is not a PASS, even in the CI artifact.
        with TemporaryDirectory() as temp:
            root = Path(temp)
            home = root / 'webots'
            (home / 'resources').mkdir(parents=True)
            (home / 'resources/version.txt').write_text('R2025a\n')
            (home / 'webots').write_text('stub')
            (home / 'webots').chmod(0o755)
            evidence = root / 'geometry' / 'route-h-native'
            with patch.object(h_runner.subprocess, 'Popen') as spawned:
                spawned.return_value.wait.return_value = 0
                spawned.return_value.poll.return_value = 0
                with self.assertRaisesRegex(RuntimeError, 'no native H ray evidence'):
                    h_runner.native_run(home, (5,), output_root=evidence)
            invocations = list(evidence.glob('invocation-*'))
            self.assertEqual(len(invocations), 1)
            self.assertFalse(list(evidence.rglob('summary.json')))
            self.assertTrue(list(evidence.rglob('native.log')))



if __name__ == "__main__":
    unittest.main()

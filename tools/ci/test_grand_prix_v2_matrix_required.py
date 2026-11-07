"""Host-only routing checks for mandatory all-12 native L/H matrix.

These tests never claim any real Webots result: missing native raw files fail.
"""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools.ci import run_grand_prix_u_geometry as geometry
from tools.ci import run_grand_prix_v2_contact_native as contact
from tools.ci import run_grand_prix_v2_h_native as h_probe
from tools.grand_prix.route_courses_v2 import reference_course


class FullNativeMatrixRequiredTests(unittest.TestCase):
    def _fake_producer(self, root, indices, *, omit_last=False):
        directory = root / 'invocation-host-mock'
        directory.mkdir(parents=True)
        records = []
        for order, index in enumerate(indices[:-1] if omit_last else indices):
            identifier = reference_course(index).identifier
            relative = f'{order:02d}-{identifier}/native.json'
            path = directory / relative
            path.parent.mkdir()
            path.write_bytes(b'host fixture: NOT real native evidence')
            records.append(dict(configuration=identifier,
                                evidence_file=relative,
                                evidence_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        (directory / 'summary.json').write_text(json.dumps(dict(
            webots='R2025a', results=records)) + '\n')

    def _run(self, *, incomplete_h=False, fail_l=False):
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            home = base / 'webots'
            (home / 'resources').mkdir(parents=True)
            (home / 'resources/version.txt').write_text('R2025a\n')
            out = base / 'geometry'
            lroot = out / 'route-contact-native'
            hroot = out / 'route-h-native'
            def fake_l(home_arg, indices):
                if fail_l:
                    raise RuntimeError('native L refusal')
                self.assertEqual(indices, tuple(range(12)))
                self._fake_producer(lroot, indices)
            def fake_h(home_arg, indices, *, output_root):
                self.assertEqual(indices, tuple(range(12)))
                self.assertEqual(output_root, hroot)
                self._fake_producer(hroot, indices, omit_last=incomplete_h)
            with patch.object(geometry, 'OUT', out), \
                 patch.object(contact, 'OUT', lroot), \
                 patch.object(contact, 'native_run', side_effect=fake_l) as lcall, \
                 patch.object(h_probe, 'native_run', side_effect=fake_h) as hcall:
                if incomplete_h:
                    with self.assertRaisesRegex(RuntimeError, 'incomplete full native matrix'):
                        geometry.run_full_route_matrix_native(home)
                    self.assertFalse((out / 'sha256.json').exists())
                elif fail_l:
                    with self.assertRaisesRegex(RuntimeError, 'native L refusal'):
                        geometry.run_full_route_matrix_native(home)
                    hcall.assert_not_called()
                    self.assertFalse((out / 'sha256.json').exists())
                else:
                    geometry.run_full_route_matrix_native(home)
                    self.assertEqual(len(json.loads((out / 'sha256.json').read_text())), 26)
                lcall.assert_called_once()
                if not fail_l:
                    hcall.assert_called_once()

    def test_exact_all_twelve_and_digest_manifest(self):
        self._run()

    def test_partial_h_evidence_refutes_whole_job(self):
        self._run(incomplete_h=True)

    def test_l_refutation_prevents_h_or_positive_digest(self):
        self._run(fail_l=True)

    def test_wrong_native_version_fails_closed(self):
        with TemporaryDirectory() as temporary:
            home = Path(temporary) / 'webots'
            (home / 'resources').mkdir(parents=True)
            (home / 'resources/version.txt').write_text('R2024b\n')
            with self.assertRaisesRegex(RuntimeError, 'R2025a'):
                geometry.run_full_route_matrix_native(home)


if __name__ == '__main__':
    unittest.main()

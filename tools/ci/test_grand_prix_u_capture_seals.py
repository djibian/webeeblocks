"""Offline falsifiers for native evidence sealing; no Webots is required."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from grand_prix_u_capture_seals import CaptureSealError, verify_new_capture_seals


class SealAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root / 'gp-u-v1-L2000-s1-camera-tracking-test'
        self.folder.mkdir()
        self.file = self.folder / 'webots.log'
        self.file.write_text('WEBEEBLOCKS_RUNTIME_V2 READY\n')
        self.seal()

    def seal(self):
        payload = self.file.read_bytes()
        (self.folder / 'sha256.json').write_text(json.dumps({
            'webots.log': hashlib.sha256(payload).hexdigest()}))

    def test_matching_evidence_passes(self):
        self.assertEqual(verify_new_capture_seals(self.root, set()), 1)

    def test_sealed_earlier_invocation_not_rescanned(self):
        with self.assertRaisesRegex(CaptureSealError, 'no new'):
            verify_new_capture_seals(self.root, {self.folder.name})

    def test_late_appended_crash_refused(self):
        self.file.write_text(self.file.read_text() + 'Segmentation fault (core dumped)\n')
        with self.assertRaisesRegex(CaptureSealError, 'post-seal mutation'):
            verify_new_capture_seals(self.root, set())

    def test_unsealed_extra_file_refused(self):
        (self.folder / 'native_trace.csv').write_text('late')
        with self.assertRaisesRegex(CaptureSealError, 'unsealed'):
            verify_new_capture_seals(self.root, set())

    def test_missing_file_refused(self):
        self.file.unlink()
        with self.assertRaisesRegex(CaptureSealError, 'missing'):
            verify_new_capture_seals(self.root, set())

    def test_unreadable_manifest_refused(self):
        (self.folder / 'sha256.json').write_text('garbled')
        with self.assertRaisesRegex(CaptureSealError, 'unreadable'):
            verify_new_capture_seals(self.root, set())

    def test_symlink_refused(self):
        other = self.root / 'target'
        other.write_bytes(self.file.read_bytes())
        self.file.unlink()
        self.file.symlink_to(other)
        with self.assertRaisesRegex(CaptureSealError, 'non-regular'):
            verify_new_capture_seals(self.root, set())


if __name__ == '__main__':
    unittest.main()

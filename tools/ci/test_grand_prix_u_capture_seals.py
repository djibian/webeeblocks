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
        self.assertEqual(verify_new_capture_seals(self.root, set(), {self.folder.name}), 1)

    def test_sealed_earlier_invocation_not_rescanned(self):
        with self.assertRaisesRegex(CaptureSealError, 'missing or inconsistent'):
            verify_new_capture_seals(self.root, {self.folder.name}, set())

    def test_late_appended_crash_refused(self):
        self.file.write_text(self.file.read_text() + 'Segmentation fault (core dumped)\n')
        with self.assertRaisesRegex(CaptureSealError, 'post-seal mutation'):
            verify_new_capture_seals(self.root, set(), {self.folder.name})

    def test_unsealed_extra_file_refused(self):
        (self.folder / 'native_trace.csv').write_text('late')
        with self.assertRaisesRegex(CaptureSealError, 'unsealed'):
            verify_new_capture_seals(self.root, set(), {self.folder.name})

    def test_missing_file_refused(self):
        self.file.unlink()
        with self.assertRaisesRegex(CaptureSealError, 'missing'):
            verify_new_capture_seals(self.root, set(), {self.folder.name})

    def test_unreadable_manifest_refused(self):
        (self.folder / 'sha256.json').write_text('garbled')
        with self.assertRaisesRegex(CaptureSealError, 'unreadable'):
            verify_new_capture_seals(self.root, set(), {self.folder.name})

    def test_symlink_refused(self):
        other = self.root / 'target'
        other.write_bytes(self.file.read_bytes())
        self.file.unlink()
        self.file.symlink_to(other)
        with self.assertRaisesRegex(CaptureSealError, 'non-regular'):
            verify_new_capture_seals(self.root, set(), {self.folder.name})


    def test_deleted_entire_trial_refused_among_two(self):
        second = self.root / 'gp-u-v1-L2000-s2-witness'
        second.mkdir()
        (second / 'webots.log').write_bytes(self.file.read_bytes())
        (second / 'sha256.json').write_text((self.folder / 'sha256.json').read_text())
        self.file.unlink()
        (self.folder / 'sha256.json').unlink()
        self.folder.rmdir()
        with self.assertRaisesRegex(CaptureSealError, 'missing or unexpected native trial'):
            verify_new_capture_seals(self.root, set(), {self.folder.name, second.name})

    def test_renamed_entire_trial_refused(self):
        self.folder.rename(self.root / 'gp-u-v1-L2000-s1-renamed')
        with self.assertRaisesRegex(CaptureSealError, 'missing or unexpected native trial'):
            verify_new_capture_seals(self.root, set(), {self.folder.name})

    def test_directory_symlink_refused(self):
        source = self.root / 'independent-source'
        self.folder.rename(source)
        self.folder.symlink_to(source, target_is_directory=True)
        with self.assertRaisesRegex(CaptureSealError, 'non-directory or symlink'):
            verify_new_capture_seals(self.root, set(), {self.folder.name})

    def test_broken_directory_symlink_refused(self):
        self.file.unlink()
        (self.folder / 'sha256.json').unlink()
        self.folder.rmdir()
        self.folder.symlink_to(self.root / 'absent', target_is_directory=True)
        with self.assertRaisesRegex(CaptureSealError, 'non-directory or symlink'):
            verify_new_capture_seals(self.root, set(), {self.folder.name})

    def test_duplicate_manifest_key_refused(self):
        correct = hashlib.sha256(self.file.read_bytes()).hexdigest()
        (self.folder / 'sha256.json').write_text(
            '{"webots.log":"' + '0' * 64 + '","webots.log":"' + correct + '"}')
        with self.assertRaisesRegex(CaptureSealError, 'duplicate JSON manifest key'):
            verify_new_capture_seals(self.root, set(), {self.folder.name})

    def test_multiple_valid_trial_directories_pass(self):
        second = self.root / 'gp-u-v1-L2000-s2-witness'
        second.mkdir()
        (second / 'webots.log').write_bytes(self.file.read_bytes())
        (second / 'sha256.json').write_text((self.folder / 'sha256.json').read_text())
        self.assertEqual(verify_new_capture_seals(
            self.root, set(), {self.folder.name, second.name}), 2)

    def test_unregistered_extra_trial_refused(self):
        (self.root / 'gp-u-v1-unexpected').mkdir()
        with self.assertRaisesRegex(CaptureSealError, 'missing or unexpected native trial'):
            verify_new_capture_seals(self.root, set(), {self.folder.name})

    def test_missing_expected_trial_inventory_refused(self):
        with self.assertRaisesRegex(CaptureSealError, 'missing or inconsistent'):
            verify_new_capture_seals(self.root, set(), set())



if __name__ == '__main__':
    unittest.main()

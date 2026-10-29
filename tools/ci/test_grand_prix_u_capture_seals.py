"""Offline falsifiers for native evidence sealing; no Webots is required."""
import hashlib
import json
from pathlib import Path
import signal
import tempfile
import unittest

from grand_prix_u_capture_seals import CaptureSealError, verify_new_capture_seals
from grand_prix_u_log_capture import require_no_terminal_crash, require_no_fatal_exit_statuses
from types import SimpleNamespace


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

    def test_post_result_fatal_abort_is_refused(self):
        # The completed negative result must not excuse a late glibc abort.
        fatal = (
            'Segmentation fault (core dumped)',
            'Traceback (most recent call last)',
            'Aborted (core dumped)',
            'malloc(): corrupted top size',
            'free(): double free detected in tcache 2',
            'double free or corruption (out)',
            'corrupted size vs. prev_size',
            '*** stack smashing detected ***',
            'Fatal glibc error: malloc assertion failure',
            'AddressSanitizer:DEADLYSIGNAL',
        )
        for message in fatal:
            with self.subTest(message=message):
                self.file.write_text('GP_U_RESULT valid-negative\n' + message + '\n')
                with self.assertRaisesRegex(RuntimeError, 'native crash'):
                    require_no_terminal_crash(self.file)

    def test_planned_shutdown_warning_not_misclassified(self):
        # R2025a can report this warning after intentional harness SIGTERM.
        self.file.write_text(
            "INFO: grand_prix_u_evaluator: Terminating.\n"
            "WARNING: 'grand_prix_u_evaluator' controller crashed.\n"
            'Warning: The X11 connection broke (error 1).\n')
        require_no_terminal_crash(self.file)

    def test_fatal_native_direct_exit_is_refused_even_without_log_message(self):
        # Direct ELF: negative signal. xvfb-run/shell wrappers: 128 + signal.
        fatal = [int(getattr(signal, name)) for name in (
            'SIGABRT', 'SIGBUS', 'SIGFPE', 'SIGILL', 'SIGSEGV')
            if hasattr(signal, name)]
        for number in fatal:
            for code in (-number, 128 + number):
                with self.subTest(code=code):
                    with self.assertRaisesRegex(RuntimeError, 'fatal native direct-child'):
                        require_no_fatal_exit_statuses([SimpleNamespace(returncode=code)])
        for code in (0, 1, -15, -9, 143, 137):
            with self.subTest(nonfatal_or_harness_code=code):
                require_no_fatal_exit_statuses([SimpleNamespace(returncode=code)])
        with self.assertRaisesRegex(RuntimeError, 'status missing'):
            require_no_fatal_exit_statuses([SimpleNamespace(returncode=None)])


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

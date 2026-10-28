#!/usr/bin/env python3
"""Host-only adversarial contracts for the software-rendering APT isolation."""
import tempfile
import unittest
from pathlib import Path
from prepare_webots_apt import prepare


class AptSourceIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'sources.list.d').mkdir()
        self.main = self.root / 'sources.list'
        self.main.write_text('deb http://archive.ubuntu.com/ubuntu jammy main\n')
        self.cuda = self.root / 'sources.list.d/cuda.list'
        self.cuda.write_text('deb [signed-by=/etc/apt/keyrings/cuda.gpg] https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/ /\n')

    def test_exact_cuda_removed_and_other_sources_byte_identical(self):
        before = self.main.read_bytes()
        changes = prepare(self.root, software_rendering=True)
        self.assertEqual(len(changes), 1)
        self.assertEqual(self.main.read_bytes(), before)
        self.assertTrue(self.cuda.read_text().startswith('# WEBEEBLOCKS_SOFTWARE_RENDERING_ONLY deb '))
        self.assertEqual(prepare(self.root, software_rendering=True), [])

    def test_no_gpu_flag_refuses_without_modification(self):
        before = self.cuda.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'software rendering'):
            prepare(self.root, software_rendering=False)
        self.assertEqual(self.cuda.read_bytes(), before)

    def test_unrecognized_cuda_entry_refuses_atomically(self):
        unrelated = self.root / 'sources.list.d/z-ambiguous.list'
        unrelated.write_text('deb https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/ /\n')
        before = self.cuda.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'unexpected NVIDIA'):
            prepare(self.root, software_rendering=True)
        self.assertEqual(self.cuda.read_bytes(), before)

    def test_deb822_refuses_without_modification(self):
        deb822 = self.root / 'sources.list.d/cuda.sources'
        deb822.write_text('Types: deb\nURIs: https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/\nSuites: /\n')
        before = self.cuda.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'Deb822'):
            prepare(self.root, software_rendering=True)
        self.assertEqual(self.cuda.read_bytes(), before)

    def test_preserves_mixed_list_entries(self):
        self.cuda.write_text('deb http://archive.ubuntu.com/ubuntu jammy main\n'
            'deb https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/ /\n'
            'deb https://deb.debian.org/debian stable main\n')
        prepare(self.root, software_rendering=True)
        text = self.cuda.read_text()
        self.assertIn('deb http://archive.ubuntu.com/ubuntu jammy main\n', text)
        self.assertIn('deb https://deb.debian.org/debian stable main\n', text)

    def test_commented_source_is_noop(self):
        self.cuda.write_text('# deb https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/ /\n')
        self.assertEqual(prepare(self.root, software_rendering=True), [])


if __name__ == '__main__':
    unittest.main()

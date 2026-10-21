import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import zipfile

from support import seal


class SealTests(unittest.TestCase):
    def test_reopened_archive_exact_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'evidence'
            root.mkdir()
            (root / 'native.log').write_text('fixture signal 11\n')
            dest = Path(tmp) / 'archive.zip'
            self.assertEqual(len(seal(root, dest)), 64)
            with zipfile.ZipFile(dest) as z:
                self.assertEqual(set(z.namelist()), {'native.log', 'manifest.json'})
                self.assertEqual(z.read('native.log'), b'fixture signal 11\n')

    def test_late_writer_content_or_inventory_prevents_publication(self):
        for mutation in ('content', 'inventory'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / 'evidence'
                root.mkdir()
                (root / 'native.log').write_text('initial\n')
                dest = Path(tmp) / 'archive.zip'
                original = zipfile.ZipFile.write

                def racing_write(archive, filename, *args, **kwargs):
                    result = original(archive, filename, *args, **kwargs)
                    if Path(filename).name == 'native.log':
                        (root / ('native.log' if mutation == 'content' else 'late.log')).write_text('late\n')
                    return result

                with patch.object(zipfile.ZipFile, 'write', racing_write), self.assertRaises(ValueError):
                    seal(root, dest)
                self.assertFalse(dest.exists())
                self.assertFalse(dest.with_suffix('.zip.partial').exists())

    def test_existing_archive_and_symlink_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'evidence'
            root.mkdir()
            dest = Path(tmp) / 'archive.zip'
            dest.write_bytes(b'prior evidence')
            with self.assertRaises(ValueError):
                seal(root, dest)
            self.assertEqual(dest.read_bytes(), b'prior evidence')
            dest.unlink()
            (root / 'link').symlink_to('/etc/os-release')
            with self.assertRaises(ValueError):
                seal(root, dest)
            self.assertFalse(dest.exists())


if __name__ == '__main__':
    unittest.main()

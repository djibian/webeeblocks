"""No-Webots unit tests for the historical Linux U teacher launcher."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.grand_prix import launch_linux as launcher


class LinuxLauncherTests(unittest.TestCase):
    def test_world_is_reproducible_and_uses_real_robot_window(self):
        for seed in (0, 1, 4, 65535):
            text = launcher.render(seed)
            self.assertEqual(text, launcher.render(seed))
            self.assertEqual(text.count('EXTERNPROTO "webots://'), 4)
            self.assertNotIn(launcher.PREFIX, text)
            self.assertIn('window "grand_prix_u"', text)
            self.assertIn('controller "grand_prix_u_evaluator"', text)
            self.assertIn('basicTimeStep 8', text)
        for seed in (-1, 65536, True):
            with self.assertRaises(ValueError):
                launcher.render(seed)

    def test_world_never_overwrites_edits_or_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'teacher.wbt'
            launcher.create_once(path, 'original')
            launcher.create_once(path, 'original')
            with self.assertRaises(RuntimeError):
                launcher.create_once(path, 'changed')
            self.assertEqual(path.read_text(), 'original')
            link = Path(tmp)/'symlink'
            link.symlink_to(path)
            with self.assertRaises(RuntimeError):
                launcher.create_once(link, 'original')

    def test_check_only_does_not_build_or_start_webots(self):
        with mock.patch.object(launcher, 'find_home', return_value=Path('/fake')), \
             mock.patch.object(launcher, 'verify_install', return_value=Path('/fake/webots')), \
             mock.patch.object(launcher, 'world_for') as world, \
             mock.patch.object(launcher.subprocess, 'run') as run:
            self.assertEqual(launcher.main(['--seed', '4', '--check-only']), 0)
            self.assertEqual(launcher.main(['--seed', '65536', '--check-only']), 1)
            world.assert_not_called()
            run.assert_not_called()

    def test_reject_wrong_installed_webots_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home/'resources').mkdir()
            (home/'resources/version.txt').write_text('R2025b')
            with self.assertRaisesRegex(RuntimeError, 'R2025a requis'):
                launcher.verify_install(home)


if __name__ == '__main__':
    unittest.main()

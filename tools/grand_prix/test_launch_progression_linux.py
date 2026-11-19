"""Verify the host's world/Robot Window binding and project lifetime."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.grand_prix import launch_progression_linux as launcher
from tools.grand_prix.course_active_world_v2 import active_course_world
from tools.grand_prix.progression_courses import progression_course


class ProgressionLaunchTests(unittest.TestCase):
    def test_each_active_lesson_binds_its_scene_to_the_shared_page(self):
        for activity in (1, 2, 3):
            with self.subTest(activity=activity), tempfile.TemporaryDirectory() as temp:
                project = Path(temp)
                world = launcher.prepare_lesson_project(project, activity)
                self.assertEqual(world.relative_to(project).as_posix(),
                                 f'worlds/grand_prix_progression_a{activity}.wbt')
                self.assertEqual(world.read_text(), active_course_world(progression_course(activity)))
                self.assertTrue(world.with_name('.' + world.stem + '.wbproj').is_file())
                windows = project / 'plugins/robot_windows'
                selected = windows / launcher.ROBOT_WINDOW
                page = (selected / (launcher.ROBOT_WINDOW + '.html')).read_text()
                self.assertEqual(page.count(f'data-progression-activity="{activity}"'), 1)
                self.assertLess(page.index(launcher.PROFILES), page.index('src="setup.js"'))
                self.assertTrue((windows / launcher.PROFILES).is_file())
                self.assertEqual((selected / 'setup.js').resolve(),
                                 launcher.ROOT / 'plugins/robot_windows' / launcher.ROBOT_WINDOW / 'setup.js')
                self.assertIn('DEF GP_ROUTE_EVALUATOR Robot', world.read_text())

    def test_unknown_activity_refuses_before_writing_a_project(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            with self.assertRaises(ValueError):
                launcher.prepare_lesson_project(project, 8)
            self.assertEqual(list(project.iterdir()), [])

    def test_normal_entry_point_opens_and_retires_its_project(self):
        launched = []
        home = Path('/webots/R2025a')

        def read_at_launch(prepared_home, world, env, *, mode):
            self.assertEqual((prepared_home, mode), (home, 'realtime'))
            self.assertEqual(env, {'WEBOTS_HOME': str(home)})
            self.assertTrue(world.is_file())
            launched.append(world)
            return subprocess.CompletedProcess([], 0)

        with (patch.dict(launcher.os.environ, {'DISPLAY': ':0'}),
              patch.object(launcher, 'webots_home', return_value=home),
              patch.object(launcher, 'prepare_route_native', return_value={'WEBOTS_HOME': str(home)}),
              patch.object(launcher, 'launch_graphical', side_effect=read_at_launch)):
            self.assertEqual(launcher.main(['--activity', '3']), 0)
        self.assertEqual(len(launched), 1)
        self.assertFalse(launched[0].parents[1].exists())


if __name__ == '__main__':
    unittest.main()

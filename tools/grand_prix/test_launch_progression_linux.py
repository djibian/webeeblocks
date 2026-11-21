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
        for activity in launcher.active_progression_activities():
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
                # The selected student page must keep the existing shared
                # edit, native execution, failure, stop/reset and file controls.
                # These are binding checks, not a GUI or physical PASS.
                for button in ('projectActivity', 'projectOpen', 'projectSaveAs',
                               'projectSave', 'resetSimulation', 'submit',
                               'stepMode', 'stepNext', 'stepContinue',
                               'runtimeState', 'runtimeDetail'):
                    with self.subTest(activity=activity, button=button):
                        self.assertIn(f'id="{button}"', page)
                self.assertIn('../blockly_v2/project_ui.js', page)
                self.assertIn('../blockly/webeeblocks/runtime_outcome.js', page)
                self.assertEqual((selected / 'setup.js').resolve(),
                                 launcher.ROOT / 'plugins/robot_windows' / launcher.ROBOT_WINDOW / 'setup.js')
                self.assertIn('DEF GP_ROUTE_EVALUATOR Robot', world.read_text())

    def test_variants_share_one_profile_and_project_identity_per_lesson(self):
        for activity, count in ((4, 3), (5, 5), (6, 5), (7, 7)):
            first_page = None
            for variant in range(1, count + 1):
                with self.subTest(activity=activity, variant=variant), tempfile.TemporaryDirectory() as temp:
                    project = Path(temp)
                    if variant not in launcher.admitted_variants(activity):
                        with self.assertRaises(ValueError):
                            launcher.prepare_lesson_project(project, activity, variant)
                        self.assertEqual(list(project.iterdir()), [])
                        continue
                    world = launcher.prepare_lesson_project(project, activity, variant)
                    self.assertEqual(world.name, f'grand_prix_progression_a{activity}.wbt')
                    course = progression_course(activity, variant)
                    self.assertEqual(world.read_text(), active_course_world(course))
                    selected = project / 'plugins/robot_windows' / launcher.ROBOT_WINDOW
                    page_bytes = (selected / (launcher.ROBOT_WINDOW + '.html')).read_bytes()
                    if first_page is None:
                        first_page = page_bytes
                    self.assertEqual(page_bytes, first_page)

    def test_menu_inventory_matches_all_native_admitted_variants(self):
        self.assertEqual(launcher.active_progression_activities()[:3], (1, 2, 3))
        self.assertEqual(tuple(count for _, count in launcher.LESSON_MENU),
                         (1, 1, 1, 3, 5, 5, 7))
        for activity, (_, count) in enumerate(launcher.LESSON_MENU, 1):
            for variant in range(1, count + 1):
                with self.subTest(activity=activity, variant=variant):
                    name = f'gp-progression-v1-a{activity}-v{variant}'
                    if variant in launcher.admitted_variants(activity):
                        self.assertEqual(launcher.active_course_from_identifier(name).identifier, name)
                    else:
                        with self.assertRaises(ValueError):
                            launcher.active_course_from_identifier(name)
            with self.assertRaises(ValueError):
                launcher.active_course_from_identifier(
                    f'gp-progression-v1-a{activity}-v{count + 1}')

    def test_menu_launches_only_selected_world_and_cancel_is_noop(self):
        selections = []
        original = launcher.prepare_lesson_project

        def prepare(project, activity, variant):
            selections.append((activity, variant))
            return original(project, activity, variant)

        home = Path('/webots/R2025a')
        with (patch.object(launcher, 'choose_lesson', return_value=(1, 1)),
              patch.object(launcher, 'prepare_lesson_project', side_effect=prepare),
              patch.object(launcher, 'webots_home', return_value=home),
              patch.object(launcher, 'prepare_route_native', return_value={'WEBOTS_HOME': str(home)})):
            self.assertEqual(launcher.main(['--menu', '--preflight-only']), 0)
        self.assertEqual(selections, [(1, 1)])

        with (patch.object(launcher, 'choose_lesson', return_value=None),
              patch.object(launcher, 'prepare_lesson_project',
                           side_effect=AssertionError('no project after cancellation'))):
            self.assertEqual(launcher.main(['--menu', '--preflight-only']), 0)

    def test_unknown_activity_refuses_before_writing_a_project(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            for selection in ((8, 1), (1, 2), (4, 4), (7, 8)):
                with self.subTest(selection=selection), self.assertRaises(ValueError):
                    launcher.prepare_lesson_project(project, *selection)
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
            last_activity = launcher.active_progression_activities()[-1]
            last_variant = launcher.admitted_variants(last_activity)[-1]
            self.assertEqual(launcher.main(['--activity', str(last_activity),
                                            '--variant', str(last_variant)]), 0)
        self.assertEqual(len(launched), 1)
        self.assertFalse(launched[0].parents[1].exists())


if __name__ == '__main__':
    unittest.main()

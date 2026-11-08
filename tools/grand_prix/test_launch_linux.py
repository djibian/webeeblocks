"""Host orchestration and refusals for the bounded Linux Grand Prix entry points.

No headless test substitutes for real interactive Webots/Blockly/file dialogs.
"""
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.grand_prix.launch_linux import main, render_legacy_u, webots_home, launch_graphical, reference_configurations, ensure_webots_assets


class LinuxGrandPrixLauncherTests(unittest.TestCase):
    def test_world_uses_real_controllers_and_dedicated_window(self):
        world = render_legacy_u(4)
        self.assertIn('basicTimeStep 8', world)
        self.assertIn('controller "grand_prix_u_flight"', world)
        self.assertIn('window "grand_prix_u"', world)
        self.assertIn('controller "grand_prix_u_evaluator"', world)
        self.assertIn('DEF GP_U_EVALUATOR Robot', world)
        self.assertIn('controllerArgs [ "4" "2.000" ]', world)
        self.assertNotIn('controller "<none>"', world)
        self.assertNotIn('window "<none>"', world)
        self.assertNotIn('https://raw.githubusercontent.com/cyberbotics/webots/R2025a/', world)

    def test_seed_is_reproducible_without_rewriting_program(self):
        self.assertEqual(render_legacy_u(0), render_legacy_u(0))
        self.assertNotEqual(render_legacy_u(0), render_legacy_u(1))

    def test_legacy_confirmation_required_before_side_effects(self):
        with self.assertRaises(SystemExit) as caught:
            main(["--seed", "4", "--preflight-only"])
        self.assertEqual(caught.exception.code, 2)

    def test_invalid_seed_rejected_before_side_effects(self):
        with self.assertRaises(SystemExit) as caught:
            main(["--legacy-u", "--seed", "65536", "--preflight-only"])
        self.assertEqual(caught.exception.code, 2)

    def test_webots_version_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "webots").write_text("#!/bin/sh\n", encoding="utf-8")
            (home / "webots").chmod(0o755)
            (home / "resources").mkdir()
            (home / "resources/version.txt").write_text("R2025b\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "R2025a"):
                webots_home(str(home))

    def test_pinned_local_webots_assets_fail_closed_without_network(self):
        import hashlib
        import json
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "webots"
            relative = "projects/objects/floors/protos/Floor.proto"
            target = home / relative
            target.parent.mkdir(parents=True)
            content = b"official pinned Floor fixture"
            target.write_bytes(content)
            lock = Path(directory) / "assets.lock.json"
            item = {"path": relative, "bytes": len(content),
                    "sha256": hashlib.sha256(content).hexdigest()}
            manifest = {"schema": 1,
                        "source_commit": "c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b",
                        "assets": [item]}
            lock.write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual(ensure_webots_assets(home, lock), 1)
            target.write_bytes(b"official pinned Floor fixture!")
            with self.assertRaisesRegex(RuntimeError, "non conforme"):
                ensure_webots_assets(home, lock)
            target.unlink()
            with self.assertRaisesRegex(RuntimeError, "absente"):
                ensure_webots_assets(home, lock)
            manifest["assets"][0]["path"] = "projects/../../escape.proto"
            lock.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "interdit"):
                ensure_webots_assets(home, lock)

    def test_asset_preflight_precedes_blockly_or_native_build(self):
        from tools.grand_prix.launch_linux import prepare_native
        with mock.patch("tools.grand_prix.launch_linux.ensure_webots_assets",
                        side_effect=RuntimeError("ressources manquantes")) as assets, \
             mock.patch("tools.grand_prix.launch_linux.ensure_blockly_assets") as blockly, \
             mock.patch("tools.grand_prix.launch_linux.subprocess.run") as run:
            with self.assertRaisesRegex(RuntimeError, "ressources manquantes"):
                prepare_native(Path("/mock/webots"))
            assets.assert_called_once()
            blockly.assert_not_called()
            run.assert_not_called()

    def test_missing_blockly_media_requires_reprepare_and_fail_closed(self):
        # Vendor JS alone does not establish a complete offline Blockly editor.
        from tools.grand_prix.launch_linux import ensure_blockly_assets
        with tempfile.TemporaryDirectory() as directory:
            blockly = Path(directory)
            files = (
                "vendor/VERSION", "vendor/blockly_compressed.js",
                "vendor/blocks_compressed.js", "vendor/msg/fr.js",
                "webots/RobotWindow.js", "webots/request_methods.js",
            )
            for relative in files:
                path = blockly / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("13.2.1\n" if relative == "vendor/VERSION" else "test\n",
                                encoding="utf-8")
            self.assertFalse((blockly / "vendor/media").exists())
            with mock.patch("tools.grand_prix.launch_linux.BLOCKLY", blockly):
                with mock.patch("tools.grand_prix.launch_linux.subprocess.run") as prepare:
                    with self.assertRaisesRegex(RuntimeError, "Ressources Blockly"):
                        ensure_blockly_assets()
                    prepare.assert_called_once()
                    self.assertIn("prepare_runtime_v2.sh", str(prepare.call_args))
                def finish_preparation(*args, **kwargs):
                    (blockly / "vendor/media").mkdir()
                with mock.patch("tools.grand_prix.launch_linux.subprocess.run",
                                side_effect=finish_preparation) as prepare:
                    ensure_blockly_assets()
                    prepare.assert_called_once()

    def test_graphical_start_is_explicitly_paused(self):
        with mock.patch("tools.grand_prix.launch_linux.subprocess.run") as run:
            run.return_value.returncode = 0
            home = Path("/mock/webots")
            world = Path("/mock/worlds/teacher.wbt")
            result = launch_graphical(home, world, {"WEBOTS_HOME": str(home)})
            self.assertEqual(result.returncode, 0)
            self.assertEqual(
                run.call_args.args[0],
                [str(home / "webots"), "--mode=pause", "--stdout", "--stderr", str(world)],
            )
            self.assertFalse(run.call_args.kwargs["check"])

    def test_reference_catalog_is_canonical_and_discovery_never_launches(self):
        """Host-only listing must not imply qualification or touch Webots."""
        from io import StringIO
        from tools.grand_prix.route_courses_v2 import (
            course_from_identifier, reference_course,
        )
        entries = reference_configurations()
        self.assertEqual(tuple(i for i, _ in entries), tuple(range(12)))
        self.assertEqual(len({identifier for _, identifier in entries}), 12)
        for index, identifier in entries:
            self.assertEqual(course_from_identifier(identifier), reference_course(index))

        with mock.patch("tools.grand_prix.launch_linux.webots_home") as home, \
             mock.patch("tools.grand_prix.launch_linux.prepare_native") as native, \
             mock.patch("tools.grand_prix.launch_linux.launch_graphical") as gui, \
             mock.patch("sys.stdout", new_callable=StringIO) as output:
            self.assertEqual(main(["--list-configurations"]), 0)
        home.assert_not_called()
        native.assert_not_called()
        gui.assert_not_called()
        text = output.getvalue()
        self.assertIn("NON QUALIFIÉS", text)
        for index, identifier in entries:
            self.assertIn(f"  {index:02d}  {identifier}\n", text)
        self.assertEqual(sum(line.startswith("  ") for line in text.splitlines()), 12)

    def test_listing_conflicts_fail_closed_before_preflight(self):
        with mock.patch("tools.grand_prix.launch_linux.webots_home") as home:
            for arguments in (
                ["--list-configurations", "--legacy-u"],
                ["--list-configurations", "--preflight-only"],
                ["--list-configurations", "--seed", "5"],
                ["--list-configurations", "--webots-home", "/unused"],
            ):
                with self.subTest(arguments=arguments), self.assertRaises(SystemExit) as caught:
                    main(arguments)
                self.assertEqual(caught.exception.code, 2)
            home.assert_not_called()

    def test_headless_run_does_not_claim_gui_delivery(self):
        with mock.patch.dict(os.environ, {"DISPLAY": "", "WAYLAND_DISPLAY": ""}):
            with mock.patch("tools.grand_prix.launch_linux.webots_home") as home:
                self.assertEqual(main(["--legacy-u"]), 1)
                home.assert_not_called()


    def test_variable_static_inspection_has_full_inert_l_h_world(self):
        from tools.grand_prix.route_courses_v2 import reference_course
        from tools.grand_prix import inspect_static_linux as preview
        for index in (0, 5, 6, 11):
            with self.subTest(index=index):
                identifier, world = preview.render_preview(index)
                course = reference_course(index)
                self.assertEqual(identifier, course.identifier)
                self.assertIn('basicTimeStep 8', world)
                self.assertEqual(world.count('DEF GP_V2_L_'), 4)
                self.assertEqual(world.count('DEF GP_V2_H_'), 3 * course.count)
                self.assertEqual(world.count('DEF GP_V2_FINAL_'), 4)
                self.assertEqual(world.count('controller "<none>"'), 1)
                self.assertEqual(world.count('window "<none>"'), 1)
                self.assertNotIn('GP_ROUTE_EVALUATOR', world)
                self.assertNotIn('controller "grand_prix_u_flight"', world)
        for index in (-1, 12, None, True):
            with self.subTest(index=index), self.assertRaises(ValueError):
                preview.render_preview(index)

    def test_static_inspection_gui_is_resource_checked_and_tempfile_is_retired(self):
        from tools.grand_prix import inspect_static_linux as preview
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / 'webots'
            worlds = Path(directory) / 'worlds'
            worlds.mkdir()
            observed = {}

            def graphical(mock_home, world, env):
                self.assertEqual(mock_home, home)
                self.assertEqual(env['WEBOTS_HOME'], str(home))
                observed['world'] = world
                observed['scene'] = world.read_text(encoding='utf-8')
                return mock.Mock(returncode=0)

            with mock.patch.dict(os.environ, {'DISPLAY': ':99', 'WAYLAND_DISPLAY': ''}), \
                 mock.patch.object(preview, 'ROOT', Path(directory)), \
                 mock.patch.object(preview, 'webots_home', return_value=home) as version, \
                 mock.patch.object(preview, 'ensure_webots_assets', return_value=24) as assets, \
                 mock.patch.object(preview, 'launch_graphical', side_effect=graphical) as launch:
                self.assertEqual(preview.main(['--index', '5']), 0)
            version.assert_called_once_with(None)
            assets.assert_called_once_with(home)
            launch.assert_called_once()
            self.assertIn('Grand Prix STATIC ', observed['scene'])
            self.assertNotIn('GP_ROUTE_EVALUATOR', observed['scene'])
            self.assertFalse(observed['world'].exists())
            self.assertFalse(observed['world'].with_name(
                '.' + observed['world'].stem + '.wbproj').exists())

    def test_static_inspection_headless_and_missing_assets_refuse_before_gui(self):
        from tools.grand_prix import inspect_static_linux as preview
        with mock.patch.dict(os.environ, {'DISPLAY': '', 'WAYLAND_DISPLAY': ''}), \
             mock.patch.object(preview, 'webots_home') as home, \
             mock.patch.object(preview, 'launch_graphical') as launch:
            self.assertEqual(preview.main(['--index', '5']), 1)
            home.assert_not_called()
            launch.assert_not_called()
        with mock.patch.dict(os.environ, {'DISPLAY': ':99'}), \
             mock.patch.object(preview, 'webots_home', return_value=Path('/mock/webots')), \
             mock.patch.object(preview, 'ensure_webots_assets',
                               side_effect=RuntimeError('official resources missing')), \
             mock.patch.object(preview, 'launch_graphical') as launch:
            self.assertEqual(preview.main(['--index', '5']), 1)
            launch.assert_not_called()
        for index in ('-1', '12'):
            with self.subTest(index=index), self.assertRaises(SystemExit) as caught:
                preview.main(['--index', index])
            self.assertEqual(caught.exception.code, 2)


    def test_custom_course_id_reuses_full_inert_canonical_world(self):
        from tools.grand_prix.route_courses_v2 import plan_course, course_from_identifier
        from tools.grand_prix import inspect_static_linux as preview
        course = plan_course(17, (2.0, 2.5, 3.0), ('G', 'D'), 2)
        identifier, world = preview.render_identifier(course.identifier)
        self.assertEqual(identifier, course.identifier)
        self.assertEqual(course_from_identifier(identifier), course)
        self.assertIn('Grand Prix STATIC ' + identifier, world)
        self.assertEqual(world.count('DEF GP_V2_L_'), 4)
        self.assertEqual(world.count('DEF GP_V2_H_'), 6)
        self.assertEqual(world.count('DEF GP_V2_FINAL_'), 4)
        self.assertEqual(world.count('controller "<none>"'), 1)
        self.assertEqual(world.count('window "<none>"'), 1)
        self.assertNotIn('GP_ROUTE_EVALUATOR', world)
        for rejected in (None, True, 'gp-u-v1', identifier + '-alias',
                         identifier.replace('-H2', '-H4')):
            with self.subTest(rejected=rejected), self.assertRaises(ValueError):
                preview.render_identifier(rejected)

    def test_custom_course_id_cli_rejects_ambiguous_or_forged_input(self):
        from tools.grand_prix.route_courses_v2 import reference_course
        from tools.grand_prix import inspect_static_linux as preview
        identity = reference_course(5).identifier
        for args in ([], ['--index', '5', '--course-id', identity]):
            with self.subTest(args=args), self.assertRaises(SystemExit) as error:
                preview.main(args)
            self.assertEqual(error.exception.code, 2)
        with mock.patch.dict(os.environ, {'DISPLAY': ':99'}), \
             mock.patch.object(preview, 'webots_home') as home:
            self.assertEqual(preview.main(['--course-id', identity + '-alias']), 1)
            home.assert_not_called()

    def test_custom_course_id_cli_opens_paused_inert_world_and_cleans_up(self):
        from tools.grand_prix.route_courses_v2 import plan_course
        from tools.grand_prix import inspect_static_linux as preview
        course = plan_course(17, (2., 2.5, 3.), ('G', 'D'), 2)
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / 'worlds').mkdir()
            observed = {}
            def launch(_home, world, _env):
                observed['text'] = world.read_text(encoding='utf-8')
                observed['world'] = world
                return mock.Mock(returncode=0)
            with mock.patch.dict(os.environ, {'DISPLAY': ':99'}), \
                 mock.patch.object(preview, 'ROOT', directory), \
                 mock.patch.object(preview, 'webots_home', return_value=directory) as home, \
                 mock.patch.object(preview, 'ensure_webots_assets', return_value=12), \
                 mock.patch.object(preview, 'launch_graphical', side_effect=launch) as gui:
                self.assertEqual(preview.main(['--course-id', course.identifier]), 0)
            home.assert_called_once_with(None)
            gui.assert_called_once()
            self.assertIn('Grand Prix STATIC ' + course.identifier, observed['text'])
            self.assertNotIn('GP_ROUTE_EVALUATOR', observed['text'])
            self.assertIn('controller "<none>"', observed['text'])
            self.assertFalse(observed['world'].exists())
            self.assertFalse(observed['world'].with_name(
                '.' + observed['world'].stem + '.wbproj').exists())

    def test_static_inspection_direct_script_imports_from_any_cwd_without_pythonpath(self):
        from tools.grand_prix import inspect_static_linux as preview
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as directory:
            env = os.environ.copy()
            env.pop('PYTHONPATH', None)
            result = subprocess.run(
                [sys.executable, str(Path(preview.__file__).resolve()), '--help'],
                cwd=directory, env=env, capture_output=True, text=True, timeout=20,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('INSPECTION SEULEMENT', result.stdout)


    def test_variable_editor_sandbox_preserves_course_and_disables_evaluator_only(self):
        from tools.grand_prix.course_active_world_v2 import active_course_world
        from tools.grand_prix.route_courses_v2 import reference_course
        from tools.grand_prix.launch_variable_editor_linux import render_editor_sandbox
        for index in range(12):
            course = reference_course(index)
            active = active_course_world(course)
            sandbox = render_editor_sandbox(course)
            with self.subTest(index=index):
                self.assertEqual(sandbox, active.replace(
                    '  controller "grand_prix_route_evaluator"\n',
                    '  controller "<none>"\n', 1))
                self.assertEqual(sandbox.count('  controller "<none>"'), 1)
                self.assertEqual(sandbox.count('controller "grand_prix_route_flight"'), 1)
                self.assertEqual(sandbox.count('window "grand_prix_route_v2"'), 1)
                self.assertEqual(sandbox.count('DEF GP_ROUTE_EVALUATOR Robot {'), 1)
                self.assertEqual(sandbox.count('DEF GP_V2_L_'), 4)
                self.assertEqual(sandbox.count('DEF GP_V2_H_'), 3 * course.count)
                self.assertNotIn('controller "grand_prix_route_evaluator"', sandbox)
                self.assertNotIn('controller "grand_prix_u_flight"', sandbox)

    def test_variable_editor_preflight_checks_assets_before_build(self):
        from tools.grand_prix import launch_variable_editor_linux as sandbox
        with mock.patch.object(sandbox, "ensure_webots_assets",
                               side_effect=RuntimeError("official R2025a assets absent")) as assets, \
             mock.patch.object(sandbox, "ensure_blockly_assets") as blockly, \
             mock.patch.object(sandbox.subprocess, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "assets absent"):
                sandbox.prepare_editor(Path("/mock/webots"))
            assets.assert_called_once()
            blockly.assert_not_called()
            run.assert_not_called()
        with tempfile.TemporaryDirectory() as directory:
            flight = Path(directory) / "controllers/grand_prix_route_flight"
            flight.mkdir(parents=True)
            binary = flight / "grand_prix_route_flight"
            binary.write_text("fake binary", encoding="utf-8")
            binary.chmod(0o755)
            with mock.patch.object(sandbox, "ROOT", Path(directory)), \
                 mock.patch.object(sandbox, "FLIGHT", flight), \
                 mock.patch.object(sandbox, "ensure_webots_assets") as assets, \
                 mock.patch.object(sandbox, "ensure_blockly_assets") as blockly, \
                 mock.patch.object(sandbox.subprocess, "run") as run:
                env = sandbox.prepare_editor(Path("/mock/webots"))
            self.assertEqual(env["WEBOTS_HOME"], "/mock/webots")
            assets.assert_called_once()
            blockly.assert_called_once()
            self.assertEqual(run.call_count, 2)
            self.assertIn("prepare_route_runtime.py", str(run.call_args_list[0]))
            self.assertIn("release", str(run.call_args_list[1]))

    def test_variable_editor_sandbox_gui_is_paused_and_retires_only_owned_world(self):
        from tools.grand_prix import launch_variable_editor_linux as sandbox
        from tools.grand_prix.route_courses_v2 import reference_course
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "worlds").mkdir()
            fixed = base / "worlds/user_existing.wbt"
            fixed.write_text("existing user world", encoding="utf-8")
            seen = {}
            def graphical(_home, world, _env):
                seen["world"] = world
                seen["scene"] = world.read_text(encoding="utf-8")
                world.with_name("." + world.stem + ".wbproj").write_text(
                    "owned generated project", encoding="utf-8")
                return mock.Mock(returncode=0)
            with mock.patch.dict(os.environ, {"DISPLAY": ":99", "WAYLAND_DISPLAY": ""}), \
                 mock.patch.object(sandbox, "ROOT", base), \
                 mock.patch.object(sandbox, "webots_home", return_value=base) as home, \
                 mock.patch.object(sandbox, "prepare_editor",
                                   return_value={"WEBOTS_HOME": str(base)}) as prepared, \
                 mock.patch.object(sandbox, "launch_graphical", side_effect=graphical) as gui:
                self.assertEqual(sandbox.main([
                    "--course-id", reference_course(5).identifier,
                    "--editor-sandbox"]), 0)
            home.assert_called_once_with(None)
            prepared.assert_called_once_with(base)
            gui.assert_called_once()
            self.assertIn('Grand Prix variable EXPERIMENTAL ', seen["scene"])
            self.assertIn('controller "grand_prix_route_flight"', seen["scene"])
            self.assertIn('window "grand_prix_route_v2"', seen["scene"])
            self.assertIn('controller "<none>"', seen["scene"])
            self.assertNotIn('controller "grand_prix_route_evaluator"', seen["scene"])
            self.assertFalse(seen["world"].exists())
            self.assertFalse(seen["world"].with_name(
                "." + seen["world"].stem + ".wbproj").exists())
            self.assertEqual(fixed.read_text(encoding="utf-8"), "existing user world")

    def test_variable_editor_invalid_input_and_headless_refuse_before_preflight(self):
        from tools.grand_prix import launch_variable_editor_linux as sandbox
        from tools.grand_prix.route_courses_v2 import reference_course
        config = reference_course(5).identifier
        for arguments in (
            [], ["--index", "5", "--course-id", config],
            ["--index", "5"], ["--editor-sandbox", "--index", "12"],
        ):
            with self.subTest(arguments=arguments), self.assertRaises(SystemExit) as error:
                sandbox.main(arguments)
            self.assertEqual(error.exception.code, 2)
        with mock.patch.object(sandbox, "webots_home") as home:
            self.assertEqual(sandbox.main([
                "--course-id", config + "-alias", "--editor-sandbox"]), 1)
            home.assert_not_called()
        with mock.patch.dict(os.environ, {"DISPLAY": "", "WAYLAND_DISPLAY": ""}), \
             mock.patch.object(sandbox, "webots_home") as home:
            self.assertEqual(sandbox.main(["--index", "5", "--editor-sandbox"]), 1)
            home.assert_not_called()
        with mock.patch.object(sandbox, "webots_home", return_value=Path("/mock")) as home, \
             mock.patch.object(sandbox, "prepare_editor", return_value={}) as prepared, \
             mock.patch.object(sandbox, "launch_graphical") as graphical:
            self.assertEqual(sandbox.main(["--index", "5", "--preflight-only"]), 0)
            home.assert_called_once_with(None)
            prepared.assert_called_once()
            graphical.assert_not_called()

    def test_variable_editor_entry_imports_from_any_workdir(self):
        from tools.grand_prix import launch_variable_editor_linux as sandbox
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as directory:
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            output = subprocess.run(
                [sys.executable, str(Path(sandbox.__file__).resolve()), "--help"],
                cwd=directory, env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(output.returncode, 0, output.stderr)
        self.assertIn("SANDBOX Blockly Linux", output.stdout)


class ControlledRenderFpsABTests(unittest.TestCase):
    """#912: display-only renderer settings must not modify native physics."""

    def test_canonical_world_only_changes_render_budget(self):
        from tools.grand_prix.launch_linux import configure_render_fps, render_route
        from tools.grand_prix.route_courses_v2 import reference_course
        for index in (0, 5, 11):
            source = render_route(reference_course(index))
            self.assertEqual(configure_render_fps(source, None), source)
            for fps in (25, 30, 60):
                with self.subTest(index=index, fps=fps):
                    changed = configure_render_fps(source, fps)
                    self.assertEqual(changed.replace(f"FPS {fps} ", "", 1), source)
                    self.assertIn(f"basicTimeStep 8 randomSeed 1 FPS {fps}", changed)
                    self.assertEqual(changed.count("WorldInfo {"), 1)
                    self.assertIn('controller "grand_prix_route_flight"', changed)
                    self.assertIn('controller "grand_prix_route_evaluator"', changed)
                    self.assertIn('window "grand_prix_route_v2"', changed)

    def test_malformed_or_unknown_world_fails_closed(self):
        from tools.grand_prix.launch_linux import configure_render_fps, render_route
        from tools.grand_prix.route_courses_v2 import reference_course
        source = render_route(reference_course(5))
        for invalid in (False, True, -1, 0, 24, 61, "25", 25.0):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                configure_render_fps(source, invalid)
        for altered in (source.replace("basicTimeStep 8", "basicTimeStep 16"),
                        source.replace("WorldInfo {", "WorldInfo { FPS 90 ", 1),
                        source + "\nWorldInfo {}\n"):
            with self.subTest(length=len(altered)), self.assertRaises(RuntimeError):
                configure_render_fps(altered, 25)

    def test_explicit_cli_render_cap_does_not_activate_legacy_or_listing(self):
        from tools.grand_prix import launch_linux as launcher
        for arguments in (["--legacy-u", "--render-fps", "25"],
                          ["--list-configurations", "--render-fps", "25"],
                          ["--index", "5", "--render-fps", "24"]):
            with self.subTest(arguments=arguments), self.assertRaises(SystemExit) as caught:
                launcher.main(arguments)
            self.assertEqual(caught.exception.code, 2)

        from tools.grand_prix.route_courses_v2 import reference_course
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "worlds").mkdir()
            scenes = []
            def gui(_home, world, _env):
                scenes.append(world.read_text(encoding="utf-8"))
                return mock.Mock(returncode=0)
            with mock.patch.dict(os.environ, {"DISPLAY": ":99", "WAYLAND_DISPLAY": ""}), \
                 mock.patch.object(launcher, "ROOT", root), \
                 mock.patch.object(launcher, "webots_home", return_value=Path("/mock/webots")), \
                 mock.patch.object(launcher, "prepare_route_native", return_value={}), \
                 mock.patch.object(launcher, "launch_graphical", side_effect=gui):
                for fps in (25, 30, 60):
                    self.assertEqual(launcher.main(["--index", "5", "--render-fps", str(fps)]), 0)
                self.assertEqual(launcher.main(["--index", "5"]), 0)
            self.assertEqual(len(scenes), 4)
            original = launcher.render_route(reference_course(5))
            for actual, fps in zip(scenes[:3], (25, 30, 60)):
                self.assertEqual(actual.replace(f"FPS {fps} ", "", 1), original)
            self.assertEqual(scenes[3], original, "default arm must stay byte-identical")


class ActiveVariableLinuxLauncherTests(unittest.TestCase):
    def test_every_reference_and_custom_course_reuses_exact_active_composer(self):
        from tools.grand_prix.launch_linux import render_route
        from tools.grand_prix.course_active_world_v2 import active_course_world
        from tools.grand_prix.route_courses_v2 import reference_course, plan_course
        courses = [reference_course(i) for i in range(12)]
        courses.append(plan_course(17, (2., 2.5, 3.), ('G', 'D'), 2))
        for course in courses:
            world = render_route(course)
            self.assertEqual(world, active_course_world(course).replace(
                'https://raw.githubusercontent.com/cyberbotics/webots/R2025a/', 'webots://'))
            self.assertEqual(world.count('controllerArgs [ "' + course.identifier + '" ]'), 2)
            self.assertIn('window "grand_prix_route_v2"', world)
            self.assertNotIn('controller "<none>"', world)
            self.assertNotIn('grand_prix_u_flight', world)

    def test_route_asset_refusal_precedes_any_preparation(self):
        from tools.grand_prix import launch_linux as launcher
        with mock.patch.object(launcher, 'ensure_webots_assets',
                               side_effect=RuntimeError('missing pinned assets')), \
             mock.patch.object(launcher, 'ensure_blockly_assets') as blockly, \
             mock.patch.object(launcher.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'missing pinned assets'):
                launcher.prepare_route_native(Path('/mock/webots'))
            blockly.assert_not_called()
            run.assert_not_called()

    def test_route_build_targets_production_and_refuses_missing_executable(self):
        from tools.grand_prix import launch_linux as launcher
        with tempfile.TemporaryDirectory() as temp:
            flight = Path(temp) / 'grand_prix_route_flight'
            flight.mkdir()
            home = Path('/mock/webots')
            with mock.patch.object(launcher, 'ROUTE_FLIGHT', flight), \
                 mock.patch.object(launcher, 'ensure_webots_assets'), \
                 mock.patch.object(launcher, 'ensure_blockly_assets'), \
                 mock.patch.object(launcher.subprocess, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'compilé introuvable'):
                    launcher.prepare_route_native(home)
                self.assertEqual(run.call_count, 2)
                self.assertTrue(str(run.call_args_list[0].args[0][1]).endswith('prepare_route_runtime.py'))
                self.assertEqual(run.call_args_list[1].args[0], ['make', '-C', str(flight), 'release'])
                binary = flight / 'grand_prix_route_flight'
                binary.write_text('fixture, not a native binary')
                binary.chmod(0o755)
                self.assertEqual(launcher.prepare_route_native(home)['WEBOTS_HOME'], str(home))

    def test_ambiguous_invalid_and_headless_route_never_build_or_launch(self):
        from tools.grand_prix import launch_linux as launcher
        with mock.patch.object(launcher, 'prepare_native') as legacy, \
             mock.patch.object(launcher, 'prepare_route_native') as prepare, \
             mock.patch.object(launcher, 'launch_graphical') as gui:
            for arguments in ([], ['--index', '12'], ['--index', '5', '--legacy-u'],
                              ['--index', '5', '--course-id', 'x'],
                              ['--index', '5', '--seed', '4'],
                              ['--list-configurations', '--index', '5']):
                with self.subTest(arguments=arguments), self.assertRaises(SystemExit):
                    launcher.main(arguments)
            self.assertEqual(launcher.main(['--course-id', 'gp-u-v1', '--preflight-only']), 1)
            with mock.patch.dict(os.environ, {'DISPLAY': '', 'WAYLAND_DISPLAY': ''}):
                self.assertEqual(launcher.main(['--index', '5']), 1)
            legacy.assert_not_called()
            prepare.assert_not_called()
            gui.assert_not_called()

    def test_route_gui_receives_production_world_and_retires_only_owned_files(self):
        from tools.grand_prix import launch_linux as launcher
        from tools.grand_prix.route_courses_v2 import reference_course
        for selection in (['--index', '5'], ['--course-id', reference_course(5).identifier]):
            for failure in (False, True):
                with self.subTest(selection=selection, failure=failure), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    (root / 'worlds').mkdir()
                    unrelated = root / 'worlds/.keep.wbproj'
                    unrelated.write_text('keep')
                    observed = []
                    def gui(home, world, env):
                        self.assertIn('controller "grand_prix_route_evaluator"', world.read_text())
                        self.assertIn('window "grand_prix_route_v2"', world.read_text())
                        world.with_name('.' + world.stem + '.wbproj').write_text('owned')
                        observed.append(world)
                        if failure:
                            raise OSError('native launch failed')
                        return mock.Mock(returncode=7)
                    with mock.patch.dict(os.environ, {'DISPLAY': ':99'}), \
                         mock.patch.object(launcher, 'ROOT', root), \
                         mock.patch.object(launcher, 'webots_home', return_value=Path('/mock/webots')), \
                         mock.patch.object(launcher, 'prepare_native') as legacy, \
                         mock.patch.object(launcher, 'prepare_route_native', return_value={}) as prepare, \
                         mock.patch.object(launcher, 'launch_graphical', side_effect=gui):
                        self.assertEqual(launcher.main(selection), 1 if failure else 7)
                    legacy.assert_not_called()
                    prepare.assert_called_once()
                    self.assertEqual(len(observed), 1)
                    self.assertFalse(observed[0].exists())
                    self.assertEqual(list((root / 'worlds').iterdir()), [unrelated])

    def test_route_preflight_can_run_headless_without_claiming_gui(self):
        from tools.grand_prix import launch_linux as launcher
        with mock.patch.dict(os.environ, {'DISPLAY': '', 'WAYLAND_DISPLAY': ''}), \
             mock.patch.object(launcher, 'webots_home', return_value=Path('/mock/webots')), \
             mock.patch.object(launcher, 'prepare_native') as legacy, \
             mock.patch.object(launcher, 'prepare_route_native', return_value={}) as prepare, \
             mock.patch.object(launcher, 'launch_graphical') as gui:
            self.assertEqual(launcher.main(['--index', '5', '--preflight-only']), 0)
            prepare.assert_called_once()
            legacy.assert_not_called()
            gui.assert_not_called()


if __name__ == "__main__":
    unittest.main()

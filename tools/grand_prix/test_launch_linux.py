"""Static falsification for the bounded historical-U Linux entry point.

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


if __name__ == "__main__":
    unittest.main()

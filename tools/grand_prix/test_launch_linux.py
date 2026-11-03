"""Static falsification for the bounded historical-U Linux entry point.

No headless test substitutes for real interactive Webots/Blockly/file dialogs.
"""
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.grand_prix.launch_linux import main, render_legacy_u, webots_home, launch_graphical


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

    def test_headless_run_does_not_claim_gui_delivery(self):
        with mock.patch.dict(os.environ, {"DISPLAY": "", "WAYLAND_DISPLAY": ""}):
            with mock.patch("tools.grand_prix.launch_linux.webots_home") as home:
                self.assertEqual(main(["--legacy-u"]), 1)
                home.assert_not_called()


if __name__ == "__main__":
    unittest.main()

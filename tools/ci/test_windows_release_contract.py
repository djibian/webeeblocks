#!/usr/bin/env python3
"""Static fail-closed contract for the Windows classroom release path."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
BLOCKLY = ROOT / "plugins" / "robot_windows" / "blockly_v2"
PACKAGING = ROOT / "packaging" / "windows"


class WindowsReleaseContractTests(unittest.TestCase):
    def test_robot_window_bridge_is_local_pinned_and_fail_safe(self) -> None:
        main = (BLOCKLY / "main.js").read_text(encoding="utf-8")
        self.assertIn("import('./webots/RobotWindow.js')", main)
        self.assertNotIn("cyberbotics.com/wwi", main)
        robot_window = (BLOCKLY / "webots" / "RobotWindow.js").read_text(encoding="utf-8")
        requests = (BLOCKLY / "webots" / "request_methods.js").read_text(encoding="utf-8")
        for bridge in (robot_window, requests):
            self.assertIn("c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b", bridge)
        self.assertIn("from './request_methods.js'", robot_window)
        self.assertIn("if (!messageMatch || !robotMatch)", robot_window)
        self.assertIn("Malformed robot message ignored", robot_window)
        self.assertIn("const value = separator === -1 ? ''", requests)

    def test_preparation_is_lockfile_exact(self) -> None:
        for name in ("prepare_runtime_v2.ps1", "prepare_runtime_v2.sh"):
            preparation = (ROOT / "tools" / name).read_text(encoding="utf-8")
            self.assertIn("npm ci --ignore-scripts --no-audit --no-fund", preparation)
            self.assertNotIn("npm install --ignore-scripts", preparation)
        lock = (BLOCKLY / "package-lock.json").read_text(encoding="utf-8")
        self.assertIn('"blockly": "13.2.1"', lock)
        self.assertIn('"version": "13.2.1"', lock)

    def test_packager_builds_and_removes_runtime_network_dependencies(self) -> None:
        packager = (
            ROOT / "tools" / "build_windows_classroom_release.ps1"
        ).read_text(encoding="utf-8")
        for required in (
            "& $make -C $controllerDir clean",
            "& $make -C $controllerDir",
            "crazyflie_runtime_v2.exe",
            "Expected exactly four pinned remote references",
            "../protos/Crazyflie.proto",
            "textures/fast_helix.png",
            "MANIFEST.sha256",
            "Compression.ZipFile]::CreateFromDirectory",
        ):
            self.assertIn(required, packager)
        self.assertIn("$worldText -match '\"(?:https?|webots)://'", packager)
        self.assertIn("$protoText -match '\"(?:https?|webots)://'", packager)
        self.assertNotIn("Convert-ToMsysPath", packager)
        self.assertNotIn("bash -lc", packager)
        self.assertIn("msys64\\usr\\bin\\make.exe", packager)
        self.assertIn("msys64\\mingw64\\bin\\gcc.exe", packager)
        self.assertIn("$env:WEBOTS_HOME = $webotsRoot", packager)

    def test_student_boundary_is_explicit(self) -> None:
        readme = (PACKAGING / "README-WINDOWS.md").read_text(encoding="utf-8")
        acceptance = (PACKAGING / "WINDOWS-ACCEPTANCE.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Ni Git, ni Node.js, ni npm", readme)
        self.assertIn("Statut : **NON VALIDÉ**", acceptance)
        self.assertIn("réseau coupé", acceptance)
        self.assertIn("30 min", acceptance)

    def test_launcher_opens_only_packaged_world_with_r2025a(self) -> None:
        launcher = (PACKAGING / "Launch-WebeeBlocks.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("worlds\\crazyflie_runtime_v2.wbt", launcher)
        self.assertIn("--mode=pause", launcher)
        self.assertIn("$worldArgument = '\"' + $world + '\"'", launcher)
        self.assertIn("Test-WebotsR2025a", launcher)
        self.assertIn("--version", launcher)
        self.assertIn("-match 'R2025a'", launcher)
        self.assertIn("-ValidateOnly", (ROOT / "tools" / "ci" / "test_windows_classroom_release.ps1").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

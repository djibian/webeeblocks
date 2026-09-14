#!/usr/bin/env python3
"""Static fail-closed contract for the Windows classroom release path."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
BLOCKLY = ROOT / "plugins" / "robot_windows" / "blockly_v2"
PACKAGING = ROOT / "packaging" / "windows"


class WindowsReleaseContractTests(unittest.TestCase):
    def test_robot_window_bridge_is_local_pinned_and_fail_safe(self) -> None:
        main = (BLOCKLY / "main.js").read_text(encoding="utf-8")
        self.assertIn("document.currentScript && document.currentScript.src", main)
        self.assertIn(
            "import(new URL('./webots/RobotWindow.js', WEBEEBLOCKS_MAIN_SCRIPT_URL).href)",
            main,
        )
        self.assertNotIn("import('./webots/RobotWindow.js')", main)
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
            "classroom_fixes.css",
            "classroom_fixes.js",
            "Expected exactly four pinned remote references",
            "../protos/Crazyflie.proto",
            "textures/fast_helix.png",
            "MANIFEST.sha256",
            "Compression.ZipFile]::CreateFromDirectory",
            "msys64\\mingw64\\bin\\g++.exe",
            "WebeeBlocksLauncher.cpp",
            "WebeeBlocksLauncher.exe",
            "'-static'",
            "libstdc++-6.dll",
            "libgcc_s_seh-1.dll",
            "libwinpthread-1.dll",
        ):
            self.assertIn(required, packager)
        self.assertIn("$worldText -match '\"(?:https?|webots)://'", packager)
        self.assertIn("$protoText -match '\"(?:https?|webots)://'", packager)
        self.assertNotIn("Convert-ToMsysPath", packager)
        self.assertNotIn("bash -lc", packager)
        self.assertIn("msys64\\usr\\bin\\make.exe", packager)
        self.assertIn("msys64\\mingw64\\bin\\gcc.exe", packager)
        self.assertIn("$env:WEBOTS_HOME = $webotsRoot", packager)
        self.assertNotIn("'Launch-WebeeBlocks.ps1'", packager)

    def test_robot_window_release_assets_are_complete_and_cache_isolated(self) -> None:
        html = (BLOCKLY / "blockly_v2.html").read_text(encoding="utf-8")
        packager = (
            ROOT / "tools" / "build_windows_classroom_release.ps1"
        ).read_text(encoding="utf-8")
        release_check = (
            ROOT / "tools" / "ci" / "test_windows_classroom_release.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn(
            '<meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate">',
            html,
        )
        self.assertIn('<meta http-equiv="Pragma" content="no-cache">', html)
        self.assertIn('<meta http-equiv="Expires" content="0">', html)
        self.assertIn("$assetPattern = '(?<prefix>(?:src|href)=\")", packager)
        self.assertIn("Referenced Robot Window asset missing from release", packager)
        self.assertIn("Get-FileHash -LiteralPath $assetPath -Algorithm SHA256", packager)
        self.assertIn('"?wb=$digest"', packager)
        self.assertIn("Write-Utf8NoBom $blocklyHtmlPath $blocklyHtml", packager)

        runtime_root = (
            "blockly_v2.html",
            "execution_observer.css",
            "main.css",
            "main.js",
            "project_files.css",
            "project_ui.js",
            "classroom_fixes.css",
            "classroom_fixes.js",
            "led_observability.js",
            "physical_preflight_runtime.js",
        )
        for name in runtime_root:
            self.assertIn(f"'{name}'", packager)
        self.assertNotIn("Get-ChildItem -LiteralPath $blocklySource -File", packager)
        self.assertNotIn("prepare_blockly_vendor.js", packager)

        references = {
            re.split(r"[?#]", match.group(1), maxsplit=1)[0]
            for match in re.finditer(r'(?:src|href)="([^"]+)"', html)
        }
        direct_references = sorted(
            reference for reference in references if "/" not in reference
        )
        self.assertGreater(len(direct_references), 0)
        for reference in direct_references:
            self.assertIn(f"'{reference}'", packager)

        self.assertIn('src="led_observability.js"', html)
        self.assertIn('src="physical_preflight_runtime.js"', html)
        self.assertTrue((BLOCKLY / "led_observability.js").is_file())
        self.assertTrue((BLOCKLY / "physical_preflight_runtime.js").is_file())

        self.assertIn(
            "$robotWindowsRoot = Join-Path $packageDir 'plugins\\robot_windows'",
            packager,
        )
        self.assertIn(
            "Get-ChildItem -LiteralPath $robotWindowsRoot -File -Recurse",
            packager,
        )
        self.assertIn(
            '$robotWindowReleaseName = "blockly_v2_$($robotWindowDigest.Substring(0, 16))"',
            packager,
        )
        self.assertIn(
            "Move-Item -LiteralPath $blocklyTarget -Destination $robotWindowReleaseRoot",
            packager,
        )
        self.assertIn(
            "Expected exactly one Runtime v2 Robot Window identity in the source world",
            packager,
        )
        self.assertIn(
            "$worldText = $worldText.Replace($sourceRobotWindow, $packagedRobotWindow)",
            packager,
        )
        self.assertIn("^blockly_v2_[0-9a-f]{16}$", release_check)
        self.assertIn(
            "Robot Window top-level cache identity is not derived from the packaged plugin bytes",
            release_check,
        )
        self.assertIn(
            "Packaged world does not select the content-addressed Robot Window",
            release_check,
        )
        self.assertNotIn(
            "'plugins\\robot_windows\\blockly_v2\\blockly_v2.html'",
            release_check,
        )

    def test_runtime_generated_blockly_media_uses_native_exact_byte_proxy(self) -> None:
        main = (BLOCKLY / "main.js").read_text(encoding="utf-8")
        launcher = (PACKAGING / "WebeeBlocksLauncher.cpp").read_text(encoding="utf-8")
        vendor_preparation = (BLOCKLY / "prepare_blockly_vendor.js").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "var WEBEEBLOCKS_MEDIA_URL = new URL('./vendor/media/', WEBEEBLOCKS_MAIN_SCRIPT_URL).href;",
            main,
        )
        self.assertIn("media: WEBEEBLOCKS_MEDIA_URL", main)
        self.assertNotIn("media: 'vendor/media/'", main)
        self.assertIn("http://127.0.0.1:", launcher)
        self.assertIn("url_encode_path(relative_url)", launcher)
        self.assertIn(
            'send_reply(client, 200, "OK", mime_type(target), read_bytes(target));',
            launcher,
        )
        self.assertIn("sprites.png", vendor_preparation)
        self.assertIn("replaceAll('sprites.svg', 'sprites.png')", vendor_preparation)

    def test_native_firefox_broker_dependency_closure_is_fail_closed(self) -> None:
        packager = (
            ROOT / "tools" / "build_windows_classroom_release.ps1"
        ).read_text(encoding="utf-8")
        release_check = (
            ROOT / "tools" / "ci" / "test_windows_classroom_release.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "foreach ($qtDll in @('Qt6Core.dll', 'Qt6Widgets.dll'))",
            packager,
        )
        self.assertNotIn(
            "foreach ($qtDll in @('Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Widgets.dll'))",
            packager,
        )
        self.assertIn("$widgetsImports = (& $objdump -p $qtWidgets | Out-String)", packager)
        self.assertIn("Qt6Gui\\.dll", packager)
        self.assertIn("platforms\\qwindows.dll", packager)
        self.assertIn(
            "QT_PLUGIN_PATH = $(WEBOTS_HOME)/msys64/mingw64/share/qt6/plugins",
            packager,
        )
        self.assertIn("msys64\\mingw64\\bin\\cpp", release_check)

    def test_classroom_ui_loads_packaged_fixes(self) -> None:
        html = (BLOCKLY / "blockly_v2.html").read_text(encoding="utf-8")
        self.assertIn('href="classroom_fixes.css"', html)
        self.assertIn('src="classroom_fixes.js"', html)

    def test_student_boundary_is_explicit(self) -> None:
        readme = (PACKAGING / "README-WINDOWS.md").read_text(encoding="utf-8")
        acceptance = (PACKAGING / "WINDOWS-ACCEPTANCE.md").read_text(
            encoding="utf-8"
        )
        deployment = (ROOT / "docs" / "WINDOWS_DEPLOYMENT.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Ni Git, ni Node.js, ni npm", readme)
        self.assertIn("**Google Chrome**", readme)
        self.assertIn("preuves réelles W1/W2", readme)
        self.assertIn("exclusivement sur Windows 11", readme)
        self.assertIn(r"C:\Program Files\Webots", readme)
        self.assertNotIn(r"C:\\Program Files\\Webots", readme)
        self.assertIn("BASELINE CHROME VALIDÉE", acceptance)
        self.assertIn("- Windows 11 64 bits ;", acceptance)
        self.assertNotIn("- Windows 10/11 64 bits ;", acceptance)
        self.assertIn("MODÈLE DE REVALIDATION", acceptance)
        self.assertIn("| W1 | PASS", acceptance)
        self.assertIn("| W2 | PASS", acceptance)
        self.assertIn("Edge et Firefox ne sont pas couverts", acceptance)
        self.assertIn("#87", acceptance)
        self.assertIn("réseau coupé", acceptance)
        self.assertIn("30 min", acceptance)
        self.assertIn("rouvert sous Linux avec le même AST", acceptance)
        self.assertIn("release compatibility target remains **Windows 10 or 11 64-bit", deployment)
        self.assertIn("validated classroom baseline is **Windows 11", deployment)
        self.assertIn("Google Chrome", deployment)
        self.assertIn(
            "Edge is not part of the currently validated classroom boundary",
            deployment,
        )
        self.assertIn(
            "Firefox project-file parity is not currently supported",
            deployment,
        )
        self.assertNotIn("Statut : **NON VALIDÉ**", acceptance)
        self.assertNotIn("Microsoft Edge ou Google Chrome recommandé", readme)
        self.assertNotIn(
            "Firefox utilise le parcours de sauvegarde de secours",
            readme,
        )

    def test_native_launcher_owns_startup_and_session_identity(self) -> None:
        command = (PACKAGING / "Launch-WebeeBlocks.cmd").read_text(encoding="utf-8")
        launcher = (PACKAGING / "WebeeBlocksLauncher.cpp").read_text(encoding="utf-8")
        release_check = (
            ROOT / "tools" / "ci" / "test_windows_classroom_release.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn("WebeeBlocksLauncher.exe", command)
        self.assertNotIn("powershell", command.lower())
        self.assertIn('package_root / L"worlds" / L"crazyflie_runtime_v2.wbt"', launcher)
        self.assertIn('L" --mode=realtime "', launcher)
        self.assertNotIn("--mode=pause", launcher)
        self.assertNotIn("--mode=run", launcher)
        self.assertIn('capture_process(console, L"--version")', launcher)
        self.assertIn('version.find("R2025a")', launcher)
        self.assertIn('session_name_stream << "webeeblocks_session_"', launcher)
        self.assertIn("struct SessionFiles", launcher)
        self.assertIn('"Connection: close\\r\\n\\r\\n"', launcher)
        self.assertIn("Access-Control-Allow-Origin: *", launcher)
        self.assertIn('L"--validate-only"', launcher)

        self.assertIn("'WebeeBlocksLauncher.exe'", release_check)
        self.assertIn("--validate-only", release_check)
        self.assertNotIn("powershell.exe", release_check)
        self.assertIn("PowerShell launcher must not be shipped", release_check)


if __name__ == "__main__":
    unittest.main()

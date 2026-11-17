#!/usr/bin/env python3
"""Draft-only static release closure: A6 native Windows assets are neither silently
missing nor treated as an authorized pupil / physical flight deliverable.
A live R2025a Windows build and teacher acceptance remain independent gates.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'tools/build_windows_classroom_release.ps1'
ACTIVITIES=ROOT/'plugins/robot_windows/blockly/webeeblocks/activities.js'
WINDOW=ROOT/'plugins/robot_windows/blockly_count_h/blockly_count_h.html'
WORLD=ROOT/'worlds/crazyflie_classroom_count_h_start.wbt'

class Activity6WindowsPackagingContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script=SOURCE.read_text(encoding='utf-8')
        cls.activities=ACTIVITIES.read_text(encoding='utf-8')
        cls.window=WINDOW.read_text(encoding='utf-8')
        cls.world=WORLD.read_text(encoding='utf-8')

    def test_hidden_a6_and_historical_05_06_not_advertised(self):
        self.assertRegex(self.activities,
          r"starterVisible: false,\s*id: 'progression-count-h-v1'")
        for historic in ('progression-reactive-v1',
                         'progression-combined-decisions-v1'):
            self.assertRegex(self.activities,
              r"starterVisible: false,\s*id: '"+historic+"'")
        self.assertIn("'05-reactive.wbb'",self.script)
        self.assertIn("'06-multi-perception.wbb'",self.script)
        self.assertIn("'Historique'",self.script)
        self.assertIn("Copy-RequiredFile $starter.FullName",self.script)
        self.assertIn("$expectedProgressionNames",self.script)
        self.assertIn("$actualProgressionNames.Count -ne $expectedProgressionNames.Count",self.script)
        self.assertIn("$archivedIntermediateNames -ccontains $starter.Name",self.script)
        witness=(ROOT/'tools/ci/test_windows_classroom_release.ps1').read_text(encoding='utf-8')
        for marker in ("Windows classroom starter bytes changed",
                       "$actualActiveNames", "$actualHistoricalNames",
                       "A6 WBT does not select the content-addressed A6 Robot Window",
                       "Activity 6 observer is not a Windows PE executable"):
            self.assertIn(marker,witness)

    def test_windows_compiles_native_a6_observer_and_contains_exact_scenes(self):
        for expected in (
          "$countObserverDir = Join-Path $repoRoot 'controllers\\progression_count_h_flight_observer'",
          '& $make -C $countObserverDir clean',
          '& $make -C $countObserverDir\n',
          "Join-Path $countObserverDir 'progression_count_h_flight_observer.exe'",
          "Copy-RequiredFile $countObserverBinary",
          "'count-h-1-v1.wbo'", "'count-h-2-v1.wbo'", "'count-h-3-v1.wbo'",
          "'worlds\\crazyflie_classroom_count_h_start.wbt'",
          "'worlds\\.crazyflie_classroom_count_h_start.wbproj'",
        ):
            self.assertIn(expected,self.script)

    def test_dedicated_world_is_offline_and_blue_origin(self):
        self.assertIn('translation -1.40 0 0.055', self.world)
        self.assertIn('window "blockly_count_h"',self.world)
        self.assertEqual(self.world.count('https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/'),4)
        for marker in (
          "($countWorldText.Split($remotePrefix).Count - 1) -ne 4",
          "($countWorldText.Split('translation -1.40 0 0.055').Count - 1) -ne 1",
          "Replace('Floor { size 4 4 }', $floor.TrimEnd())",
          "$countWorldText -match '\"(?:https?|webots)://'",
          "Join-Path $packageDir 'worlds\\crazyflie_classroom_count_h_start.wbt'",
        ):
            self.assertIn(marker,self.script)
        self.assertIn("Copy-RequiredFile (Join-Path $repoRoot 'worlds\\.crazyflie_classroom_count_h_start.wbproj')",self.script)

    def test_versioned_a6_window_resolves_complete_canonical_editor(self):
        self.assertIn('<base href="../blockly_v2/">',self.window)
        self.assertIn("WebeeBlocksInitialActivityId = 'progression-count-h-v1'",self.window)
        for marker in (
          "$sourceBase = '<base href=\"../blockly_v2/\">'",
          "'<base href=\"../' + $robotWindowReleaseName + '/\">'",
          '$countWindowReleaseName = "blockly_count_h_$($countHtmlDigest.Substring(0, 16))"',
          'Write-Utf8NoBom (Join-Path $countWindowReleaseDir "$countWindowReleaseName.html")',
          "window \"blockly_count_h\"",
          '$countWindowReleaseName',
        ):
            self.assertIn(marker,self.script)
        self.assertIn("Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256",self.script)
        self.assertIn("'MANIFEST.sha256'",self.script)

if __name__=='__main__':
    unittest.main()

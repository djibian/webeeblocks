[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$ArchivePath,
  [Parameter(Mandatory = $true)]
  [string]$WebotsHome
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-Release {
  param([bool]$Condition, [string]$Message)
  if (-not $Condition) { throw $Message }
}

$archive = (Resolve-Path -LiteralPath $ArchivePath).Path
$testRoot = Join-Path $env:RUNNER_TEMP 'WebeeBlocks release check with spaces'
if ((Split-Path $testRoot -Leaf) -ne 'WebeeBlocks release check with spaces') {
  throw 'Unsafe release-test extraction target.'
}
if (Test-Path -LiteralPath $testRoot) {
  Remove-Item -LiteralPath $testRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $testRoot | Out-Null
Expand-Archive -LiteralPath $archive -DestinationPath $testRoot

$manifestPath = Join-Path $testRoot 'MANIFEST.sha256'
Assert-Release (Test-Path -LiteralPath $manifestPath -PathType Leaf) 'Missing release manifest.'
$manifestEntries = @(Get-Content -LiteralPath $manifestPath | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
Assert-Release ($manifestEntries.Count -ge 20) 'Release manifest is unexpectedly small.'
$rootPrefix = [System.IO.Path]::GetFullPath($testRoot) + [System.IO.Path]::DirectorySeparatorChar
foreach ($line in $manifestEntries) {
  Assert-Release ($line -match '^([0-9a-f]{64})  (.+)$') "Malformed manifest line: $line"
  $expected = $Matches[1]
  $relative = $Matches[2]
  Assert-Release (-not [System.IO.Path]::IsPathRooted($relative)) "Absolute path in manifest: $relative"
  $target = [System.IO.Path]::GetFullPath((Join-Path $testRoot ($relative.Replace('/', '\'))))
  Assert-Release ($target.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) "Path traversal in manifest: $relative"
  Assert-Release (Test-Path -LiteralPath $target -PathType Leaf) "Missing manifest file: $relative"
  $actual = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
  Assert-Release ($actual -eq $expected) "Checksum mismatch: $relative"
}

$robotWindowsRoot = Join-Path $testRoot 'plugins\robot_windows'
$robotWindowCandidates = @(Get-ChildItem -LiteralPath $robotWindowsRoot -Directory | Where-Object {
  $_.Name -match '^blockly_v2_[0-9a-f]{16}$'
})
Assert-Release ($robotWindowCandidates.Count -eq 1) 'Expected exactly one content-addressed Runtime v2 Robot Window directory.'
$robotWindowName = $robotWindowCandidates[0].Name
$robotWindowRoot = $robotWindowCandidates[0].FullName
$robotWindowHtml = Join-Path $robotWindowRoot "${robotWindowName}.html"
Assert-Release (Test-Path -LiteralPath $robotWindowHtml -PathType Leaf) 'Content-addressed Robot Window HTML is missing.'
Assert-Release (-not (Test-Path -LiteralPath (Join-Path $robotWindowsRoot 'blockly_v2') -PathType Container)) 'Stable blockly_v2 package path defeats top-level cache isolation.'

# Reconstruct the canonical pre-rename plugin tree and independently verify that
# the packaged Robot Window name is exactly the digest derived by the builder.
$identityEntries = @(Get-ChildItem -LiteralPath $robotWindowsRoot -File -Recurse | ForEach-Object {
  $relative = [System.IO.Path]::GetRelativePath($robotWindowsRoot, $_.FullName).Replace('\', '/')
  $prefix = "$robotWindowName/"
  if ($relative.StartsWith($prefix, [System.StringComparison]::Ordinal)) {
    $tail = $relative.Substring($prefix.Length)
    if ($tail -eq "${robotWindowName}.html") {
      $tail = 'blockly_v2.html'
    }
    $relative = 'blockly_v2/' + $tail
  }
  [PSCustomObject]@{
    Relative = $relative
    Hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  }
})
$identityLines = @($identityEntries | Sort-Object Relative | ForEach-Object { "$($_.Hash)  $($_.Relative)" })
$identityText = (($identityLines -join "`n") + "`n")
$identityHasher = [System.Security.Cryptography.SHA256]::Create()
try {
  $identityBytes = [System.Text.Encoding]::UTF8.GetBytes($identityText)
  $identityHashBytes = $identityHasher.ComputeHash($identityBytes)
}
finally {
  $identityHasher.Dispose()
}
$identityDigest = -join ($identityHashBytes | ForEach-Object { $_.ToString('x2') })
Assert-Release ($robotWindowName -eq "blockly_v2_$($identityDigest.Substring(0, 16))") 'Robot Window top-level cache identity is not derived from the packaged plugin bytes.'

$robotWindowRelative = "plugins\robot_windows\$robotWindowName"
$required = @(
  'Launch-WebeeBlocks.cmd',
  'Launch-WebeeBlocks.ps1',
  'README-WINDOWS.md',
  'WINDOWS-ACCEPTANCE.md',
  'controllers\crazyflie_runtime_v2\crazyflie_runtime_v2.exe',
  'controllers\crazyflie_runtime_v2\runtime.ini',
  'controllers\crazyflie_classroom_v2\crazyflie_classroom_v2.exe',
  'controllers\crazyflie_classroom_v2\runtime.ini',
  'controllers\progression_sequence_3d\progression_sequence_3d.exe',
  'controllers\progression_altitude_v1\progression_altitude_v1.exe',
  "${robotWindowRelative}\${robotWindowName}.html",
  "${robotWindowRelative}\vendor\VERSION",
  "${robotWindowRelative}\vendor\blockly_compressed.js",
  "${robotWindowRelative}\webots\RobotWindow.js",
  'plugins\robot_windows\blockly\webeeblocks\semantic_ast.js',
  'plugins\robot_windows\blockly\webeeblocks\project_files.js',
  'plugins\robot_windows\blockly\webeeblocks\crazyflie_v2.js',
  'protos\Crazyflie.proto',
  'protos\meshes\cf2_assembly.dae',
  'protos\meshes\ccw_prop.dae',
  'protos\textures\fast_helix.png',
  'worlds\crazyflie_runtime_v2.wbt',
  'worlds\scenes\sequence-v1.wbo',
  'worlds\scenes\altitude-v1.wbo',
  'worlds\scenes\legacy-scene-v1.wbo',
  'worlds\scenes\legacy-evaluators-v1.wbo'
)
foreach ($relative in $required) {
  Assert-Release (Test-Path -LiteralPath (Join-Path $testRoot $relative) -PathType Leaf) "Missing required release path: $relative"
}

$sceneSource = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) 'worlds\scenes\sequence-v1.wbo'
$scenePackaged = Join-Path $testRoot 'worlds\scenes\sequence-v1.wbo'
Assert-Release ((Get-FileHash -LiteralPath $sceneSource -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $scenePackaged -Algorithm SHA256).Hash) 'Packaged Activity 1 scene differs from the exact source asset.'
$altitudeSceneSource = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) 'worlds\scenes\altitude-v1.wbo'
$altitudeScenePackaged = Join-Path $testRoot 'worlds\scenes\altitude-v1.wbo'
Assert-Release ((Get-FileHash -LiteralPath $altitudeSceneSource -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $altitudeScenePackaged -Algorithm SHA256).Hash) 'Packaged Activity 2 scene differs from the native-tested source asset.'

$version = (Get-Content -LiteralPath (Join-Path $robotWindowRoot 'vendor\VERSION') -Raw).Trim()
Assert-Release ($version -eq '13.2.1') "Unexpected Blockly release version: $version"

$worldPath = Join-Path $testRoot 'worlds\crazyflie_runtime_v2.wbt'
$worldText = Get-Content -LiteralPath $worldPath -Raw
$craftPattern = '(?m)^\s*name "Crazyflie WebeeBlocks"\r?\n\s*controller "crazyflie_classroom_v2"\s*$'
$legacyPattern = '(?m)^\s*name "Progression sequence evaluator"\r?\n\s*controller "crazyflie_runtime_v2"\s*$'
Assert-Release ($worldText -match $craftPattern) 'Packaged pupil Crazyflie does not run the strict school scene selector.'
Assert-Release ($worldText -match $legacyPattern) 'Packaged legacy evaluator no longer runs its original controller.'
Assert-Release (($worldText.Split('controller "crazyflie_classroom_v2"').Count - 1) -eq 1) 'Multiple school flight controllers present.'
Assert-Release (($worldText.Split('controller "crazyflie_runtime_v2"').Count - 1) -eq 1) 'Unexpected physical legacy controller count.'
$releaseRepo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$observerRelative = 'controllers\progression_sequence_3d\progression_sequence_3d.exe'
$observerSource = Join-Path $releaseRepo $observerRelative
$observerPackaged = Join-Path $testRoot $observerRelative
Assert-Release ((Get-FileHash -LiteralPath $observerSource -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $observerPackaged -Algorithm SHA256).Hash) 'Packaged Activity 1 native supervisor differs from the freshly built Webots executable.'
$observerBytes = [System.IO.File]::ReadAllBytes($observerPackaged)
Assert-Release ($observerBytes.Length -gt 2 -and $observerBytes[0] -eq 0x4d -and $observerBytes[1] -eq 0x5a) 'Activity 1 observer is not a Windows PE executable.'
Assert-Release (-not (Test-Path -LiteralPath (Join-Path $testRoot 'controllers\progression_sequence_3d\progression_sequence_3d.py') -PathType Leaf)) 'Windows release still depends on an Activity 1 Python observer.'
$altitudeObserverRelative = 'controllers\progression_altitude_v1\progression_altitude_v1.exe'
$altitudeObserverSource = Join-Path $releaseRepo $altitudeObserverRelative
$altitudeObserverPackaged = Join-Path $testRoot $altitudeObserverRelative
Assert-Release ((Get-FileHash -LiteralPath $altitudeObserverSource -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $altitudeObserverPackaged -Algorithm SHA256).Hash) 'Packaged Activity 2 native supervisor differs from the exact Webots build.'
$altitudeObserverBytes = [System.IO.File]::ReadAllBytes($altitudeObserverPackaged)
Assert-Release ($altitudeObserverBytes.Length -gt 2 -and $altitudeObserverBytes[0] -eq 0x4d -and $altitudeObserverBytes[1] -eq 0x5a) 'Activity 2 observer is not a Windows PE executable.'
Assert-Release (-not (Test-Path -LiteralPath (Join-Path $testRoot 'controllers\progression_altitude_v1\progression_altitude_v1.py') -PathType Leaf)) 'Windows release must not depend on a Python Activity 2 oracle.'
$schoolSource = Join-Path $releaseRepo 'controllers\crazyflie_classroom_v2\crazyflie_classroom_v2.exe'
$schoolPackaged = Join-Path $testRoot 'controllers\crazyflie_classroom_v2\crazyflie_classroom_v2.exe'
Assert-Release ((Get-FileHash -LiteralPath $schoolSource -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $schoolPackaged -Algorithm SHA256).Hash) 'Packaged school pilot differs from the exact independently built executable.'
$schoolBytes = [System.IO.File]::ReadAllBytes($schoolPackaged)
Assert-Release ($schoolBytes.Length -gt 2 -and $schoolBytes[0] -eq 0x4d -and $schoolBytes[1] -eq 0x5a) 'School pilot is not a Windows PE executable.'
$sceneText = Get-Content -LiteralPath $scenePackaged -Raw
Assert-Release ($sceneText -match 'controller "progression_sequence_3d"\s+supervisor TRUE') 'Packaged scene does not bind its isolated observer.'
$altitudeSceneText = Get-Content -LiteralPath $altitudeScenePackaged -Raw
Assert-Release ($altitudeSceneText -match 'controller "progression_altitude_v1"\s+supervisor TRUE') 'Packaged Activity 2 scene does not bind the native C evaluator.'
Assert-Release ($altitudeSceneText.Contains('DEF ACTIVITY2_START_CANOPY Solid')) 'Packaged Activity 2 scene lost the real collision roof.'
Assert-Release ($worldText.Contains('DEF WEBEEBLOCKS_CLASSROOM_START_WORLD WorldInfo {')) 'Release must open the typed neutral classroom world.'
Assert-Release (-not $worldText.Contains('DEF WEBEEBLOCKS_LEGACY_SCENE')) 'Legacy scenario was preloaded before activity selection.'
Assert-Release (-not $worldText.Contains('DEF WEBEEBLOCKS_LEGACY_EVALUATORS')) 'Legacy evaluators were preloaded before activity selection.'
foreach ($scene in @('legacy-scene-v1.wbo', 'legacy-evaluators-v1.wbo')) {
  $source = Join-Path $releaseRepo "worlds\scenes\$scene"
  $packaged = Join-Path $testRoot "worlds\scenes\$scene"
  Assert-Release ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $packaged -Algorithm SHA256).Hash) "Restoration scene differs from exact source: $scene"
}
# All four default Floor maps must be local, unchanged pinned R2025a bytes.
foreach ($map in @('base_color', 'roughness', 'normal', 'occlusion')) {
  $texture = "chequered_parquetry_${map}.jpg"
  $relative = "worlds\textures\parquetry\$texture"
  $packaged = Join-Path $testRoot $relative
  $upstream = Join-Path $releaseRepo ".ci-webots-r2025a\projects\appearances\protos\textures\parquetry\$texture"
  Assert-Release (Test-Path -LiteralPath $packaged -PathType Leaf) "Missing default floor map: $relative"
  Assert-Release ((Get-FileHash -LiteralPath $packaged -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $upstream -Algorithm SHA256).Hash) "Altered default floor map: $relative"
  Assert-Release ($worldText.Contains("textures/parquetry/$texture")) "Unused default floor map: $relative"
}
Assert-Release ($worldText.Contains('textureTransform TextureTransform { scale 8 8 }')) 'Default floor must repeat at 0.50 m on the 4 m floor.'
$windowPattern = '(?m)^\s*window\s+"' + [regex]::Escape($robotWindowName) + '"\s*$'
Assert-Release ($worldText -match $windowPattern) 'Packaged world does not select the content-addressed Robot Window.'
Assert-Release ($worldText -notmatch '(?m)^\s*window\s+"blockly_v2"\s*$') 'Packaged world still selects the stale top-level Robot Window identity.'

$runtimeIni = Get-Content -LiteralPath (Join-Path $testRoot 'controllers\crazyflie_runtime_v2\runtime.ini') -Raw
Assert-Release ($runtimeIni -match '(?m)^\[environment variables with paths\]\r?$') 'Controller runtime.ini lacks the path-aware environment section.'
Assert-Release ($runtimeIni -match '(?m)^WEBOTS_LIBRARY_PATH\s*=\s*\$\(WEBOTS_HOME\)/lib/controller:\$\(WEBOTS_HOME\)/msys64/mingw64/bin\r?$') 'Controller runtime.ini does not bind the prebuilt executable to Webots R2025a libraries.'

$schoolRuntimeIni = Get-Content -LiteralPath (Join-Path $testRoot 'controllers\crazyflie_classroom_v2\runtime.ini') -Raw
Assert-Release ($schoolRuntimeIni -ceq $runtimeIni) 'School pilot does not inherit the exact pinned Webots/Qt runtime closure.'
$forbidden = @(Get-ChildItem -LiteralPath $testRoot -Recurse -Force | Where-Object {
  $_.Name -in @('node_modules', 'package.json', 'package-lock.json', 'Makefile') -or
  $_.Extension -in @('.c', '.o', '.a')
})
$forbiddenPaths = @($forbidden | ForEach-Object { $_.FullName })
Assert-Release ($forbidden.Count -eq 0) ("Development-only release paths: " + ($forbiddenPaths -join ', '))

$runtimeText = Get-ChildItem -LiteralPath $testRoot -Recurse -File | Where-Object {
  $_.Extension -in @('.wbt', '.wbo', '.proto', '.html', '.css') -or $_.Name -in @('main.js', 'project_ui.js')
}
foreach ($file in $runtimeText) {
  if ($file.Extension -in @('.wbt', '.wbo', '.proto')) {
    $pattern = '(?i)"(?:https?|webots)://'
  }
  else {
    $pattern = '(?i)(https?://|//cdn\.)'
  }
  $matches = Select-String -LiteralPath $file.FullName -Pattern $pattern
  Assert-Release ($null -eq $matches) "Remote runtime dependency in $($file.FullName)"
}

$exe = Join-Path $testRoot 'controllers\crazyflie_runtime_v2\crazyflie_runtime_v2.exe'
$bytes = [System.IO.File]::ReadAllBytes($exe)
Assert-Release ($bytes.Length -gt 2 -and $bytes[0] -eq 0x4d -and $bytes[1] -eq 0x5a) 'Controller is not a Windows PE executable.'

Get-ChildItem -LiteralPath (Join-Path $testRoot 'plugins') -Recurse -File -Filter '*.js' | ForEach-Object {
  & node --check $_.FullName
  if ($LASTEXITCODE -ne 0) { throw "JavaScript syntax failure in $($_.FullName)" }
}

$windowsPowerShellMajor = (& powershell.exe -NoLogo -NoProfile -Command '$PSVersionTable.PSVersion.Major' | Out-String).Trim()
Assert-Release ($LASTEXITCODE -eq 0 -and $windowsPowerShellMajor -eq '5') "Expected Windows PowerShell 5.1 for the packaged launcher, got major version '$windowsPowerShellMajor'."

# Exercise the exact packaged CMD local-profile selection on a real Windows
# runner. The production PowerShell launcher is replaced only in this isolated
# harness so no interactive Webots session is required. The stub records the
# Chrome executable/profile environment handed off by the CMD. Existing Webots
# RobotWindow preferences are deliberately seeded and must remain byte-for-byte
# semantically unchanged: the supported launch path no longer mutates them.
$launcherHarness = Join-Path $env:RUNNER_TEMP 'WebeeBlocks launcher profile probe with spaces'
if (Test-Path -LiteralPath $launcherHarness) {
  Remove-Item -LiteralPath $launcherHarness -Recurse -Force
}
New-Item -ItemType Directory -Path $launcherHarness | Out-Null
$launcherCmdPath = Join-Path $launcherHarness 'Launch-WebeeBlocks.cmd'
Copy-Item -LiteralPath (Join-Path $testRoot 'Launch-WebeeBlocks.cmd') -Destination $launcherCmdPath
$launcherCmdText = Get-Content -LiteralPath $launcherCmdPath -Raw
Assert-Release ($launcherCmdText -notmatch '(?i)\breg\.exe\b') 'Packaged CMD must not mutate Webots RobotWindow registry preferences.'
Assert-Release ($launcherCmdText -notmatch 'WebeeBlocks-Chrome\.cmd') 'Packaged CMD must not depend on a generated Chrome helper.'
Set-Content -LiteralPath (Join-Path $launcherHarness 'Launch-WebeeBlocks.ps1') -Value @'
$root = Split-Path $MyInvocation.MyCommand.Path -Parent
Set-Content -LiteralPath (Join-Path $root 'chrome-exe.txt') -Value $env:WEBEEBLOCKS_CHROME_EXE -Encoding UTF8
Set-Content -LiteralPath (Join-Path $root 'chrome-profile.txt') -Value $env:WEBEEBLOCKS_CHROME_PROFILE -Encoding UTF8
exit 0
'@ -Encoding Ascii

$fakeProgramFiles = Join-Path $launcherHarness 'Program Files'
$fakeChrome = Join-Path $fakeProgramFiles 'Google\Chrome\Application\chrome.exe'
New-Item -ItemType Directory -Path (Split-Path $fakeChrome -Parent) -Force | Out-Null
Set-Content -LiteralPath $fakeChrome -Value '' -Encoding Ascii
$launcherProbeCmd = Join-Path $launcherHarness 'Run-Launch-WebeeBlocks-Probe.cmd'
$fakeProgramFilesForCmd = $fakeProgramFiles.Replace('%', '%%')
Set-Content -LiteralPath $launcherProbeCmd -Value @"
@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "ProgramFiles=$fakeProgramFilesForCmd"
call "%~dp0Launch-WebeeBlocks.cmd" <nul
exit /b %errorlevel%
"@ -Encoding Ascii

$registryKey = 'HKCU\Software\Cyberbotics\Webots-R2025a\RobotWindow'
$registryProviderKey = 'Registry::HKEY_CURRENT_USER\Software\Cyberbotics\Webots-R2025a\RobotWindow'
$registryBackup = Join-Path $launcherHarness 'robot-window-before.reg'
& reg.exe query $registryKey *> $null
$registryExisted = $LASTEXITCODE -eq 0
if ($registryExisted) {
  & reg.exe export $registryKey $registryBackup /y *> $null
  if ($LASTEXITCODE -ne 0) { throw 'Could not snapshot the runner RobotWindow registry key before the launcher probe.' }
}

$oldLocalAppData = $env:LOCALAPPDATA
try {
  $env:LOCALAPPDATA = Join-Path $launcherHarness 'Local AppData'
  New-Item -ItemType Directory -Path $env:LOCALAPPDATA -Force | Out-Null

  & reg.exe add $registryKey /v browser /t REG_SZ /d 'sentinel-browser.exe' /f *> $null
  if ($LASTEXITCODE -ne 0) { throw 'Could not seed the RobotWindow browser sentinel for the launcher probe.' }
  & reg.exe add $registryKey /v newBrowserWindow /t REG_DWORD /d 1 /f *> $null
  if ($LASTEXITCODE -ne 0) { throw 'Could not seed the RobotWindow window-mode sentinel for the launcher probe.' }

  Push-Location $launcherHarness
  try {
    & $env:ComSpec /d /c 'Run-Launch-WebeeBlocks-Probe.cmd'
    $launcherCmdExit = $LASTEXITCODE
  }
  finally {
    Pop-Location
  }

  Assert-Release ($launcherCmdExit -eq 0) "Packaged Launch-WebeeBlocks.cmd failed its local Chrome profile probe (exit $launcherCmdExit)."
  $localProfile = Join-Path $env:LOCALAPPDATA 'WebeeBlocks\Chrome-R2025a'
  Assert-Release (Test-Path -LiteralPath $localProfile -PathType Container) 'Packaged CMD did not create the dedicated local Chrome profile directory.'
  $probeFiles = @(Get-ChildItem -LiteralPath $localProfile -File -Filter '.webeeblocks-write-*.tmp' -ErrorAction SilentlyContinue)
  Assert-Release ($probeFiles.Count -eq 0) 'Packaged CMD left its Chrome profile write probe behind.'

  $observedChrome = (Get-Content -LiteralPath (Join-Path $launcherHarness 'chrome-exe.txt') -Raw).Trim()
  $observedProfile = (Get-Content -LiteralPath (Join-Path $launcherHarness 'chrome-profile.txt') -Raw).Trim()
  Assert-Release ($observedChrome -eq $fakeChrome) "Packaged CMD handed off the wrong Chrome executable: $observedChrome"
  Assert-Release ($observedProfile -eq $localProfile) "Packaged CMD handed off the wrong dedicated local Chrome profile: $observedProfile"
  Assert-Release (-not (Test-Path -LiteralPath (Join-Path $env:LOCALAPPDATA 'WebeeBlocks\WebeeBlocks-Chrome.cmd'))) 'Packaged CMD unexpectedly generated a Chrome helper.'

  $untouchedRobotWindow = Get-ItemProperty -LiteralPath $registryProviderKey
  Assert-Release ([string]$untouchedRobotWindow.browser -eq 'sentinel-browser.exe') 'Packaged CMD modified the prior RobotWindow browser preference.'
  Assert-Release ([int]$untouchedRobotWindow.newBrowserWindow -eq 1) 'Packaged CMD modified the prior RobotWindow window-mode preference.'
}
finally {
  $env:LOCALAPPDATA = $oldLocalAppData
  & reg.exe delete $registryKey /f *> $null
  if ($registryExisted -and (Test-Path -LiteralPath $registryBackup -PathType Leaf)) {
    & reg.exe import $registryBackup *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Could not restore the runner RobotWindow registry key after the launcher probe.' }
  }
  if (Test-Path -LiteralPath $launcherHarness) {
    Remove-Item -LiteralPath $launcherHarness -Recurse -Force
  }
}

$launcher = Join-Path $testRoot 'Launch-WebeeBlocks.ps1'
& powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $launcher -ValidateOnly -WebotsHome $WebotsHome
if ($LASTEXITCODE -ne 0) { throw 'Release launcher validation failed under Windows PowerShell 5.1.' }

# GitHub-hosted Windows has no trustworthy interactive Webots/Robot Window session.
# Prove the diagnosed product boundary directly instead: the executable extracted
# from the exact ZIP must load with the Webots controller libraries, the MinGW
# C++ runtime directory inherited from the official R2025a launcher, and the
# Qt/MSYS2 bin directory declared by runtime.ini (plus Windows system DLL
# locations), enter libController, and reach its deterministic IPC connection
# path. A missing runtime DLL fails before this marker and therefore cannot pass
# this oracle.
# Both native flight executables must load from the exact extracted ZIP:
# the historic evaluator runtime AND the pupil's school-only scene adapter.
$nativePilots = @(
  [PSCustomObject]@{ Label = 'historical'; Path = $exe }
  [PSCustomObject]@{ Label = 'school'; Path = $schoolPackaged }
)
foreach ($candidate in $nativePilots) {
$probeExe = $candidate.Path
$controllerStdout = Join-Path $env:RUNNER_TEMP "webeeblocks-$($candidate.Label).stdout.log"
$controllerStderr = Join-Path $env:RUNNER_TEMP "webeeblocks-$($candidate.Label).stderr.log"
Remove-Item -LiteralPath $controllerStdout, $controllerStderr -Force -ErrorAction SilentlyContinue
$oldWebotsHome = $env:WEBOTS_HOME
$oldControllerUrl = $env:WEBOTS_CONTROLLER_URL
$oldPath = $env:PATH
$process = $null
try {
  $env:WEBOTS_HOME = $WebotsHome
  $env:WEBOTS_CONTROLLER_URL = 'ipc://65535'
  $env:PATH = @(
    (Join-Path $WebotsHome 'lib\controller'),
    (Join-Path $WebotsHome 'msys64\mingw64\bin\cpp'),
    (Join-Path $WebotsHome 'msys64\mingw64\bin'),
    (Join-Path $env:SystemRoot 'System32'),
    $env:SystemRoot
  ) -join ';'

  $process = Start-Process `
    -FilePath $probeExe `
    -WorkingDirectory (Split-Path $probeExe -Parent) `
    -RedirectStandardOutput $controllerStdout `
    -RedirectStandardError $controllerStderr `
    -PassThru

  $enteredLibController = $false
  $deadline = [DateTime]::UtcNow.AddSeconds(8)
  do {
    Start-Sleep -Milliseconds 250
    $stderr = if (Test-Path -LiteralPath $controllerStderr) { Get-Content -LiteralPath $controllerStderr -Raw } else { '' }
    if ($stderr -match 'Cannot connect to Webots instance') {
      $enteredLibController = $true
      break
    }
    $process.Refresh()
    if ($process.HasExited) { break }
  } while ([DateTime]::UtcNow -lt $deadline)

  if (-not $enteredLibController) {
    $process.Refresh()
    $exitDetail = if ($process.HasExited) { "exit=$($process.ExitCode)" } else { 'timeout' }
    $stdout = if (Test-Path -LiteralPath $controllerStdout) { Get-Content -LiteralPath $controllerStdout -Raw } else { '<no stdout>' }
    $stderr = if (Test-Path -LiteralPath $controllerStderr) { Get-Content -LiteralPath $controllerStderr -Raw } else { '<no stderr>' }
    throw "Packaged controller did not enter the Webots controller runtime ($exitDetail).`nSTDOUT:`n$stdout`nSTDERR:`n$stderr"
  }
}
finally {
  if ($null -ne $process) {
    $process.Refresh()
    if (-not $process.HasExited) {
      Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
      $process.WaitForExit()
    }
  }
  $env:WEBOTS_HOME = $oldWebotsHome
  $env:WEBOTS_CONTROLLER_URL = $oldControllerUrl
  $env:PATH = $oldPath
}

}
# Probe the exact extracted second native controller independently of the
# flight runtime. A missing dependent DLL must fail before libController's IPC
# message; this does not substitute for a Webots scene/flight acceptance test.
$observerStdout = Join-Path $env:RUNNER_TEMP 'webeeblocks-observer.stdout.log'
$observerStderr = Join-Path $env:RUNNER_TEMP 'webeeblocks-observer.stderr.log'
Remove-Item -LiteralPath $observerStdout, $observerStderr -Force -ErrorAction SilentlyContinue
$oldWebotsHome = $env:WEBOTS_HOME
$oldControllerUrl = $env:WEBOTS_CONTROLLER_URL
$oldPath = $env:PATH
$observerProcess = $null
try {
  $env:WEBOTS_HOME = $WebotsHome
  $env:WEBOTS_CONTROLLER_URL = 'ipc://65535'
  $env:PATH = @(
    (Join-Path $WebotsHome 'lib\controller'),
    (Join-Path $WebotsHome 'msys64\mingw64\bin\cpp'),
    (Join-Path $WebotsHome 'msys64\mingw64\bin'),
    (Join-Path $env:SystemRoot 'System32'),
    $env:SystemRoot
  ) -join ';'
  $observerProcess = Start-Process `
    -FilePath $observerPackaged `
    -WorkingDirectory (Split-Path $observerPackaged -Parent) `
    -RedirectStandardOutput $observerStdout `
    -RedirectStandardError $observerStderr `
    -PassThru
  $observerEnteredController = $false
  $deadline = [DateTime]::UtcNow.AddSeconds(8)
  do {
    Start-Sleep -Milliseconds 250
    $stderr = if (Test-Path -LiteralPath $observerStderr) { Get-Content -LiteralPath $observerStderr -Raw } else { '' }
    if ($stderr -match 'Cannot connect to Webots instance') {
      $observerEnteredController = $true
      break
    }
    $observerProcess.Refresh()
    if ($observerProcess.HasExited) { break }
  } while ([DateTime]::UtcNow -lt $deadline)
  if (-not $observerEnteredController) {
    $observerProcess.Refresh()
    $exitDetail = if ($observerProcess.HasExited) { "exit=$($observerProcess.ExitCode)" } else { 'timeout' }
    $stdout = if (Test-Path -LiteralPath $observerStdout) { Get-Content -LiteralPath $observerStdout -Raw } else { '<no stdout>' }
    $stderr = if (Test-Path -LiteralPath $observerStderr) { Get-Content -LiteralPath $observerStderr -Raw } else { '<no stderr>' }
    throw "Packaged Activity 1 observer failed to enter libController ($exitDetail).`nSTDOUT:`n$stdout`nSTDERR:`n$stderr"
  }
}
finally {
  if ($null -ne $observerProcess) {
    $observerProcess.Refresh()
    if (-not $observerProcess.HasExited) {
      Stop-Process -Id $observerProcess.Id -Force -ErrorAction SilentlyContinue
      $observerProcess.WaitForExit()
    }
  }
  $env:WEBOTS_HOME = $oldWebotsHome
  $env:WEBOTS_CONTROLLER_URL = $oldControllerUrl
  $env:PATH = $oldPath
}
# Probe the exact extracted Activity 2 native controller independently of the
# flight runtime. A missing dependent DLL must fail before libController's IPC
# message; this does not substitute for a Webots scene/flight acceptance test.
$altitudeObserverStdout = Join-Path $env:RUNNER_TEMP 'webeeblocks-altitude-observer.stdout.log'
$altitudeObserverStderr = Join-Path $env:RUNNER_TEMP 'webeeblocks-altitude-observer.stderr.log'
Remove-Item -LiteralPath $altitudeObserverStdout, $altitudeObserverStderr -Force -ErrorAction SilentlyContinue
$oldWebotsHome = $env:WEBOTS_HOME
$oldControllerUrl = $env:WEBOTS_CONTROLLER_URL
$oldPath = $env:PATH
$altitudeObserverProcess = $null
try {
  $env:WEBOTS_HOME = $WebotsHome
  $env:WEBOTS_CONTROLLER_URL = 'ipc://65535'
  $env:PATH = @(
    (Join-Path $WebotsHome 'lib\controller'),
    (Join-Path $WebotsHome 'msys64\mingw64\bin\cpp'),
    (Join-Path $WebotsHome 'msys64\mingw64\bin'),
    (Join-Path $env:SystemRoot 'System32'),
    $env:SystemRoot
  ) -join ';'
  $altitudeObserverProcess = Start-Process `
    -FilePath $altitudeObserverPackaged `
    -WorkingDirectory (Split-Path $altitudeObserverPackaged -Parent) `
    -RedirectStandardOutput $altitudeObserverStdout `
    -RedirectStandardError $altitudeObserverStderr `
    -PassThru
  $altitudeObserverEnteredController = $false
  $deadline = [DateTime]::UtcNow.AddSeconds(8)
  do {
    Start-Sleep -Milliseconds 250
    $stderr = if (Test-Path -LiteralPath $altitudeObserverStderr) { Get-Content -LiteralPath $altitudeObserverStderr -Raw } else { '' }
    if ($stderr -match 'Cannot connect to Webots instance') {
      $altitudeObserverEnteredController = $true
      break
    }
    $altitudeObserverProcess.Refresh()
    if ($altitudeObserverProcess.HasExited) { break }
  } while ([DateTime]::UtcNow -lt $deadline)
  if (-not $altitudeObserverEnteredController) {
    $altitudeObserverProcess.Refresh()
    $exitDetail = if ($altitudeObserverProcess.HasExited) { "exit=$($altitudeObserverProcess.ExitCode)" } else { 'timeout' }
    $stdout = if (Test-Path -LiteralPath $altitudeObserverStdout) { Get-Content -LiteralPath $altitudeObserverStdout -Raw } else { '<no stdout>' }
    $stderr = if (Test-Path -LiteralPath $altitudeObserverStderr) { Get-Content -LiteralPath $altitudeObserverStderr -Raw } else { '<no stderr>' }
    throw "Packaged Activity 2 observer failed to enter libController ($exitDetail).`nSTDOUT:`n$stdout`nSTDERR:`n$stderr"
  }
}
finally {
  if ($null -ne $altitudeObserverProcess) {
    $altitudeObserverProcess.Refresh()
    if (-not $altitudeObserverProcess.HasExited) {
      Stop-Process -Id $altitudeObserverProcess.Id -Force -ErrorAction SilentlyContinue
      $altitudeObserverProcess.WaitForExit()
    }
  }
  $env:WEBOTS_HOME = $oldWebotsHome
  $env:WEBOTS_CONTROLLER_URL = $oldControllerUrl
  $env:PATH = $oldPath
}
Write-Host "PASS: Windows classroom archive has the verified pupil school gate, original evaluator controller, Activity 1 native supervisor, no Python runtime dependency, and all four PE/IPC load witnesses ($($manifestEntries.Count) files)."

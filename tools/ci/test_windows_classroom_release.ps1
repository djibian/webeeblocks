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
  "${robotWindowRelative}\${robotWindowName}.html",
  "${robotWindowRelative}\vendor\VERSION",
  "${robotWindowRelative}\vendor\blockly_compressed.js",
  "${robotWindowRelative}\webots\RobotWindow.js",
  'plugins\robot_windows\blockly\webeeblocks\semantic_ast.js',
  'plugins\robot_windows\blockly\webeeblocks\project_files.js',
  'plugins\robot_windows\blockly\google-blockly-31ee4ea\blocks\crazyflie_v2.js',
  'protos\Crazyflie.proto',
  'protos\meshes\cf2_assembly.dae',
  'protos\meshes\ccw_prop.dae',
  'protos\textures\fast_helix.png',
  'worlds\crazyflie_runtime_v2.wbt'
)
foreach ($relative in $required) {
  Assert-Release (Test-Path -LiteralPath (Join-Path $testRoot $relative) -PathType Leaf) "Missing required release path: $relative"
}

$version = (Get-Content -LiteralPath (Join-Path $robotWindowRoot 'vendor\VERSION') -Raw).Trim()
Assert-Release ($version -eq '13.2.1') "Unexpected Blockly release version: $version"

$worldPath = Join-Path $testRoot 'worlds\crazyflie_runtime_v2.wbt'
$worldText = Get-Content -LiteralPath $worldPath -Raw
$windowPattern = '(?m)^\s*window\s+"' + [regex]::Escape($robotWindowName) + '"\s*$'
Assert-Release ($worldText -match $windowPattern) 'Packaged world does not select the content-addressed Robot Window.'
Assert-Release ($worldText -notmatch '(?m)^\s*window\s+"blockly_v2"\s*$') 'Packaged world still selects the stale top-level Robot Window identity.'

$runtimeIni = Get-Content -LiteralPath (Join-Path $testRoot 'controllers\crazyflie_runtime_v2\runtime.ini') -Raw
Assert-Release ($runtimeIni -match '(?m)^\[environment variables with paths\]\r?$') 'Controller runtime.ini lacks the path-aware environment section.'
Assert-Release ($runtimeIni -match '(?m)^WEBOTS_LIBRARY_PATH\s*=\s*\$\(WEBOTS_HOME\)/lib/controller:\$\(WEBOTS_HOME\)/msys64/mingw64/bin\r?$') 'Controller runtime.ini does not bind the prebuilt executable to Webots R2025a libraries.'

$forbidden = @(Get-ChildItem -LiteralPath $testRoot -Recurse -Force | Where-Object {
  $_.Name -in @('node_modules', 'package.json', 'package-lock.json', 'Makefile') -or
  $_.Extension -in @('.c', '.o', '.a')
})
$forbiddenPaths = @($forbidden | ForEach-Object { $_.FullName })
Assert-Release ($forbidden.Count -eq 0) ("Development-only release paths: " + ($forbiddenPaths -join ', '))

$runtimeText = Get-ChildItem -LiteralPath $testRoot -Recurse -File | Where-Object {
  $_.Extension -in @('.wbt', '.proto', '.html', '.css') -or $_.Name -in @('main.js', 'project_ui.js')
}
foreach ($file in $runtimeText) {
  if ($file.Extension -in @('.wbt', '.proto')) {
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
$oldProgramFiles = $env:ProgramFiles
try {
  $env:LOCALAPPDATA = Join-Path $launcherHarness 'Local AppData'
  $env:ProgramFiles = $fakeProgramFiles
  New-Item -ItemType Directory -Path $env:LOCALAPPDATA -Force | Out-Null

  & reg.exe add $registryKey /v browser /t REG_SZ /d 'sentinel-browser.exe' /f *> $null
  if ($LASTEXITCODE -ne 0) { throw 'Could not seed the RobotWindow browser sentinel for the launcher probe.' }
  & reg.exe add $registryKey /v newBrowserWindow /t REG_DWORD /d 1 /f *> $null
  if ($LASTEXITCODE -ne 0) { throw 'Could not seed the RobotWindow window-mode sentinel for the launcher probe.' }

  Push-Location $launcherHarness
  try {
    & $env:ComSpec /d /c 'Launch-WebeeBlocks.cmd <nul'
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
  $env:ProgramFiles = $oldProgramFiles
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
$controllerStdout = Join-Path $env:RUNNER_TEMP 'webeeblocks-packaged-controller.stdout.log'
$controllerStderr = Join-Path $env:RUNNER_TEMP 'webeeblocks-packaged-controller.stderr.log'
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
    -FilePath $exe `
    -WorkingDirectory (Split-Path $exe -Parent) `
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

Write-Host "PASS: Windows classroom archive is self-contained, checksummed, path-safe, cache-isolated, launcher-ready and its packaged controller loads through the declared Webots R2025a runtime ($($manifestEntries.Count) files)."

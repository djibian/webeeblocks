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

$required = @(
  'Launch-WebeeBlocks.cmd',
  'Launch-WebeeBlocks.ps1',
  'README-WINDOWS.md',
  'WINDOWS-ACCEPTANCE.md',
  'controllers\crazyflie_runtime_v2\crazyflie_runtime_v2.exe',
  'controllers\crazyflie_runtime_v2\runtime.ini',
  'plugins\robot_windows\blockly_v2\blockly_v2.html',
  'plugins\robot_windows\blockly_v2\vendor\VERSION',
  'plugins\robot_windows\blockly_v2\vendor\blockly_compressed.js',
  'plugins\robot_windows\blockly_v2\webots\RobotWindow.js',
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

$version = (Get-Content -LiteralPath (Join-Path $testRoot 'plugins\robot_windows\blockly_v2\vendor\VERSION') -Raw).Trim()
Assert-Release ($version -eq '13.2.1') "Unexpected Blockly release version: $version"

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

& (Join-Path $testRoot 'Launch-WebeeBlocks.ps1') -ValidateOnly -WebotsHome $WebotsHome
if ($LASTEXITCODE -ne 0) { throw 'Release launcher validation failed.' }

$webotsExe = Join-Path $WebotsHome 'msys64\mingw64\bin\webots.exe'
Assert-Release (Test-Path -LiteralPath $webotsExe -PathType Leaf) 'Webots console executable is missing for packaged startup proof.'
$world = Join-Path $testRoot 'worlds\crazyflie_runtime_v2.wbt'
$stdoutPath = Join-Path $env:RUNNER_TEMP 'webeeblocks-packaged-runtime.stdout.log'
$stderrPath = Join-Path $env:RUNNER_TEMP 'webeeblocks-packaged-runtime.stderr.log'
Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
if ($world.Contains('"')) { throw 'The packaged world path contains an unsupported quote.' }
$webotsArguments = '--stdout --stderr --batch --minimize --no-rendering --mode=fast "' + $world + '"'
$oldQtOpenGl = $env:QT_OPENGL
try {
  # Keep the native Windows Qt platform plugin selected by the installed Webots
  # runtime. The Windows package ships qwindows.dll; forcing an unavailable
  # offscreen QPA backend makes Webots terminate before loading the world.
  # Software OpenGL remains CI-only and does not alter the packaged controller.
  $env:QT_OPENGL = 'software'
  $process = Start-Process `
    -FilePath $webotsExe `
    -ArgumentList $webotsArguments `
    -WorkingDirectory $testRoot `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -PassThru
}
finally {
  $env:QT_OPENGL = $oldQtOpenGl
}
$ready = $false
$earlyExitCode = $null
try {
  $deadline = [DateTime]::UtcNow.AddSeconds(35)
  do {
    Start-Sleep -Seconds 1
    $stdout = if (Test-Path -LiteralPath $stdoutPath) { Get-Content -LiteralPath $stdoutPath -Raw } else { '' }
    if ($stdout -match '(?m)^WEBEEBLOCKS_RUNTIME_V2 READY\s*$') {
      $ready = $true
      break
    }
    $process.Refresh()
    if ($process.HasExited) {
      $earlyExitCode = $process.ExitCode
      break
    }
  } while ([DateTime]::UtcNow -lt $deadline)
}
finally {
  $process.Refresh()
  if (-not $process.HasExited) {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    $process.WaitForExit()
  }
}
if (-not $ready) {
  $stdout = if (Test-Path -LiteralPath $stdoutPath) { Get-Content -LiteralPath $stdoutPath -Raw } else { '<no stdout>' }
  $stderr = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw } else { '<no stderr>' }
  $exitDetail = if ($null -eq $earlyExitCode) { 'timeout' } else { "exit=$earlyExitCode" }
  throw "Packaged Webots world never reached controller READY ($exitDetail).`nSTDOUT:`n$stdout`nSTDERR:`n$stderr"
}

Write-Host "PASS: Windows classroom archive is self-contained, checksummed, path-safe, launcher-ready and starts its packaged controller ($($manifestEntries.Count) files)."

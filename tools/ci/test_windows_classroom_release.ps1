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

# GitHub-hosted Windows has no trustworthy interactive Webots/Robot Window session.
# Prove the diagnosed product boundary directly instead: the executable extracted
# from the exact ZIP must load with only the two Webots runtime directories that
# runtime.ini declares (plus Windows system DLL locations), enter libController,
# and reach its deterministic IPC connection path. A missing runtime DLL fails
# before this marker and therefore cannot pass this oracle.
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

Write-Host "PASS: Windows classroom archive is self-contained, checksummed, path-safe, launcher-ready and its packaged controller loads through the declared Webots R2025a runtime ($($manifestEntries.Count) files)."

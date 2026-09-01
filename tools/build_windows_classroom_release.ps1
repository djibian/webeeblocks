[CmdletBinding()]
param(
  [string]$OutputDirectory = 'dist',
  [Parameter(Mandatory = $true)]
  [string]$WebotsProjectsPath,
  [string]$WebotsHome = $env:WEBOTS_HOME
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$projectsRoot = (Resolve-Path -LiteralPath $WebotsProjectsPath).Path
$packageName = 'WebeeBlocks-Windows-R2025a'

if ([System.IO.Path]::IsPathRooted($OutputDirectory)) {
  $outputRoot = [System.IO.Path]::GetFullPath($OutputDirectory)
}
else {
  $outputRoot = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $OutputDirectory))
}
$packageDir = Join-Path $outputRoot $packageName
$archivePath = Join-Path $outputRoot "$packageName.zip"
if ((Split-Path $packageDir -Leaf) -ne $packageName) {
  throw 'Unsafe package output target.'
}

function Copy-RequiredFile {
  param([string]$Source, [string]$Destination)
  if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
    throw "Required release file is missing: $Source"
  }
  $parent = Split-Path $Destination -Parent
  if (-not (Test-Path -LiteralPath $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
  }
  Copy-Item -LiteralPath $Source -Destination $Destination -Force
}

function Write-Utf8NoBom {
  param([string]$Path, [string]$Content)
  $parent = Split-Path $Path -Parent
  if (-not (Test-Path -LiteralPath $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
  }
  [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($false))
}

if ([string]::IsNullOrWhiteSpace($WebotsHome)) {
  throw 'WebotsHome is required to compile the Windows controller.'
}
$webotsRoot = (Resolve-Path -LiteralPath $WebotsHome).Path
$make = Join-Path $webotsRoot 'msys64\usr\bin\make.exe'
$gcc = Join-Path $webotsRoot 'msys64\mingw64\bin\gcc.exe'
foreach ($requiredTool in @($make, $gcc)) {
  if (-not (Test-Path -LiteralPath $requiredTool -PathType Leaf)) {
    throw "Webots R2025a MSYS2 tool is missing: $requiredTool"
  }
}

& (Join-Path $PSScriptRoot 'prepare_runtime_v2.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Runtime v2 asset preparation failed.' }

$controllerDir = Join-Path $repoRoot 'controllers\crazyflie_runtime_v2'
$oldWebotsHome = $env:WEBOTS_HOME
$oldPath = $env:PATH
try {
  $env:WEBOTS_HOME = $webotsRoot
  $env:PATH = ((Join-Path $webotsRoot 'msys64\mingw64\bin'), (Join-Path $webotsRoot 'msys64\usr\bin'), $oldPath) -join ';'
  & $make -C $controllerDir clean
  if ($LASTEXITCODE -ne 0) {
    throw "Webots R2025a controller clean failed with exit code $LASTEXITCODE."
  }
  & $make -C $controllerDir
  if ($LASTEXITCODE -ne 0) {
    throw "Webots R2025a controller build failed with exit code $LASTEXITCODE."
  }
}
finally {
  $env:WEBOTS_HOME = $oldWebotsHome
  $env:PATH = $oldPath
}
$controllerBinary = Join-Path $controllerDir 'crazyflie_runtime_v2.exe'
if (-not (Test-Path -LiteralPath $controllerBinary -PathType Leaf) -or (Get-Item $controllerBinary).Length -le 0) {
  throw 'The official Webots Windows build produced no controller executable.'
}

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
if (Test-Path -LiteralPath $packageDir) {
  Remove-Item -LiteralPath $packageDir -Recurse -Force
}
if (Test-Path -LiteralPath $archivePath) {
  Remove-Item -LiteralPath $archivePath -Force
}
New-Item -ItemType Directory -Path $packageDir | Out-Null

foreach ($name in @('Launch-WebeeBlocks.cmd', 'Launch-WebeeBlocks.ps1', 'README-WINDOWS.md', 'WINDOWS-ACCEPTANCE.md', 'THIRD_PARTY_NOTICES.md')) {
  Copy-RequiredFile `
    (Join-Path $repoRoot "packaging\windows\$name") `
    (Join-Path $packageDir $name)
}

$blocklySource = Join-Path $repoRoot 'plugins\robot_windows\blockly_v2'
$blocklyTarget = Join-Path $packageDir 'plugins\robot_windows\blockly_v2'
foreach ($name in @('blockly_v2.html', 'execution_observer.css', 'main.css', 'main.js', 'project_files.css', 'project_ui.js')) {
  Copy-RequiredFile (Join-Path $blocklySource $name) (Join-Path $blocklyTarget $name)
}
foreach ($directory in @('vendor', 'webots')) {
  $source = Join-Path $blocklySource $directory
  $target = Join-Path $blocklyTarget $directory
  if (-not (Test-Path -LiteralPath $source -PathType Container)) {
    throw "Required Runtime v2 directory is missing: $source"
  }
  New-Item -ItemType Directory -Path $target -Force | Out-Null
  Copy-Item -Path (Join-Path $source '*') -Destination $target -Recurse -Force
}

$contractsSource = Join-Path $repoRoot 'plugins\robot_windows\blockly\webeeblocks'
$contractsTarget = Join-Path $packageDir 'plugins\robot_windows\blockly\webeeblocks'
New-Item -ItemType Directory -Path $contractsTarget -Force | Out-Null
Get-ChildItem -LiteralPath $contractsSource -File -Filter '*.js' | ForEach-Object {
  Copy-RequiredFile $_.FullName (Join-Path $contractsTarget $_.Name)
}
Copy-RequiredFile `
  (Join-Path $repoRoot 'plugins\robot_windows\blockly\google-blockly-31ee4ea\blocks\crazyflie_v2.js') `
  (Join-Path $packageDir 'plugins\robot_windows\blockly\google-blockly-31ee4ea\blocks\crazyflie_v2.js')
Copy-RequiredFile $controllerBinary (Join-Path $packageDir 'controllers\crazyflie_runtime_v2\crazyflie_runtime_v2.exe')

$crazyflieRoot = Join-Path $projectsRoot 'robots\bitcraze\crazyflie\protos'
$protoSource = Join-Path $crazyflieRoot 'Crazyflie.proto'
$protoText = Get-Content -LiteralPath $protoSource -Raw
$remoteTexture = 'webots://projects/default/protos/textures/fast_helix.png'
if (($protoText.Split($remoteTexture).Count - 1) -ne 1) {
  throw 'Unexpected Crazyflie.proto fast-helix dependency count.'
}
$protoText = $protoText.Replace($remoteTexture, 'textures/fast_helix.png')
if ($protoText -match '"(?:https?|webots)://') {
  throw 'Crazyflie.proto still contains a remote runtime asset.'
}
Write-Utf8NoBom (Join-Path $packageDir 'protos\Crazyflie.proto') $protoText
foreach ($mesh in @('cf2_assembly.dae', 'ccw_prop.dae')) {
  Copy-RequiredFile `
    (Join-Path $crazyflieRoot "meshes\$mesh") `
    (Join-Path $packageDir "protos\meshes\$mesh")
}
Copy-RequiredFile `
  (Join-Path $projectsRoot 'default\protos\textures\fast_helix.png') `
  (Join-Path $packageDir 'protos\textures\fast_helix.png')

$worldSource = Join-Path $repoRoot 'worlds\crazyflie_runtime_v2.wbt'
$worldText = Get-Content -LiteralPath $worldSource -Raw
$remotePrefix = 'https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/'
if (($worldText.Split($remotePrefix).Count - 1) -ne 4) {
  throw 'Expected exactly four pinned remote references in the source Runtime v2 world.'
}
$worldText = $worldText.Replace(
  'EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/robots/bitcraze/crazyflie/protos/Crazyflie.proto"',
  'EXTERNPROTO "../protos/Crazyflie.proto"'
)
foreach ($line in @(
  'EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/objects/backgrounds/protos/TexturedBackground.proto"',
  'EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/objects/backgrounds/protos/TexturedBackgroundLight.proto"',
  'EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/objects/floors/protos/Floor.proto"'
)) {
  $worldText = $worldText.Replace("$line`r`n", '').Replace("$line`n", '')
}
$worldText = $worldText.Replace('TexturedBackground { }', 'Background { skyColor [ 0.75 0.83 0.92 ] }')
$worldText = $worldText.Replace('TexturedBackgroundLight { }', 'DirectionalLight { direction -0.4 -0.5 -1 intensity 1.5 }')
$floor = @'
Solid {
  translation 0 0 -0.025
  children [
    Shape {
      appearance PBRAppearance { baseColor 0.65 0.68 0.72 roughness 0.8 }
      geometry Box { size 4 4 0.05 }
    }
  ]
  boundingObject Box { size 4 4 0.05 }
}
'@
$worldText = $worldText.Replace('Floor { size 4 4 }', $floor.TrimEnd())
if ($worldText -match '"(?:https?|webots)://') {
  throw 'The classroom world still contains a remote runtime asset.'
}
Write-Utf8NoBom (Join-Path $packageDir 'worlds\crazyflie_runtime_v2.wbt') $worldText
Copy-RequiredFile `
  (Join-Path $repoRoot 'worlds\.crazyflie_runtime_v2.wbproj') `
  (Join-Path $packageDir 'worlds\.crazyflie_runtime_v2.wbproj')

$manifestLines = Get-ChildItem -LiteralPath $packageDir -File -Recurse | Sort-Object FullName | ForEach-Object {
  $relative = [System.IO.Path]::GetRelativePath($packageDir, $_.FullName).Replace('\', '/')
  $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  "$hash  $relative"
}
Write-Utf8NoBom (Join-Path $packageDir 'MANIFEST.sha256') (($manifestLines -join "`n") + "`n")

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
  $packageDir,
  $archivePath,
  [System.IO.Compression.CompressionLevel]::Optimal,
  $false
)
if (-not (Test-Path -LiteralPath $archivePath -PathType Leaf) -or (Get-Item $archivePath).Length -le 0) {
  throw 'Windows classroom archive was not created.'
}

Write-Host "WEBEEBLOCKS_WINDOWS_RELEASE=$archivePath"

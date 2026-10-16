[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$WebotsHome,
  [Parameter(Mandatory = $true)][string]$PythonExe,
  [Parameter(Mandatory = $true)][string]$ClassroomPackagePath,
  [Parameter(Mandatory = $true)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$webotsRoot = (Resolve-Path -LiteralPath $WebotsHome).Path
$PythonExe = (Resolve-Path -LiteralPath $PythonExe).Path
$runtimeIni = Join-Path $ClassroomPackagePath 'controllers\crazyflie_runtime_v2\runtime.ini'
$runtimeText = Get-Content -LiteralPath $runtimeIni -Raw
if ($runtimeText -notmatch '(?m)^WEBOTS_LIBRARY_PATH\s*=\s*\$\(WEBOTS_HOME\)/lib/controller:\$\(WEBOTS_HOME\)/msys64/mingw64/bin\r?$') {
  throw 'The proven classroom Windows runtime closure is missing.'
}
$controller = Join-Path $repoRoot 'controllers\grand_prix_u_flight'
$make = Join-Path $webotsRoot 'msys64\usr\bin\make.exe'
$oldHome = $env:WEBOTS_HOME
$oldPath = $env:PATH
try {
  $env:WEBOTS_HOME = $webotsRoot
  $env:PATH = ((Join-Path $webotsRoot 'msys64\mingw64\bin'), (Join-Path $webotsRoot 'msys64\usr\bin'), $oldPath) -join ';'
  & $make -C $controller clean
  if ($LASTEXITCODE -ne 0) { throw 'Grand Prix controller clean failed.' }
  & $PythonExe (Join-Path $repoRoot 'tools\grand_prix\prepare_u_runtime.py')
  if ($LASTEXITCODE -ne 0) { throw 'Exact shared Runtime composition failed.' }
  & $make -C $controller
  if ($LASTEXITCODE -ne 0) { throw 'Grand Prix Windows controller build failed.' }
}
finally { $env:WEBOTS_HOME = $oldHome; $env:PATH = $oldPath }
$binary = Join-Path $controller 'grand_prix_u_flight.exe'
if (-not (Test-Path -LiteralPath $binary -PathType Leaf) -or (Get-Item -LiteralPath $binary).Length -le 0) {
  throw 'Grand Prix Windows controller executable missing.'
}
$packageName = 'WebeeBlocks-Grand-Prix-Controller-Windows-R2025a'
$output = [IO.Path]::GetFullPath($OutputDirectory)
$package = Join-Path $output $packageName
$archive = Join-Path $output "$packageName.zip"
if ((Test-Path -LiteralPath $package) -or (Test-Path -LiteralPath $archive)) { throw 'Use a fresh controller output directory.' }
$target = Join-Path $package 'controllers\grand_prix_u_flight'
New-Item -ItemType Directory -Path $target -Force | Out-Null
Copy-Item -LiteralPath $binary -Destination $target
Copy-Item -LiteralPath $runtimeIni -Destination (Join-Path $target 'runtime.ini')
Copy-Item -LiteralPath (Join-Path $repoRoot 'docs\GRAND_PRIX_WINDOWS_CONTROLLER.md') -Destination (Join-Path $package 'README.md')
$sha = (& git -C $repoRoot rev-parse HEAD | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $sha -notmatch '^[0-9a-f]{40}$') { throw 'Exact controller source SHA unavailable.' }
[IO.File]::WriteAllText((Join-Path $package 'SOURCE_SHA'), "$sha`n", [Text.UTF8Encoding]::new($false))
# Retain the exact composed C/broker inputs and unchanged native authority source.
# These are build provenance, never an alternate authority implementation.
$sourcePaths = @(
  'controllers/grand_prix_u_flight/build/runtime_u.c',
  'controllers/grand_prix_u_flight/build/file_broker_u.cpp',
  'controllers/grand_prix_u_flight/grand_prix_u_deadline.cpp',
  'controllers/crazyflie_runtime_v2/activity_scene.cpp'
)
$sourceHashes = @{}
foreach ($path in $sourcePaths) { $sourceHashes[$path] = (Get-FileHash -LiteralPath (Join-Path $repoRoot $path) -Algorithm SHA256).Hash.ToLowerInvariant() }
[IO.File]::WriteAllText((Join-Path $package 'BUILD_INPUTS.json'), (($sourceHashes | ConvertTo-Json) + "`n"), [Text.UTF8Encoding]::new($false))
$manifest = @(Get-ChildItem -LiteralPath $package -Recurse -File | Sort-Object FullName | ForEach-Object {
  $relative = [IO.Path]::GetRelativePath($package, $_.FullName).Replace('\', '/')
  $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  "$hash  $relative"
})
[IO.File]::WriteAllText((Join-Path $package 'MANIFEST.sha256'), (($manifest -join "`n") + "`n"), [Text.UTF8Encoding]::new($false))
Compress-Archive -Path (Join-Path $package '*') -DestinationPath $archive -CompressionLevel Optimal
Write-Host "WEBEEBLOCKS_GP_CONTROLLER_ARCHIVE=$archive"

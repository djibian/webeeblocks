# Build only the real variable Grand Prix route pilot; no U pilot fallback.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$WebotsHome,
  [Parameter(Mandatory=$true)][string]$PythonExe,
  [Parameter(Mandatory=$true)][string]$ClassroomPackagePath
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$webots = (Resolve-Path -LiteralPath $WebotsHome).Path
$python = (Resolve-Path -LiteralPath $PythonExe).Path
$runtimeIni = Join-Path $ClassroomPackagePath 'controllers\crazyflie_runtime_v2\runtime.ini'
if (-not (Test-Path -LiteralPath $runtimeIni -PathType Leaf)) {
  throw 'Verified classroom DLL runtime closure missing.'
}
$version = (Get-Content -LiteralPath (Join-Path $webots 'resources\version.txt') -Raw).Trim()
if ($version -cne 'R2025a') { throw "Webots version must be exactly R2025a, got $version" }
$controller = Join-Path $root 'controllers\grand_prix_route_flight'
$make = Join-Path $webots 'msys64\usr\bin\make.exe'
if (-not (Test-Path -LiteralPath $make -PathType Leaf)) { throw 'Webots MinGW make missing.' }
$oldHome=$env:WEBOTS_HOME
$oldPath=$env:PATH
try {
  $env:WEBOTS_HOME=$webots
  $env:PATH=((Join-Path $webots 'msys64\mingw64\bin'),(Join-Path $webots 'msys64\usr\bin'),$oldPath) -join ';'
  & $make -C $controller clean
  if ($LASTEXITCODE -ne 0) { throw 'Native route clean failed.' }
  & $python (Join-Path $root 'tools\grand_prix\prepare_route_runtime.py')
  if ($LASTEXITCODE -ne 0) { throw 'Native route runtime composition failed.' }
  & $make -C $controller
  if ($LASTEXITCODE -ne 0) { throw 'Native route Windows compilation failed.' }
}
finally {
  $env:WEBOTS_HOME=$oldHome
  $env:PATH=$oldPath
}
$binary=Join-Path $controller 'grand_prix_route_flight.exe'
if (-not (Test-Path -LiteralPath $binary -PathType Leaf) -or
    (Get-Item -LiteralPath $binary).Length -le 0) {
  throw 'Compiled route Windows pilot absent.'
}
Write-Host "GP_ROUTE_NATIVE_WINDOWS_BINARY=$binary"

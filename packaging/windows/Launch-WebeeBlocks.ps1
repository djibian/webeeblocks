[CmdletBinding()]
param(
  [string]$WebotsHome = $env:WEBOTS_HOME,
  [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$world = Join-Path $PSScriptRoot 'worlds\crazyflie_runtime_v2.wbt'
if (-not (Test-Path -LiteralPath $world -PathType Leaf)) {
  throw "Monde WebeeBlocks introuvable : $world"
}

$worldText = Get-Content -LiteralPath $world -Raw
if ($worldText -match '"(?:https?|webots)://') {
  throw 'Le monde de classe contient encore une ressource distante.'
}

$candidates = [System.Collections.Generic.List[string]]::new()
foreach ($home in @($WebotsHome, (Join-Path $env:ProgramFiles 'Webots'))) {
  if ([string]::IsNullOrWhiteSpace($home)) { continue }
  $candidates.Add((Join-Path $home 'msys64\mingw64\bin\webotsw.exe'))
  $candidates.Add((Join-Path $home 'msys64\mingw64\bin\webots.exe'))
}
foreach ($commandName in @('webotsw.exe', 'webots.exe')) {
  $command = Get-Command $commandName -ErrorAction SilentlyContinue
  if ($null -ne $command) { $candidates.Add($command.Source) }
}

$webots = $candidates | Where-Object {
  -not [string]::IsNullOrWhiteSpace($_) -and (Test-Path -LiteralPath $_ -PathType Leaf)
} | Select-Object -First 1
if ([string]::IsNullOrWhiteSpace($webots)) {
  throw 'Webots R2025a est introuvable. Installez-le dans C:\Program Files\Webots ou definissez WEBOTS_HOME.'
}

if ($ValidateOnly) {
  Write-Host "WEBEEBLOCKS_WINDOWS_LAUNCHER_OK webots=$webots world=$world"
  exit 0
}

if ($world.Contains('"')) { throw 'Le chemin du monde contient un guillemet non pris en charge.' }
$worldArgument = '"' + $world + '"'
Start-Process -FilePath $webots -ArgumentList @('--mode=pause', $worldArgument) -WorkingDirectory $PSScriptRoot
Write-Host 'WebeeBlocks demarre. La fenetre Blockly va s’ouvrir dans le navigateur configure par Webots.'

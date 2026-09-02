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
foreach ($candidateHome in @($WebotsHome, (Join-Path $env:ProgramFiles 'Webots'))) {
  if ([string]::IsNullOrWhiteSpace($candidateHome)) { continue }
  $candidates.Add((Join-Path $candidateHome 'msys64\mingw64\bin\webotsw.exe'))
  $candidates.Add((Join-Path $candidateHome 'msys64\mingw64\bin\webots.exe'))
}
foreach ($commandName in @('webotsw.exe', 'webots.exe')) {
  $command = Get-Command $commandName -ErrorAction SilentlyContinue
  if ($null -ne $command) { $candidates.Add($command.Source) }
}

function Test-WebotsR2025a {
  param([string]$Executable)
  if ([string]::IsNullOrWhiteSpace($Executable) -or -not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
    return $false
  }
  $versionExecutable = $Executable
  if ([System.IO.Path]::GetFileName($Executable).Equals('webotsw.exe', [System.StringComparison]::OrdinalIgnoreCase)) {
    $consoleExecutable = Join-Path (Split-Path $Executable -Parent) 'webots.exe'
    if (-not (Test-Path -LiteralPath $consoleExecutable -PathType Leaf)) { return $false }
    $versionExecutable = $consoleExecutable
  }
  $version = (& $versionExecutable --version 2>&1 | Out-String).Trim()
  return ($LASTEXITCODE -eq 0 -and $version -match 'R2025a')
}

$webots = $candidates | Where-Object { Test-WebotsR2025a -Executable $_ } | Select-Object -First 1
if ([string]::IsNullOrWhiteSpace($webots)) {
  throw 'Webots R2025a est introuvable. Installez exactement R2025a dans C:\Program Files\Webots ou definissez WEBOTS_HOME.'
}

if ($ValidateOnly) {
  Write-Host "WEBEEBLOCKS_WINDOWS_LAUNCHER_OK webots=$webots world=$world version=R2025a mode=run"
  exit 0
}

if ($world.Contains('"')) { throw 'Le chemin du monde contient un guillemet non pris en charge.' }
$worldArgument = '"' + $world + '"'
Start-Process -FilePath $webots -ArgumentList @('--mode=run', $worldArgument) -WorkingDirectory $PSScriptRoot
Write-Host "WebeeBlocks demarre. La simulation et la fenetre Blockly vont s'initialiser automatiquement."

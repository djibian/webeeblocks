[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$ArchivePath,
  [Parameter(Mandatory = $true)][string]$WebotsHome,
  [Parameter(Mandatory = $true)][string]$PythonExe
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$testRoot = Join-Path $env:RUNNER_TEMP ('Grand Prix installed project ' + [Guid]::NewGuid().ToString('N'))
Expand-Archive -LiteralPath $ArchivePath -DestinationPath $testRoot
& $PythonExe (Join-Path $PSScriptRoot 'test_grand_prix_windows_project.py') --package $testRoot
if ($LASTEXITCODE -ne 0) { throw 'Assembled project byte/asset/configuration closure failed.' }
$sha = (& git -C $repoRoot rev-parse HEAD | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or (Get-Content -LiteralPath (Join-Path $testRoot 'SOURCE_SHA') -Raw).Trim() -ne $sha) {
  throw 'Wrong assembled project source SHA.'
}
$oldSeed = $env:WEBEEBLOCKS_GP_SEED
try {
  foreach ($seed in @('0', '1', '4')) {
    $env:WEBEEBLOCKS_GP_SEED = $seed
    & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass `
      -File (Join-Path $testRoot 'Launch-WebeeBlocks.ps1') -ValidateOnly -WebotsHome $WebotsHome
    if ($LASTEXITCODE -ne 0) { throw "Installed configuration $seed launcher/session/HTTP closure failed." }
  }
  $env:WEBEEBLOCKS_GP_SEED = '../invalid'
  $diagnostic = & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass `
    -File (Join-Path $testRoot 'Launch-WebeeBlocks.ps1') -ValidateOnly -WebotsHome $WebotsHome 2>&1 | Out-String
  if ($LASTEXITCODE -eq 0 -or $diagnostic -notmatch 'Configuration Grand Prix inconnue') {
    throw 'Unknown configuration was not rejected before launch.'
  }
}
finally { $env:WEBEEBLOCKS_GP_SEED = $oldSeed }
# The exact evaluator from the final assembly must still use its own interpreter.
$env:WEBOTS_HOME = (Resolve-Path -LiteralPath $WebotsHome).Path
& (Join-Path $testRoot 'runtime\python\webeeblocks-gp-python.exe') -I `
  (Join-Path $testRoot 'controllers\grand_prix_u_evaluator\grand_prix_u_evaluator.py') --verify-imports
if ($LASTEXITCODE -ne 0) { throw 'Final assembled evaluator imports failed.' }
& $PythonExe (Join-Path $PSScriptRoot 'run_grand_prix_windows_native.py') `
  --package $testRoot --webots-home $WebotsHome --output (Join-Path $repoRoot 'ci-artifacts\gp-windows-native')
if ($LASTEXITCODE -ne 0) { throw 'Installed native Windows U campaign failed.' }
Write-Host 'PASS assembled U Windows package: exact manifests, launcher/session/HTTP closure, relocated embedded evaluator and real native missions; full pupil GUI/pedagogical acceptance remains unproven.'

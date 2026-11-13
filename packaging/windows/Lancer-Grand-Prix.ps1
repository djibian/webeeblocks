[CmdletBinding()]
param(
 [int]$Index=-1,
 [ValidateSet(25,30,60)][int]$Fps=60
)
$ErrorActionPreference='Stop'
$indexValue=$Index
if ($indexValue -lt 0) {
  $raw=Read-Host 'Parcours canonique (0 a 11, Entree = 5)'
  if ([string]::IsNullOrWhiteSpace($raw)) { $raw='5' }
  if ($raw -cnotmatch '^(?:[0-9]|10|11)$') { throw 'Parcours invalide.' }
  $indexValue=[int]$raw
}
if (-not $PSBoundParameters.ContainsKey('Fps')) {
  $raw=Read-Host 'FPS natifs Webots (60, 30, 25, Entree = 60)'
  if ([string]::IsNullOrWhiteSpace($raw)) { $raw='60' }
  if ($raw -cnotmatch '^(?:60|30|25)$') { throw 'FPS invalides.' }
  $Fps=[int]$raw
}
$env:WEBEEBLOCKS_GP_INDEX=[string]$indexValue
$env:WEBEEBLOCKS_GP_FPS=[string]$Fps
Write-Host ("Grand Prix canonique {0:D2}, rendu natif plafond {1} FPS, physique 8 ms." -f $indexValue,$Fps)
& (Join-Path $PSScriptRoot 'Launch-WebeeBlocks.cmd')
exit $LASTEXITCODE

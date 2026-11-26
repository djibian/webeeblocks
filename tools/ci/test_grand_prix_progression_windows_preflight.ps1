# Exercise the packaged selector, real PS5.1 session staging, refusals and cleanup.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Package,
  [Parameter(Mandatory=$true)][string]$WebotsHome,
  [Parameter(Mandatory=$true)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path -LiteralPath $Package).Path
$webotsRoot = (Resolve-Path -LiteralPath $WebotsHome).Path
$ps51 = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
$front = Join-Path $root 'Lancer-Progression.ps1'
$cmd = Join-Path $root 'Lancer-Progression.cmd'
$launch = Join-Path $root 'Launch-WebeeBlocks.ps1'
if (Test-Path -LiteralPath $OutputDirectory) { throw 'Use a fresh preflight evidence directory' }
$out = (New-Item -ItemType Directory -Path $OutputDirectory).FullName
$marker = 'GP_ROUTE_WINDOWS_LAUNCHER_SESSION_STAGED_OK'
$version = & $ps51 -NoProfile -Command '$PSVersionTable.PSVersion.ToString()'
if ($LASTEXITCODE -ne 0 -or "$version" -cnotmatch '^5\.1\.') {
  throw 'Windows PowerShell 5.1 required'
}
$version | Set-Content -LiteralPath (Join-Path $out 'powershell-version.txt') -Encoding UTF8
Copy-Item -LiteralPath (Join-Path $root 'SOURCE_SHA') -Destination $out
$manifest = Get-FileHash -LiteralPath (Join-Path $root 'MANIFEST.sha256') -Algorithm SHA256
function Invoke-Case {
  param([string]$Name,[string]$Exe,[string[]]$Arguments,[string]$Refusal='')
  $savedPreference = $ErrorActionPreference
  try {
    # Capture the actual child's status, including intended negative exits.
    $ErrorActionPreference = 'Continue'
    $log = (& $Exe @Arguments 2>&1 | Out-String)
    $code = $LASTEXITCODE
  } finally { $ErrorActionPreference = $savedPreference }
  $log | Set-Content -LiteralPath (Join-Path $out "$Name.log") -Encoding UTF8
  if ($Refusal) {
    if ($code -eq 0 -or $log -match $marker -or $log -notmatch $Refusal) {
      throw "Expected exact refusal in $Name (exit=$code)"
    }
  } elseif ($code -ne 0 -or ([regex]::Matches($log,$marker)).Count -ne 1) {
    throw "Missing successful session staging in $Name (exit=$code)"
  }
  if (@(Get-ChildItem -LiteralPath $root -Force -Filter '._gp_route_session_*').Count -ne 0) {
    throw "Native session staging leaked after $Name"
  }
  Write-Host "GP_PROGRESSION_PREFLIGHT_PASS $Name exit=$code"
}
$old = @($env:WEBEEBLOCKS_GP_INDEX,$env:WEBEEBLOCKS_GP_ACTIVITY,$env:WEBEEBLOCKS_GP_FPS)
try {
  $counts = @(1,1,1,3,5,5,7,12)
  $tested = 0
  for ($a=1; $a -le 8; $a++) {
    for ($v=1; $v -le $counts[$a-1]; $v++) {
      Invoke-Case -Name "A$a-V$v" -Exe $ps51 -Arguments @('-NoProfile','-ExecutionPolicy','Bypass','-File',$front,'-Activite',"$a",'-Variante',"$v",'-WebotsHome',$webotsRoot,'-ValidateOnly')
      $tested++
    }
  }
  if ($tested -ne 35) { throw 'Incomplete preflight matrix' }
  # Verify the same public .cmd entry point from a directory with spaces.
  foreach ($pair in @(@(1,1),@(8,12))) {
    Invoke-Case -Name "CMD-A$($pair[0])-V$($pair[1])" -Exe $cmd -Arguments @('-Activite',"$($pair[0])",'-Variante',"$($pair[1])",'-WebotsHome',$webotsRoot,'-ValidateOnly')
  }
  foreach ($pair in @(@(1,2),@(8,13))) {
    Invoke-Case -Name "REFUSE-A$($pair[0])-V$($pair[1])" -Exe $ps51 -Arguments @('-NoProfile','-ExecutionPolicy','Bypass','-File',$front,'-Activite',"$($pair[0])",'-Variante',"$($pair[1])",'-WebotsHome',$webotsRoot,'-ValidateOnly') -Refusal 'indisponible'
  }
  $env:WEBEEBLOCKS_GP_INDEX='0'
  $env:WEBEEBLOCKS_GP_ACTIVITY='8'
  $env:WEBEEBLOCKS_GP_FPS='20'
  Invoke-Case -Name 'REFUSE-mismatched-activity-index' -Exe $ps51 -Arguments @('-NoProfile','-ExecutionPolicy','Bypass','-File',$launch,'-WebotsHome',$webotsRoot,'-ValidateOnly') -Refusal 'Association activit.*parcours incoh'
  if ((Get-FileHash -LiteralPath (Join-Path $root 'MANIFEST.sha256') -Algorithm SHA256).Hash -cne $manifest.Hash) {
    throw 'Package manifest changed during launch preflights'
  }
  @{source_sha=(Get-Content -LiteralPath (Join-Path $root 'SOURCE_SHA') -Raw).Trim(); preflights=$tested; cmd=2; refusals=3; powershell=$version; gui='UNPROVEN'} |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $out 'result.json') -Encoding UTF8
  Write-Host 'GP_PROGRESSION_WINDOWS_PREFLIGHT_PASS 35/35 CMD=2 REFUSALS=3'
} finally {
  $env:WEBEEBLOCKS_GP_INDEX=$old[0]
  $env:WEBEEBLOCKS_GP_ACTIVITY=$old[1]
  $env:WEBEEBLOCKS_GP_FPS=$old[2]
}

# The final negative child exited nonzero by design; the harness succeeded.
exit 0

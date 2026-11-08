# Native Windows CI proof for the passive #914 collector. No Webots, GPU or network needed.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function Require([bool]$ok, [string]$message) { if (-not $ok) { throw $message } }

$root = Join-Path ([IO.Path]::GetTempPath()) ('gp-capture-test-' + [Guid]::NewGuid().ToString('N'))
$webotsHome = Join-Path $root 'Webots'
$exeDir = Join-Path $webotsHome 'msys64\mingw64\bin'
$foreignDir = Join-Path $root 'foreign'
$versionDir = Join-Path $webotsHome 'resources'
$exe = Join-Path $exeDir 'webots.exe'
$foreignExe = Join-Path $foreignDir 'webots.exe'
$source = Join-Path $PSScriptRoot '..\grand_prix\capture_windows_host.ps1'
$good = Join-Path $root 'good'
$bad = Join-Path $root 'should-not-exist'
$processes = [Collections.Generic.List[object]]::new()

try {
  New-Item -ItemType Directory -Path $exeDir, $foreignDir, $versionDir -Force | Out-Null
  # A local Windows cmd.exe renamed as webots.exe supplies a real process with
  # observable Windows PID/path/counters, without installing or running Webots.
  $cmdExe = Join-Path $env:SystemRoot 'System32\cmd.exe'
  Copy-Item -LiteralPath $cmdExe -Destination $exe
  Copy-Item -LiteralPath $cmdExe -Destination $foreignExe
  [IO.File]::WriteAllText((Join-Path $versionDir 'version.txt'), 'R2025a')

  $p = Start-Process -FilePath $exe -ArgumentList '/C ping -n 25 127.0.0.1 >NUL' -PassThru -WindowStyle Hidden
  $processes.Add($p)
  Start-Sleep -Milliseconds 300
  Require (-not $p.HasExited) 'Windows fixture process ended prematurely.'
  & $source -SourceSha ('a' * 40) -CourseId 'gp-route-v2-L2000-2500-3000-TGD-s105-H2' `
    -Variant reference -WebotsProcessId $p.Id -WebotsHome $webotsHome `
    -OutputDirectory $good -DurationSeconds 5 -SamplePeriodMs 200

  $metadata = Get-Content -LiteralPath (Join-Path $good 'metadata.json') -Raw | ConvertFrom-Json
  $samples = @(Import-Csv -LiteralPath (Join-Path $good 'samples.csv'))
  Require ($metadata.schema -eq 'webeeblocks.windows-passive-host-v1') 'Wrong metadata schema.'
  Require ($metadata.source_sha -ceq ('a' * 40)) 'Wrong exact source SHA.'
  Require ($metadata.webots_version -eq 'R2025a') 'Wrong exact Webots version.'
  Require ($metadata.webots_executable_sha256 -eq (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()) 'Wrong Webots binary digest.'
  Require ($metadata.performance_acceptance -eq 'NOT_MEASURED') 'Host observations falsely claim product performance.'
  Require ($metadata.sample_count -ge 2 -and $samples.Count -eq $metadata.sample_count) 'Host samples missing.'
  Require ([double]$samples[-1].elapsed_ms -gt [double]$samples[0].elapsed_ms) 'Non-monotonic sample times.'
  Require ($metadata.PSObject.Properties.Name -notcontains 'hostname') 'Host identity should not be exported.'

  $rejected = $false
  try {
    & $source -SourceSha ('a' * 40) -CourseId 'test' -Variant candidate `
      -WebotsProcessId $p.Id -WebotsHome $webotsHome -OutputDirectory $good `
      -DurationSeconds 5 -SamplePeriodMs 200
  } catch { $rejected = $true }
  Require $rejected 'Second trial overwrote the already captured output.'

  $other = Start-Process -FilePath $foreignExe -ArgumentList '/C ping -n 20 127.0.0.1 >NUL' -PassThru -WindowStyle Hidden
  $processes.Add($other)
  Start-Sleep -Milliseconds 200
  Require (-not $other.HasExited) 'Foreign-name fixture process ended prematurely.'
  $rejected = $false
  try {
    & $source -SourceSha ('b' * 40) -CourseId 'test' -Variant candidate `
      -WebotsProcessId $other.Id -WebotsHome $webotsHome -OutputDirectory $bad `
      -DurationSeconds 5 -SamplePeriodMs 200
  } catch { $rejected = $true }
  Require ($rejected -and -not (Test-Path -LiteralPath $bad)) 'Matching process name bypassed exact Webots executable identity.'

  Write-Host 'PASS Windows host telemetry: real PID/counters, exact Webots binary hash, no overwrite, foreign executable rejected.'
}
finally {
  foreach ($p in $processes) {
    try { $p.Refresh(); if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } } catch {}
  }
  Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}

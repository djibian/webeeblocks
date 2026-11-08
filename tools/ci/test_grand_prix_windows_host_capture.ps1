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
$exe = Join-Path $exeDir 'webots-bin.exe'
$launcherExe = Join-Path $exeDir 'webotsw.exe'
$foreignExe = Join-Path $foreignDir 'webots-bin.exe'
$browserExe = Join-Path $root 'browser.exe'
$source = Join-Path $PSScriptRoot '..\grand_prix\capture_windows_host.ps1'
$good = Join-Path $root 'good'
$bad = Join-Path $root 'should-not-exist'
$processes = [Collections.Generic.List[object]]::new()

try {
  New-Item -ItemType Directory -Path $exeDir, $foreignDir, $versionDir -Force | Out-Null
  # A renamed cmd.exe supplies real Windows PID/path/counters without Webots.
  # Test both the simulation engine name and an official-layout launcher name.
  $cmdExe = Join-Path $env:SystemRoot 'System32\cmd.exe'
  Copy-Item -LiteralPath $cmdExe -Destination $exe
  Copy-Item -LiteralPath $cmdExe -Destination $launcherExe
  Copy-Item -LiteralPath $cmdExe -Destination $foreignExe
  Copy-Item -LiteralPath $cmdExe -Destination $browserExe
  [IO.File]::WriteAllText((Join-Path $versionDir 'version.txt'), 'R2025a')

  $p = Start-Process -FilePath $exe -ArgumentList '/C ping -n 25 127.0.0.1 >NUL' -PassThru -WindowStyle Hidden
  $processes.Add($p)
  Start-Sleep -Milliseconds 300
  Require (-not $p.HasExited) 'Windows fixture process ended prematurely.'

  # Falsify privacy on an existing-but-invalid version.txt before any capture.
  [IO.File]::WriteAllText((Join-Path $versionDir 'version.txt'), 'C:\Users\PrivateProfile\confidential\tokens.txt')
  $versionError = $null
  try {
    & $source -SourceSha ('a' * 40) -CourseId 'test' -Variant candidate `
      -WebotsProcessId $p.Id -WebotsHome $webotsHome -OutputDirectory $bad `
      -DurationSeconds 5 -SamplePeriodMs 200
  } catch { $versionError = $_.Exception.Message }
  Require ($versionError -ceq 'Webots R2025a required; unsupported version metadata.' -and
           -not (Test-Path -LiteralPath $bad)) 'Invalid version metadata was disclosed or accepted.'
  [IO.File]::WriteAllText((Join-Path $versionDir 'version.txt'), 'R2025a')

$captureOutput = (& $source -SourceSha ('a' * 40) -CourseId 'gp-route-v2-L2000-2500-3000-TGD-s105-H2' `
    -Variant reference -WebotsProcessId $p.Id -WebotsHome $webotsHome `
    -BrowserExe $browserExe -OutputDirectory $good -DurationSeconds 5 -SamplePeriodMs 200 6>&1 | Out-String)
  Require ($captureOutput.Contains('WEBEEBLOCKS_WINDOWS_HOST_EVIDENCE_WRITTEN=1')) 'Missing path-free completion marker.'
  Require (-not $captureOutput.Contains($root) -and -not $captureOutput.Contains($good)) 'Host capture leaked a private path.'

  $metadata = Get-Content -LiteralPath (Join-Path $good 'metadata.json') -Raw | ConvertFrom-Json
  $samples = @(Import-Csv -LiteralPath (Join-Path $good 'samples.csv'))
  Require ($metadata.schema -eq 'webeeblocks.windows-passive-host-v1') 'Wrong metadata schema.'
  Require ($metadata.source_sha -ceq ('a' * 40)) 'Wrong exact source SHA.'
  Require ($metadata.webots_version -eq 'R2025a') 'Wrong exact Webots version.'
  Require ($metadata.webots_executable_sha256 -eq (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()) 'Wrong Webots engine digest.'
  Require ($metadata.process_name -eq 'webots-bin' -and
           $metadata.sampling_scope -like 'single Webots engine PID*') 'The actual simulation engine was not measured.'
  Require ($metadata.external_browser.exe_sha256 -eq (Get-FileHash -LiteralPath $browserExe -Algorithm SHA256).Hash.ToLowerInvariant() -and $metadata.external_browser.used_in_gui -eq 'UNVERIFIED') 'Invented or unbound browser metadata.'
  Require ($metadata.performance_acceptance -eq 'NOT_MEASURED') 'Host observations falsely claim product performance.'
  Require ($metadata.sample_count -ge 2 -and $samples.Count -eq $metadata.sample_count) 'Host samples missing.'
  Require ([double]$samples[-1].elapsed_ms -gt [double]$samples[0].elapsed_ms) 'Non-monotonic sample times.'
  Require ($metadata.PSObject.Properties.Name -notcontains 'hostname') 'Host identity should not be exported.'

  $rejectionMessage = $null
  try {
    & $source -SourceSha ('a' * 40) -CourseId 'test' -Variant candidate `
      -WebotsProcessId $p.Id -WebotsHome $webotsHome -OutputDirectory $good `
      -DurationSeconds 5 -SamplePeriodMs 200
  } catch { $rejectionMessage = $_.Exception.Message }
  Require ($rejectionMessage -eq 'Output directory already exists; use a fresh folder for each trial.') `
    'Existing destination refusal failed or disclosed the private path.'

  # Reject user-profile input paths without echoing their absolute values.
  $missingWebots = Join-Path $root 'profile-private-missing-webots'
  $rejectionMessage = $null
  try {
    & $source -SourceSha ('a' * 40) -CourseId 'test' -Variant candidate `
      -WebotsProcessId $p.Id -WebotsHome $missingWebots -OutputDirectory $bad `
      -DurationSeconds 5 -SamplePeriodMs 200
  } catch { $rejectionMessage = $_.Exception.Message }
  Require ($rejectionMessage -eq 'Missing Webots version file.' -and `
           -not (Test-Path -LiteralPath $bad)) `
    'Missing Webots path refusal failed or disclosed the private path.'

  $missingBrowser = Join-Path $root 'profile-private-missing-browser.exe'
  $rejectionMessage = $null
  try {
    & $source -SourceSha ('a' * 40) -CourseId 'test' -Variant candidate `
      -WebotsProcessId $p.Id -WebotsHome $webotsHome -BrowserExe $missingBrowser `
      -OutputDirectory $bad -DurationSeconds 5 -SamplePeriodMs 200
  } catch { $rejectionMessage = $_.Exception.Message }
  Require ($rejectionMessage -eq 'Selected browser executable is missing or inaccessible.' -and `
           -not (Test-Path -LiteralPath $bad)) `
    'Missing browser path refusal failed or disclosed the private path.'

  # A same-installation launcher must never be measured as the engine:
  # it can wait for a child with virtually no simulation CPU use.
  $launcher = Start-Process -FilePath $launcherExe -ArgumentList '/C ping -n 20 127.0.0.1 >NUL' -PassThru -WindowStyle Hidden
  $processes.Add($launcher)
  Start-Sleep -Milliseconds 200
  Require (-not $launcher.HasExited) 'Launcher fixture exited prematurely.'
  $launcherError = $null
  try {
    & $source -SourceSha ('b' * 40) -CourseId 'test' -Variant candidate `
      -WebotsProcessId $launcher.Id -WebotsHome $webotsHome -OutputDirectory $bad `
      -DurationSeconds 5 -SamplePeriodMs 200
  } catch { $launcherError = $_.Exception.Message }
  Require ($launcherError -eq "PID $($launcher.Id) is not an inspectable Webots simulation engine." -and
           -not (Test-Path -LiteralPath $bad)) 'Official launcher was mistaken for simulation engine.'

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

# Passive Windows R2025a host measurements. This never controls Webots.
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{40}$')][string]$SourceSha,
  [Parameter(Mandatory = $true)][ValidateNotNullOrEmpty()][string]$CourseId,
  [Parameter(Mandatory = $true)][ValidateSet('reference', 'candidate')][string]$Variant,
  [Parameter(Mandatory = $true)][ValidateRange(1, 2147483647)][int]$WebotsProcessId,
  [Parameter(Mandatory = $true)][string]$WebotsHome,
  [Parameter(Mandatory = $true)][string]$OutputDirectory,
  [string]$BrowserExe,
  [ValidateRange(5, 3600)][int]$DurationSeconds = 30,
  [ValidateRange(200, 5000)][int]$SamplePeriodMs = 500
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($DurationSeconds * 1000 -lt $SamplePeriodMs * 2) {
  throw 'Sampling duration must cover at least two intervals.'
}
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
  throw 'The passive benchmark requires Windows.'
}
$versionFile = Join-Path $WebotsHome 'resources\version.txt'
if (-not (Test-Path -LiteralPath $versionFile -PathType Leaf)) {
  throw "Missing Webots version file: $versionFile"
}
$version = (Get-Content -LiteralPath $versionFile -Raw).Trim()
if ($version -ne 'R2025a') { throw "Webots R2025a required, found $version" }
# A filename containing "webots" is insufficient: bind the PID to the
# executable in the exact installation selected for this A/B capture.
$knownExecutables = @(
  (Join-Path $WebotsHome 'msys64\mingw64\bin\webotsw.exe'),
  (Join-Path $WebotsHome 'msys64\mingw64\bin\webots.exe'),
  (Join-Path $WebotsHome 'webotsw.exe'),
  (Join-Path $WebotsHome 'webots.exe')
) | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
    ForEach-Object { (Resolve-Path -LiteralPath $_).Path }
if ($knownExecutables.Count -lt 1) {
  throw 'No Webots executable found in the selected R2025a installation.'
}
$initial = Get-Process -Id $WebotsProcessId -ErrorAction Stop
if ($initial.ProcessName -notmatch '(?i)^webotsw?$' -or -not $initial.Path) {
  throw "PID $WebotsProcessId is not an inspectable Webots executable."
}
$actualProcessPath = [IO.Path]::GetFullPath($initial.Path)
$matchedExecutable = @($knownExecutables | Where-Object {
  [string]::Equals($_, $actualProcessPath, [StringComparison]::OrdinalIgnoreCase)
})
if ($matchedExecutable.Count -ne 1) {
  throw 'Webots PID executable does not match the selected R2025a installation.'
}
$webotsExecutableSha256 = (Get-FileHash -LiteralPath $matchedExecutable[0] -Algorithm SHA256).Hash.ToLowerInvariant()
$startTicks = $initial.StartTime.ToUniversalTime().Ticks
if ($null -eq $initial.CPU) { throw 'Webots CPU time unavailable.' }
# An optional external browser executable identifies prepared bytes, not
# proof of which browser Webots actually opened in a GUI run.
$browserEvidence = $null
if ($BrowserExe) {
  $browserPath = (Resolve-Path -LiteralPath $BrowserExe -ErrorAction Stop).Path
  if (-not (Test-Path -LiteralPath $browserPath -PathType Leaf)) {
    throw 'Selected browser executable is missing.'
  }
  $browserFile = Get-Item -LiteralPath $browserPath
  $browserEvidence = [ordered]@{
    product = [string]$browserFile.VersionInfo.ProductName
    version = [string]$browserFile.VersionInfo.ProductVersion
    exe_sha256 = (Get-FileHash -LiteralPath $browserPath -Algorithm SHA256).Hash.ToLowerInvariant()
    used_in_gui = 'UNVERIFIED'
  }
}
$destination = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $destination) {
  throw "Use a fresh folder for each trial: $destination"
}
New-Item -ItemType Directory -Path $destination -ErrorAction Stop | Out-Null

# Equipment model/driver is NOT proof of actual OpenGL renderer/acceleration.
$os = Get-CimInstance -ClassName Win32_OperatingSystem
$cpus = @(Get-CimInstance -ClassName Win32_Processor)
$video = @(Get-CimInstance -ClassName Win32_VideoController)
$metadata = [ordered]@{
  schema = 'webeeblocks.windows-passive-host-v1'
  source_sha = $SourceSha.ToLowerInvariant()
  course_id = $CourseId
  variant = $Variant
  webots_version = $version
  webots_executable_sha256 = $webotsExecutableSha256
  external_browser = $browserEvidence
  process_name = $initial.ProcessName
  webots_pid = $WebotsProcessId
  process_start_utc = $initial.StartTime.ToUniversalTime().ToString('o')
  measurement_start_utc = [DateTime]::UtcNow.ToString('o')
  requested_duration_s = $DurationSeconds
  requested_period_ms = $SamplePeriodMs
  operating_system = [ordered]@{
    caption = $os.Caption
    version = $os.Version
    build = $os.BuildNumber
    ram_bytes = ([long]$os.TotalVisibleMemorySize * 1024)
  }
  cpus = @($cpus | ForEach-Object {
    [ordered]@{ model = $_.Name; logical_processors = $_.NumberOfLogicalProcessors }
  })
  video_devices = @($video | Where-Object { $null -ne $_ } | ForEach-Object {
    [ordered]@{ model = $_.Name; driver_version = $_.DriverVersion }
  })
  sampling_scope = 'single Webots PID; no children, GPU utilization or simulation clock'
  performance_acceptance = 'NOT_MEASURED'
}
$clock = [Diagnostics.Stopwatch]::StartNew()
$lastElapsed = $clock.Elapsed.TotalSeconds
$lastCpu = [double]$initial.CPU
$samples = [Collections.Generic.List[object]]::new()
while ($clock.Elapsed.TotalSeconds -lt $DurationSeconds) {
  Start-Sleep -Milliseconds $SamplePeriodMs
  $current = Get-Process -Id $WebotsProcessId -ErrorAction Stop
  if ($current.StartTime.ToUniversalTime().Ticks -ne $startTicks) {
    throw 'Original Webots process exited or the PID was reused.'
  }
  if ($null -eq $current.CPU) { throw 'Webots CPU time became unavailable.' }
  $elapsed = $clock.Elapsed.TotalSeconds
  $period = $elapsed - $lastElapsed
  $cpu = [double]$current.CPU
  $delta = $cpu - $lastCpu
  if ($period -le 0 -or $delta -lt -0.001) {
    throw 'Non-monotonic host measurement.'
  }
  # One occupied logical CPU = 100%; a multicore process may exceed 100%.
  $samples.Add([pscustomobject][ordered]@{
    elapsed_ms = [Math]::Round($elapsed * 1000, 3)
    utc = [DateTime]::UtcNow.ToString('o')
    period_ms = [Math]::Round($period * 1000, 3)
    cpu_percent_one_core = [Math]::Round([Math]::Max(0, $delta) / $period * 100, 3)
    process_cpu_total_s = [Math]::Round($cpu, 6)
    working_set_bytes = [long]$current.WorkingSet64
    private_memory_bytes = [long]$current.PrivateMemorySize64
    thread_count = $current.Threads.Count
  })
  $lastElapsed = $elapsed
  $lastCpu = $cpu
}
$clock.Stop()
if ($samples.Count -lt 2) { throw 'Insufficient samples.' }
$metadata['actual_duration_s'] = [Math]::Round($clock.Elapsed.TotalSeconds, 6)
$metadata['sample_count'] = $samples.Count
$utf8 = [Text.UTF8Encoding]::new($false)
[IO.File]::WriteAllText((Join-Path $destination 'metadata.json'),
  (($metadata | ConvertTo-Json -Depth 8) + [Environment]::NewLine), $utf8)
$samples | Export-Csv -LiteralPath (Join-Path $destination 'samples.csv') -NoTypeInformation -Encoding UTF8
Write-Host "WEBEEBLOCKS_WINDOWS_HOST_EVIDENCE=$destination"
Write-Host 'HOST ONLY: simulator speed, p99 step latency, OpenGL renderer and GUI acceptance are NOT measured.'
 -or -not $initial.Path) {
  throw "PID $WebotsProcessId is not an inspectable Webots executable."
}
$actualProcessPath = [IO.Path]::GetFullPath($initial.Path)
$matchedExecutable = @($knownExecutables | Where-Object {
  [string]::Equals($_, $actualProcessPath, [StringComparison]::OrdinalIgnoreCase)
})
if ($matchedExecutable.Count -ne 1) {
  throw 'Webots PID executable does not match the selected R2025a installation.'
}
$webotsExecutableSha256 = (Get-FileHash -LiteralPath $matchedExecutable[0] -Algorithm SHA256).Hash.ToLowerInvariant()
$startTicks = $initial.StartTime.ToUniversalTime().Ticks
if ($null -eq $initial.CPU) { throw 'Webots CPU time unavailable.' }
$destination = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $destination) {
  throw "Use a fresh folder for each trial: $destination"
}
New-Item -ItemType Directory -Path $destination -ErrorAction Stop | Out-Null

# Equipment model/driver is NOT proof of actual OpenGL renderer/acceleration.
$os = Get-CimInstance -ClassName Win32_OperatingSystem
$cpus = @(Get-CimInstance -ClassName Win32_Processor)
$video = @(Get-CimInstance -ClassName Win32_VideoController)
$metadata = [ordered]@{
  schema = 'webeeblocks.windows-passive-host-v1'
  source_sha = $SourceSha.ToLowerInvariant()
  course_id = $CourseId
  variant = $Variant
  webots_version = $version
  process_name = $initial.ProcessName
  webots_pid = $WebotsProcessId
  process_start_utc = $initial.StartTime.ToUniversalTime().ToString('o')
  measurement_start_utc = [DateTime]::UtcNow.ToString('o')
  requested_duration_s = $DurationSeconds
  requested_period_ms = $SamplePeriodMs
  operating_system = [ordered]@{
    caption = $os.Caption
    version = $os.Version
    build = $os.BuildNumber
    ram_bytes = ([long]$os.TotalVisibleMemorySize * 1024)
  }
  cpus = @($cpus | ForEach-Object {
    [ordered]@{ model = $_.Name; logical_processors = $_.NumberOfLogicalProcessors }
  })
  video_devices = @($video | Where-Object { $null -ne $_ } | ForEach-Object {
    [ordered]@{ model = $_.Name; driver_version = $_.DriverVersion }
  })
  sampling_scope = 'single Webots PID; no children, GPU utilization or simulation clock'
  performance_acceptance = 'NOT_MEASURED'
}
$clock = [Diagnostics.Stopwatch]::StartNew()
$lastElapsed = $clock.Elapsed.TotalSeconds
$lastCpu = [double]$initial.CPU
$samples = [Collections.Generic.List[object]]::new()
while ($clock.Elapsed.TotalSeconds -lt $DurationSeconds) {
  Start-Sleep -Milliseconds $SamplePeriodMs
  $current = Get-Process -Id $WebotsProcessId -ErrorAction Stop
  if ($current.StartTime.ToUniversalTime().Ticks -ne $startTicks) {
    throw 'Original Webots process exited or the PID was reused.'
  }
  if ($null -eq $current.CPU) { throw 'Webots CPU time became unavailable.' }
  $elapsed = $clock.Elapsed.TotalSeconds
  $period = $elapsed - $lastElapsed
  $cpu = [double]$current.CPU
  $delta = $cpu - $lastCpu
  if ($period -le 0 -or $delta -lt -0.001) {
    throw 'Non-monotonic host measurement.'
  }
  # One occupied logical CPU = 100%; a multicore process may exceed 100%.
  $samples.Add([pscustomobject][ordered]@{
    elapsed_ms = [Math]::Round($elapsed * 1000, 3)
    utc = [DateTime]::UtcNow.ToString('o')
    period_ms = [Math]::Round($period * 1000, 3)
    cpu_percent_one_core = [Math]::Round([Math]::Max(0, $delta) / $period * 100, 3)
    process_cpu_total_s = [Math]::Round($cpu, 6)
    working_set_bytes = [long]$current.WorkingSet64
    private_memory_bytes = [long]$current.PrivateMemorySize64
    thread_count = $current.Threads.Count
  })
  $lastElapsed = $elapsed
  $lastCpu = $cpu
}
$clock.Stop()
if ($samples.Count -lt 2) { throw 'Insufficient samples.' }
$metadata['actual_duration_s'] = [Math]::Round($clock.Elapsed.TotalSeconds, 6)
$metadata['sample_count'] = $samples.Count
$utf8 = [Text.UTF8Encoding]::new($false)
[IO.File]::WriteAllText((Join-Path $destination 'metadata.json'),
  (($metadata | ConvertTo-Json -Depth 8) + [Environment]::NewLine), $utf8)
$samples | Export-Csv -LiteralPath (Join-Path $destination 'samples.csv') -NoTypeInformation -Encoding UTF8
Write-Host "WEBEEBLOCKS_WINDOWS_HOST_EVIDENCE=$destination"
Write-Host 'HOST ONLY: simulator speed, p99 step latency, OpenGL renderer and GUI acceptance are NOT measured.'

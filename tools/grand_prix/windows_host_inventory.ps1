# Read-only, offline host inventory for Grand Prix Windows A/B testing (#914).
# Collects no hostname, username, serial number, address, or MAC.
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$WebotsHome,
  [Parameter(Mandatory = $true)][string]$OutputPath,
  [string]$BrowserExe,
  [string]$SourceSha
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ($SourceSha -and $SourceSha -cnotmatch '^[0-9a-f]{40}$') {
  throw 'SourceSha must be an exact lowercase 40-character Git commit SHA.'
}
$webots = (Resolve-Path -LiteralPath $WebotsHome -ErrorAction Stop).Path
# Match the supported Windows R2025a layout used by the classroom launcher.
$bin = Join-Path $webots 'msys64\mingw64\bin'
$exe = @('webotsw.exe', 'webots.exe') |
  ForEach-Object { Join-Path $bin $_ } |
  Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
  Select-Object -First 1
$versionFile = Join-Path $webots 'resources\version.txt'
if (-not $exe -or -not (Test-Path -LiteralPath $versionFile -PathType Leaf)) {
  throw 'Webots executable or resources/version.txt is missing.'
}
$webotsVersion = (Get-Content -LiteralPath $versionFile -Raw).Trim()
if ($webotsVersion -ne 'R2025a') { throw "Expected Webots R2025a; found $webotsVersion" }

$target = [IO.Path]::GetFullPath($OutputPath)
if (Test-Path -LiteralPath $target) { throw 'Refusing to overwrite an existing inventory.' }
$parent = Split-Path -Parent $target
if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
  throw 'Output directory must already exist.'
}
$os = Get-CimInstance -ClassName Win32_OperatingSystem
$system = Get-CimInstance -ClassName Win32_ComputerSystem
$cpu = @(Get-CimInstance -ClassName Win32_Processor | ForEach-Object {
  [ordered]@{
    model = [string]$_.Name
    cores = [int]$_.NumberOfCores
    logical_processors = [int]$_.NumberOfLogicalProcessors
  }
})
$gpu = @(Get-CimInstance -ClassName Win32_VideoController | ForEach-Object {
  [ordered]@{
    model = [string]$_.Name
    driver_version = [string]$_.DriverVersion
    driver_date = if ($_.DriverDate) { ([datetime]$_.DriverDate).ToUniversalTime().ToString('o') } else { $null }
  }
})
if (-not $os -or -not $system -or $cpu.Count -lt 1 -or $gpu.Count -lt 1) {
  throw 'Incomplete OS, CPU, RAM or display adapter inventory.'
}
if ($system.TotalPhysicalMemory -le 0) { throw 'Invalid physical memory size.' }

$browser = $null
if ($BrowserExe) {
  $browserPath = (Resolve-Path -LiteralPath $BrowserExe -ErrorAction Stop).Path
  if (-not (Test-Path -LiteralPath $browserPath -PathType Leaf)) { throw 'Browser executable missing.' }
  $browserFile = Get-Item -LiteralPath $browserPath
  $browser = [ordered]@{
    product = [string]$browserFile.VersionInfo.ProductName
    version = [string]$browserFile.VersionInfo.ProductVersion
    exe_sha256 = (Get-FileHash -LiteralPath $browserPath -Algorithm SHA256).Hash.ToLowerInvariant()
  }
}
$webotsExe = Get-Item -LiteralPath $exe
$inventory = [ordered]@{
  schema = 'webeeblocks-grand-prix-windows-host-v1'
  captured_utc = [datetime]::UtcNow.ToString('o')
  source_sha = if ($SourceSha) { $SourceSha } else { $null }
  os = [ordered]@{
    caption = [string]$os.Caption
    version = [string]$os.Version
    build_number = [string]$os.BuildNumber
    architecture = [string]$os.OSArchitecture
  }
  physical_memory_bytes = [int64]$system.TotalPhysicalMemory
  cpu = $cpu
  display_adapters = $gpu
  webots = [ordered]@{
    release = $webotsVersion
    product_version = [string]$webotsExe.VersionInfo.ProductVersion
    exe_sha256 = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
  }
  browser = $browser
  actual_opengl_renderer = $null
  actual_opengl_source = 'UNMEASURED: capture Webots --sysinfo / GUI OpenGL context on this host'
  measurement_state = 'INVENTORY_ONLY_NOT_A_PERFORMANCE_OR_ACCEPTANCE_RESULT'
}
$json = $inventory | ConvertTo-Json -Depth 8
$utf8NoBom = [Text.UTF8Encoding]::new($false)
# Atomically refuse late creation by another measurement, too.
$bytes = $utf8NoBom.GetBytes($json + "`n")
$stream = [IO.File]::Open($target, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose() }
Write-Host "WEBEEBLOCKS_GP_WINDOWS_INVENTORY=$target"
Write-Host 'Inventory only: no measured OpenGL renderer, FPS, p99, native safety or human PASS.'

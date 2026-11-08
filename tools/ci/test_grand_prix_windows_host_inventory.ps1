# Windows-native regression test for #914; no Webots installation or network required.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Require([bool]$Condition, [string]$Message) {
  if (-not $Condition) { throw $Message }
}
$root = Join-Path ([IO.Path]::GetTempPath()) ('gp-host-test-' + [Guid]::NewGuid().ToString('N'))
$webots = Join-Path $root 'webots'
$versionDir = Join-Path $webots 'resources'
New-Item -ItemType Directory -Path $versionDir -Force | Out-Null
$webotsBin = Join-Path $webots 'msys64\mingw64\bin'
New-Item -ItemType Directory -Path $webotsBin -Force | Out-Null
$webotsExe = Join-Path $webotsBin 'webotsw.exe'
$versionPath = Join-Path $versionDir 'version.txt'
$browser = Join-Path $root 'browser.exe'
$target = Join-Path $root 'inventory.json'
$script = Join-Path $PSScriptRoot '..\grand_prix\windows_host_inventory.ps1'

# A deterministic CIM fixture avoids treating the CI VM's graphics adapter
# as the portable Windows machine. This function is visible to the child script.
function Get-CimInstance {
  param([string]$ClassName)
  switch ($ClassName) {
    'Win32_OperatingSystem' { return [pscustomobject]@{
      Caption='Windows fixture'; Version='10.0.22631'; BuildNumber='22631'; OSArchitecture='64-bit'
    } }
    'Win32_ComputerSystem' { return [pscustomobject]@{ TotalPhysicalMemory=[int64](16GB) } }
    'Win32_Processor' { return [pscustomobject]@{
      Name='Fixture CPU'; NumberOfCores=4; NumberOfLogicalProcessors=8
    } }
    'Win32_VideoController' { return [pscustomobject]@{
      Name='Fixture GPU'; DriverVersion='1.2.3'; DriverDate=[datetime]'2026-01-01'
    } }
    default { throw "Unexpected CIM query: $ClassName" }
  }
}

try {
  [IO.File]::WriteAllText($webotsExe, 'dummy-Webots-R2025a')
  [IO.File]::WriteAllText($browser, 'dummy-browser')
  [IO.File]::WriteAllText($versionPath, 'R2025a')
  $inventoryOutput = (& $script -WebotsHome $webots -BrowserExe $browser -SourceSha ('a' * 40) -OutputPath $target 6>&1 | Out-String)
  Require ($inventoryOutput.Contains('WEBEEBLOCKS_GP_WINDOWS_INVENTORY_WRITTEN=1')) 'Missing path-free completion marker.'
  Require (-not $inventoryOutput.Contains($root) -and -not $inventoryOutput.Contains($target)) 'Inventory printed a private absolute path.'
  Require (Test-Path -LiteralPath $target) 'Missing JSON inventory.'
  $text = Get-Content -LiteralPath $target -Raw
  $json = $text | ConvertFrom-Json
  Require ($json.schema -eq 'webeeblocks-grand-prix-windows-host-v1') 'Wrong inventory schema.'
  Require ($json.os.caption -eq 'Windows fixture' -and $json.cpu[0].model -eq 'Fixture CPU') 'Wrong synthetic system inventory.'
  Require ($json.display_adapters[0].model -eq 'Fixture GPU' -and $json.display_adapters[0].driver_version -eq '1.2.3') 'Wrong synthetic GPU inventory.'
  Require ($json.source_sha -ceq ('a' * 40)) 'Wrong exact source SHA.'
  Require ($json.webots.release -eq 'R2025a') 'Wrong Webots release.'
  Require ($json.webots.exe_sha256 -eq (Get-FileHash -LiteralPath $webotsExe -Algorithm SHA256).Hash.ToLowerInvariant()) 'Wrong Webots executable digest.'
  Require ($json.webots.exe_relative_path -ceq 'msys64/mingw64/bin/webotsw.exe') 'Wrong selected Webots executable path.'
  Require ($json.browser.exe_sha256 -eq (Get-FileHash -LiteralPath $browser -Algorithm SHA256).Hash.ToLowerInvariant()) 'Wrong browser executable digest.'
  Require ($json.actual_opengl_renderer -eq $null) 'Invented OpenGL renderer.'
  Require ($json.measurement_state -eq 'INVENTORY_ONLY_NOT_A_PERFORMANCE_OR_ACCEPTANCE_RESULT') 'Invented performance result.'
  Require ($json.cpu.Count -ge 1 -and $json.display_adapters.Count -ge 1) 'Missing real host CPU/GPU evidence.'
  foreach ($name in @('hostname', 'username', 'serial_number', 'mac_address', 'full_path')) {
    Require ($json.PSObject.Properties.Name -notcontains $name) "Privacy field present: $name"
  }

  $wasRejected = $false
  try { & $script -WebotsHome $webots -OutputPath $target } catch { $wasRejected = $true }
  Require $wasRejected 'Existing inventory was overwritten.'
  Require ((Get-Content -LiteralPath $target -Raw) -ceq $text) 'Failed request changed the inventory.'

  $invalid = Join-Path $root 'invalid.json'
  $wasRejected = $false
  try { & $script -WebotsHome $webots -OutputPath $invalid -SourceSha 'not-a-sha' } catch { $wasRejected = $true }
  Require ($wasRejected -and -not (Test-Path -LiteralPath $invalid)) 'Invalid source SHA was accepted.'
  [IO.File]::WriteAllText($versionPath, 'R2024b')
  $wasRejected = $false
  try { & $script -WebotsHome $webots -OutputPath $invalid } catch { $wasRejected = $true }
  Require ($wasRejected -and -not (Test-Path -LiteralPath $invalid)) 'Wrong Webots release was accepted.'

  # Exercise the supported fallback from webotsw.exe to webots.exe.
  [IO.File]::WriteAllText($versionPath, 'R2025a')
  Remove-Item -LiteralPath $webotsExe
  $fallbackExe = Join-Path $webotsBin 'webots.exe'
  [IO.File]::WriteAllText($fallbackExe, 'dummy-Webots-console-R2025a')
  $fallbackTarget = Join-Path $root 'inventory-fallback.json'
  & $script -WebotsHome $webots -OutputPath $fallbackTarget
  $fallback = Get-Content -LiteralPath $fallbackTarget -Raw | ConvertFrom-Json
  Require ($fallback.webots.exe_relative_path -ceq 'msys64/mingw64/bin/webots.exe') 'Incorrect fallback executable path.'
  Require ($fallback.webots.exe_sha256 -eq (Get-FileHash -LiteralPath $fallbackExe -Algorithm SHA256).Hash.ToLowerInvariant()) 'Incorrect fallback executable digest.'

  Remove-Item -LiteralPath $fallbackExe
  $missingTarget = Join-Path $root 'inventory-missing.json'
  $wasRejected = $false
  try { & $script -WebotsHome $webots -OutputPath $missingTarget } catch { $wasRejected = $true }
  Require ($wasRejected -and -not (Test-Path -LiteralPath $missingTarget)) 'Missing Webots executable was accepted.'

  Write-Host 'PASS Windows host inventory: exact provenance, privacy, no invented metrics, negative cases.'
}
finally {
  Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}

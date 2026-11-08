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
$webotsExe = Join-Path $webotsBin 'webots-bin.exe'
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
  Require ($json.webots.exe_relative_path -ceq 'msys64/mingw64/bin/webots-bin.exe') 'Wrong selected Webots engine path.'
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
  # Invalid user-local paths must fail closed without disclosing the path in
  # the thrown message; the successful-output check above is not sufficient.
  $missingInputTarget = Join-Path $root 'missing-input-inventory.json'
  foreach ($probe in @(
    @{ Kind = 'Webots'; Home = (Join-Path $root 'profile-private-missing-webots'); Browser = $browser },
    @{ Kind = 'Browser'; Home = $webots; Browser = (Join-Path $root 'profile-private-missing-browser.exe') }
  )) {
    $failureMessage = $null
    try {
      & $script -WebotsHome ([string]$probe.Home) -BrowserExe ([string]$probe.Browser) -OutputPath $missingInputTarget 6>&1 | Out-Null
    } catch { $failureMessage = $_.Exception.Message }
    Require ($failureMessage -and $failureMessage.Contains('missing or inaccessible')) ($probe.Kind + ' missing path was not refused cleanly.')
    Require (-not $failureMessage.Contains($root)) ($probe.Kind + ' error exposed a private absolute path.')
    Require (-not (Test-Path -LiteralPath $missingInputTarget)) 'Failed input path wrote an inventory.'
  }

  [IO.File]::WriteAllText($versionPath, 'R2024b')
  $wasRejected = $false
  try { & $script -WebotsHome $webots -OutputPath $invalid } catch { $wasRejected = $true }
  Require ($wasRejected -and -not (Test-Path -LiteralPath $invalid)) 'Wrong Webots release was accepted.'

  # An untrusted version file must never leak its raw contents through an error.
  [IO.File]::WriteAllText($versionPath, 'C:\Users\PrivateProfile\confidential\tokens.txt')
  $versionError = $null
  try { & $script -WebotsHome $webots -OutputPath $invalid } catch { $versionError = $_.Exception.Message }
  Require ($versionError -ceq 'Expected Webots R2025a; unsupported version metadata.' -and
           -not (Test-Path -LiteralPath $invalid)) 'Invalid version metadata was disclosed or accepted.'


  # The native executable hash must change when only the engine changes.
  [IO.File]::WriteAllText($versionPath, 'R2025a')
  [IO.File]::WriteAllText($webotsExe, 'patched-engine-only')
  $engineTarget = Join-Path $root 'inventory-patched.json'
  & $script -WebotsHome $webots -OutputPath $engineTarget
  $patched = Get-Content -LiteralPath $engineTarget -Raw | ConvertFrom-Json
  Require ($patched.webots.exe_sha256 -eq (Get-FileHash -LiteralPath $webotsExe -Algorithm SHA256).Hash.ToLowerInvariant() -and
           $patched.webots.exe_sha256 -ne $json.webots.exe_sha256) 'Native engine change was invisible to provenance.'

  # The launcher may exist while the actual simulation engine is missing.
  Remove-Item -LiteralPath $webotsExe
  $fallbackExe = Join-Path $webotsBin 'webots.exe'
  [IO.File]::WriteAllText($fallbackExe, 'dummy-Webots-console-R2025a')
  $fallbackTarget = Join-Path $root 'inventory-launcher-only.json'
  $launcherError = $null
  try { & $script -WebotsHome $webots -OutputPath $fallbackTarget } catch { $launcherError = $_.Exception.Message }
  Require ($launcherError -ceq 'Webots simulation engine or resources/version.txt is missing.' -and
           -not (Test-Path -LiteralPath $fallbackTarget)) 'Launcher-only inventory was accepted.'

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

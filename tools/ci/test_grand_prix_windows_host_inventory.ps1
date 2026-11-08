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
$webotsExe = Join-Path $webots 'webots.exe'
$versionPath = Join-Path $versionDir 'version.txt'
$browser = Join-Path $root 'browser.exe'
$target = Join-Path $root 'inventory.json'
$script = Join-Path $PSScriptRoot '..\grand_prix\windows_host_inventory.ps1'

try {
  [IO.File]::WriteAllText($webotsExe, 'dummy-Webots-R2025a')
  [IO.File]::WriteAllText($browser, 'dummy-browser')
  [IO.File]::WriteAllText($versionPath, 'R2025a')
  & $script -WebotsHome $webots -BrowserExe $browser -SourceSha ('a' * 40) -OutputPath $target
  Require (Test-Path -LiteralPath $target) 'Missing JSON inventory.'
  $text = Get-Content -LiteralPath $target -Raw
  $json = $text | ConvertFrom-Json
  Require ($json.schema -eq 'webeeblocks-grand-prix-windows-host-v1') 'Wrong inventory schema.'
  Require ($json.source_sha -ceq ('a' * 40)) 'Wrong exact source SHA.'
  Require ($json.webots.release -eq 'R2025a') 'Wrong Webots release.'
  Require ($json.webots.exe_sha256 -eq (Get-FileHash -LiteralPath $webotsExe -Algorithm SHA256).Hash.ToLowerInvariant()) 'Wrong Webots executable digest.'
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

  Write-Host 'PASS Windows host inventory: exact provenance, privacy, no invented metrics, negative cases.'
}
finally {
  Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}

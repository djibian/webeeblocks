[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$ArchivePath,
  [Parameter(Mandatory = $true)][string]$WebotsHome,
  [Parameter(Mandatory = $true)][string]$PythonExe
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$testRoot = Join-Path $env:RUNNER_TEMP ('Grand Prix controller ' + [Guid]::NewGuid().ToString('N'))
Expand-Archive -LiteralPath $ArchivePath -DestinationPath $testRoot
function Require([bool]$Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
$manifest = Join-Path $testRoot 'MANIFEST.sha256'
$listed = @()
foreach ($line in (Get-Content -LiteralPath $manifest)) {
  Require ($line -match '^([0-9a-f]{64})  (.+)$') 'Invalid controller manifest.'
  $hash = $Matches[1]; $name = $Matches[2]
  $path = [IO.Path]::GetFullPath((Join-Path $testRoot $name))
  Require ($path.StartsWith($testRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) 'Manifest escapes controller package.'
  Require ($name -notin $listed) 'Duplicate controller manifest entry.'
  Require ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -eq $hash) "Bad packaged controller bytes: $name"
  $listed += $name
}
Require (@(Get-ChildItem -LiteralPath $testRoot -Recurse -File | Where-Object FullName -ne $manifest).Count -eq $listed.Count) 'Unmanifested controller file.'
$sha = (& git -C $repoRoot rev-parse HEAD | Out-String).Trim()
Require ($LASTEXITCODE -eq 0 -and (Get-Content -LiteralPath (Join-Path $testRoot 'SOURCE_SHA') -Raw).Trim() -eq $sha) 'Wrong controller source SHA.'
$inputs = Get-Content -LiteralPath (Join-Path $testRoot 'BUILD_INPUTS.json') -Raw | ConvertFrom-Json
foreach ($property in $inputs.PSObject.Properties) {
  Require ((Get-FileHash -LiteralPath (Join-Path $repoRoot $property.Name) -Algorithm SHA256).Hash.ToLowerInvariant() -eq $property.Value) "Changed composition input: $($property.Name)"
}
$exe = Join-Path $testRoot 'controllers\grand_prix_u_flight\grand_prix_u_flight.exe'
$sourceExe = Join-Path $repoRoot 'controllers\grand_prix_u_flight\grand_prix_u_flight.exe'
Require ((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $sourceExe -Algorithm SHA256).Hash) 'Packaged controller differs from the exact build.'
$imports = (& (Join-Path $WebotsHome 'msys64\mingw64\bin\objdump.exe') -p $exe | Out-String)
Require ($LASTEXITCODE -eq 0) 'Cannot inspect packaged PE imports.'
foreach ($dll in @('Controller.dll', 'Qt6Core.dll', 'Qt6Widgets.dll')) {
  Require ($imports -match ('(?im)^\s*DLL Name:\s*' + [regex]::Escape($dll) + '\s*$')) "Missing native dependency $dll"
}
$oldHome = $env:WEBOTS_HOME
$oldPath = $env:PATH
$oldUrl = $env:WEBOTS_CONTROLLER_URL
$process = $null
try {
  $env:WEBOTS_HOME = (Resolve-Path -LiteralPath $WebotsHome).Path
  $env:PATH = @(
    (Join-Path $WebotsHome 'lib\controller'),
    (Join-Path $WebotsHome 'msys64\mingw64\bin\cpp'),
    (Join-Path $WebotsHome 'msys64\mingw64\bin'),
    (Join-Path $env:SystemRoot 'System32'), $env:SystemRoot
  ) -join ';'
  # The same assertions/negative cases execute with Windows' actual compiler.
  & $PythonExe (Join-Path $repoRoot 'tools\ci\test_grand_prix_u_pose.py')
  Require ($LASTEXITCODE -eq 0) 'Composed pose/angle/deadline/broker tests failed under the Windows toolchain.'
  $env:WEBOTS_CONTROLLER_URL = 'ipc://65535'
  $stdout = Join-Path $testRoot 'native.stdout.log'
  $stderr = Join-Path $testRoot 'native.stderr.log'
  $process = Start-Process -FilePath $exe -WorkingDirectory (Split-Path $exe -Parent) `
    -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
  $deadline = [DateTime]::UtcNow.AddSeconds(10)
  $entered = $false
  do {
    Start-Sleep -Milliseconds 200
    $errors = if (Test-Path -LiteralPath $stderr) { Get-Content -LiteralPath $stderr -Raw } else { '' }
    if ($errors -match 'Cannot connect to Webots instance') { $entered = $true; break }
    $process.Refresh()
    if ($process.HasExited) { break }
  } while ([DateTime]::UtcNow -lt $deadline)
  Require $entered "Grand Prix PE did not enter native libController: $errors"
}
finally {
  if ($null -ne $process) {
    $process.Refresh()
    if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force; $process.WaitForExit() }
  }
  $env:WEBOTS_HOME = $oldHome
  $env:PATH = $oldPath
  $env:WEBOTS_CONTROLLER_URL = $oldUrl
}
Write-Host 'PASS Windows Grand Prix controller: exact package/build inputs, real composed C/C++ tests, Qt/Controller PE imports and native IPC entry; no GUI/mission acceptance claimed.'

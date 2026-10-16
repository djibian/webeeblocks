[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$ArchivePath,
  [Parameter(Mandatory = $true)][string]$WebotsHome
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$testRoot = Join-Path $env:RUNNER_TEMP ('Grand Prix evaluator ' + [Guid]::NewGuid().ToString('N'))
Expand-Archive -LiteralPath $ArchivePath -DestinationPath $testRoot
function Require([bool]$Condition, [string]$Message) {
  if (-not $Condition) { throw $Message }
}
$manifestPath = Join-Path $testRoot 'MANIFEST.sha256'
$listed = @()
foreach ($line in (Get-Content -LiteralPath $manifestPath)) {
  Require ($line -match '^([0-9a-f]{64})  (.+)$') "Invalid manifest line: $line"
  $hash = $Matches[1]; $relative = $Matches[2]
  $file = [IO.Path]::GetFullPath((Join-Path $testRoot $relative))
  Require ($file.StartsWith($testRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) 'Manifest path escapes package.'
  Require ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -eq $hash) "Bad packaged bytes: $relative"
  Require ($relative -notin $listed) "Duplicate manifest entry: $relative"
  $listed += $relative
}
$files = @(Get-ChildItem -LiteralPath $testRoot -Recurse -File | Where-Object FullName -ne $manifestPath)
Require ($files.Count -eq $listed.Count) 'Unmanifested packaged file.'
$sourceSha = (Get-Content -LiteralPath (Join-Path $testRoot 'SOURCE_SHA') -Raw).Trim()
$currentSha = (& git -C $repoRoot rev-parse HEAD | Out-String).Trim()
Require ($LASTEXITCODE -eq 0 -and $sourceSha -eq $currentSha) 'Wrong source SHA.'
$sourcePairs = @(
  @('controllers\grand_prix_u_evaluator\grand_prix_u_evaluator.py', 'controllers\grand_prix_u_evaluator\evaluator_impl.py'),
  @('packaging\windows\grand_prix_evaluator_bootstrap.py', 'controllers\grand_prix_u_evaluator\grand_prix_u_evaluator.py'),
  @('tools\grand_prix\layout_u.py', 'tools\grand_prix\layout_u.py'),
  @('tools\grand_prix\oracle_u.py', 'tools\grand_prix\oracle_u.py'),
  @('tools\grand_prix\simulation_time.py', 'tools\grand_prix\simulation_time.py')
)
foreach ($pair in $sourcePairs) {
  Require ((Get-FileHash -LiteralPath (Join-Path $repoRoot $pair[0]) -Algorithm SHA256).Hash -eq
    (Get-FileHash -LiteralPath (Join-Path $testRoot $pair[1]) -Algorithm SHA256).Hash) "Changed evaluator source: $($pair[0])"
}
$python = Join-Path $testRoot 'runtime\python\python.exe'
$entry = Join-Path $testRoot 'controllers\grand_prix_u_evaluator\grand_prix_u_evaluator.py'
$pth = Get-Content -LiteralPath (Join-Path $testRoot 'runtime\python\python312._pth') -Raw
Require ($pth -eq "python312.zip`n.`n") 'Unexpected embedded Python search path.'
$ini = Get-Content -LiteralPath (Join-Path $testRoot 'controllers\grand_prix_u_evaluator\runtime.ini') -Raw
Require ($ini -eq "[python]`nCOMMAND = `$(WEBEEBLOCKS_GP_PYTHON)`nOPTIONS = -I`n") 'Interpreter selection admits an ambient fallback.'
$oldWebots = $env:WEBOTS_HOME
$oldPath = $env:PATH
$oldPythonPath = $env:PYTHONPATH
$oldPythonHome = $env:PYTHONHOME
$oldControllerUrl = $env:WEBOTS_CONTROLLER_URL
$process = $null
try {
  $env:WEBOTS_HOME = (Resolve-Path -LiteralPath $WebotsHome).Path
  # No ambient Python directory, pip, installed packages or shell lookup.
  $env:PATH = @(
    (Join-Path $WebotsHome 'lib\controller'),
    (Join-Path $WebotsHome 'msys64\mingw64\bin\cpp'),
    (Join-Path $WebotsHome 'msys64\mingw64\bin'),
    (Join-Path $env:SystemRoot 'System32'), $env:SystemRoot
  ) -join ';'
  $poison = Join-Path $testRoot 'ambient Python'
  New-Item -ItemType Directory -Path $poison | Out-Null
  [IO.File]::WriteAllText((Join-Path $poison 'sitecustomize.py'), "raise RuntimeError('ambient Python leaked')`n")
  [IO.File]::WriteAllText((Join-Path $poison 'controller.py'), "raise RuntimeError('ambient controller leaked')`n")
  $env:PYTHONPATH = $poison
  $env:PYTHONHOME = $poison
  $result = & $python -I $entry --verify-imports
  Require ($LASTEXITCODE -eq 0) 'Packaged interpreter/API/oracle imports failed.'
  $record = ($result | Out-String) | ConvertFrom-Json
  Require ($record.python -eq '3.12.10' -and $record.executable -eq $python) 'Wrong interpreter.'
  Require ($record.isolated -eq 1 -and $record.no_site -eq 1) 'Interpreter isolation not effective.'
  Require ($record.oracle -eq 'grand-prix-u-v1' -and $record.milliseconds -eq 210000 -and $record.gates -eq 3) 'Wrong product oracle/geometries.'
  Require ([IO.Path]::GetFullPath($record.layout) -eq (Join-Path $testRoot 'tools\grand_prix\layout_u.py')) 'Foreign layout module.'
  Require ([IO.Path]::GetFullPath($record.oracle_module) -eq (Join-Path $testRoot 'tools\grand_prix\oracle_u.py')) 'Foreign oracle module.'
  Require ([IO.Path]::GetFullPath($record.controller) -eq (Join-Path $env:WEBOTS_HOME 'lib\controller\python\controller\__init__.py')) 'Foreign Webots API.'
  Write-Host ('GP_U_WINDOWS_IMPORTS ' + ($record | ConvertTo-Json -Compress))

  # Like the existing classroom native-load test, intentionally use absent IPC.
  # Require the original evaluator to enter libController, not merely import a stub.
  $env:WEBOTS_CONTROLLER_URL = 'ipc://65535'
  $stdout = Join-Path $testRoot 'native.stdout.log'
  $stderr = Join-Path $testRoot 'native.stderr.log'
  $process = Start-Process -FilePath $python -ArgumentList @('-I', '-u', "`"$entry`"", '4', '2.0') `
    -WorkingDirectory $poison -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
  $deadline = [DateTime]::UtcNow.AddSeconds(10)
  $entered = $false
  do {
    Start-Sleep -Milliseconds 200
    $errors = if (Test-Path -LiteralPath $stderr) { Get-Content -LiteralPath $stderr -Raw } else { '' }
    if ($errors -match 'Cannot connect to Webots instance') { $entered = $true; break }
    $process.Refresh()
    if ($process.HasExited) { break }
  } while ([DateTime]::UtcNow -lt $deadline)
  Require $entered "Original evaluator did not enter the native Webots IPC path: $errors"
}
finally {
  if ($null -ne $process) {
    $process.Refresh()
    if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force; $process.WaitForExit() }
  }
  $env:WEBOTS_HOME = $oldWebots
  $env:PATH = $oldPath
  $env:PYTHONPATH = $oldPythonPath
  $env:PYTHONHOME = $oldPythonHome
  $env:WEBOTS_CONTROLLER_URL = $oldControllerUrl
}
# Archive corruption must be rejected before a package/output tree is created.
$bad = Join-Path $testRoot 'corrupt.zip'
[IO.File]::WriteAllText($bad, 'corrupt')
$badOutput = Join-Path $testRoot 'bad output'
$refused = $false
try { & (Join-Path $repoRoot 'tools\grand_prix\build_windows_evaluator.ps1') -OutputDirectory $badOutput -PythonArchive $bad }
catch {
  if ($_.Exception.Message -notmatch 'checksum/size mismatch') { throw }
  $refused = $true
}
Require $refused 'Corrupt archive accepted.'
Require (-not (Test-Path -LiteralPath (Join-Path $badOutput 'WebeeBlocks-Grand-Prix-Evaluator-Windows-R2025a'))) 'Corrupt archive was extracted.'
Write-Host 'PASS packaged Windows evaluator: exact CPython, unchanged sources/oracles, isolated imports, native IPC entry and corrupt-archive refusal; no mission/GUI acceptance claimed.'

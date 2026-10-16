[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$OutputDirectory,
  [string]$PythonArchive
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$lock = Get-Content -LiteralPath (Join-Path $repoRoot 'packaging\windows\grand_prix_python_lock.json') -Raw | ConvertFrom-Json
$outputRoot = [IO.Path]::GetFullPath($OutputDirectory)
$packageName = 'WebeeBlocks-Grand-Prix-Evaluator-Windows-R2025a'
$package = Join-Path $outputRoot $packageName
$archive = Join-Path $outputRoot "$packageName.zip"
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
if (-not $PythonArchive) {
  $PythonArchive = Join-Path $outputRoot $lock.filename
  if (-not (Test-Path -LiteralPath $PythonArchive -PathType Leaf)) {
    Invoke-WebRequest -Uri $lock.url -OutFile $PythonArchive
  }
}
$PythonArchive = (Resolve-Path -LiteralPath $PythonArchive).Path
# Verify before extraction or any execution. A bad existing archive is not retried.
$digest = (Get-FileHash -LiteralPath $PythonArchive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($digest -ne $lock.sha256 -or (Get-Item -LiteralPath $PythonArchive).Length -ne $lock.size) {
  throw "Embedded Python archive checksum/size mismatch: $digest"
}
if ((Test-Path -LiteralPath $package) -or (Test-Path -LiteralPath $archive)) {
  throw 'Evaluator output already exists; use a new empty output directory.'
}
function Copy-Source([string]$Source, [string]$Target) {
  $destination = Join-Path $package $Target
  New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
  Copy-Item -LiteralPath (Join-Path $repoRoot $Source) -Destination $destination
}
$runtime = Join-Path $package 'runtime\python'
Expand-Archive -LiteralPath $PythonArchive -DestinationPath $runtime
$pathFile = Join-Path $runtime 'python312._pth'
$pathText = "python312.zip`n.`n"
[IO.File]::WriteAllText($pathFile, $pathText, [Text.UTF8Encoding]::new($false))
foreach ($source in @('layout_u.py', 'oracle_u.py', 'simulation_time.py')) {
  Copy-Source "tools\grand_prix\$source" "tools\grand_prix\$source"
}
Copy-Source 'controllers\grand_prix_u_evaluator\grand_prix_u_evaluator.py' 'controllers\grand_prix_u_evaluator\evaluator_impl.py'
Copy-Source 'packaging\windows\grand_prix_evaluator_bootstrap.py' 'controllers\grand_prix_u_evaluator\grand_prix_u_evaluator.py'
Copy-Source 'packaging\windows\grand_prix_python_lock.json' 'PYTHON-SOURCE.json'
Copy-Source 'docs\GRAND_PRIX_WINDOWS_EVALUATOR.md' 'README.md'
# Webots R2025a resolves $(...) using the controller environment before COMMAND.
# A future product launcher must set this to the absolute packaged executable.
# No PATH/default-Python fallback is admitted by this controller configuration.
$ini = "[python]`nCOMMAND = `$(WEBEEBLOCKS_GP_PYTHON)`nOPTIONS = -I`n"
[IO.File]::WriteAllText((Join-Path $package 'controllers\grand_prix_u_evaluator\runtime.ini'), $ini, [Text.UTF8Encoding]::new($false))
$sourceSha = (& git -C $repoRoot rev-parse HEAD | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $sourceSha -notmatch '^[0-9a-f]{40}$') { throw 'Exact source SHA unavailable.' }
[IO.File]::WriteAllText((Join-Path $package 'SOURCE_SHA'), "$sourceSha`n", [Text.UTF8Encoding]::new($false))
$manifest = @(Get-ChildItem -LiteralPath $package -Recurse -File | Sort-Object FullName | ForEach-Object {
  $relative = [IO.Path]::GetRelativePath($package, $_.FullName).Replace('\', '/')
  $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
  "$hash  $relative"
})
[IO.File]::WriteAllText((Join-Path $package 'MANIFEST.sha256'), (($manifest -join "`n") + "`n"), [Text.UTF8Encoding]::new($false))
Compress-Archive -Path (Join-Path $package '*') -DestinationPath $archive -CompressionLevel Optimal
Write-Host "WEBEEBLOCKS_GP_EVALUATOR_ARCHIVE=$archive"

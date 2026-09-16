$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$rootDir = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$blocklyDir = Join-Path $rootDir 'plugins\robot_windows\blockly_v2'

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  throw 'Node.js >= 22 is required to prepare Runtime v2 Blockly assets.'
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw 'npm is required to prepare Runtime v2 Blockly assets.'
}

$nodeMajor = [int](& node -p "Number(process.versions.node.split('.')[0])")
if ($nodeMajor -lt 22) {
  throw "Node.js >= 22 is required; found $(& node --version)."
}

Push-Location $blocklyDir
try {
  & npm ci --ignore-scripts --no-audit --no-fund
  if ($LASTEXITCODE -ne 0) { throw "npm ci failed with exit code $LASTEXITCODE." }

  & npm run prepare:blockly
  if ($LASTEXITCODE -ne 0) { throw "npm run prepare:blockly failed with exit code $LASTEXITCODE." }

  $versionFile = Join-Path $blocklyDir 'vendor\VERSION'
  if ((Get-Content -Raw $versionFile).Trim() -ne '13.2.1') {
    throw 'Prepared Blockly version is not 13.2.1.'
  }

  foreach ($relativePath in @(
    'vendor\blockly_compressed.js',
    'vendor\blocks_compressed.js',
    'vendor\msg\fr.js',
    'webots\RobotWindow.js',
    'webots\request_methods.js'
  )) {
    $path = Join-Path $blocklyDir $relativePath
    if (-not (Test-Path -Path $path -PathType Leaf) -or (Get-Item $path).Length -le 0) {
      throw "Required prepared asset is missing or empty: $relativePath"
    }
  }

  $progressionSource = Join-Path $rootDir 'activities\progression'
  $progressionManifestPath = Join-Path $progressionSource 'index.json'
  if (-not (Test-Path -LiteralPath $progressionManifestPath -PathType Leaf)) {
    throw 'Classroom progression starter manifest is missing.'
  }
  $progressionManifest = Get-Content -LiteralPath $progressionManifestPath -Raw | ConvertFrom-Json
  if ($null -eq $progressionManifest -or $progressionManifest.version -ne 1 -or $null -eq $progressionManifest.starters) {
    throw 'Classroom progression starter manifest is invalid.'
  }
  $progressionEntries = @($progressionManifest.starters)
  if ($progressionEntries.Count -eq 0) {
    throw 'Classroom progression starter manifest is empty.'
  }

  $declaredFiles = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
  $declaredActivityIds = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
  foreach ($entry in $progressionEntries) {
    $file = [string]$entry.file
    $activityId = [string]$entry.activityId
    if ($file -notmatch '^\d{2}-[a-z0-9-]+\.wbb$' -or [System.IO.Path]::GetFileName($file) -ne $file) {
      throw "Invalid classroom progression starter filename: $file"
    }
    if ($activityId -notmatch '^progression-[a-z0-9-]+-v1$') {
      throw "Invalid classroom progression activity id: $activityId"
    }
    if (-not $declaredFiles.Add($file) -or -not $declaredActivityIds.Add($activityId)) {
      throw "Duplicate classroom progression starter declaration: $file / $activityId"
    }

    $starterPath = Join-Path $progressionSource $file
    if (-not (Test-Path -LiteralPath $starterPath -PathType Leaf)) {
      throw "Declared classroom progression starter is missing: $file"
    }
    $project = Get-Content -LiteralPath $starterPath -Raw | ConvertFrom-Json
    if ($project.format -ne 'webeeblocks-project' -or $project.version -ne 1) {
      throw "Classroom progression starter has an invalid project format: $file"
    }
    if ($project.activity.id -ne $activityId -or $project.activity.semantics -ne 'webeeblocks-ast-v1') {
      throw "Classroom progression starter does not match its manifest activity: $file"
    }
  }

  $sourceStarterFiles = @(Get-ChildItem -LiteralPath $progressionSource -File -Filter '*.wbb' | Sort-Object Name | ForEach-Object { $_.Name })
  $declaredStarterFiles = @($progressionEntries | ForEach-Object { [string]$_.file } | Sort-Object)
  if (($sourceStarterFiles -join "`n") -ne ($declaredStarterFiles -join "`n")) {
    throw 'Classroom progression manifest must declare every progression starter exactly once.'
  }

  $progressionTarget = Join-Path $blocklyDir 'vendor\classroom-activities\progression'
  if (Test-Path -LiteralPath $progressionTarget) {
    Remove-Item -LiteralPath $progressionTarget -Recurse -Force
  }
  New-Item -ItemType Directory -Path $progressionTarget -Force | Out-Null
  Copy-Item -LiteralPath $progressionManifestPath -Destination (Join-Path $progressionTarget 'index.json') -Force
  foreach ($entry in $progressionEntries) {
    $file = [string]$entry.file
    Copy-Item -LiteralPath (Join-Path $progressionSource $file) -Destination (Join-Path $progressionTarget $file) -Force
  }
  $packagedStarterFiles = @(Get-ChildItem -LiteralPath $progressionTarget -File -Filter '*.wbb' | Sort-Object Name | ForEach-Object { $_.Name })
  if (($packagedStarterFiles -join "`n") -ne ($declaredStarterFiles -join "`n")) {
    throw 'Prepared classroom progression starter bundle is incomplete.'
  }

  $mediaDir = Join-Path $blocklyDir 'vendor\media'
  if (-not (Test-Path -Path $mediaDir -PathType Container)) {
    throw 'Required Blockly media directory is missing.'
  }
}
finally {
  Pop-Location
}

Write-Host 'Runtime v2 Blockly assets ready: blockly@13.2.1 + classroom progression starters'

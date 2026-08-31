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
  & npm install --ignore-scripts --no-audit --no-fund
  if ($LASTEXITCODE -ne 0) { throw "npm install failed with exit code $LASTEXITCODE." }

  & npm run prepare:blockly
  if ($LASTEXITCODE -ne 0) { throw "npm run prepare:blockly failed with exit code $LASTEXITCODE." }

  $versionFile = Join-Path $blocklyDir 'vendor\VERSION'
  if ((Get-Content -Raw $versionFile).Trim() -ne '13.2.1') {
    throw 'Prepared Blockly version is not 13.2.1.'
  }

  foreach ($relativePath in @(
    'vendor\blockly_compressed.js',
    'vendor\blocks_compressed.js',
    'vendor\msg\fr.js'
  )) {
    $path = Join-Path $blocklyDir $relativePath
    if (-not (Test-Path -Path $path -PathType Leaf) -or (Get-Item $path).Length -le 0) {
      throw "Required prepared asset is missing or empty: $relativePath"
    }
  }

  $mediaDir = Join-Path $blocklyDir 'vendor\media'
  if (-not (Test-Path -Path $mediaDir -PathType Container)) {
    throw 'Required Blockly media directory is missing.'
  }
}
finally {
  Pop-Location
}

Write-Host 'Runtime v2 Blockly assets ready: blockly@13.2.1'

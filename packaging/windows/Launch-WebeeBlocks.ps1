[CmdletBinding()]
param(
  [string]$WebotsHome = $env:WEBOTS_HOME,
  [switch]$ValidateOnly,
  [switch]$ServeAssets,
  [string]$ServeAssetsRoot,
  [string]$ServeAssetsReadyFile,
  [int]$ServeAssetsParentPid = 0
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Write-WebeeBlocksReply {
  param(
    [System.Net.Sockets.NetworkStream]$Stream,
    [int]$Status,
    [string]$Reason,
    [string]$ContentType,
    [byte[]]$Body
  )
  $header = "HTTP/1.1 $Status $Reason`r`n" +
            "Content-Type: $ContentType`r`n" +
            "Content-Length: $($Body.Length)`r`n" +
            "Cache-Control: no-store, no-cache, must-revalidate`r`n" +
            "Pragma: no-cache`r`n" +
            "Access-Control-Allow-Origin: *`r`n" +
            "Connection: close`r`n`r`n"
  $headerBytes = [System.Text.Encoding]::ASCII.GetBytes($header)
  $Stream.Write($headerBytes, 0, $headerBytes.Length)
  if ($Body.Length -gt 0) {
    $Stream.Write($Body, 0, $Body.Length)
  }
  $Stream.Flush()
}

function Get-WebeeBlocksContentType {
  param([string]$Path)
  switch ([System.IO.Path]::GetExtension($Path).ToLowerInvariant()) {
    '.html' { return 'text/html; charset=utf-8' }
    '.css' { return 'text/css; charset=utf-8' }
    '.js' { return 'application/javascript; charset=utf-8' }
    '.json' { return 'application/json; charset=utf-8' }
    '.png' { return 'image/png' }
    '.jpg' { return 'image/jpeg' }
    '.jpeg' { return 'image/jpeg' }
    '.svg' { return 'image/svg+xml' }
    '.ico' { return 'image/x-icon' }
    default { return 'application/octet-stream' }
  }
}

function Invoke-WebeeBlocksAssetServer {
  param(
    [string]$Root,
    [string]$ReadyFile,
    [int]$ParentProcessId
  )

  if ($ParentProcessId -le 0) {
    throw 'Le serveur HTTP local exige un processus parent valide.'
  }
  $rootPath = [System.IO.Path]::GetFullPath($Root)
  if (-not (Test-Path -LiteralPath $rootPath -PathType Container)) {
    throw "Racine HTTP locale introuvable : $rootPath"
  }
  $rootPrefix = $rootPath + [System.IO.Path]::DirectorySeparatorChar
  $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
  try {
    $listener.Start()
    $port = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
    $readyTempFile = $ReadyFile + '.tmp'
    Remove-Item -LiteralPath $readyTempFile -Force -ErrorAction SilentlyContinue
    [System.IO.File]::WriteAllText($readyTempFile, [string]$port, [System.Text.UTF8Encoding]::new($false))
    [System.IO.File]::Move($readyTempFile, $ReadyFile)

    while ($true) {
      $parent = Get-Process -Id $ParentProcessId -ErrorAction SilentlyContinue
      if ($null -eq $parent) { break }
      if (-not $listener.Pending()) {
        Start-Sleep -Milliseconds 50
        continue
      }

      $client = $listener.AcceptTcpClient()
      $stream = $null
      $reader = $null
      try {
        $stream = $client.GetStream()
        $reader = [System.IO.StreamReader]::new($stream, [System.Text.Encoding]::ASCII, $false, 4096, $true)
        $requestLine = $reader.ReadLine()
        if ([string]::IsNullOrWhiteSpace($requestLine)) {
          continue
        }
        while ($true) {
          $headerLine = $reader.ReadLine()
          if ($null -eq $headerLine -or $headerLine.Length -eq 0) { break }
        }
        $parts = $requestLine.Split(' ')
        if ($parts.Count -lt 2 -or $parts[0] -ne 'GET') {
          Write-WebeeBlocksReply $stream 405 'Method Not Allowed' 'text/plain; charset=utf-8' ([System.Text.Encoding]::UTF8.GetBytes('Method Not Allowed'))
          continue
        }

        $requestUri = [System.Uri]::new('http://127.0.0.1' + $parts[1])
        $relative = [System.Uri]::UnescapeDataString($requestUri.AbsolutePath.TrimStart('/')).Replace('/', [System.IO.Path]::DirectorySeparatorChar)
        if ([string]::IsNullOrWhiteSpace($relative)) {
          Write-WebeeBlocksReply $stream 404 'Not Found' 'text/plain; charset=utf-8' ([System.Text.Encoding]::UTF8.GetBytes('Not Found'))
          continue
        }
        $target = [System.IO.Path]::GetFullPath((Join-Path $rootPath $relative))
        if (-not $target.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase) -or
            -not (Test-Path -LiteralPath $target -PathType Leaf)) {
          Write-WebeeBlocksReply $stream 404 'Not Found' 'text/plain; charset=utf-8' ([System.Text.Encoding]::UTF8.GetBytes('Not Found'))
          continue
        }
        $body = [System.IO.File]::ReadAllBytes($target)
        Write-WebeeBlocksReply $stream 200 'OK' (Get-WebeeBlocksContentType $target) $body
      }
      catch {
        try {
          if ($null -ne $stream) {
            Write-WebeeBlocksReply $stream 500 'Internal Server Error' 'text/plain; charset=utf-8' ([System.Text.Encoding]::UTF8.GetBytes('Internal Server Error'))
          }
        }
        catch { }
      }
      finally {
        if ($null -ne $reader) { $reader.Dispose() }
        if ($null -ne $stream) { $stream.Dispose() }
        $client.Close()
      }
    }
  }
  finally {
    $listener.Stop()
  }
}

if ($ServeAssets) {
  if ([string]::IsNullOrWhiteSpace($ServeAssetsRoot) -or
      [string]::IsNullOrWhiteSpace($ServeAssetsReadyFile) -or
      $ServeAssetsParentPid -le 0) {
    throw 'Arguments du serveur HTTP local incomplets.'
  }
  Invoke-WebeeBlocksAssetServer -Root $ServeAssetsRoot -ReadyFile $ServeAssetsReadyFile -ParentProcessId $ServeAssetsParentPid
  exit 0
}

$world = Join-Path $PSScriptRoot 'worlds\crazyflie_runtime_v2.wbt'
if (-not (Test-Path -LiteralPath $world -PathType Leaf)) {
  throw "Monde WebeeBlocks introuvable : $world"
}

$worldText = Get-Content -LiteralPath $world -Raw
if ($worldText -match '"(?:https?|webots)://') {
  throw 'Le monde de classe contient encore une ressource distante.'
}

function Get-PackagedRobotWindow {
  param([string]$WorldText)

  $matches = [regex]::Matches($WorldText, '(?m)^\s*window\s+"(blockly_v2_[0-9a-f]{16})"\s*$')
  if ($matches.Count -ne 1) {
    throw 'Le monde de classe doit contenir exactement une Robot Window versionnee.'
  }
  $name = $matches[0].Groups[1].Value
  $root = Join-Path $PSScriptRoot "plugins\robot_windows\$name"
  $html = Join-Path $root "$name.html"
  if (-not (Test-Path -LiteralPath $root -PathType Container) -or -not (Test-Path -LiteralPath $html -PathType Leaf)) {
    throw "Robot Window de classe introuvable : $name"
  }
  [PSCustomObject]@{ Name = $name; Root = $root; Html = $html }
}

function Quote-WebeeBlocksProcessArgument {
  param([string]$Value)
  if ($Value.Contains('"')) {
    throw 'Un chemin du lanceur contient un guillemet non pris en charge.'
  }
  return '"' + $Value + '"'
}

function Start-WebeeBlocksLocalServer {
  param([string]$Root)

  if ([string]::IsNullOrWhiteSpace($PSCommandPath) -or -not (Test-Path -LiteralPath $PSCommandPath -PathType Leaf)) {
    throw 'Script du lanceur WebeeBlocks introuvable.'
  }
  $token = [Guid]::NewGuid().ToString('N')
  $readyFile = Join-Path ([System.IO.Path]::GetTempPath()) "webeeblocks-assets-$token.ready"
  $errorFile = Join-Path ([System.IO.Path]::GetTempPath()) "webeeblocks-assets-$token.stderr.log"
  $readyTempFile = $readyFile + '.tmp'
  Remove-Item -LiteralPath $readyFile, $readyTempFile, $errorFile -Force -ErrorAction SilentlyContinue

  $arguments = @(
    '-NoLogo',
    '-NoProfile',
    '-NonInteractive',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    (Quote-WebeeBlocksProcessArgument $PSCommandPath),
    '-ServeAssets',
    '-ServeAssetsRoot',
    (Quote-WebeeBlocksProcessArgument $Root),
    '-ServeAssetsReadyFile',
    (Quote-WebeeBlocksProcessArgument $readyFile),
    '-ServeAssetsParentPid',
    [string]$PID
  )
  $process = Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -WindowStyle Hidden -RedirectStandardError $errorFile -PassThru
  $deadline = [DateTime]::UtcNow.AddSeconds(8)
  do {
    if (Test-Path -LiteralPath $readyFile -PathType Leaf) {
      $readyText = (Get-Content -LiteralPath $readyFile -Raw).Trim()
      $port = 0
      if ([int]::TryParse($readyText, [ref]$port) -and $port -gt 0 -and $port -le 65535) {
        return [PSCustomObject]@{
          Process = $process
          Port = $port
          ReadyFile = $readyFile
          ReadyTempFile = $readyTempFile
          ErrorFile = $errorFile
        }
      }
      Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
      $process.WaitForExit()
      Remove-Item -LiteralPath $readyFile, $readyTempFile, $errorFile -Force -ErrorAction SilentlyContinue
      throw "Port HTTP local invalide : $readyText"
    }
    $process.Refresh()
    if ($process.HasExited) {
      $detail = if (Test-Path -LiteralPath $errorFile -PathType Leaf) { (Get-Content -LiteralPath $errorFile -Raw).Trim() } else { '' }
      if ([string]::IsNullOrWhiteSpace($detail)) { $detail = "code $($process.ExitCode)" }
      Remove-Item -LiteralPath $readyFile, $readyTempFile, $errorFile -Force -ErrorAction SilentlyContinue
      throw "Le serveur HTTP local WebeeBlocks a echoue : $detail"
    }
    Start-Sleep -Milliseconds 100
  } while ([DateTime]::UtcNow -lt $deadline)

  Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
  $process.WaitForExit()
  Remove-Item -LiteralPath $readyFile, $readyTempFile, $errorFile -Force -ErrorAction SilentlyContinue
  throw 'Le serveur HTTP local WebeeBlocks ne s est pas initialise.'
}

function Stop-WebeeBlocksLocalServer {
  param($Server)
  if ($null -eq $Server) { return }
  if ($null -ne $Server.Process) {
    $Server.Process.Refresh()
    if (-not $Server.Process.HasExited) {
      Stop-Process -Id $Server.Process.Id -Force -ErrorAction SilentlyContinue
      $Server.Process.WaitForExit()
    }
  }
  Remove-Item -LiteralPath $Server.ReadyFile, $Server.ReadyTempFile, $Server.ErrorFile -Force -ErrorAction SilentlyContinue
}

function Convert-RobotWindowChildUrls {
  param(
    [string]$Html,
    [string]$PluginRoot,
    [int]$Port
  )

  $packageRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
  $packagePrefix = $packageRoot + [System.IO.Path]::DirectorySeparatorChar
  $pattern = '(?<prefix>(?:src|href)=")(?<url>[^"]+)(?<suffix>")'
  $rewritten = [regex]::Replace(
    $Html,
    $pattern,
    [System.Text.RegularExpressions.MatchEvaluator]{
      param($match)
      $url = $match.Groups['url'].Value
      if ($url -match '^(?:[a-z][a-z0-9+.-]*:|//|#)') {
        throw "Dependance Robot Window non locale inattendue : $url"
      }
      $assetRelative = ($url -split '[?#]', 2)[0]
      $assetPath = [System.IO.Path]::GetFullPath((Join-Path $PluginRoot $assetRelative))
      if (-not $assetPath.StartsWith($packagePrefix, [System.StringComparison]::OrdinalIgnoreCase) -or
          -not (Test-Path -LiteralPath $assetPath -PathType Leaf)) {
        throw "Dependance Robot Window absente du paquet : $assetRelative"
      }
      $packageRelative = $assetPath.Substring($packagePrefix.Length).Replace('\', '/')
      $queryIndex = $url.IndexOf('?')
      $query = if ($queryIndex -ge 0) { $url.Substring($queryIndex) } else { '' }
      return $match.Groups['prefix'].Value + "http://127.0.0.1:$Port/$packageRelative$query" + $match.Groups['suffix'].Value
    }
  )
  return $rewritten
}

function Assert-LocalServerFile {
  param(
    [int]$Port,
    [string]$RelativePath,
    [string]$ExpectedContentType
  )

  $normalized = $RelativePath.Replace('\', '/')
  $uri = [System.Uri]::new("http://127.0.0.1:$Port/$normalized")
  $request = [System.Net.HttpWebRequest]::Create($uri)
  $request.KeepAlive = $true
  $response = [System.Net.HttpWebResponse]$request.GetResponse()
  try {
    if ($response.StatusCode -ne [System.Net.HttpStatusCode]::OK) {
      throw "Reponse HTTP locale inattendue pour $RelativePath : $($response.StatusCode)"
    }
    if (-not $response.ContentType.StartsWith($ExpectedContentType, [System.StringComparison]::OrdinalIgnoreCase)) {
      throw "Type MIME HTTP local inattendu pour $RelativePath : $($response.ContentType)"
    }
    if (-not [string]::Equals($response.Headers['Connection'], 'close', [System.StringComparison]::OrdinalIgnoreCase)) {
      throw "Le serveur HTTP local ne ferme pas explicitement la connexion pour $RelativePath."
    }
    $memory = [System.IO.MemoryStream]::new()
    try {
      $response.GetResponseStream().CopyTo($memory)
      $actualBytes = $memory.ToArray()
    }
    finally {
      $memory.Dispose()
    }
    $expectedBytes = [System.IO.File]::ReadAllBytes((Join-Path $PSScriptRoot $RelativePath))
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
      $actualHash = [System.BitConverter]::ToString($sha.ComputeHash($actualBytes))
      $expectedHash = [System.BitConverter]::ToString($sha.ComputeHash($expectedBytes))
    }
    finally {
      $sha.Dispose()
    }
    if ($actualHash -ne $expectedHash) {
      throw "Octets HTTP locaux incoherents pour $RelativePath."
    }
  }
  finally {
    $response.Close()
  }
}

$candidates = [System.Collections.Generic.List[string]]::new()
foreach ($candidateHome in @($WebotsHome, (Join-Path $env:ProgramFiles 'Webots'))) {
  if ([string]::IsNullOrWhiteSpace($candidateHome)) { continue }
  $candidates.Add((Join-Path $candidateHome 'msys64\mingw64\bin\webotsw.exe'))
  $candidates.Add((Join-Path $candidateHome 'msys64\mingw64\bin\webots.exe'))
}
foreach ($commandName in @('webotsw.exe', 'webots.exe')) {
  $command = Get-Command $commandName -ErrorAction SilentlyContinue
  if ($null -ne $command) { $candidates.Add($command.Source) }
}

function Test-WebotsR2025a {
  param([string]$Executable)
  if ([string]::IsNullOrWhiteSpace($Executable) -or -not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
    return $false
  }
  $versionExecutable = $Executable
  if ([System.IO.Path]::GetFileName($Executable).Equals('webotsw.exe', [System.StringComparison]::OrdinalIgnoreCase)) {
    $consoleExecutable = Join-Path (Split-Path $Executable -Parent) 'webots.exe'
    if (-not (Test-Path -LiteralPath $consoleExecutable -PathType Leaf)) { return $false }
    $versionExecutable = $consoleExecutable
  }
  $version = (& $versionExecutable --version 2>&1 | Out-String).Trim()
  return ($LASTEXITCODE -eq 0 -and $version -match 'R2025a')
}

$webots = $candidates | Where-Object { Test-WebotsR2025a -Executable $_ } | Select-Object -First 1
if ([string]::IsNullOrWhiteSpace($webots)) {
  throw 'Webots R2025a est introuvable. Installez exactement R2025a dans C:\Program Files\Webots ou definissez WEBOTS_HOME.'
}

$robotWindow = Get-PackagedRobotWindow -WorldText $worldText

if ($ValidateOnly) {
  $launcherText = [System.IO.File]::ReadAllText($PSCommandPath, [System.Text.Encoding]::UTF8)
  foreach ($jobVerb in @('Start', 'Receive', 'Stop', 'Remove')) {
    $forbiddenJobCommand = $jobVerb + '-Job'
    if ($launcherText -match ('(?m)\b' + [regex]::Escape($forbiddenJobCommand) + '\b')) {
      throw "Le lanceur de classe ne doit pas executer de job PowerShell : $forbiddenJobCommand"
    }
  }

  $server = $null
  try {
    $server = Start-WebeeBlocksLocalServer -Root $PSScriptRoot
    $htmlRelative = "plugins\robot_windows\$($robotWindow.Name)\$($robotWindow.Name).html"
    Assert-LocalServerFile -Port $server.Port -RelativePath $htmlRelative -ExpectedContentType 'text/html'
    Assert-LocalServerFile -Port $server.Port -RelativePath (Join-Path "plugins\robot_windows\$($robotWindow.Name)" 'main.css') -ExpectedContentType 'text/css'
    Assert-LocalServerFile -Port $server.Port -RelativePath (Join-Path "plugins\robot_windows\$($robotWindow.Name)" 'vendor\msg\fr.js') -ExpectedContentType 'application/javascript'
    Assert-LocalServerFile -Port $server.Port -RelativePath 'plugins\robot_windows\blockly\webeeblocks\semantic_ast.js' -ExpectedContentType 'application/javascript'

    $originalHtml = [System.IO.File]::ReadAllText($robotWindow.Html, [System.Text.Encoding]::UTF8)
    $rewrittenHtml = Convert-RobotWindowChildUrls -Html $originalHtml -PluginRoot $robotWindow.Root -Port $server.Port
    $references = [regex]::Matches($rewrittenHtml, '(?:src|href)="([^"]+)"')
    if ($references.Count -lt 10) { throw 'La Robot Window re-ecrite contient trop peu de dependances pour valider le pont HTTP.' }
    foreach ($reference in $references) {
      if (-not $reference.Groups[1].Value.StartsWith("http://127.0.0.1:$($server.Port)/", [System.StringComparison]::Ordinal)) {
        throw "Une dependance de demarrage contourne le serveur HTTP local : $($reference.Groups[1].Value)"
      }
    }
  }
  finally {
    Stop-WebeeBlocksLocalServer -Server $server
  }
  Write-Host "WEBEEBLOCKS_WINDOWS_LAUNCHER_OK webots=$webots world=$world version=R2025a mode=realtime local_http=loopback-connection-close process_isolated=true"
  exit 0
}

if ($world.Contains('"')) { throw 'Le chemin du monde contient un guillemet non pris en charge.' }
$worldArgument = '"' + $world + '"'
$server = $null
$originalHtml = $null
$webotsProcess = $null
try {
  $server = Start-WebeeBlocksLocalServer -Root $PSScriptRoot
  $originalHtml = [System.IO.File]::ReadAllText($robotWindow.Html, [System.Text.Encoding]::UTF8)
  $proxiedHtml = Convert-RobotWindowChildUrls -Html $originalHtml -PluginRoot $robotWindow.Root -Port $server.Port
  $proxiedHtml = $proxiedHtml.Replace('<head>', '<head><link rel="icon" href="data:,">')
  [System.IO.File]::WriteAllText($robotWindow.Html, $proxiedHtml, [System.Text.UTF8Encoding]::new($false))

  $webotsProcess = Start-Process -FilePath $webots -ArgumentList @('--mode=realtime', $worldArgument) -WorkingDirectory $PSScriptRoot -PassThru
  Write-Host "WebeeBlocks demarre. La simulation et la fenetre Blockly vont s'initialiser automatiquement."
  $webotsProcess.WaitForExit()
  if ($webotsProcess.ExitCode -ne 0) {
    throw "Webots s'est termine avec le code $($webotsProcess.ExitCode)."
  }
}
finally {
  if ($null -ne $originalHtml) {
    [System.IO.File]::WriteAllText($robotWindow.Html, $originalHtml, [System.Text.UTF8Encoding]::new($false))
  }
  Stop-WebeeBlocksLocalServer -Server $server
}

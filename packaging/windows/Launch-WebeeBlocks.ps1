[CmdletBinding()]
param(
  [string]$WebotsHome = $env:WEBOTS_HOME,
  [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$WebeeBlocksLocalServerPort = 18455

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

function Start-WebeeBlocksLocalServer {
  param(
    [string]$Root,
    [int]$Port
  )

  $rootPath = [System.IO.Path]::GetFullPath($Root)
  $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
  try {
    $listener.Start()
    $boundPort = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
    if ($boundPort -ne $Port) {
      throw "Le serveur HTTP local WebeeBlocks a obtenu le port inattendu $boundPort au lieu de $Port."
    }
    return [PSCustomObject]@{ Listener = $listener; Port = $boundPort; Root = $rootPath }
  }
  catch {
    $listener.Stop()
    throw
  }
}

function Invoke-WebeeBlocksLocalServerRequest {
  param($Server)

  if ($null -eq $Server -or -not $Server.Listener.Pending()) { return $false }
  $client = $Server.Listener.AcceptTcpClient()
  $client.ReceiveTimeout = 5000
  $client.SendTimeout = 5000
  $stream = $null
  $reader = $null
  try {
    $stream = $client.GetStream()
    $reader = [System.IO.StreamReader]::new($stream, [System.Text.Encoding]::ASCII, $false, 4096, $true)
    $requestLine = $reader.ReadLine()
    if ([string]::IsNullOrWhiteSpace($requestLine)) { return $true }
    while ($true) {
      $headerLine = $reader.ReadLine()
      if ($null -eq $headerLine -or $headerLine.Length -eq 0) { break }
    }
    $parts = $requestLine.Split(' ')
    if ($parts.Count -lt 2 -or $parts[0] -ne 'GET') {
      Write-WebeeBlocksReply $stream 405 'Method Not Allowed' 'text/plain; charset=utf-8' ([System.Text.Encoding]::UTF8.GetBytes('Method Not Allowed'))
      return $true
    }

    $requestUri = [System.Uri]::new('http://127.0.0.1' + $parts[1])
    $relative = [System.Uri]::UnescapeDataString($requestUri.AbsolutePath.TrimStart('/')).Replace('/', [System.IO.Path]::DirectorySeparatorChar)
    if ([string]::IsNullOrWhiteSpace($relative)) {
      Write-WebeeBlocksReply $stream 404 'Not Found' 'text/plain; charset=utf-8' ([System.Text.Encoding]::UTF8.GetBytes('Not Found'))
      return $true
    }
    $rootPrefix = $Server.Root + [System.IO.Path]::DirectorySeparatorChar
    $target = [System.IO.Path]::GetFullPath((Join-Path $Server.Root $relative))
    if (-not $target.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase) -or
        -not (Test-Path -LiteralPath $target -PathType Leaf)) {
      Write-WebeeBlocksReply $stream 404 'Not Found' 'text/plain; charset=utf-8' ([System.Text.Encoding]::UTF8.GetBytes('Not Found'))
      return $true
    }
    $body = [System.IO.File]::ReadAllBytes($target)
    Write-WebeeBlocksReply $stream 200 'OK' (Get-WebeeBlocksContentType $target) $body
    return $true
  }
  catch {
    try {
      if ($null -ne $stream) {
        Write-WebeeBlocksReply $stream 500 'Internal Server Error' 'text/plain; charset=utf-8' ([System.Text.Encoding]::UTF8.GetBytes('Internal Server Error'))
      }
    }
    catch { }
    return $true
  }
  finally {
    if ($null -ne $reader) { $reader.Dispose() }
    if ($null -ne $stream) { $stream.Dispose() }
    $client.Close()
  }
}

function Stop-WebeeBlocksLocalServer {
  param($Server)
  if ($null -eq $Server) { return }
  $Server.Listener.Stop()
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

function Set-WebeeBlocksRobotWindowHtml {
  param(
    $RobotWindow,
    [string]$OriginalHtml,
    [int]$Port
  )
  $rewritten = Convert-RobotWindowChildUrls -Html $OriginalHtml -PluginRoot $RobotWindow.Root -Port $Port
  $rewritten = $rewritten.Replace('<head>', '<head><link rel="icon" href="data:,">')
  [System.IO.File]::WriteAllText($RobotWindow.Html, $rewritten, [System.Text.UTF8Encoding]::new($false))
  return $rewritten
}

function Assert-LocalServerFile {
  param(
    $Server,
    [string]$RelativePath,
    [string]$ExpectedContentType
  )

  $normalized = $RelativePath.Replace('\', '/')
  $uri = [System.Uri]::new("http://127.0.0.1:$($Server.Port)/$normalized")
  $request = [System.Net.HttpWebRequest]::Create($uri)
  $request.KeepAlive = $true
  $async = $request.BeginGetResponse($null, $null)
  $deadline = [DateTime]::UtcNow.AddSeconds(8)
  while (-not $async.AsyncWaitHandle.WaitOne(10)) {
    while (Invoke-WebeeBlocksLocalServerRequest -Server $Server) { }
    if ([DateTime]::UtcNow -ge $deadline) {
      throw "Le serveur HTTP local ne repond pas pour $RelativePath."
    }
  }
  while (Invoke-WebeeBlocksLocalServerRequest -Server $Server) { }
  $response = [System.Net.HttpWebResponse]$request.EndGetResponse($async)
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

function Assert-LocalServerRecoversFromAbortedRequest {
  param(
    $Server,
    [string]$RelativePath,
    [string]$ExpectedContentType
  )

  $client = [System.Net.Sockets.TcpClient]::new()
  try {
    $client.LingerState = [System.Net.Sockets.LingerOption]::new($true, 0)
    $client.Connect([System.Net.IPAddress]::Loopback, $Server.Port)
    $stream = $client.GetStream()
    $partial = [System.Text.Encoding]::ASCII.GetBytes('GET /aborted-request')
    $stream.Write($partial, 0, $partial.Length)
    $stream.Flush()
  }
  finally {
    $client.Close()
  }

  $deadline = [DateTime]::UtcNow.AddSeconds(5)
  while (-not $Server.Listener.Pending()) {
    if ([DateTime]::UtcNow -ge $deadline) {
      throw 'La requete HTTP interrompue n a pas atteint le serveur local.'
    }
    Start-Sleep -Milliseconds 10
  }
  if (-not (Invoke-WebeeBlocksLocalServerRequest -Server $Server)) {
    throw 'Le serveur local n a pas traite la requete HTTP interrompue.'
  }

  Assert-LocalServerFile -Server $Server -RelativePath $RelativePath -ExpectedContentType $ExpectedContentType
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
$originalHtml = [System.IO.File]::ReadAllText($robotWindow.Html, [System.Text.Encoding]::UTF8)

if ($ValidateOnly) {
  for ($attempt = 1; $attempt -le 2; $attempt++) {
    $server = $null
    try {
      $server = Start-WebeeBlocksLocalServer -Root $PSScriptRoot -Port $WebeeBlocksLocalServerPort
      if ($server.Port -ne $WebeeBlocksLocalServerPort) {
        throw "Le serveur HTTP local doit conserver le port $WebeeBlocksLocalServerPort entre les relances."
      }
      $rewritten = Set-WebeeBlocksRobotWindowHtml -RobotWindow $robotWindow -OriginalHtml $originalHtml -Port $server.Port
      if (-not $worldText.Contains(('window "' + $robotWindow.Name + '"'))) {
        throw 'Le monde de classe ne conserve pas l identite Robot Window stable.'
      }
      $faviconMarker = '<link rel="icon" href="data:,">'
      if ([regex]::Matches($rewritten, [regex]::Escape($faviconMarker)).Count -ne 1) {
        throw 'La Robot Window doit neutraliser exactement une requete favicon implicite.'
      }
      $dependencyHtml = $rewritten.Replace($faviconMarker, '')
      $references = [regex]::Matches($dependencyHtml, '(?:src|href)="([^"]+)"')
      if ($references.Count -lt 10) {
        throw 'La Robot Window contient trop peu de dependances pour valider le pont HTTP.'
      }
      foreach ($reference in $references) {
        if (-not $reference.Groups[1].Value.StartsWith("http://127.0.0.1:$WebeeBlocksLocalServerPort/", [System.StringComparison]::Ordinal)) {
          throw "Une dependance de demarrage contourne l origine HTTP locale stable : $($reference.Groups[1].Value)"
        }
      }
      $robotWindowRelative = "plugins\robot_windows\$($robotWindow.Name)"
      Assert-LocalServerRecoversFromAbortedRequest -Server $server -RelativePath (Join-Path $robotWindowRelative 'main.css') -ExpectedContentType 'text/css'
      Assert-LocalServerFile -Server $server -RelativePath (Join-Path $robotWindowRelative "$($robotWindow.Name).html") -ExpectedContentType 'text/html'
      Assert-LocalServerFile -Server $server -RelativePath (Join-Path $robotWindowRelative 'main.css') -ExpectedContentType 'text/css'
      Assert-LocalServerFile -Server $server -RelativePath (Join-Path $robotWindowRelative 'vendor\msg\fr.js') -ExpectedContentType 'application/javascript'
      Assert-LocalServerFile -Server $server -RelativePath 'plugins\robot_windows\blockly\webeeblocks\semantic_ast.js' -ExpectedContentType 'application/javascript'
    }
    finally {
      [System.IO.File]::WriteAllText($robotWindow.Html, $originalHtml, [System.Text.UTF8Encoding]::new($false))
      Stop-WebeeBlocksLocalServer -Server $server
    }
  }
  Write-Host "WEBEEBLOCKS_WINDOWS_LAUNCHER_OK webots=$webots world=$world version=R2025a mode=realtime local_http=loopback-port-$WebeeBlocksLocalServerPort-stable-window-identity-connection-close"
  exit 0
}

$server = $null
$webotsProcess = $null
try {
  $server = Start-WebeeBlocksLocalServer -Root $PSScriptRoot -Port $WebeeBlocksLocalServerPort
  Set-WebeeBlocksRobotWindowHtml -RobotWindow $robotWindow -OriginalHtml $originalHtml -Port $server.Port | Out-Null

  if ($world.Contains('"')) { throw 'Le chemin du monde contient un guillemet non pris en charge.' }
  $worldArgument = '"' + $world + '"'
  $webotsProcess = Start-Process -FilePath $webots -ArgumentList @('--mode=realtime', $worldArgument) -WorkingDirectory $PSScriptRoot -PassThru
  Write-Host "WebeeBlocks demarre. La simulation et la fenetre Blockly vont s'initialiser automatiquement."

  while (-not $webotsProcess.WaitForExit(15)) {
    while (Invoke-WebeeBlocksLocalServerRequest -Server $server) { }
  }
  while (Invoke-WebeeBlocksLocalServerRequest -Server $server) { }
  if ($webotsProcess.ExitCode -ne 0) {
    throw "Webots s'est termine avec le code $($webotsProcess.ExitCode)."
  }
}
finally {
  [System.IO.File]::WriteAllText($robotWindow.Html, $originalHtml, [System.Text.UTF8Encoding]::new($false))
  Stop-WebeeBlocksLocalServer -Server $server
}

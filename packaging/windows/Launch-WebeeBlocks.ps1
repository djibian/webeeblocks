[CmdletBinding()]
param(
  [string]$WebotsHome = $env:WEBOTS_HOME,
  [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$world = Join-Path $PSScriptRoot 'worlds\crazyflie_runtime_v2.wbt'
if (-not (Test-Path -LiteralPath $world -PathType Leaf)) {
  throw "Monde WebeeBlocks introuvable : $world"
}
$worldRoot = Split-Path $world -Parent
$worldBaseName = [System.IO.Path]::GetFileNameWithoutExtension($world)
$worldPerspective = Join-Path $worldRoot ".$worldBaseName.wbproj"
if (-not (Test-Path -LiteralPath $worldPerspective -PathType Leaf)) {
  throw "Perspective WebeeBlocks introuvable : $worldPerspective"
}
$worldPerspectiveText = Get-Content -LiteralPath $worldPerspective -Raw
if ([regex]::Matches($worldPerspectiveText, '(?m)^robotWindow:\s+Crazyflie WebeeBlocks\s*$').Count -ne 1) {
  throw 'La perspective de classe doit ouvrir exactement la Robot Window Crazyflie WebeeBlocks.'
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

function New-WebeeBlocksRobotWindowSession {
  param(
    $RobotWindow,
    [string]$WorldText,
    [string]$PerspectivePath
  )

  $token = [Guid]::NewGuid().ToString('N').Substring(0, 12)
  $name = "$($RobotWindow.Name)_session_${PID}_$token"
  $robotWindowsRoot = Split-Path $RobotWindow.Root -Parent
  $root = Join-Path $robotWindowsRoot $name
  $html = Join-Path $root "$name.html"
  $worldRoot = Split-Path $world -Parent
  $sessionWorld = Join-Path $worldRoot "$name.wbt"
  $sessionPerspective = Join-Path $worldRoot ".$name.wbproj"
  if ((Test-Path -LiteralPath $root) -or
      (Test-Path -LiteralPath $sessionWorld) -or
      (Test-Path -LiteralPath $sessionPerspective)) {
    throw "Identite de session WebeeBlocks deja presente : $name"
  }

  try {
    New-Item -ItemType Directory -Path $root | Out-Null
    Copy-Item -Path (Join-Path $RobotWindow.Root '*') -Destination $root -Recurse -Force
    $copiedHtml = Join-Path $root "$($RobotWindow.Name).html"
    if (-not (Test-Path -LiteralPath $copiedHtml -PathType Leaf)) {
      throw "HTML Robot Window de session introuvable : $copiedHtml"
    }
    Move-Item -LiteralPath $copiedHtml -Destination $html

    $sourceMarker = 'window "' + $RobotWindow.Name + '"'
    $markerCount = [regex]::Matches($WorldText, [regex]::Escape($sourceMarker)).Count
    if ($markerCount -ne 1) {
      throw 'Le monde de classe ne contient pas exactement une identite Robot Window remplacable.'
    }
    $sessionWorldText = $WorldText.Replace($sourceMarker, ('window "' + $name + '"'))
    [System.IO.File]::WriteAllText($sessionWorld, $sessionWorldText, [System.Text.UTF8Encoding]::new($false))
    Copy-Item -LiteralPath $PerspectivePath -Destination $sessionPerspective
    return [PSCustomObject]@{
      Name = $name
      Root = $root
      Html = $html
      World = $sessionWorld
      Perspective = $sessionPerspective
    }
  }
  catch {
    if (Test-Path -LiteralPath $sessionPerspective) {
      Remove-Item -LiteralPath $sessionPerspective -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $sessionWorld) {
      Remove-Item -LiteralPath $sessionWorld -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $root) {
      Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
    }
    throw
  }
}

function Remove-WebeeBlocksRobotWindowSession {
  param($Session)
  if ($null -eq $Session) { return }
  if (Test-Path -LiteralPath $Session.Perspective) {
    Remove-Item -LiteralPath $Session.Perspective -Force -ErrorAction SilentlyContinue
  }
  if (Test-Path -LiteralPath $Session.World) {
    Remove-Item -LiteralPath $Session.World -Force -ErrorAction SilentlyContinue
  }
  if (Test-Path -LiteralPath $Session.Root) {
    Remove-Item -LiteralPath $Session.Root -Recurse -Force -ErrorAction SilentlyContinue
  }
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
  param([string]$Root)

  $rootPath = [System.IO.Path]::GetFullPath($Root)
  $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
  try {
    $listener.Start()
    $port = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
    if ($port -le 0) { throw 'Le serveur HTTP local WebeeBlocks n a obtenu aucun port.' }
    return [PSCustomObject]@{ Listener = $listener; Port = $port; Root = $rootPath }
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

function Set-WebeeBlocksSessionHtml {
  param(
    $Session,
    [int]$Port
  )
  $html = [System.IO.File]::ReadAllText($Session.Html, [System.Text.Encoding]::UTF8)
  $rewritten = Convert-RobotWindowChildUrls -Html $html -PluginRoot $Session.Root -Port $Port
  $rewritten = $rewritten.Replace('<head>', '<head><link rel="icon" href="data:,">')
  [System.IO.File]::WriteAllText($Session.Html, $rewritten, [System.Text.UTF8Encoding]::new($false))
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

  # The aborted client must be contained locally; the same listener/session must
  # still serve exact packaged bytes to the next valid request.
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

if ($ValidateOnly) {
  $serverA = $null
  $serverB = $null
  $sessionA = $null
  $sessionB = $null
  try {
    # Keep the first launch alive while constructing a complete second launch.
    # Distinct top-level Robot Window identities make stale browser documents
    # unable to retain the first launch's ephemeral child-asset origin.
    $serverA = Start-WebeeBlocksLocalServer -Root $PSScriptRoot
    $sessionA = New-WebeeBlocksRobotWindowSession -RobotWindow $robotWindow -WorldText $worldText -PerspectivePath $worldPerspective
    $rewrittenA = Set-WebeeBlocksSessionHtml -Session $sessionA -Port $serverA.Port

    $serverB = Start-WebeeBlocksLocalServer -Root $PSScriptRoot
    $sessionB = New-WebeeBlocksRobotWindowSession -RobotWindow $robotWindow -WorldText $worldText -PerspectivePath $worldPerspective
    $rewrittenB = Set-WebeeBlocksSessionHtml -Session $sessionB -Port $serverB.Port

    if ($sessionA.Name -eq $sessionB.Name) {
      throw 'Deux relances WebeeBlocks ont reutilise la meme identite Robot Window.'
    }
    if ($serverA.Port -eq $serverB.Port) {
      throw 'Deux serveurs WebeeBlocks simultanes ont reutilise le meme port ephemere.'
    }
    $sourcePerspectiveHash = (Get-FileHash -LiteralPath $worldPerspective -Algorithm SHA256).Hash
    foreach ($probe in @(
      [PSCustomObject]@{ Server = $serverA; Session = $sessionA; Html = $rewrittenA },
      [PSCustomObject]@{ Server = $serverB; Session = $sessionB; Html = $rewrittenB }
    )) {
      if (-not ([System.IO.File]::ReadAllText($probe.Session.World)).Contains(('window "' + $probe.Session.Name + '"'))) {
        throw 'Le monde de session ne selectionne pas son identite Robot Window unique.'
      }
      if ((Split-Path $probe.Session.Perspective -Leaf) -ne ".$($probe.Session.Name).wbproj") {
        throw 'La perspective de session ne correspond pas au nom exact du monde de session.'
      }
      if (-not (Test-Path -LiteralPath $probe.Session.Perspective -PathType Leaf)) {
        throw 'La perspective de session WebeeBlocks est absente.'
      }
      $sessionPerspectiveHash = (Get-FileHash -LiteralPath $probe.Session.Perspective -Algorithm SHA256).Hash
      if ($sessionPerspectiveHash -ne $sourcePerspectiveHash) {
        throw 'La perspective de session ne preserve pas exactement la perspective de classe.'
      }
      $faviconMarker = '<link rel="icon" href="data:,">'
      if ([regex]::Matches($probe.Html, [regex]::Escape($faviconMarker)).Count -ne 1) {
        throw 'La Robot Window de session doit neutraliser exactement une requete favicon implicite.'
      }
      $dependencyHtml = $probe.Html.Replace($faviconMarker, '')
      $references = [regex]::Matches($dependencyHtml, '(?:src|href)="([^"]+)"')
      if ($references.Count -lt 10) {
        throw 'La Robot Window de session contient trop peu de dependances pour valider le pont HTTP.'
      }
      foreach ($reference in $references) {
        if (-not $reference.Groups[1].Value.StartsWith("http://127.0.0.1:$($probe.Server.Port)/", [System.StringComparison]::Ordinal)) {
          throw "Une dependance de demarrage contourne le serveur HTTP propre a la session : $($reference.Groups[1].Value)"
        }
      }
      $sessionRelative = "plugins\robot_windows\$($probe.Session.Name)"
      Assert-LocalServerRecoversFromAbortedRequest -Server $probe.Server -RelativePath (Join-Path $sessionRelative 'main.css') -ExpectedContentType 'text/css'
      Assert-LocalServerFile -Server $probe.Server -RelativePath (Join-Path $sessionRelative "$($probe.Session.Name).html") -ExpectedContentType 'text/html'
      Assert-LocalServerFile -Server $probe.Server -RelativePath (Join-Path $sessionRelative 'main.css') -ExpectedContentType 'text/css'
      Assert-LocalServerFile -Server $probe.Server -RelativePath (Join-Path $sessionRelative 'vendor\msg\fr.js') -ExpectedContentType 'application/javascript'
      Assert-LocalServerFile -Server $probe.Server -RelativePath 'plugins\robot_windows\blockly\webeeblocks\semantic_ast.js' -ExpectedContentType 'application/javascript'
    }
  }
  finally {
    Stop-WebeeBlocksLocalServer -Server $serverB
    Stop-WebeeBlocksLocalServer -Server $serverA
    Remove-WebeeBlocksRobotWindowSession -Session $sessionB
    Remove-WebeeBlocksRobotWindowSession -Session $sessionA
  }
  foreach ($removedSession in @($sessionA, $sessionB)) {
    if ($null -ne $removedSession -and
        ((Test-Path -LiteralPath $removedSession.Perspective) -or
         (Test-Path -LiteralPath $removedSession.World) -or
         (Test-Path -LiteralPath $removedSession.Root))) {
      throw 'Le nettoyage de session WebeeBlocks a laisse un artefact temporaire.'
    }
  }
  Write-Host "WEBEEBLOCKS_WINDOWS_LAUNCHER_OK webots=$webots world=$world version=R2025a mode=realtime local_http=loopback-ephemeral-session-isolated-connection-close"
  exit 0
}

$server = $null
$session = $null
$webotsProcess = $null
try {
  $server = Start-WebeeBlocksLocalServer -Root $PSScriptRoot
  $session = New-WebeeBlocksRobotWindowSession -RobotWindow $robotWindow -WorldText $worldText -PerspectivePath $worldPerspective
  Set-WebeeBlocksSessionHtml -Session $session -Port $server.Port | Out-Null

  if ($session.World.Contains('"')) { throw 'Le chemin du monde de session contient un guillemet non pris en charge.' }
  $worldArgument = '"' + $session.World + '"'
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
  Stop-WebeeBlocksLocalServer -Server $server
  Remove-WebeeBlocksRobotWindowSession -Session $session
}
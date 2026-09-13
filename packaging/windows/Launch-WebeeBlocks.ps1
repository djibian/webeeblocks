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

function Start-WebeeBlocksLocalServer {
  param([string]$Root)

  $job = Start-Job -ArgumentList $Root -ScriptBlock {
    param([string]$ServerRoot)
    $ErrorActionPreference = 'Stop'
    Set-StrictMode -Version Latest

    $rootPath = [System.IO.Path]::GetFullPath($ServerRoot)
    $rootPrefix = $rootPath + [System.IO.Path]::DirectorySeparatorChar
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    $port = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
    Write-Output "WEBEEBLOCKS_LOCAL_SERVER_READY=$port"

    function Write-Reply {
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

    function Get-ContentType {
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

    try {
      while ($true) {
        $client = $listener.AcceptTcpClient()
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
            Write-Reply $stream 405 'Method Not Allowed' 'text/plain; charset=utf-8' ([System.Text.Encoding]::UTF8.GetBytes('Method Not Allowed'))
            continue
          }

          $requestUri = [System.Uri]::new('http://127.0.0.1' + $parts[1])
          $relative = [System.Uri]::UnescapeDataString($requestUri.AbsolutePath.TrimStart('/')).Replace('/', [System.IO.Path]::DirectorySeparatorChar)
          if ([string]::IsNullOrWhiteSpace($relative)) {
            Write-Reply $stream 404 'Not Found' 'text/plain; charset=utf-8' ([System.Text.Encoding]::UTF8.GetBytes('Not Found'))
            continue
          }
          $target = [System.IO.Path]::GetFullPath((Join-Path $rootPath $relative))
          if (-not $target.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase) -or
              -not (Test-Path -LiteralPath $target -PathType Leaf)) {
            Write-Reply $stream 404 'Not Found' 'text/plain; charset=utf-8' ([System.Text.Encoding]::UTF8.GetBytes('Not Found'))
            continue
          }
          $body = [System.IO.File]::ReadAllBytes($target)
          Write-Reply $stream 200 'OK' (Get-ContentType $target) $body
        }
        catch {
          try {
            if ($null -ne $stream) {
              Write-Reply $stream 500 'Internal Server Error' 'text/plain; charset=utf-8' ([System.Text.Encoding]::UTF8.GetBytes('Internal Server Error'))
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

  $deadline = [DateTime]::UtcNow.AddSeconds(8)
  do {
    foreach ($line in @(Receive-Job -Job $job -Keep)) {
      if ([string]$line -match '^WEBEEBLOCKS_LOCAL_SERVER_READY=(\d+)$') {
        return [PSCustomObject]@{ Job = $job; Port = [int]$Matches[1] }
      }
    }
    if ($job.State -eq 'Failed') {
      $reason = if ($null -ne $job.ChildJobs[0].JobStateInfo.Reason) { $job.ChildJobs[0].JobStateInfo.Reason.Message } else { 'unknown failure' }
      throw "Le serveur HTTP local WebeeBlocks a echoue : $reason"
    }
    Start-Sleep -Milliseconds 100
  } while ([DateTime]::UtcNow -lt $deadline)

  Stop-Job -Job $job -ErrorAction SilentlyContinue
  Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
  throw 'Le serveur HTTP local WebeeBlocks ne s est pas initialise.'
}

function Stop-WebeeBlocksLocalServer {
  param($Server)
  if ($null -eq $Server) { return }
  Stop-Job -Job $Server.Job -ErrorAction SilentlyContinue
  Remove-Job -Job $Server.Job -Force -ErrorAction SilentlyContinue
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
  $server = $null
  try {
    $server = Start-WebeeBlocksLocalServer -Root $PSScriptRoot
    $htmlRelative = [System.IO.Path]::GetRelativePath($PSScriptRoot, $robotWindow.Html)
    Assert-LocalServerFile -Port $server.Port -RelativePath $htmlRelative -ExpectedContentType 'text/html'
    Assert-LocalServerFile -Port $server.Port -RelativePath (Join-Path "plugins\robot_windows\$($robotWindow.Name)" 'main.css') -ExpectedContentType 'text/css'
    Assert-LocalServerFile -Port $server.Port -RelativePath (Join-Path "plugins\robot_windows\$($robotWindow.Name)" 'vendor\msg\fr.js') -ExpectedContentType 'application/javascript'
    Assert-LocalServerFile -Port $server.Port -RelativePath 'plugins\robot_windows\blockly\webeeblocks\semantic_ast.js' -ExpectedContentType 'application/javascript'
  }
  finally {
    Stop-WebeeBlocksLocalServer -Server $server
  }
  Write-Host "WEBEEBLOCKS_WINDOWS_LAUNCHER_OK webots=$webots world=$world version=R2025a mode=realtime local_http=loopback-connection-close"
  exit 0
}

if ($world.Contains('"')) { throw 'Le chemin du monde contient un guillemet non pris en charge.' }
$worldArgument = '"' + $world + '"'
$server = $null
$originalHtml = $null
$localHtml = Join-Path $robotWindow.Root '.webeeblocks-local.html'
$webotsProcess = $null
try {
  $server = Start-WebeeBlocksLocalServer -Root $PSScriptRoot
  $originalHtml = [System.IO.File]::ReadAllText($robotWindow.Html, [System.Text.Encoding]::UTF8)
  [System.IO.File]::WriteAllText($localHtml, $originalHtml, [System.Text.UTF8Encoding]::new($false))

  $localRelative = [System.IO.Path]::GetRelativePath($PSScriptRoot, $localHtml).Replace('\', '/')
  $redirectHtml = @"
<!doctype html>
<html><head><meta charset="utf-8"><meta http-equiv="Cache-Control" content="no-store"></head><body>
<script>
(function() {
  const original = new URL(window.location.href);
  const target = new URL('http://127.0.0.1:$($server.Port)/$localRelative');
  target.search = original.search;
  target.searchParams.set('webeeblocksWebSocketServer', original.origin.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:') + '/');
  window.location.replace(target.toString());
})();
</script>
</body></html>
"@
  [System.IO.File]::WriteAllText($robotWindow.Html, $redirectHtml, [System.Text.UTF8Encoding]::new($false))

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
  Remove-Item -LiteralPath $localHtml -Force -ErrorAction SilentlyContinue
  Stop-WebeeBlocksLocalServer -Server $server
}

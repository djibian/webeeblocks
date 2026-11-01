# EXPERIMENT ONLY — R3 Windows interactive observation, exact #778, no product edits.
# Run in Windows PowerShell 5.1 or PowerShell 7. Never run with real pupil projects.
# Chrome DevTools is exposed only on a random loopback port in a fresh profile,
# and the profile is kept PRIVATE locally; only whitelisted digests leave it.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$ArtifactZip,
  [switch]$AutoCollisionReconstruction
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$PRODUCT='f243b2b597a2a6bd6af38e895787d9dd4bdfef5e'
$OUTER_SHA='07c5a175f80d1481794f4a064a3229984a4f008c5b457899de5c670f37a36f2b'
$PE_SHA='2c8f8e5da9370f4242e860e26952f2838c5cec7ffc5bd327161f1be49434c74a'
$REPORT=[ordered]@{protocol='R3_WINDOWS_INTERACTIVE_V1';productHead=$PRODUCT;sourcePR=778;
  sourceArtifact=13075341081;status='UNPROVEN';checks=[ordered]@{};observations=@()}
$stamp=Get-Date -Format yyyyMMdd-HHmmss
$root=Join-Path $env:LOCALAPPDATA ('WebeeBlocks-R3-qualification-'+$stamp)
New-Item -ItemType Directory -Path $root -Force | Out-Null
$private=Join-Path $root 'PRIVATE'
New-Item -ItemType Directory -Path $private -Force | Out-Null
$RESULT=Join-Path $root 'R3-rapport-expurge.json'
function Check([string]$name,[string]$state,[string]$why) {
  $REPORT.checks[$name]=[ordered]@{status=$state;detail=$why}
  Write-Host "$name : $state"
}
function Save-Report {
  $REPORT.observations=@($REPORT.observations)
  $REPORT | ConvertTo-Json -Depth 14 | Set-Content -LiteralPath $RESULT -Encoding UTF8
}
function Assert-Sha([string]$path,[string]$sha) {
  if(-not (Test-Path -LiteralPath $path -PathType Leaf)){throw "Fichier absent : $path"}
  $actual=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
  if($actual -ne $sha){throw "SHA256 différent pour $(Split-Path $path -Leaf) : $actual"}
}
function Get-Port([string]$dir) {
  $file=Join-Path $dir 'DevToolsActivePort'
  $limit=(Get-Date).AddSeconds(15)
  do {
    if(Test-Path -LiteralPath $file){
      $first=@(Get-Content -LiteralPath $file -TotalCount 1)[0]
      if($first -match '^\d{2,5}$'){return [int]$first}
    }
    Start-Sleep -Milliseconds 200
  }while((Get-Date) -lt $limit)
  throw "Chrome n'a pas ouvert son port de diagnostic prive"
}
function Get-Pages([int]$port) {
  @(Invoke-RestMethod -Uri "http://127.0.0.1:$port/json/list" -TimeoutSec 4 |
    Where-Object { $_.type -eq 'page' -and $_.url -match '^http://(127\.0\.0\.1|localhost):\d+/robot_windows/.+_session_\d+_[0-9a-f]{12}/' })
}
function Send-Cdp([string]$wsurl,[string]$method,[object]$parameters) {
  $ws=[System.Net.WebSockets.ClientWebSocket]::new()
  $cts=[System.Threading.CancellationTokenSource]::new(10000)
  try {
    $ws.ConnectAsync([Uri]$wsurl,$cts.Token).GetAwaiter().GetResult()
    $json=(@{id=17;method=$method;params=$parameters} | ConvertTo-Json -Depth 15 -Compress)
    $bytes=[System.Text.Encoding]::UTF8.GetBytes($json)
    $ws.SendAsync([ArraySegment[byte]]::new($bytes),[System.Net.WebSockets.WebSocketMessageType]::Text,
                  $true,$cts.Token).GetAwaiter().GetResult()
    do {
      $stream=[System.IO.MemoryStream]::new()
      try {
        do {
          $buf=New-Object byte[] 65536
          $segment=[ArraySegment[byte]]::new($buf)
          $recv=$ws.ReceiveAsync($segment,$cts.Token).GetAwaiter().GetResult()
          if($recv.MessageType -eq [System.Net.WebSockets.WebSocketMessageType]::Close){throw 'CDP closed'}
          $stream.Write($buf,0,$recv.Count)
          if($stream.Length -gt 1048576){throw 'CDP response too large'}
        }while(-not $recv.EndOfMessage)
        $answer=[System.Text.Encoding]::UTF8.GetString($stream.ToArray()) | ConvertFrom-Json
      }finally{$stream.Dispose()}
    }while($answer.id -ne 17)
    if($answer.error){throw "CDP protocol error"}
    return $answer.result
  }finally{
    $ws.Dispose();$cts.Dispose()
  }
}
function Eval([object]$page,[string]$code) {
  $reply=Send-Cdp $page.webSocketDebuggerUrl 'Runtime.evaluate' @{
    expression=$code;awaitPromise=$true;returnByValue=$true;silent=$true}
  if($reply.exceptionDetails){throw 'Erreur JS du protocole de test; examiner le navigateur local'}
  return $reply.result.value
}
$SNAP=@'
(async()=>{
  const h=async(x)=>{
    const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(x));
    return Array.from(new Uint8Array(bytes), b=>b.toString(16).padStart(2,'0')).join('');
  };
  const w=typeof workspace==='undefined'?null:workspace;
  let workspaceSha=null,astSha=null,count=0;
  if(w){
    count=w.getAllBlocks(false).length;
    workspaceSha=await h(JSON.stringify(Blockly.serialization.workspaces.save(w)));
    if(count>0) astSha=await h(JSON.stringify(WebeeBlocksSemanticAst.compileWorkspace(w)));
  }
  window.__r3_qual_document_id ||= crypto.randomUUID();
  return {
    documentId:window.__r3_qual_document_id,
    path:location.pathname,host:location.hostname,
    state:document.getElementById('runtimeState')?.textContent||null,
    detail:document.getElementById('runtimeDetail')?.textContent?.slice(0,100)||null,
    runDisabled:!!document.getElementById('submit')?.disabled,
    resetLabel:document.getElementById('resetSimulation')?.textContent||null,
    wsOpen:typeof robotWindow!=='undefined' && robotWindow?.socket?.readyState===1,
    nativeClaimAck:typeof runtimeBackend!=='undefined' && runtimeBackend?.authorized===true,
    pending:typeof runtimeRecoveryPending!=='undefined' && runtimeRecoveryPending,
    nameCleared:window.name==='',
    workspaceSha,astSha,blockCount:count
  }
})()
'@
function Wait-Page([int]$port,[string]$exclude,[int]$seconds) {
  $stop=(Get-Date).AddSeconds($seconds)
  do {
    $pages=Get-Pages $port
    foreach($p in $pages){
      if($p.id -ne $exclude -and $p.url -match '_session_'){return $p}
    }
    Start-Sleep -Milliseconds 800
  }while((Get-Date) -lt $stop)
  return $null
}
function Wait-State([object]$p,[string]$state,[int]$seconds) {
  $stop=(Get-Date).AddSeconds($seconds)
  do {
    try{
      $s=Eval $p $SNAP
      if($s.state -eq $state){return $s}
    }catch{}
    Start-Sleep -Milliseconds 600
  }while((Get-Date) -lt $stop)
  return $null
}
function Native-Light([object]$p,[string]$color) {
  # Calls the unchanged WebeeBlocks WWI backend; resolves only from C response.
  $js="(async()=>{ await runtimeBackend.setLight('$color');return {accepted:true}; })()"
  $v=Eval $p $js
  return $v.accepted -eq $true
}
function Denied-Without-Key([object]$p,[string]$color) {
  # Deliberate unauthenticated LIGHT sent over a genuine RobotWindow socket.
  # JS wait resolves only after a correlated ERR AUTH_DENIED from native C.
  $js=@"
(async()=>{
 const id=runtimeBackend.nextId++;
 const answer=new Promise((resolve)=>{
   const timer=setTimeout(()=>{window.removeEventListener('webeeblocks-wwi',handler);resolve('TIMEOUT')},6000);
   function handler(e){
     if(e.detail==='WEBEEBLOCKS_RUNTIME_V2 RESPONSE '+id+' ERR AUTH_DENIED'){
       clearTimeout(timer);window.removeEventListener('webeeblocks-wwi',handler);resolve('AUTH_DENIED');
     }
   }
   window.addEventListener('webeeblocks-wwi',handler);
 });
 robotWindow.send('WEBEEBLOCKS_RUNTIME_V2 REQUEST '+id+' LIGHT $color');
 return await answer;
})()
"@
  return (Eval $p $js) -eq 'AUTH_DENIED'
}
function Launch-Pupil([string]$path){
  # Normal CMD launcher, never invoke webots.exe with a substituted controller.
  return Start-Process -FilePath $env:ComSpec -ArgumentList @('/d','/c',('"' + $path + '"')) -WorkingDirectory (Split-Path $path) -PassThru
}
$chromeProcess=$null;$otherChrome=$null;$launchProcess=$null
try{
  Assert-Sha $ArtifactZip $OUTER_SHA
  Check 'artifact_provenance' 'PASS' 'Archive-of-archive SHA256 exact from #783.'
  $a=Join-Path $root 'artifact'
  Expand-Archive -LiteralPath $ArtifactZip -DestinationPath $a -Force
  $inner=Get-ChildItem -LiteralPath $a -Filter 'WebeeBlocks-Windows-R2025a.zip' -File -Recurse | Select-Object -First 1
  if(-not $inner){throw 'Archive WebeeBlocks introuvable dans artefact GitHub'}
  $testRoot=Join-Path $root 'package'
  Expand-Archive -LiteralPath $inner.FullName -DestinationPath $testRoot
  # ZipFile.CreateFromDirectory(..., includeBaseDirectory=false): content is at ZIP root.
  $pkg=$testRoot
  $manifest=Join-Path $pkg 'MANIFEST.sha256'
  if(-not (Test-Path $manifest)){throw 'Manifeste absent'}
  $files=0
  foreach($line in Get-Content -LiteralPath $manifest){
    if($line -notmatch '^([a-fA-F0-9]{64})  (.+)$'){throw 'Ligne du manifeste invalide'}
    $expected=$Matches[1].ToLowerInvariant()
    $relative=$Matches[2].Replace('/','\')
    $f=[IO.Path]::GetFullPath((Join-Path $pkg $relative))
    if(-not $f.StartsWith($pkg+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){
      throw 'Chemin hors paquet interdit'
    }
    Assert-Sha $f $expected
    $files++
  }
  $pe=Join-Path $pkg 'controllers\crazyflie_runtime_v2\crazyflie_runtime_v2.exe'
  Assert-Sha $pe $PE_SHA
  Check 'manifest_and_windows_pe' 'PASS' "$files fichiers verifies; SHA PE exact."
  $webotsHome= if($env:WEBOTS_HOME){$env:WEBOTS_HOME}else{'C:\Program Files\Webots'}
  $webots=Join-Path $webotsHome 'msys64\mingw64\bin\webots.exe'
  if(-not (Test-Path $webots)){throw 'Webots R2025a non installe'}
  $ver=(& $webots --version 2>&1 | Out-String)
  if($ver -notmatch 'R2025a'){throw 'Version Webots differente de R2025a'}
  Check 'webots_version' 'PASS' 'Version R2025a observee'
  $chrome=@('C:\Program Files\Google\Chrome\Application\chrome.exe',
             'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
             (Join-Path $env:LOCALAPPDATA 'Google\Chrome\Application\chrome.exe')) |
          Where-Object {Test-Path -LiteralPath $_} | Select-Object -First 1
  if(-not $chrome){throw 'Google Chrome introuvable'}
  $profile=Join-Path $private 'chrome-r3'
  New-Item -ItemType Directory -Path $profile -Force | Out-Null
  $env:WEBEEBLOCKS_CHROME_EXE=$chrome
  $env:WEBEEBLOCKS_CHROME_PROFILE=$profile
  $env:WEBEEBLOCKS_RECOVERY_STATE_DIR=Join-Path $private 'native-r3-state'
  New-Item -ItemType Directory -Path $env:WEBEEBLOCKS_RECOVERY_STATE_DIR -Force | Out-Null
  $chromeProcess=Start-Process -FilePath $chrome -ArgumentList @(
       ('--user-data-dir="'+$profile+'"'),'--remote-debugging-port=0',
       '--no-first-run','--no-default-browser-check','about:blank') -PassThru
  $port=Get-Port $profile
  $launcher=Join-Path $pkg 'Launch-WebeeBlocks.cmd'
  $launchProcess=Launch-Pupil $launcher
  $page=Wait-Page $port '' 90
  if(-not $page){throw 'Robot Window reelle non vue par Chrome CDP'}
  $aReady=Wait-State $page 'PRÊT' 45
  if(-not $aReady -or -not $aReady.wsOpen -or -not $aReady.nativeClaimAck -or $aReady.runDisabled){
    throw 'READY/WWI/autorite de la 1re fenetre non demontres'
  }
  Check 'session1_native_admission' 'PASS' 'Chrome target+WS OPEN+AUTH_OK native+PRÊT.'
  if(Native-Light $page 'red'){Check 'session1_light' 'PASS' 'setLight() confirme par ACK C'}
  else{throw 'LED 1 non confirmee par C'}
  $firstPath=$aReady.path
  Write-Host 'Fermez normalement Webots, puis appuyez Entree (ne fermez pas Chrome).'
  [void](Read-Host)
  $stop=(Get-Date).AddSeconds(40)
  while(-not $launchProcess.HasExited -and (Get-Date) -lt $stop){
    $launchProcess.Refresh();Start-Sleep -Milliseconds 500
  }
  if(-not $launchProcess.HasExited){throw 'Premier lanceur non termine normalement'}
  Check 'session1_close' 'PASS' 'Lanceur 1 termine; absence de suppression du repertoire R3'
  $launchProcess=Launch-Pupil $launcher
  $next=Wait-Page $port $page.id 90
  if(-not $next){throw 'Deuxieme onglet/session Chrome introuvable'}
  $bReady=Wait-State $next 'PRÊT' 45
  if(-not $bReady -or -not $bReady.wsOpen -or -not $bReady.nativeClaimAck){throw 'Admission 2 non prouvee'}
  if($bReady.path -eq $firstPath){throw 'Identite de session relancee non renouvelee'}
  Check 'session2_normal_new_world' 'PASS' 'Nouvelle session _session_ admise; monde different du precedent'
  Check 'owned_reuse_same_world' 'UNPROVEN' 'Le lanceur cree un chemin .wbt different a chaque execution.'
  if(Native-Light $next 'blue'){Check 'session2_light' 'PASS' 'ACK C reel dans la seconde session'}
  else{throw 'LED 2 non confirmee'}
  $before=$null
  if($AutoCollisionReconstruction){
    # Test-only Blockly fixture from the existing native collision research.
    # Does not change C or spoof RESET/SCENE/ACK.
    $prepare=@'
(()=>{
const xml='<xml xmlns="https://developers.google.com/blockly/xml"><block type="webeeblocks_v2_takeoff" id="r3_takeoff" x="40" y="40"><field name="HEIGHT">0.5</field><next><block type="webeeblocks_v2_move" id="r3_move"><field name="DIRECTION">forward</field><field name="DISTANCE">2</field><next><block type="webeeblocks_v2_land" id="r3_land"/></next></block></next></block></xml>';
workspace.clear();Blockly.Xml.domToWorkspace(Blockly.utils.xml.textToDom(xml),workspace);
return {count:workspace.getAllBlocks(false).length};
})()
'@
    $loaded=Eval $next $prepare
    if($loaded.count -lt 3){throw 'Fixture Blockly incomplet'}
    $before=Eval $next $SNAP
    for($attempt=1;$attempt -le 2;$attempt++){
      [void](Eval $next '(()=>{document.getElementById("submit").click();return true})()')
      if(-not (Wait-State $next 'ARRÊTÉ' 65)){throw "Collision native $attempt non observee"}
      if($attempt -eq 1){
        [void](Eval $next '(()=>{document.getElementById("resetSimulation").click();return true})()')
        if(-not (Wait-State $next 'PRÊT' 20)){throw 'RESET strict intermediaire non etabli'}
      }
    }
    # Same bounded test trigger as native Linux fixture: only UI selection,
    # never a fake controller response or altered physics timeout.
    $allowed=Eval $next '(()=>{runtimeNeedsRebuild=true;updateRuntimeActions();return document.getElementById("resetSimulation").textContent==="Reconstruire"&&!document.getElementById("resetSimulation").disabled})()'
    if(-not $allowed){throw 'Bouton reconstruction indisponible'}
    [void](Eval $next '(()=>{document.getElementById("resetSimulation").click();return true})()')
    Check 'reconstruction_trigger' 'PASS' 'Reelle world_reload apres deux collisions; UI basculee par sonde, pas de RESET_TIMEOUT pretendu.'
  }else{
    Write-Host 'Preparez un programme Blockly fictif non vide; faites apparaitre Reconstruire, puis tapez Entree.'
    [void](Read-Host)
    $before=Eval $next $SNAP
    if($before.blockCount -lt 2){throw 'Programme non trivial requis'}
    if($before.resetLabel -ne 'Reconstruire'){throw 'Reconstruction non disponible'}
    Write-Host 'Cliquez Reconstruire dans Chrome, puis tapez Entree.'
    [void](Read-Host)
  }
  if(-not $before -or $before.blockCount -lt 2){throw 'Blockly initial non observe'}
  $restored=$null
  $limit=(Get-Date).AddSeconds(90)
  while((Get-Date) -lt $limit){
    try{
      $p=Get-Pages $port | Where-Object { $_.id -eq $next.id } | Select-Object -First 1
      if($p){
        $current=Eval $p $SNAP
        if($current.documentId -ne $before.documentId -and $current.state -eq 'PRÊT' -and
           $current.wsOpen -and $current.nativeClaimAck -and -not $current.runDisabled){
          $restored=$current
          break
        }
      }
    }catch{}
    Start-Sleep -Milliseconds 600
  }
  if(-not $restored){throw 'Aucun nouveau document du meme contexte revenu a PRET'}
  if($restored.workspaceSha -ne $before.workspaceSha -or $restored.astSha -ne $before.astSha){
    Check 'blockly_ast_bytes' 'FAIL' 'Empreintes Blockly/AST modifiees apres reload'
    throw 'Bloc/AST different'
  }
  Check 'world_reload_same_chrome_target' 'PASS' 'Target ID stable; document ID renouvele et WebSocket reconnecte'
  Check 'blockly_ast_bytes' 'PASS' 'Deux SHA256 de la serialisation Blockly/AST identiques, meme tab'
  Check 'window_name_consumption' $(if($restored.nameCleared){'PASS'}else{'FAIL'}) 'window.name vide au retour PRET; secret non extrait'
  Check 'native_recovery_sequence' 'UNPROVEN' 'RESETx2/SCENEx2/CLEAR deduits du code produit mais sans capture independante des trames.'
  if(Native-Light $next 'red'){Check 'postreload_owner_light' 'PASS' 'La capacite courante autorise LIGHT apres reload'}
  else{throw 'Ancien navigateur revenu PRET trompeur ou commande refusee'}
  # Same-profile second document, distinct Chrome page.
  # Second document must target the CURRENT second-session URL, never stale session 1.
  $freshURL=$next.url
  Start-Process -FilePath $chrome -ArgumentList @(
      ('--user-data-dir="'+$profile+'"'),'--new-window',('"'+$freshURL+'"')) | Out-Null
  $same=Wait-Page $port $next.id 30
  if($same -and $same.url -eq $freshURL){
    $s=Eval $same $SNAP
    $denied=Denied-Without-Key $same 'blue'
    Check 'same_profile_second_window' $(if($denied -and -not $s.nativeClaimAck -and $s.runDisabled){'PASS'}else{'FAIL'}) 'Second document WS: C AUTH_DENIED et Run verrouille'
  }else{Check 'same_profile_second_window' 'UNPROVEN' 'Seconde Robot Window Chrome non observee'}
  $otherProfile=Join-Path $private 'chrome-independent'
  New-Item -ItemType Directory -Path $otherProfile | Out-Null
  $otherChrome=Start-Process -FilePath $chrome -ArgumentList @(
    ('--user-data-dir="'+$otherProfile+'"'),'--remote-debugging-port=0',
    '--no-first-run','--no-default-browser-check',('"'+$freshURL+'"')) -PassThru
  $otherPort=Get-Port $otherProfile
  $other=Wait-Page $otherPort '' 30
  if($other){
    $osnap=Eval $other $SNAP
    $denied2=Denied-Without-Key $other 'green'
    Check 'independent_profile_second_window' $(if($denied2 -and -not $osnap.nativeClaimAck -and $osnap.runDisabled){'PASS'}else{'FAIL'}) 'Profil distinct WS: C AUTH_DENIED et Run verrouille'
  }else{Check 'independent_profile_second_window' 'UNPROVEN' 'Profil Chrome distinct non connecte'}
  if(Native-Light $next 'red'){Check 'owner_after_competitors' 'PASS' 'Proprietaire courant toujours admis'}
  else{Check 'owner_after_competitors' 'FAIL' 'Perte de pouvoir du proprietaire'}
  Check 'old_bearer_and_stale_ack' 'UNPROVEN' 'Aucun secret persiste ou exporte par le banc; ancien document non preserve.'
  if(@($REPORT.checks.Values | Where-Object {$_.status -eq 'FAIL'}).Count -eq 0){
    $REPORT.status='PARTIAL_PASS_WITH_UNPROVEN_NATIVE_DETAILS'
  }else{$REPORT.status='FAIL'}
}catch{
  $REPORT.status='UNPROVEN_OR_FAIL_CLOSED'
  Check 'qualification_interrupted' 'UNPROVEN' ($_.Exception.Message -replace '[A-Za-z]:\\[^ :\r\n]+','<chemin_prive>')
}finally{
  Save-Report
  Write-Host "Rapport expurge : $RESULT"
  Write-Host "Dossier PRIVATE a conserver localement, NE PAS PARTAGER : $private"
  Write-Host 'Le protocole ne supprime jamais de fichier de garde ni de checkpoint.'
  # Do not kill Webots or Chrome if a recovery might be pending.
  # The operator closes the disposable GUI only after retaining evidence.
}

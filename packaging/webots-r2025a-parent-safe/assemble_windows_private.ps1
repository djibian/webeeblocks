[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$OfficialRoot,
  [Parameter(Mandatory=$true)][string]$MsysBin,
  [Parameter(Mandatory=$true)][string]$MsysPlugins,
  [Parameter(Mandatory=$true)][string]$KernelDirectory,
  [Parameter(Mandatory=$true)][string]$PrivateRoot,
  [Parameter(Mandatory=$true)][string]$ReportDirectory
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$expected=@{
 'webots-bin.exe'='52b8c047047094c30f0cd358456ca5a18c73209457c2129991068f5825c8a06e'
 'Qt6Core.dll'='85bd00fb398346adef666fa9275a6c06f0955927e09d7909cd558700f4d92179'
 'Qt6Gui.dll'='b268755f2cf1c3eb4f25b6b8435481ff91be0f8a16d578f7d88bc413676c1660'
 'Qt6Widgets.dll'='ac1bd54bd2e4eac84e047893e3b0b3b2c9951395bc538552406c6869bb40eb89'
 'libstdc++-6.dll'='494bd9045948198ef4d3bc838c7362d4cfd49c890b439c096b1817aa7c7fa6ff'
 'libgcc_s_seh-1.dll'='d7e343dd266747177c3699bc3201ea36eceef158e98530e089263bc55bb2a6d7'
 'libwinpthread-1.dll'='72bf8802de3a99d28f0bc2db9a11f281a9f9f3fa83dab2bc67e69fac3bd3d9c0'
 'libopenal-1.dll'='cb97d2f5a9797ff64db90d0691e4ff9eb2a088026351c9bad7aa26d229a354ce'
 'webots.exe'='34e3824b3bb1d64cea8ed58ec4089b607fb83c906d36290df8e2d4a8ee2227c0'
}
$requiredVersions=@{
 'mingw-w64-x86_64-qt6-base'='6.11.2-2'
 'mingw-w64-x86_64-qt6-declarative'='6.11.2-1'
 'mingw-w64-x86_64-qt6-websockets'='6.11.2-1'
 'mingw-w64-x86_64-openal'='1.25.2-1'
}
function Assert-Digest([string]$Path,[string]$Hash) {
 if(-not(Test-Path -LiteralPath $Path -PathType Leaf)){throw "M2_FILE_MISSING $Path"}
 $got=(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
 if($got -ne $Hash){throw "M2_SHA_MISMATCH $Path expected=$Hash observed=$got"}
}
$versionList=Get-Content -LiteralPath (Join-Path $KernelDirectory 'msys2-package-versions.txt')
foreach($entry in $requiredVersions.GetEnumerator()) {
 if(@($versionList | Where-Object {$_ -ceq "$($entry.Key) $($entry.Value)"}).Count -ne 1){ throw "M2_ORIGINAL_PACKAGE_VERSION_NOT_PROVEN $($entry.Key)" }
 $pacman=Join-Path (Split-Path $MsysBin -Parent) '..\..\usr\bin\pacman.exe'
 $actual=(& $pacman -Q $entry.Key 2>&1 | Out-String).Trim()
 if($LASTEXITCODE -ne 0 -or $actual -cne "$($entry.Key) $($entry.Value)"){throw "M2_SDK_VERSION_DRIFT $actual expected=$($entry.Value)"}
}
if((Get-Content -LiteralPath (Join-Path $OfficialRoot 'resources\version.txt') -Raw).Trim() -cne 'R2025a'){throw 'M2_OFFICIAL_R2025A_MISMATCH'}
$officialBin=Join-Path $OfficialRoot 'msys64\mingw64\bin'
Assert-Digest (Join-Path $officialBin 'webots.exe') $expected['webots.exe']
if(-not(Test-Path -LiteralPath (Join-Path $officialBin 'webotsw.exe'))){throw 'M2_OFFICIAL_WEBOTSW_MISSING'}
foreach($name in @('webots-bin.exe','Qt6Core.dll','Qt6Gui.dll','Qt6Widgets.dll')) {Assert-Digest (Join-Path $KernelDirectory $name) $expected[$name]}
if(Test-Path -LiteralPath $PrivateRoot){throw 'M2_PRIVATE_ROOT_MUST_NOT_EXIST'}
New-Item -ItemType Directory -Path $PrivateRoot | Out-Null
# Original installer is the source, never a runtime fallback.
Copy-Item -Path (Join-Path $OfficialRoot '*') -Destination $PrivateRoot -Recurse -Force
$bin=Join-Path $PrivateRoot 'msys64\mingw64\bin'
if(-not (Test-Path -LiteralPath $bin -PathType Container)){throw 'M2_COPY_MISSING_BIN'}
$qt=@(Get-ChildItem -LiteralPath $MsysBin -Filter 'Qt6*.dll' -File)
if($qt.Count -lt 10){throw 'M2_INCOMPLETE_QT_SOURCE'}
foreach($dll in $qt) {Copy-Item -LiteralPath $dll.FullName -Destination (Join-Path $bin $dll.Name) -Force}
foreach($name in @('webots-bin.exe','Qt6Core.dll','Qt6Gui.dll','Qt6Widgets.dll')){Copy-Item -LiteralPath (Join-Path $KernelDirectory $name) -Destination (Join-Path $bin $name) -Force}
foreach($name in @('libstdc++-6.dll','libgcc_s_seh-1.dll','libwinpthread-1.dll','libopenal-1.dll')) {
 Assert-Digest (Join-Path $MsysBin $name) $expected[$name]
 Copy-Item -LiteralPath (Join-Path $MsysBin $name) -Destination (Join-Path $bin $name) -Force
}
$dstPlugins=Join-Path $PrivateRoot 'msys64\mingw64\share\qt6\plugins'
if(Test-Path -LiteralPath $dstPlugins){Remove-Item -LiteralPath $dstPlugins -Recurse -Force}
New-Item -ItemType Directory -Path (Split-Path $dstPlugins -Parent) -Force | Out-Null
Copy-Item -LiteralPath $MsysPlugins -Destination $dstPlugins -Recurse -Force
Assert-Digest (Join-Path $dstPlugins 'platforms\qwindows.dll') '9b3b3531ccac562a84698eff4761a6966f531bc01b1d56d5fda8c2da9c6424c1'
$objdump=Join-Path $MsysBin 'objdump.exe'
if(-not(Test-Path -LiteralPath $objdump)){throw 'M2_OBJDUMP_MISSING'}
$pending=[Collections.Generic.Queue[string]]::new()
foreach($name in @('webots-bin.exe','webots.exe')){$pending.Enqueue((Join-Path $bin $name))}
$pending.Enqueue((Join-Path $dstPlugins 'platforms\qwindows.dll'))
$seen=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$filled=@()
$edges=@()
while($pending.Count -gt 0){
 $subject=$pending.Dequeue()
 if(-not $seen.Add($subject)){continue}
 if($seen.Count -gt 450){throw 'M2_IMPORT_GRAPH_UNBOUNDED'}
 $dump=(& $objdump -p $subject 2>&1 | Out-String)
 if($LASTEXITCODE -ne 0){throw "M2_INVALID_PE $subject"}
 $imports=@([regex]::Matches($dump,'(?im)^\s*DLL Name:\s*([^\s]+)') | ForEach-Object {$_.Groups[1].Value} | Sort-Object -Unique)
 foreach($dll in $imports){
  if($dll -match '^(api-ms-win-|ext-ms-win-)'){continue}
  $path=Join-Path $bin $dll
  $system=Join-Path (Join-Path $env:SystemRoot 'System32') $dll
  if(-not(Test-Path -LiteralPath $path -PathType Leaf)){
   $sdk=Join-Path $MsysBin $dll
   if(Test-Path -LiteralPath $sdk -PathType Leaf){
    Copy-Item -LiteralPath $sdk -Destination $path
    if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $sdk -Algorithm SHA256).Hash){throw "M2_TRANSITIVE_COPY_CHANGED $dll"}
    $filled+=@{name=$dll;referer=[IO.Path]::GetFileName($subject);sha256=(Get-FileHash $path -Algorithm SHA256).Hash.ToLowerInvariant()}
   } elseif(-not(Test-Path -LiteralPath $system -PathType Leaf)){throw "M2_UNRESOLVED_DEPENDENCY $subject => $dll"}
  }
  if(Test-Path -LiteralPath $path -PathType Leaf){$pending.Enqueue($path)}
  $edges+=@{referer=[IO.Path]::GetFileName($subject);name=$dll;origin=if(Test-Path $path){'private'}else{'Windows-System32'}}
 }
}
foreach($entry in $expected.GetEnumerator()){Assert-Digest (Join-Path $bin $entry.Key) $entry.Value}
$controller=Join-Path $PrivateRoot 'lib\controller\Controller.dll'
Assert-Digest $controller '756ceba41c53f1a5f008859255254b28d6d3acb674e1ea773544cc6648c41039'
New-Item -ItemType Directory -Path $ReportDirectory -Force | Out-Null
@{status='STATIC_IMPORT_CLOSURE_ONLY';qt_sdk_package_versions=$requiredVersions;source='official R2025a installer sha256 9e326a54c104fc5fc88121e26014a409d1e35f0bbf30e23f3a712e7f842b08e7';patched_pe=$expected['webots-bin.exe'];imports_visited=$seen.Count;edges=$edges;added_dlls=$filled;remarks='Dynamic modules and clean-host UI still require independent native evidence'} | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $ReportDirectory 'import-closure.json')
Write-Host "M2_WINDOWS_STATIC_PRIVATE_IMPORT_CLOSURE=PASS checked=$($seen.Count) added=$($filled.Count)"

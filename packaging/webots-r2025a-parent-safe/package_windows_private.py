#!/usr/bin/env python3
"""Create byte-addressed private Windows classroom package; no Webots compilation."""
import argparse,hashlib,shutil,zipfile,struct
from pathlib import Path

BEGIN='$candidates = [System.Collections.Generic.List[string]]::new()'
END='$robotWindow = Get-PackagedRobotWindow -WorldText $worldText'
PRIVATE=r'''# M2: exact private Webots only, no global SDK, Program Files or PATH fallback.
$privateHome=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'Webots'))
$manifest=Join-Path $PSScriptRoot 'PRIVATE_RUNTIME.sha256'
if(-not(Test-Path -LiteralPath $manifest -PathType Leaf)){throw 'Private runtime manifest missing'}
if(-not(Test-Path -LiteralPath (Join-Path $privateHome 'resources/version.txt') -PathType Leaf)){throw 'Private runtime missing'}
if((Get-Content (Join-Path $privateHome 'resources/version.txt') -Raw).Trim() -cne 'R2025a'){throw 'Private Webots wrong version'}
if($WebotsHome -and -not [IO.Path]::GetFullPath($WebotsHome).Equals($privateHome,[StringComparison]::OrdinalIgnoreCase)){throw 'External WEBOTS_HOME forbidden'}
$seen=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$prefix=$privateHome.TrimEnd('\')+[IO.Path]::DirectorySeparatorChar
foreach($line in (Get-Content -LiteralPath $manifest)){
 if($line -cnotmatch '^([0-9a-f]{64})  Webots/([^\r\n]+)$'){throw 'Invalid private manifest entry'}
 $digest=$Matches[1];$relative=$Matches[2]
 if($relative -match '(^|/)\.\.?(/|$)|[:\\]' -or -not $seen.Add($relative)){throw 'Unsafe private manifest path'}
 $path=[IO.Path]::GetFullPath((Join-Path $privateHome $relative.Replace('/',[IO.Path]::DirectorySeparatorChar)))
 if(-not $path.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase) -or -not(Test-Path -LiteralPath $path -PathType Leaf)){throw 'Private module missing'}
 if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $digest){throw 'Private module identity mismatch'}
}
$bin=Join-Path $privateHome 'msys64/mingw64/bin'
foreach($name in @('webots-bin.exe','webots.exe','webotsw.exe','Qt6Core.dll','Qt6Gui.dll','Qt6Widgets.dll','libstdc++-6.dll','libgcc_s_seh-1.dll','libwinpthread-1.dll','libopenal-1.dll')){
 if(-not $seen.Contains(('msys64/mingw64/bin/'+$name))){throw 'Private critical module not attested'}
}
if(-not $seen.Contains('msys64/mingw64/share/qt6/plugins/platforms/qwindows.dll') -or -not $seen.Contains('lib/controller/Controller.dll')){throw 'Private QPA/Controller not attested'}
$env:WEBOTS_HOME=$privateHome
$env:PATH="$bin;$env:SystemRoot\System32;$env:SystemRoot"
$env:QT_PLUGIN_PATH=Join-Path $privateHome 'msys64/mingw64/share/qt6/plugins'
$env:QT_QPA_PLATFORM_PLUGIN_PATH=Join-Path $env:QT_PLUGIN_PATH 'platforms'
function Test-WebotsR2025a {
 param([string]$Executable)
 if(-not(Test-Path -LiteralPath $Executable -PathType Leaf)){return $false}
 $version=(& (Join-Path $bin 'webots.exe') --version 2>&1 | Out-String).Trim()
 return ($LASTEXITCODE -eq 0 -and $version -match 'R2025a')
}
$webots=Join-Path $bin 'webotsw.exe'
if(-not(Test-WebotsR2025a -Executable $webots)){throw 'Private official Webots launcher refused'}

'''

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as fd:
  for chunk in iter(lambda:fd.read(1<<20),b''):h.update(chunk)
 return h.hexdigest()

def lines(root,omit=set()):
 return ''.join(f'{sha(p)}  {p.relative_to(root).as_posix()}\n'
   for p in sorted(root.rglob('*')) if p.is_file() and p.relative_to(root).as_posix() not in omit)


def normalize_unsigned_controller_pe(exe):
 """Normalize ONLY PE/COFF timestamp and optional-header checksum.
 Independently reproduced R2025a current-M1 build differed at exactly
 offsets 0x88 (timestamp) and 0xd8 (checksum); code bytes were identical.
 Excludes the genuine Webots engine and original Qt/GCC DLL identities.
 """
 data=bytearray(exe.read_bytes())
 if len(data)<256 or data[:2]!=b'MZ':raise ValueError('M2 controller is not PE')
 pe=struct.unpack_from('<I',data,0x3c)[0]
 if pe+104>len(data) or data[pe:pe+4]!=b'PE\x00\x00':raise ValueError('M2 controller invalid PE header')
 if struct.unpack_from('<H',data,pe+24)[0] not in (0x10b,0x20b):raise ValueError('M2 controller PE optional magic unknown')
 timestamp=pe+8
 checksum_offset=pe+24+64
 before=bytes(data)
 struct.pack_into('<I',data,timestamp,0)
 struct.pack_into('<I',data,checksum_offset,0)
 value=0
 for i in range(0,len(data),2):
  if i in (checksum_offset,checksum_offset+2):continue
  value+=data[i]|((data[i+1] if i+1<len(data) else 0)<<8)
  value=(value&0xffff)+(value>>16)
 value=(value&0xffff)+(value>>16)
 value=(value&0xffff)+(value>>16)
 checksum=(value+len(data))&0xffffffff
 struct.pack_into('<I',data,checksum_offset,checksum)
 if any(before[i]!=data[i] for i in range(len(data)) if i not in (
   timestamp,timestamp+1,timestamp+2,timestamp+3,
   checksum_offset,checksum_offset+1,checksum_offset+2,checksum_offset+3)):
  raise ValueError('M2 normalization touched executable data')
 exe.write_bytes(data)
 print('M2_CURRENT_M1_CONTROLLER_PE_METADATA_NORMALIZED=PASS checksum='+hex(checksum))


def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--classroom',type=Path,required=True)
 parser.add_argument('--private-webots',type=Path,required=True)
 parser.add_argument('--output-zip',type=Path,required=True)
 a=parser.parse_args()
 classroom=a.classroom.resolve(strict=True);private=a.private_webots.resolve(strict=True)
 if (private/'resources/version.txt').read_text().strip()!='R2025a':raise ValueError('Wrong private Webots version')
 dst=classroom/'Webots'
 if dst.exists() or a.output_zip.exists():raise ValueError('Refusing overwrite of release')
 launcher=classroom/'Launch-WebeeBlocks.ps1';old=launcher.read_text(encoding='utf-8-sig')
 if old.count(BEGIN)!=1 or old.count(END)!=1 or old.index(BEGIN)>old.index(END):raise ValueError('Unexpected launcher source')
 shutil.copytree(private,dst)
 # Official Inno Setup installer metadata contains host-dependent install paths,
 # not runtime dependencies of the portable Webots engine.
 for relative in ('Webots.lnk','unins000.dat','unins000.exe'):
  candidate=dst/relative
  if not candidate.is_file():raise ValueError('Expected official installer-only metadata missing '+relative)
  candidate.unlink()
 normalize_unsigned_controller_pe(classroom/'controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.exe')
 launcher.write_text(old[:old.index(BEGIN)]+PRIVATE+old[old.index(END):],encoding='utf-8')
 (classroom/'PRIVATE_RUNTIME.sha256').write_text(
   ''.join(f'{sha(p)}  Webots/{p.relative_to(dst).as_posix()}\n' for p in sorted(dst.rglob('*')) if p.is_file()),encoding='utf-8')
 (classroom/'MANIFEST.sha256').write_text(lines(classroom,{'MANIFEST.sha256'}),encoding='utf-8')
 with zipfile.ZipFile(a.output_zip,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
  for p in sorted(classroom.rglob('*')):
   if not p.is_file():continue
   info=zipfile.ZipInfo(p.relative_to(classroom).as_posix(),date_time=(2026,11,2,0,0,0))
   info.compress_type=zipfile.ZIP_DEFLATED
   info.external_attr=0o644<<16
   with p.open('rb') as source,z.open(info,'w',force_zip64=True) as output:shutil.copyfileobj(source,output,1<<20)
 print('M2_PRIVATE_RELEASE_SHA256='+sha(a.output_zip))
if __name__=='__main__':main()

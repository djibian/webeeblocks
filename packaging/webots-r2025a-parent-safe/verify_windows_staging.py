#!/usr/bin/env python3
"""Static fail-closed input/staging check for M2, NOT Windows Q or D/W evidence.
No execution or automatic fallback to an installed SDK is performed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

KERNEL_ZIP = '86b9540cd5a41bdd5680fb81f00d35befb6610da26f414fffb67123e7267301e'
CRITICAL = {
 'msys64/mingw64/bin/webots-bin.exe': '52b8c047047094c30f0cd358456ca5a18c73209457c2129991068f5825c8a06e',
 'msys64/mingw64/bin/webots.exe': '34e3824b3bb1d64cea8ed58ec4089b607fb83c906d36290df8e2d4a8ee2227c0',
 'msys64/mingw64/bin/Qt6Core.dll': '85bd00fb398346adef666fa9275a6c06f0955927e09d7909cd558700f4d92179',
 'msys64/mingw64/bin/Qt6Gui.dll': 'b268755f2cf1c3eb4f25b6b8435481ff91be0f8a16d578f7d88bc413676c1660',
 'msys64/mingw64/bin/Qt6Widgets.dll': 'ac1bd54bd2e4eac84e047893e3b0b3b2c9951395bc538552406c6869bb40eb89',
 'msys64/mingw64/bin/libstdc++-6.dll': '494bd9045948198ef4d3bc838c7362d4cfd49c890b439c096b1817aa7c7fa6ff',
 'msys64/mingw64/bin/libgcc_s_seh-1.dll': 'd7e343dd266747177c3699bc3201ea36eceef158e98530e089263bc55bb2a6d7',
 'msys64/mingw64/bin/libwinpthread-1.dll': '72bf8802de3a99d28f0bc2db9a11f281a9f9f3fa83dab2bc67e69fac3bd3d9c0',
 'msys64/mingw64/bin/libopenal-1.dll': 'cb97d2f5a9797ff64db90d0691e4ff9eb2a088026351c9bad7aa26d229a354ce',
 'msys64/mingw64/share/qt6/plugins/platforms/qwindows.dll': '9b3b3531ccac562a84698eff4761a6966f531bc01b1d56d5fda8c2da9c6424c1',
 'lib/controller/Controller.dll': '756ceba41c53f1a5f008859255254b28d6d3acb674e1ea773544cc6648c41039',
}
SOURCE = {'webots-bin.exe','Qt6Core.dll','Qt6Gui.dll','Qt6Widgets.dll'}

def sha(path):
 h = hashlib.sha256()
 with path.open('rb') as stream:
  for chunk in iter(lambda: stream.read(1024*1024),b''):
   h.update(chunk)
 return h.hexdigest()

def verify(runtime, archive):
 runtime=runtime.resolve(strict=True)
 if sha(archive)!=KERNEL_ZIP:
  raise ValueError('original Windows ZIP SHA mismatch')
 if (runtime/'resources/version.txt').read_text().strip()!='R2025a':
  raise ValueError('private Webots release mismatch')
 launcher=runtime/'msys64/mingw64/bin/webotsw.exe'
 if not launcher.is_file() or launcher.is_symlink():
  raise ValueError('official webotsw launcher missing')
 with zipfile.ZipFile(archive) as z:
  if len(z.infolist())!=16 or z.testzip() is not None:
   raise ValueError('original ZIP entries or CRC mismatch')
  for name in SOURCE:
   p=runtime/'msys64/mingw64/bin'/name
   if not p.is_file() or sha(p)!=hashlib.sha256(z.read(name)).hexdigest():
    raise ValueError('patched source byte mismatch: '+name)
 identities={}
 for rel, expected in CRITICAL.items():
  p=runtime/rel
  if not p.is_file() or p.is_symlink() or not p.resolve().is_relative_to(runtime):
   raise ValueError('missing or unsafe private runtime file: '+rel)
  actual=sha(p)
  if actual!=expected:
   raise ValueError('wrong critical file SHA: '+rel)
  identities[rel]=actual
 return {'status':'STATIC_STAGING_ONLY_NOT_DISTRIBUTABLE',
         'critical_bytes_verified':len(identities),
         'files':identities,'webotsw_sha256_observed_not_yet_source_pinned':sha(launcher),
         'limitations':['dynamic loaded-module graph unproven',
                        'full transitive PE import closure unproven',
                        'Qt6 Windows Q unproven','clean-host D/W unproven']}

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--runtime-root',type=Path,required=True)
 p.add_argument('--kernel-zip',type=Path,required=True)
 p.add_argument('--report',type=Path,required=True)
 a=p.parse_args()
 try:
  result=verify(a.runtime_root,a.kernel_zip)
 except (OSError,ValueError,zipfile.BadZipFile) as e:
  raise SystemExit('M2_WINDOWS_STAGING_REFUSED: '+str(e))
 a.report.parent.mkdir(parents=True,exist_ok=True)
 a.report.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
 print('M2_WINDOWS_STAGING_STATIC=PASS NOT_Q_NOT_DW')
if __name__=='__main__':
 main()

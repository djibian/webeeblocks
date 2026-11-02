#!/usr/bin/env python3
"""Deterministic V5 human test preparation for the *exact* M2 private Windows ZIP.

Only authenticates provenance/contents and supplies the unchanged archive.
No notification, native Windows claim, human PASS or execution of the ZIP.
"""
import argparse,hashlib,json,re,shutil,subprocess,zipfile
from pathlib import Path
ZIP_SHA="dc614c04ca10115a85d76ce6e5150bd9e7551f0fe8cd3937f7b24563ec9b72c8"
OCI="ghcr.io/djibian/webeeblocks-m2-private-windows-r2025a@sha256:ec0d516047bacf56aa536d29e6116636cec8632392d5bcf71992a3281e6e84fd"
ARTIFACT=13144826515
PIN="1cfefebf127cd70b90d2c14a8360fd8d978e6710"
ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/"packaging/webots-r2025a-parent-safe"
PROTOCOL=DATA/"M2-WINDOWS-DW-ACCEPTANCE.md"

def sha_stream(stream):
 h=hashlib.sha256()
 for b in iter(lambda:stream.read(1<<20),b""):h.update(b)
 return h.hexdigest()

def checksums(lines):
 entries={}
 for line in lines.decode("utf-8").splitlines():
  match=re.fullmatch(r"([0-9a-f]{64})  (.+)",line)
  if not match:raise ValueError("invalid manifest format")
  digest,path=match.groups()
  if path.casefold() in entries:raise ValueError("case-insensitive manifest duplicate")
  entries[path.casefold()]=(path,digest)
 return entries

def validate(current_zip,target):
 if not re.fullmatch(r"[0-9a-f]{40}",target):raise ValueError("invalid target")
 actual=subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()
 if actual!=target:raise ValueError("checkout target SHA differs")
 prov=json.loads((DATA/"PROVENANCE.json").read_text(encoding="utf-8"))
 p=prov["windows"]["private_product"]
 for key,value in (("inner_zip_sha256",ZIP_SHA),("oci",OCI),("source_artifact",ARTIFACT),("archive_source_head",PIN)):
  if p.get(key)!=value:raise ValueError("M2 exact-provenance mismatch: "+key)
 if prov["windows"]["historical_private_product"]["inner_zip_sha256"]==ZIP_SHA:
  raise ValueError("historical/current release confused")
 protocol=PROTOCOL.read_bytes()
 if ZIP_SHA.encode() not in protocol or OCI.encode() not in protocol:
  raise ValueError("human procedure does not name current exact release")
 with current_zip.open("rb") as src:
  if sha_stream(src)!=ZIP_SHA:raise ValueError("M2 ZIP hash mismatch")
 with zipfile.ZipFile(current_zip) as z:
  names=z.namelist()
  if len(names)!=len(set(n.casefold() for n in names)):raise ValueError("duplicate ZIP name")
  if any(not n or n.startswith("/") or "\\" in n or "." in n.split("/") and n!="./" or ".." in n.split("/") or ":" in n for n in names):
   raise ValueError("unsafe member path")
  all_hash=checksums(z.read("MANIFEST.sha256"))
  webots_hash=checksums(z.read("PRIVATE_RUNTIME.sha256"))
  if len(webots_hash)!=11366:raise ValueError("M2 unexpected private runtime inventory")
  if len(all_hash)!=len(names)-1 or set(all_hash)!={n.casefold() for n in names if n!="MANIFEST.sha256"}:
   raise ValueError("M2 full manifest inventory inconsistent")
  if set(webots_hash)!={k for k in all_hash if k.startswith("webots/")}:
   raise ValueError("M2 private manifest inventory inconsistent")
  for name in names:
   with z.open(name) as src:
    digest=sha_stream(src)
   if name=="MANIFEST.sha256":continue
   if digest!=all_hash[name.casefold()][1]:raise ValueError("M2 tampered archive member: "+name)
   if name.casefold() in webots_hash and digest!=webots_hash[name.casefold()][1]:
    raise ValueError("M2 Webots module hash drift "+name)
 return {"verified_files":len(names),"private_files":len(webots_hash),"zip_sha256":ZIP_SHA,
         "oci":OCI,"original_producer_artifact":ARTIFACT,"target_sha":target,
         "qualification":"ARCHIVE_PREPARED_ONLY_NOT_WINDOWS_DW_OR_HUMAN_PASS"}

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument("--zip",required=True,type=Path)
 parser.add_argument("--target-sha",required=True)
 parser.add_argument("--output",required=True,type=Path)
 args=parser.parse_args()
 source=args.zip.resolve(strict=True)
 result=validate(source,args.target_sha)
 out=args.output.resolve()
 if out.exists():raise ValueError("checkpoint output exists; no overwrite")
 out.mkdir(parents=True)
 shutil.copyfile(source,out/"M2-private-product.zip")
 shutil.copyfile(PROTOCOL,out/"M2-WINDOWS-DW-ACCEPTANCE.md")
 (out/"SHA256SUMS").write_text(ZIP_SHA+"  M2-private-product.zip\n",encoding="utf-8")
 (out/"EXACT-M2-CHECKPOINT.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
 print("M2_V5_EXACT_WINDOWS_CHECKPOINT_ARCHIVE_PREPARED=PASS_NOT_DW")
if __name__=="__main__":main()

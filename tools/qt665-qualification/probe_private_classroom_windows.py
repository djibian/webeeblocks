#!/usr/bin/env python3
"""Fail-closed exact M2 Windows native startup: READY + actual mapped modules.
Not interactive 3D D/W, not Qt-method natural full-product trigger.
"""
import argparse,hashlib,json,os,re,socket,subprocess,sys,threading,time
from pathlib import Path
import psutil

CORE=("Qt6Core.dll","Qt6Gui.dll","Qt6Widgets.dll")
GCC=("libstdc++-6.dll","libgcc_s_seh-1.dll","libwinpthread-1.dll")
ENGINE=("webots-bin.exe","qwindows.dll","libopenal-1.dll")+CORE+GCC
CONTROLLER=("crazyflie_runtime_v2.exe","Controller.dll")+CORE+GCC

def digest(path):
 h=hashlib.sha256()
 with Path(path).open("rb") as f:
  for chunk in iter(lambda:f.read(1<<20),b""):h.update(chunk)
 return h.hexdigest()

def manifest(root):
 record={}
 for line in (root/"PRIVATE_RUNTIME.sha256").read_text(encoding="utf-8").splitlines():
  m=re.fullmatch(r"([a-f0-9]{64})  (Webots/.+)",line)
  if not m or m[2].casefold() in record:raise ValueError("M2 manifest line invalid/duplicate")
  record[m[2].casefold()]=(root/m[2],m[1])
 for name,(path,sha) in record.items():
  if not path.is_file() or not path.resolve().is_relative_to(root) or digest(path)!=sha:
   raise ValueError("M2 manifest identity mismatch: "+name)
 return record

def evidence(role,proc,root,items):
 actual={}
 module_files={Path(p.path).name.casefold():Path(p.path) for p in proc.memory_maps() if p.path}
 engine=root/"Webots/msys64/mingw64/bin"
 for name in items:
  if name=="qwindows.dll":path=root/"Webots/msys64/mingw64/share/qt6/plugins/platforms/qwindows.dll"
  elif name=="Controller.dll":path=root/"Webots/lib/controller/Controller.dll"
  elif name=="crazyflie_runtime_v2.exe":path=root/"controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.exe"
  else:path=engine/name
  found=module_files.get(name.casefold())
  if found is None:raise LookupError("Module not observed "+name)
  if found.resolve()!=path.resolve():raise ValueError("M2 ambient module "+name+" "+str(found))
  if digest(path)!=digest(found):raise ValueError("M2 wrong loaded bytes "+name)
  actual[name]={"path":str(found),"sha256":digest(found)}
 return {"role":role,"pid":proc.pid,"ppid":proc.ppid(),"created":proc.create_time(),"exe":proc.exe(),"mapped":actual}

def run(root,out):
 if sys.platform!="win32":raise RuntimeError("Windows only")
 root=root.resolve(strict=True);out.mkdir(parents=True,exist_ok=False)
 private=root/"Webots";bin=private/"msys64/mingw64/bin"
 record=manifest(root)
 process=None;seen={};threads=[];capture_errors=[]
 report={"status":"FAIL","release_archive_sha256":"9f3093082c5155ab3b77dfd902199350b7cecf9a67ceced139fcba03fb77194c","manifest_files":len(record)}
 try:
  with socket.socket() as sock:
   sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
  env=os.environ.copy()
  for key in list(env):
   if key.upper().startswith(("QT_","QML","WEBOTS","WEBEEBLOCKS","PYTHON")):env.pop(key,None)
  env["WEBOTS_HOME"]=str(private)
  env["QT_PLUGIN_PATH"]=str(private/"msys64/mingw64/share/qt6/plugins")
  env["QT_QPA_PLATFORM_PLUGIN_PATH"]=str(private/"msys64/mingw64/share/qt6/plugins/platforms")
  env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"]="true"
  env["PATH"]=os.pathsep.join((str(bin),str(private/"msys64/usr/bin"),str(Path(env["SystemRoot"])/"System32"),env["SystemRoot"]))
  world=root/"worlds/crazyflie_runtime_v2.wbt"
  cmd=[str(bin/"webots.exe"),"--stdout","--stderr","--batch","--mode=fast",f"--port={port}",str(world)]
  report["command"]=cmd;report["path"]=env["PATH"]
  def drain(pipe,name):
   try:
    with pipe,(out/name).open("wb") as file:
     while data:=pipe.read1(65536):file.write(data);file.flush()
   except Exception as error:capture_errors.append(str(error))
  process=subprocess.Popen(cmd,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  for stream,name in ((process.stdout,"stdout.log"),(process.stderr,"stderr.log")):
   thread=threading.Thread(target=drain,args=(stream,name),daemon=True);thread.start();threads.append(thread)
  rootproc=psutil.Process(process.pid);root_created=rootproc.create_time();report["launcher"]={"pid":process.pid,"exe":rootproc.exe(),"created":root_created}
  stable=None;deadline=time.monotonic()+65
  while time.monotonic()<deadline:
   if process.poll() is not None:raise RuntimeError("Launcher exited before READY, code "+str(process.returncode))
   try:children=rootproc.children(recursive=True)
   except psutil.NoSuchProcess:raise RuntimeError("Launcher disappeared")
   snapshots={}
   for child in children:
    try:
     seen[(child.pid,child.create_time())]=child
     name=child.name().casefold()
     if name not in ("webots-bin.exe","crazyflie_runtime_v2.exe"):continue
     cli=child.cmdline()
     role=("engine" if name=="webots-bin.exe" else ("runtime" if len(cli)==1 else "sequence-evaluator" if len(cli)==2 and cli[1]=="sequence-evaluator-v1" else "unknown"))
     if role=="unknown":raise ValueError("Unexpected controller CLI: "+str(cli))
     expected=(bin/"webots-bin.exe" if role=="engine" else root/"controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.exe")
     if Path(child.exe()).resolve()!=expected.resolve():raise ValueError("M2 wrong child executable")
     snapshots[role]=evidence(role,child,root,ENGINE if role=="engine" else CONTROLLER)
    except (psutil.NoSuchProcess,psutil.AccessDenied,LookupError):continue
   contents="\n".join((out/n).read_text(errors="replace") if (out/n).exists() else "" for n in ("stdout.log","stderr.log"))
   report["ready_observed"]=bool(re.search(r"WEBEEBLOCKS_RUNTIME_V2 READY(?:\s|$)",contents))
   if report["ready_observed"] and set(snapshots)=={"engine","runtime","sequence-evaluator"}:
    eng=snapshots["engine"]
    if eng["ppid"]!=process.pid or any(snapshots[r]["ppid"]!=eng["pid"] for r in ("runtime","sequence-evaluator")):
     raise ValueError("M2 unexpected native process parenthood")
    if any(psutil.Process(v["pid"]).create_time()!=v["created"] for v in snapshots.values()):raise ValueError("M2 stale/reused PID")
    if stable is None:stable=time.monotonic()
    if time.monotonic()-stable>=2:
     if re.search(r"^ERROR:|Segmentation fault|FATAL:",contents,re.MULTILINE):raise RuntimeError("M2 native fatal log")
     report["status"]="PASS_BOUNDED_REAL_PRODUCT_READY_AND_MODULES";report["processes"]=snapshots
     return
   else:stable=None
   time.sleep(.15)
  raise RuntimeError("M2 real classroom READY + engine/2 controllers/Qt mapped identity UNPROVEN in 65s")
 finally:
  retirement=[]
  if process is not None:
   try:
    pr=psutil.Process(process.pid)
    for child in pr.children(recursive=True):seen[(child.pid,child.create_time())]=child
   except psutil.NoSuchProcess:pass
   for (pid,created),child in reversed(list(seen.items())):
    try:
     if child.create_time()==created:
      child.kill();child.wait(timeout=10)
    except psutil.NoSuchProcess:pass
    except Exception as error:retirement.append(str(error))
   if process.poll() is None:process.kill()
   try:process.wait(timeout=10)
   except Exception as error:retirement.append(str(error))
   for t in threads:t.join(timeout=10)
   if any(t.is_alive() for t in threads):retirement.append("Log reader alive")
  report["capture_errors"]=capture_errors;report["cleanup_errors"]=retirement
  if retirement or capture_errors:report["status"]="FAIL"
  (out/"result.json").write_text(json.dumps(report,indent=2)+"\n")
  if retirement or capture_errors:raise RuntimeError("M2 observer capture/cleanup incomplete")

if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--package",required=True,type=Path);p.add_argument("--output",required=True,type=Path)
 a=p.parse_args();run(a.package,a.output)
 print("M2_NATIVE_WINDOWS_REAL_PRODUCT_READY_AND_MODULES=PASS_BOUNDED_NOT_DW")

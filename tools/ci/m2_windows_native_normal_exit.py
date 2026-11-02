#!/usr/bin/env python3
"""NON-GATE: actual Windows M2 Webots normal GUI close (never an artificial PASS).

No taskkill/TerminateProcess is allowed in the proof path. Forced cleanup after
failure is explicitly recorded as UNPROVEN and cannot satisfy the oracle.
"""
import argparse,ctypes,json,os,re,socket,subprocess,sys,threading,time
from ctypes import wintypes
from pathlib import Path
import psutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"qt665-qualification"))
from probe_private_classroom_windows import manifest,evidence,ENGINE,CONTROLLER
EXPECTED_ZIP="dc614c04ca10115a85d76ce6e5150bd9e7551f0fe8cd3937f7b24563ec9b72c8"

def windows_for(pid):
 user32=ctypes.WinDLL("user32",use_last_error=True)
 proc_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
 user32.EnumWindows.argtypes=(proc_type,wintypes.LPARAM)
 user32.EnumWindows.restype=wintypes.BOOL
 user32.GetWindowThreadProcessId.argtypes=(wintypes.HWND,ctypes.POINTER(wintypes.DWORD))
 user32.IsWindowVisible.argtypes=(wintypes.HWND,)
 user32.IsWindowVisible.restype=wintypes.BOOL
 user32.GetWindowTextLengthW.argtypes=(wintypes.HWND,)
 user32.GetWindowTextW.argtypes=(wintypes.HWND,wintypes.LPWSTR,ctypes.c_int)
 found=[]
 @proc_type
 def visit(hwnd,_):
  owner=wintypes.DWORD()
  user32.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
  if owner.value==pid and user32.IsWindowVisible(hwnd):
   length=user32.GetWindowTextLengthW(hwnd)
   title=ctypes.create_unicode_buffer(length+1)
   user32.GetWindowTextW(hwnd,title,len(title))
   found.append((int(hwnd),title.value))
  return True
 if not user32.EnumWindows(visit,0):raise OSError(ctypes.get_last_error(),"EnumWindows failed")
 return found

def run(root,directory):
 if sys.platform!="win32":raise RuntimeError("Win32 native only")
 root=root.resolve(strict=True)
 directory.mkdir(parents=True,exist_ok=False)
 observed={"status":"UNPROVEN","exact_release_zip_sha256":EXPECTED_ZIP,"forced_cleanup":False,"windows":[]}
 proc=None; owned={};pipes=[];failures=[];threads=[]
 def capture(pipe,filename):
  try:
   with pipe,(directory/filename).open("wb") as output:
    while data:=pipe.read1(65536):output.write(data);output.flush()
  except Exception as exc:failures.append(str(exc))
 try:
  files=manifest(root)
  observed["private_files_verified"]=len(files)
  home=root/"Webots"
  bin=home/"msys64/mingw64/bin"
  with socket.socket() as sock:
   sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
  env=os.environ.copy()
  for k in list(env):
   if k.upper().startswith(("QT_","QML","WEBOTS","WEBEEBLOCKS","PYTHON")):env.pop(k,None)
  sr=env.get("SystemRoot") or env.get("SYSTEMROOT")
  if not sr or not (Path(sr)/"System32").is_dir():raise RuntimeError("No Windows SystemRoot")
  env["PATH"]=os.pathsep.join((str(bin),str(home/"msys64/usr/bin"),str(Path(sr)/"System32"),sr))
  env["WEBOTS_HOME"]=str(home)
  env["QT_PLUGIN_PATH"]=str(home/"msys64/mingw64/share/qt6/plugins")
  env["QT_QPA_PLATFORM_PLUGIN_PATH"]=str(home/"msys64/mingw64/share/qt6/plugins/platforms")
  env["WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE"]="true"
  cmd=[str(bin/"webots.exe"),"--stdout","--stderr","--batch","--mode=fast",f"--port={port}",str(root/"worlds/crazyflie_runtime_v2.wbt")]
  proc=subprocess.Popen(cmd,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  for file,pipe in (("stdout.log",proc.stdout),("stderr.log",proc.stderr)):
   thread=threading.Thread(target=capture,args=(pipe,file),daemon=True);thread.start();threads.append(thread)
  parent=psutil.Process(proc.pid)
  observed["launcher"]={"pid":proc.pid,"created":parent.create_time(),"exe":parent.exe(),"command":cmd}
  deadline=time.monotonic()+65;ready_since=None;engine=None;roles={}
  while time.monotonic()<deadline:
   if proc.poll() is not None:raise RuntimeError("Webots launcher exited before READY")
   children=parent.children(recursive=True)
   current={}
   for child in children:
    try:
     ident=(child.pid,child.create_time());owned[ident]=child
     name=child.name().casefold()
     if name=="webots-bin.exe": role="engine"
     elif name=="crazyflie_runtime_v2.exe":
      command=child.cmdline()
      role=("runtime" if len(command)==1 else "evaluator" if len(command)==2 and command[1]=="sequence-evaluator-v1" else "unexpected")
     else:continue
     if role=="unexpected":raise ValueError("Unexpected controller process arguments")
     expected=(bin/"webots-bin.exe" if role=="engine" else root/"controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.exe")
     if Path(child.exe()).resolve()!=expected.resolve():raise RuntimeError("Unexpected product executable identity")
     detail=evidence(role,child,root,ENGINE if role=="engine" else CONTROLLER)
     current[role]=detail
    except (psutil.NoSuchProcess,psutil.AccessDenied,LookupError):continue
   logs="\n".join((directory/name).read_text(errors="replace") if (directory/name).exists() else "" for name in ("stdout.log","stderr.log"))
   if "WEBEEBLOCKS_RUNTIME_V2 READY" in logs and set(current)=={"engine","runtime","evaluator"}:
    if current["engine"]["ppid"]!=proc.pid or any(current[k]["ppid"]!=current["engine"]["pid"] for k in ("runtime","evaluator")):
     raise RuntimeError("Wrong launcher/engine/child lineage")
    if ready_since is None:ready_since=time.monotonic()
    if time.monotonic()-ready_since>=2:
     roles=current
     engine=psutil.Process(current["engine"]["pid"])
     break
   else:ready_since=None
   time.sleep(.2)
  if engine is None:raise RuntimeError("Ready or exact loaded module identity unavailable")
  observed["before_close"]=roles
  available=windows_for(engine.pid)
  observed["windows"]=[{"hwnd":h,"title":title} for h,title in available]
  candidates=[(h,title) for h,title in available if "webots" in title.lower() or "webeeblocks" in title.lower()]
  if len(candidates)!=1:raise RuntimeError("No uniquely identified visible native Webots top-level window")
  hwnd,title=candidates[0]
  user32=ctypes.WinDLL("user32",use_last_error=True)
  user32.PostMessageW.argtypes=(wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM)
  user32.PostMessageW.restype=wintypes.BOOL
  if not user32.PostMessageW(hwnd,0x0010,0,0):raise RuntimeError("Native WM_CLOSE PostMessage failed")
  observed["normal_close_request"]={"hwnd":hwnd,"title":title,"method":"WM_CLOSE via actual native window, no forced stop"}
  try:launcher_return=proc.wait(timeout=35)
  except subprocess.TimeoutExpired:raise RuntimeError("Natural Webots launcher exit not observed within 35s")
  observed["launcher_exit_code"]=launcher_return
  # Return/EOF and all owned process lifecycles: never kill to obtain proof.
  returns={}
  for role,detail in roles.items():
   identity=(detail["pid"],detail["created"])
   child=owned.get(identity)
   if child is None:raise RuntimeError("Missing exact child process identity")
   try:returns[role]=child.wait(timeout=8)
   except psutil.NoSuchProcess:returns[role]=None
   except psutil.TimeoutExpired:raise RuntimeError("Process still running after native close: "+role)
  observed["children_exit_codes"]=returns
  for t in threads:t.join(timeout=5)
  if any(t.is_alive() for t in threads):raise RuntimeError("Native log pipe EOF missing")
  if launcher_return!=0 or any(code not in (0,None) for code in returns.values()):
   raise RuntimeError("Native normal close had nonzero engine/controller exit")
  # psutil.wait() on non-parent descendants returns None when their PID
  # disappears. PID reuse or stale Process handles cannot count as survivors.
  survivors=[]
  for role,detail in roles.items():
   try:
    live=psutil.Process(detail["pid"])
    if live.create_time()==detail["created"] and live.is_running() and live.status()!=psutil.STATUS_ZOMBIE:
     survivors.append(role)
   except psutil.NoSuchProcess:
    pass
  observed["surviving_same_identity_roles"]=survivors
  if survivors:raise RuntimeError("Same-identity native children still alive: "+",".join(survivors))
  if any("Fatal error" in (directory/name).read_text(errors="replace") for name in ("stdout.log","stderr.log")):
   raise RuntimeError("Native fatal during normal shutdown")
  observed["status"]="PASS_BOUNDED_NORMAL_NATIVE_WEBOTS_CLOSE_NOT_INTERACTIVE_DW"
 finally:
  if proc is not None:
   try:
    if proc.poll() is None or any(psutil.pid_exists(pid) for pid,_ in owned):
     if observed["status"]!="PASS_BOUNDED_NORMAL_NATIVE_WEBOTS_CLOSE_NOT_INTERACTIVE_DW":
      observed["forced_cleanup"]=True
      for (pid,created),child in reversed(list(owned.items())):
       try:
        if child.create_time()==created and child.is_running():child.kill();child.wait(timeout=10)
       except psutil.NoSuchProcess:pass
      if proc.poll() is None:proc.kill()
    proc.wait(timeout=10)
   except Exception as e:failures.append(str(e))
   for t in threads:t.join(timeout=6)
  observed["capture_or_cleanup_errors"]=failures
  if failures:observed["status"]="UNPROVEN"
  (directory/"result.json").write_text(json.dumps(observed,indent=2)+"\n")
  if failures:raise RuntimeError("Native cleanup/log capture errors")
 print("M2_WINDOWS_NATIVE_NORMAL_CLOSE="+observed["status"])
 if observed["status"]!="PASS_BOUNDED_NORMAL_NATIVE_WEBOTS_CLOSE_NOT_INTERACTIVE_DW":
  raise RuntimeError("Native natural shutdown UNPROVEN")

if __name__=="__main__":
 a=argparse.ArgumentParser()
 a.add_argument("--package",type=Path,required=True)
 a.add_argument("--output",type=Path,required=True)
 b=a.parse_args()
 run(b.package,b.output)

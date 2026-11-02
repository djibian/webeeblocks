#!/usr/bin/env python3
"""Generate exact patched Webots QProgressDialog methods for Win32 Qt-only test."""
import argparse,subprocess,sys,hashlib
from pathlib import Path
PIN="c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b"
FILES=["src/webots/gui/WbMainWindow.hpp","src/webots/gui/WbMainWindow.cpp","src/webots/app/WbApplication.cpp"]
PARENT=r"""
static bool testParentDeletedDuringProgress() {
 auto *w=new WbMainWindow();
 QPointer<WbMainWindow> weak(w);
 w->createWorldLoadingProgressDialog();
 QPointer<QProgressDialog> dialog(w->current());
 if(!dialog) {delete w;return false;}
 dialog->setRange(0,100);
 QPointer<QProgressBar> bar(dialog->findChild<QProgressBar *>());
 if(!bar) {delete w;return false;}
 bool called=false,guarded=false,ownerGone=false,dialogAlive=false;
 QTimer::singleShot(0,dialog,[&]() {
   called=true;guarded=!weak.isNull()&&weak->operationDepth()>0;
   delete w;ownerGone=weak.isNull();
   dialogAlive=!dialog.isNull()&&!bar.isNull();
 });
 w->setWorldLoadingProgress(51);
 bool aliveAfter=!dialog.isNull()&&!bar.isNull();
 QCoreApplication::sendPostedEvents(nullptr,QEvent::DeferredDelete);
 QApplication::processEvents();
 bool drained=dialog.isNull()&&bar.isNull();
 std::printf("parent_destroy: callback=%d guard=%d owner=%d inner=%d return=%d drained=%d\n",
             called,guarded,ownerGone,dialogAlive,aliveAfter,drained);
 return called&&guarded&&ownerGone&&dialogAlive&&aliveAfter&&drained;
}
"""
def checked(*argv,cwd=None):
 subprocess.run([str(i) for i in argv],cwd=cwd,check=True)
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--source",type=Path,required=True)
 p.add_argument("--out",type=Path,required=True)
 a=p.parse_args()
 source=a.source.resolve(strict=True);out=a.out.resolve()
 observed=subprocess.check_output(["git","-C",str(source),"rev-parse","HEAD"],text=True).strip()
 if observed!=PIN:raise RuntimeError("Source pin mismatch")
 for name in FILES:
  target=out/name;target.parent.mkdir(parents=True,exist_ok=True)
  target.write_bytes(subprocess.check_output(["git","-C",str(source),"show","HEAD:"+name]))
 checked("git","init","-q",cwd=out)
 # The Windows runner may checkout tracked .patch as CRLF; our three Git-show
 # sources remain LF. Read the original patch Git blob, never the worktree copy.
 root=Path(__file__).resolve().parent
 repository=root.parents[1]
 rel="tools/qt665-qualification/webots-r2025a-guarded-progress-retirement.patch"
 raw=subprocess.check_output(["git","-C",str(repository),"show","HEAD:"+rel])
 blob=hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
 expected="f095a997a8e71e8753acd922e568a098bf6f765f"
 if blob!=expected:raise RuntimeError("M2_Q_PATCH_GIT_BLOB_MISMATCH "+blob)
 checkout=(root/"webots-r2025a-guarded-progress-retirement.patch").read_bytes()
 def endings(data):
  return dict(crlf=data.count(b"\r\n"),lf=data.count(b"\n"),bare_cr=data.count(b"\r")-data.count(b"\r\n"))
 originals={name:endings((out/name).read_bytes()) for name in FILES}
 report={"patch_git_blob":blob,"patch_canonical":endings(raw),"patch_checkout":endings(checkout),"sources":originals}
 import json
 (out/"q-line-endings.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
 print("M2_Q_PATCH_EOL_OBSERVED="+json.dumps(report,sort_keys=True),flush=True)
 if endings(raw)["crlf"] or endings(raw)["bare_cr"]:raise RuntimeError("M2_Q_CANONICAL_PATCH_NOT_LF")
 if any(v["crlf"] or v["bare_cr"] for v in originals.values()):raise RuntimeError("M2_Q_OFFICIAL_SOURCES_NOT_LF")
 patch=out/"canonical.patch"
 patch.write_bytes(raw)
 if patch.read_bytes()!=raw:raise RuntimeError("M2_Q_PATCH_COPY_CHANGED")
 checked("git","config","core.autocrlf","false",cwd=out)
 checked("git","apply","--check",patch,cwd=out)
 checked("git","apply",patch,cwd=out)
 checked(sys.executable,root/"repair_parent_shutdown.py","--webots-tree",out)
 cpp=out/"src/webots/gui/WbMainWindow.cpp"
 native=out/"parent_safe_q_windows.cpp"
 checked(sys.executable,root/"qt665_guarded_lease_harness.py","--patched-cpp",cpp,"--output",native)
 text=native.read_text()
 if text.count("int main(int argc, char **argv) {")!=1 or text.count("bool s4 = testCancelPreserved();")!=1 or text.count("(s1 && s2 && s3 && s4)")!=2:
  raise RuntimeError("Q harness source drift")
 text=text.replace("int main(int argc, char **argv) {",PARENT+"\nint main(int argc, char **argv) {")
 text=text.replace("bool s4 = testCancelPreserved();","bool s4 = testCancelPreserved();\n bool s5 = testParentDeletedDuringProgress();")
 text=text.replace("(s1 && s2 && s3 && s4)","(s1 && s2 && s3 && s4 && s5)")
 native.write_text(text)
 print("M2_WIN_Q_EXACT_PATCH_METHOD_HARNESS_GENERATED=PASS")
if __name__=="__main__":main()

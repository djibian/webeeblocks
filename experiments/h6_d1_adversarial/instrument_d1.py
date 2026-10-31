#!/usr/bin/env python3
"""Separate D1 real Webots owner-foreign-body deletion instrumentation, non-mutating candidate."""
from pathlib import Path
import subprocess,sys
if len(sys.argv)!=2: raise SystemExit("usage: instrument_d1.py WEBOTS")
root=Path(sys.argv[1])
subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/"h6_d3_adversarial"/"instrument.py"),str(root)],check=True)
cpath=root/"src/webots/ode/WbOdeContext.cpp"
mpath=root/"src/webots/nodes/utils/WbSolidMerger.cpp"
c=cpath.read_text();m=mpath.read_text()
def once(src,a,b,why):
 if src.count(a)!=1:raise SystemExit(f"REFUSED {why}, count={src.count(a)}")
 return src.replace(a,b)
a='''      if (it.value() == b || dJointGetBody(joint, 0) == b ||
          dJointGetBody(joint, 1) == b ||
          (!dJointGetBody(joint, 0) && !dJointGetBody(joint, 1))) {
        it.remove();  // unregister before freeing: no stale pointer after free
        dJointDestroy(joint);
      }'''
b='''      const dBodyID v0 = dJointGetBody(joint, 0);
      const dBodyID v1 = dJointGetBody(joint, 1);
      const bool drop = it.value() == b || v0 == b || v1 == b || (!v0 && !v1);
      if (std::getenv("H6_D1_AUDIT"))
        std::fprintf(stderr,
                     "H6_D1_FOREIGN_SCAN victim=%p joint=%p owner=%p ownerEnabled=%d"
                     " b0=%p b1=%p destroy=%d\\n",
                     static_cast<void *>(b),static_cast<void *>(joint),
                     static_cast<void *>(it.value()),int(dBodyIsEnabled(it.value())),
                     static_cast<void *>(v0),static_cast<void *>(v1),int(drop));
      if (drop) {
        it.remove();  // unregister before freeing: no stale pointer after free
        dJointDestroy(joint);
      }'''
c=once(c,a,b,"foreign scan")
for buffer in ("1","2"):
    old=f'std::fprintf(stderr,"H6_D3_RETIRE buffer={buffer} before=%d after=%d\\n",before,mBodyContacts{buffer}.size());'
    new=f'if (before > 0) std::fprintf(stderr,"H6_D3_RETIRE buffer={buffer} before=%d after=%d\\n",before,mBodyContacts{buffer}.size());'
    c=once(c,old,new,f"no empty-retirement log buffer{buffer}")
a='''WbSolidMerger::~WbSolidMerger() {
  WbOdeContext::instance()->removeBodyContactJointGroup(mBody);
  dBodyDestroy(mBody);
  mBody = NULL;'''
b='''WbSolidMerger::~WbSolidMerger() {
  std::fprintf(stderr,"H6_D1_REAL_BODY_DESTROY_START body=%p joints=%d\\n",
               static_cast<void *>(mBody),dBodyGetNumJoints(mBody));
  WbOdeContext::instance()->removeBodyContactJointGroup(mBody);
  std::fprintf(stderr,"H6_D1_REAL_BODY_DESTROY_BEFORE_ODE body=%p joints=%d\\n",
               static_cast<void *>(mBody),dBodyGetNumJoints(mBody));
  dBodyDestroy(mBody);
  std::fprintf(stderr,"H6_D1_REAL_BODY_DESTROY_AFTER_ODE\\n");
  mBody = NULL;'''
m=once(m,a,b,"real dBodyDestroy order")
if "#include <cstdio>" not in m:m=m.replace('#include "WbSolidMerger.hpp"','#include "WbSolidMerger.hpp"\n#include <cstdio>')
cpath.write_text(c);mpath.write_text(m)
print("H6_D1_REAL_WEBOTS_INSTRUMENTED")

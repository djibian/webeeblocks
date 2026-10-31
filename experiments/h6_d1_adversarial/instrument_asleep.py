#!/usr/bin/env python3
"""Test-only adversarial A-asleep intervention at real B destruction boundary.

The Webots candidate owner selection, registries and cleanup are unchanged.
The optional intervention only calls the documented dBodyDisable on the
real foreign attached body just before the real WbSolidMerger destructor
runs the unchanged candidate code; unmodified control also runs.
"""
from pathlib import Path
import subprocess,sys
if len(sys.argv)!=2: raise SystemExit("usage: instrument_asleep.py NATIVE_WEBOTS")
root=Path(sys.argv[1])
subprocess.run([sys.executable,str(Path(__file__).with_name("instrument_d1.py")),str(root)],check=True)
p=root/"src/webots/nodes/utils/WbSolidMerger.cpp"
s=p.read_text()
a='''  WbOdeContext::instance()->removeBodyContactJointGroup(mBody);
  std::fprintf(stderr,"H6_D1_REAL_BODY_DESTROY_BEFORE_ODE'''
b='''  // ADVERSARIAL TEST ONLY: force real attached other body asleep at the
  // moment of teardown. The no-intervention arm is also retained.
  if (std::getenv("H6_D1_FIXTURE_SLEEP_AT_TEARDOWN") &&
      !std::strcmp(std::getenv("H6_D1_FIXTURE_SLEEP_AT_TEARDOWN"),"1")) {
    for (int h6i=0; h6i<dBodyGetNumJoints(mBody); ++h6i) {
      dJointID h6j=dBodyGetJoint(mBody,h6i);
      if (dJointGetType(h6j)!=dJointTypeContact) continue;
      dBodyID h6b0=dJointGetBody(h6j,0),h6b1=dJointGetBody(h6j,1);
      dBodyID h6other=(h6b0==mBody ? h6b1 : h6b0);
      if (h6other) {
        const int h6before=dBodyIsEnabled(h6other);
        dBodyDisable(h6other);
        std::fprintf(stderr,
          "H6_D1_FIXTURE_DISABLE victim=%p other=%p before=%d after=%d joint=%p\\n",
          static_cast<void*>(mBody),static_cast<void*>(h6other),
          h6before,int(dBodyIsEnabled(h6other)),static_cast<void*>(h6j));
        break;
      }
    }
  }
  WbOdeContext::instance()->removeBodyContactJointGroup(mBody);
  std::fprintf(stderr,"H6_D1_REAL_BODY_DESTROY_BEFORE_ODE'''
assert s.count(a)==1,("destructor insertion anchor",s.count(a))
s=s.replace(a,b)
s=s.replace('#include <cstdio>','#include <cstdio>\n#include <cstdlib>\n#include <cstring>')
p.write_text(s)
print("H6_D1_TEST_ONLY_ASLEEP_TEARDOWN_INTERVENTION",p)

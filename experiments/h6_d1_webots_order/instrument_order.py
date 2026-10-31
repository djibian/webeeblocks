#!/usr/bin/env python3
"""Observational creation/retirement tracing layered on historical candidate.
Never change contact owner computation, ODE ordering, registration, or deletion.
The existing test-only asleep intervention remains explicit and opt-in.
"""
from pathlib import Path
import sys, subprocess
if len(sys.argv)!=2:
    raise SystemExit("usage: instrument_order.py NATIVE_WEBOTS")
root=Path(sys.argv[1])
subprocess.run([sys.executable,
  str(Path(__file__).resolve().parents[1]/"h6_d1_adversarial"/"instrument_asleep.py"),
  str(root)],check=True)
p=root/"src/webots/engine/WbSimulationCluster.cpp"
s=p.read_text()
anchor="    cl->mContext->registerBodyContactJoint(owner, contactJoint, cl->mSwapJointContactBuffer);"
assert s.count(anchor)==1,("creation anchor",s.count(anchor))
s=s.replace(anchor,anchor+'''
    // Test-only observation. Logs allocation and attachment before any can be freed.
    if (std::getenv("H6_D1_ORDER_AUDIT"))
      std::fprintf(stderr,
        "H6_D1_CREATE t=%.6f o1=%p o2=%p b1=%p b2=%p owner=%p joint=%p buffer=%d\\\\n",
        WbSimulationState::instance()->time(), static_cast<void *>(o1),
        static_cast<void *>(o2), static_cast<void *>(b1), static_cast<void *>(b2),
        static_cast<void *>(owner), static_cast<void *>(contactJoint),
        int(cl->mSwapJointContactBuffer));''')
s=s.replace("#include <cassert>","#include <cassert>\n#include <cstdio>\n#include <cstdlib>",1)
p.write_text(s)
p=root/"src/webots/ode/WbOdeContext.cpp"
s=p.read_text()
start=s.index("void WbOdeContext::removeBodyContactJointGroup(dBodyID b) {")
end=s.index("\n}",start)+2
segment=s[start:end]
anchor="  mJointGroupCreationMutex->unlock();"
assert segment.count(anchor)==1
segment=segment.replace(anchor,'''
  if (std::getenv("H6_D1_ORDER_AUDIT"))
    std::fprintf(stderr, "H6_D1_REGISTRY_AFTER victim=%p count1=%d count2=%d\\\\n",
                 static_cast<void *>(b), mBodyContacts1.size(), mBodyContacts2.size());
'''+anchor)
s=s[:start]+segment+s[end:]
p.write_text(s)
print("H6_D1_OBSERVATION_ONLY_OWNER_REGISTRY_INTACT")

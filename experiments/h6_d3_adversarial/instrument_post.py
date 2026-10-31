#!/usr/bin/env python3
"""Read-only post-loadState first-solver witness layered on historical D3 fixture."""
from pathlib import Path
import subprocess, sys
if len(sys.argv) != 2: raise SystemExit("usage: instrument_post.py WEBOTS_ROOT")
root=Path(sys.argv[1])
subprocess.run([sys.executable,str(Path(__file__).with_name("instrument.py")),str(root)],check=True)
solid=root/"src/webots/nodes/WbSolid.cpp"
cluster=root/"src/webots/engine/WbSimulationCluster.cpp"
s=solid.read_text()
cl=cluster.read_text()
def replace_once(src,a,b,label):
    assert src.count(a)==1,(label,src.count(a))
    return src.replace(a,b)
s=replace_once(s,'#include "WbSolid.hpp"', '#include "WbSolid.hpp"\n#include <atomic>\n// Test-only pending body: consumed by the first subsequent native physics step.\nstd::atomic<dBodyID> h6D3PostResetBody(nullptr);', "atomic instrumentation")
s=replace_once(s,'''    WbOdeContext::instance()->detachResetBodyContacts(body());
    std::fprintf(stderr, "H6_D3_ACTUAL_RESET_ID_END''',
'''    WbOdeContext::instance()->detachResetBodyContacts(body());
    h6D3PostResetBody.store(body(), std::memory_order_release);
    std::fprintf(stderr, "H6_D3_ACTUAL_RESET_ID_END''', "schedule native first-solver witness")
cl=replace_once(cl,'''void WbSimulationCluster::step() {''',
'''// Read-only adversarial observation, never changes ODE contacts or solver.
#include <atomic>
#include <cstdio>
extern std::atomic<dBodyID> h6D3PostResetBody;
static void h6D3CountJoints(dBodyID body,int &contacts,int &permanent) {
  contacts=0; permanent=0;
  if (!body) return;
  for (int i=0;i<dBodyGetNumJoints(body);++i) {
    dJointID j=dBodyGetJoint(body,i);
    if (dJointGetType(j)==dJointTypeContact) ++contacts;
    else ++permanent;
  }
}
void WbSimulationCluster::step() {
  dBodyID h6PostBody=h6D3PostResetBody.exchange(nullptr,std::memory_order_acq_rel);
  if (h6PostBody) {
    int contacts=0,permanent=0;
    h6D3CountJoints(h6PostBody,contacts,permanent);
    std::fprintf(stderr,"H6_D3_FIRST_SOLVER_BEFORE body=%p contacts=%d permanent=%d\\n",
                 static_cast<void *>(h6PostBody),contacts,permanent);
  }''',"native first physics witness");
cl=replace_once(cl,'''                            WbWorld::instance()->basicTimeStep() * 0.001, &dWorldStep, spaceUpdateFunc);

  // every step''',
'''                            WbWorld::instance()->basicTimeStep() * 0.001, &dWorldStep, spaceUpdateFunc);
  if (h6PostBody) {
    int contacts=0,permanent=0;
    h6D3CountJoints(h6PostBody,contacts,permanent);
    std::fprintf(stderr,"H6_D3_FIRST_SOLVER_AFTER body=%p contacts=%d permanent=%d\\n",
                 static_cast<void *>(h6PostBody),contacts,permanent);
  }

  // every step''',"solver completion witness");
cl=replace_once(cl,'''  WbSolidDevice::clearDirtySensorsList();''',
'''  if (h6PostBody)
    std::fprintf(stderr,"H6_D3_FIRST_SOLVER_RETIRED body=%p\\n",static_cast<void *>(h6PostBody));
  WbSolidDevice::clearDirtySensorsList();''',"retired buffer after solver")
solid.write_text(s);cluster.write_text(cl)
print("H6_D3_NATIVE_POST_LOAD_SOLVER_OBSERVER",root)

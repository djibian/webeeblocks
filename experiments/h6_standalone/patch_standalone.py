#!/usr/bin/env python3
"""H6 independent-contact lifetime experimental patch. Webots source PIN mandatory.

Key mechanism: native Webots contact joints are UNGROUPED ODE allocations, so
dJointDestroy physically releases each RESET-invalidated contact; live disabled
owner contacts retain EXACT historical cleanup gate, including first wake solver.
No change to solver, physics plugin contact groups, or Supervisor API.
H6_STANDALONE_R=0/1 is a factorial test switch only.
"""
from pathlib import Path
import subprocess,sys,hashlib
PIN="c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b"
if len(sys.argv)!=2: raise SystemExit("usage: patch_standalone.py WEBOTS_ROOT")
root=Path(sys.argv[1])
if subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()!=PIN:
    raise SystemExit("REFUSED wrong Webots source PIN")
if subprocess.check_output(["git","-C",str(root),"status","--porcelain"],text=True).strip():
    raise SystemExit("REFUSED dirty source before patch")
paths={
 "ctx_h":root/"src/webots/ode/WbOdeContext.hpp",
 "ctx_c":root/"src/webots/ode/WbOdeContext.cpp",
 "cluster_h":root/"src/webots/engine/WbSimulationCluster.hpp",
 "cluster_c":root/"src/webots/engine/WbSimulationCluster.cpp",
 "solid":root/"src/webots/nodes/WbSolid.cpp",
}
d={k:v.read_text() for k,v in paths.items()}
def once(key,a,b,label):
 if d[key].count(a)!=1: raise SystemExit(f"REFUSED {label} count={d[key].count(a)}")
 d[key]=d[key].replace(a,b)

# ODE group-owned joints cannot be destroyed individually. Two existing per-buffer
# owner maps are retained in spirit; key by joint ID to enable exact R erasure.
once("ctx_h",'  dJointGroupID bodyContactJointGroup1(dBodyID b);\n  dJointGroupID bodyContactJointGroup2(dBodyID b);\n  void removeBodyContactJointGroup(dBodyID b);',
'''  void registerBodyContactJoint(dBodyID owner, dJointID joint, bool buffer1);
  void detachResetBodyContacts(dBodyID body);
  void removeBodyContactJointGroup(dBodyID b);''',"public contact API")
once("ctx_h","  QHash<dBodyID, dJointGroupID> mBodyContactJointGroupList1, mBodyContactJointGroupList2;",
'''  // Physical contacts are individually owned; only LIVE disabled-owner joints
  // survive the original retirement gate. RESET joints are freed immediately.
  QHash<dJointID, dBodyID> mBodyContacts1, mBodyContacts2;''',"map storage")
once("ctx_c","#include <cassert>","#include <cassert>\n#include <cstdlib>\n#include <cstring>\n#include <cstdio>","includes")
once("ctx_c",'''  mBodyContactJointGroupList1.clear();
  mBodyContactJointGroupList2.clear();''','''  mBodyContacts1.clear();
  mBodyContacts2.clear();''',"constructor")
begin=d["ctx_c"].index("  QList<dJointGroupID> groups(mBodyContactJointGroupList1.values());")
end=d["ctx_c"].index("  dJointGroupDestroy(mPhysicsPluginContactJointGroup1);",begin)
d["ctx_c"]=d["ctx_c"][:begin]+'''  // All remaining contacts are standalone and must be destroyed explicitly.
  for (dJointID joint : mBodyContacts1.keys())
    dJointDestroy(joint);
  for (dJointID joint : mBodyContacts2.keys())
    dJointDestroy(joint);
  mBodyContacts1.clear();
  mBodyContacts2.clear();

'''+d["ctx_c"][end:]
begin=d["ctx_c"].index("void WbOdeContext::emptyEnabledBodyContactJointGroups1() {")
end=d["ctx_c"].index("void WbOdeContext::removeBodyContactJointGroup(dBodyID b) {",begin)
d["ctx_c"]=d["ctx_c"][:begin]+'''// Called ONLY after the solver/collision workers have returned and the buffers
// have been swapped. The original enabled(owner) gate is intentionally retained:
// unconditional removal here changes first-solver wakeup dynamics (G counterexample).
static void h6RetireContacts(QHash<dJointID, dBodyID> &contacts) {
  QMutableHashIterator<dJointID, dBodyID> it(contacts);
  while (it.hasNext()) {
    it.next();
    if (dBodyIsEnabled(it.value())) {
      dJointDestroy(it.key());
      it.remove();
    }
  }
}
void WbOdeContext::emptyEnabledBodyContactJointGroups1() {
  h6RetireContacts(mBodyContacts1);
}
void WbOdeContext::emptyEnabledBodyContactJointGroups2() {
  h6RetireContacts(mBodyContacts2);
}
void WbOdeContext::registerBodyContactJoint(dBodyID owner, dJointID joint, bool buffer1) {
  assert(owner && joint);
  if (buffer1)
    mBodyContacts1.insert(joint, owner);
  else
    mBodyContacts2.insert(joint, owner);
}
void WbOdeContext::detachResetBodyContacts(dBodyID body) {
  if (!body)
    return;
  // Contact generation and retirement use the same mutex. This does NOT assert
  // a global Webots event-loop/ODE worker barrier; it must be validated separately.
  mJointGroupCreationMutex->lock();
  int removed = 0;
  for (int i = dBodyGetNumJoints(body) - 1; i >= 0; --i) {
    dJointID joint = dBodyGetJoint(body, i);
    if (dJointGetType(joint) != dJointTypeContact)
      continue;
    const bool own = mBodyContacts1.remove(joint) || mBodyContacts2.remove(joint);
    if (!own)
      dJointAttach(joint, nullptr, nullptr); // foreign/plugin group-owned joint
    dJointDestroy(joint); // exact selective destruction if individually owned
    ++removed;
  }
  mJointGroupCreationMutex->unlock();
  if (std::getenv("H6_STANDALONE_TRACE")) {
    std::fprintf(stderr, "H6_STANDALONE_R detached=%d\\n", removed);
    std::fflush(stderr);
  }
}

'''+d["ctx_c"][end:]
begin=d["ctx_c"].index("void WbOdeContext::removeBodyContactJointGroup(dBodyID b) {")
d["ctx_c"]=d["ctx_c"][:begin]+'''void WbOdeContext::removeBodyContactJointGroup(dBodyID b) {
  mJointGroupCreationMutex->lock();
  for (QHash<dJointID, dBodyID> *map : {&mBodyContacts1, &mBodyContacts2}) {
    QMutableHashIterator<dJointID, dBodyID> it(*map);
    while (it.hasNext()) {
      it.next();
      if (it.value() == b) {
        dJointDestroy(it.key());
        it.remove();
      }
    }
  }
  mJointGroupCreationMutex->unlock();
}
'''
# Only Webots-owned joint creation is changed; plugin joints remain group-owned.
once("cluster_c",'''    dJointGroupID group = 0;
    if (b1 == NULL || (s1->isKinematic() && !s2->isKinematic()))
      group = cl->bodyContactJointGroup(b2);
    else
      group = cl->bodyContactJointGroup(b1);
    dJointID contactJoint = dJointCreateContact(jointWorld, group, &contact[i]);
    dJointAttach(contactJoint, b1, b2);''','''    dBodyID owner = (b1 == NULL || (s1->isKinematic() && !s2->isKinematic())) ? b2 : b1;
    dJointID contactJoint = dJointCreateContact(jointWorld, NULL, &contact[i]);
    dJointAttach(contactJoint, b1, b2);
    cl->mContext->registerBodyContactJoint(owner, contactJoint, cl->mSwapJointContactBuffer);''',"contact allocation and owner tracking")
once("cluster_c",'''dJointGroupID WbSimulationCluster::bodyContactJointGroup(dBodyID b) {
  return mSwapJointContactBuffer ? mContext->bodyContactJointGroup1(b) : mContext->bodyContactJointGroup2(b);
}

''',"","remove obsolete group API")
once("cluster_h","  dJointGroupID bodyContactJointGroup(dBodyID b);\n","","remove obsolete cluster header")
once("cluster_c",'''  if (mSwapJointContactBuffer)
    mContext->emptyEnabledBodyContactJointGroups1();
  else
    mContext->emptyEnabledBodyContactJointGroups2();''','''  cJointCreationMutex->lock();
  if (mSwapJointContactBuffer)
    mContext->emptyEnabledBodyContactJointGroups1();
  else
    mContext->emptyEnabledBodyContactJointGroups2();
  cJointCreationMutex->unlock();''',"retirement mutex")
once("solid", "#include <QtCore/QQueue>","#include <cstdlib>\n#include <cstring>\n#include <QtCore/QQueue>","solid includes")
once("solid","void WbSolid::resetSingleSolidPhysics() {\n  // check for joints",
'''void WbSolid::resetSingleSolidPhysics() {
  if (isSolidMerger() && std::getenv("H6_STANDALONE_R") &&
      !std::strcmp(std::getenv("H6_STANDALONE_R"), "1"))
    WbOdeContext::instance()->detachResetBodyContacts(body());
  // check for joints''',"R boundary")
# Fail closed: this is NOT a generic ODE patch; all old Webots-owned group entries gone.
for name,p in paths.items():
 p.write_text(d[name])
 print("H6_STANDALONE_FILE",name,p.relative_to(root),hashlib.sha256(p.read_bytes()).hexdigest())
assert d["cluster_c"].count("dJointCreateContact(jointWorld, NULL") == 1
assert d["ctx_c"].count("dJointDestroy(joint);") >= 3
print("H6_STANDALONE_PATCH_COMPLETE",PIN)

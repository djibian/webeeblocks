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
# This script is applied ONLY after the pinned #777 observer patch in the same checkout.
# It deliberately accepts precisely that instrumented tree, never an arbitrary dirty tree.
observer = (root/"src/webots/engine/WbSimulationCluster.cpp").read_text()
if observer.count('h6_p0_trace("solver_return", 0)') != 1 or observer.count('h6_p0_trace("M_acquired", 0)') != 1:
    raise SystemExit("REFUSED: missing exact scheduler observer anchors")

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
# Both the constructor and the destructor clear the same two maps.
# Replace exactly these two sites before replacing the destructor wholesale.
old_clear='''  mBodyContactJointGroupList1.clear();
  mBodyContactJointGroupList2.clear();'''
new_clear='''  mBodyContacts1.clear();
  mBodyContacts2.clear();'''
if d["ctx_c"].count(old_clear)!=2: raise SystemExit("REFUSED bad ctor/dtor clear anchors")
d["ctx_c"]=d["ctx_c"].replace(old_clear,new_clear)
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
print("H6_STANDALONE_BASE_APPLIED_FROM_766",PIN)


# H6 P0 experimental overlay, source-pinned. Requires #777 observer and #766 standalone above.
# Research only: changes ODE exported entry points; not an ABI- or production-safe proposal.
ode = root / "src/ode/ode/src/ode.cpp"
def p0edit(path, old, new, label):
    s = path.read_text()
    count = s.count(old)
    if count != 1:
        raise SystemExit("REFUSED P0 anchor " + label + " count=" + str(count))
    path.write_text(s.replace(old, new))

p0_declarations = r'''
// EXPERIMENT ONLY. Callback receives opaque pointer BEFORE any joint dereference.
// A plugin's thread identity or possession of a lock never confers engine authority.
static int (*h6_p0_admission)(dxJoint *, void *) = nullptr;
static void *h6_p0_admission_context = nullptr;
extern "C" __attribute__((visibility("default"))) void h6_p0_set_admission(
    int (*fn)(dxJoint *, void *), void *ctx) {
  h6_p0_admission_context = ctx;
  h6_p0_admission = fn;
}
extern "C" __attribute__((visibility("default"))) void h6_p0_destroy_owned(dxJoint *j) {
  // Explicit engine-only route: it bypasses the public admission. Caller holds M
  // and has already erased the live handle from BOTH engine registries under M.
  h6_p0_trace("P0_internal_free", (unsigned long long)(uintptr_t)j);
  dAASSERT(j);
  dIASSERT(!(j->flags & dJOINT_INGROUP));
  FinalizeAndDestroyJointInstance(j, true);
}
'''
p0edit(ode,
'''void dJointDestroy (dxJoint *j)
{
    h6_p0_trace("public_destroy_enter", (unsigned long long)(uintptr_t)j);
    dAASSERT (j);
    if (!(j->flags & dJOINT_INGROUP)) {''',
p0_declarations+'''void dJointDestroy (dxJoint *j)
{
    h6_p0_trace("P0_public_enter", (unsigned long long)(uintptr_t)j);
    // Admission is BEFORE j->flags or any other dereference. H0: caller presents
    // a currently live, synchronized joint. Stale identifiers are NOT protected.
    if (h6_p0_admission && !h6_p0_admission(j, h6_p0_admission_context)) {
      h6_p0_trace("P0_public_denied", (unsigned long long)(uintptr_t)j);
      return;
    }
    h6_p0_trace("P0_public_allowed", (unsigned long long)(uintptr_t)j);
    dAASSERT (j);
    if (!(j->flags & dJOINT_INGROUP)) {''', "ode public pre-dereference gate")

p0edit(paths["ctx_h"],
'  void registerBodyContactJoint(dBodyID owner, dJointID joint, bool buffer1);',
'''  static int h6P0Admission(dJointID joint, void *context);
  void registerBodyContactJoint(dBodyID owner, dJointID joint, bool buffer1);''', "static admission callback declaration")

p0edit(paths["ctx_c"],
'WbOdeContext *WbOdeContext::cOdeContext = NULL;',
'''extern "C" void h6_p0_set_admission(int (*)(dJointID, void *), void *);
extern "C" void h6_p0_destroy_owned(dJointID);
WbOdeContext *WbOdeContext::cOdeContext = NULL;

int WbOdeContext::h6P0Admission(dJointID joint, void *user) {
  WbOdeContext *const context = static_cast<WbOdeContext *>(user);
  // No ODE joint dereference. The admission owns exactly ONE acquisition of M.
  if (!context->mJointGroupCreationMutex->tryLock()) {
    h6_p0_trace("P0_M_contended", (unsigned long long)(uintptr_t)joint);
    context->mJointGroupCreationMutex->lock();
  }
  h6_p0_trace("P0_M_acquired", (unsigned long long)(uintptr_t)joint);
  const bool owned = context->mBodyContacts1.contains(joint) ||
                     context->mBodyContacts2.contains(joint);
  h6_p0_trace(owned ? "P0_class_engine" : "P0_class_plugin",
              (unsigned long long)(uintptr_t)joint);
  context->mJointGroupCreationMutex->unlock();
  h6_p0_trace("P0_M_released", (unsigned long long)(uintptr_t)joint);
  return owned ? 0 : 1;
}''', "context callback implementation")

p0edit(paths["ctx_c"],
'  mBodyContacts2.clear();\n  mNumberOfThreads = -1;',
'''  mBodyContacts2.clear();
  h6_p0_set_admission(&WbOdeContext::h6P0Admission, this);
  h6_p0_trace("P0_admission_installed", 0);
  mNumberOfThreads = -1;''', "install admission only after maps and M")

p0edit(paths["ctx_c"],
'''  for (dJointID joint : mBodyContacts1.keys())
    dJointDestroy(joint);
  for (dJointID joint : mBodyContacts2.keys())
    dJointDestroy(joint);
  mBodyContacts1.clear();
  mBodyContacts2.clear();''',
'''  // Engine-owned free after normal plugin cleanup and cluster destruction.
  // No callback into the public admission while holding non-recursive M.
  mJointGroupCreationMutex->lock();
  h6_p0_trace("P0_teardown_M_acquired", 0);
  while (!mBodyContacts1.isEmpty()) {
    dJointID joint = mBodyContacts1.begin().key();
    mBodyContacts1.remove(joint);
    h6_p0_trace("P0_unregister", (unsigned long long)(uintptr_t)joint);
    h6_p0_destroy_owned(joint);
  }
  while (!mBodyContacts2.isEmpty()) {
    dJointID joint = mBodyContacts2.begin().key();
    mBodyContacts2.remove(joint);
    h6_p0_trace("P0_unregister", (unsigned long long)(uintptr_t)joint);
    h6_p0_destroy_owned(joint);
  }
  h6_p0_trace("P0_registries_empty", 0);
  mJointGroupCreationMutex->unlock();
  h6_p0_trace("P0_teardown_M_released", 0);
  h6_p0_set_admission(nullptr, nullptr);
  h6_p0_trace("P0_admission_removed", 0);''',
"teardown unregister before free and disable callback")

p0edit(paths["ctx_c"],
'''    if (dBodyIsEnabled(it.value())) {
      dJointDestroy(it.key());
      it.remove();
    }''',
'''    if (dBodyIsEnabled(it.value())) {
      dJointID joint = it.key();
      it.remove();
      h6_p0_trace("P0_unregister", (unsigned long long)(uintptr_t)joint);
      h6_p0_destroy_owned(joint);
    }''', "post-solver buffer retirement")

p0edit(paths["ctx_c"],
'''  assert(owner && joint);
  if (buffer1)''',
'''  assert(owner && joint);
  assert(!mBodyContacts1.contains(joint) && !mBodyContacts2.contains(joint));
  h6_p0_trace("P0_register", (unsigned long long)(uintptr_t)joint);
  if (buffer1)''', "register only new incarnation")

p0edit(paths["ctx_c"],
'''    const bool own = mBodyContacts1.remove(joint) || mBodyContacts2.remove(joint);
    if (!own)
      dJointAttach(joint, nullptr, nullptr); // foreign/plugin group-owned joint
    dJointDestroy(joint); // exact selective destruction if individually owned
    ++removed;''',
'''    const bool own = mBodyContacts1.remove(joint) || mBodyContacts2.remove(joint);
    if (own) {
      h6_p0_trace("P0_unregister", (unsigned long long)(uintptr_t)joint);
      h6_p0_destroy_owned(joint);
      ++removed;
    }
    // Foreign/plugin contacts MUST NOT be freed or detached by P0.''',
"RESET must not alter plugin owned contact")

p0edit(paths["ctx_c"],
'''      if (it.value() == b) {
        dJointDestroy(it.key());
        it.remove();
      }''',
'''      if (it.value() == b) {
        dJointID joint = it.key();
        it.remove();
        h6_p0_trace("P0_unregister", (unsigned long long)(uintptr_t)joint);
        h6_p0_destroy_owned(joint);
      }''', "body removal unregister before free")

# Limited adversarial timing fixture under M, not an alleged no-race proof.
p0edit(paths["cluster_c"],
'#include <limits>',
'#include <limits>\n#include <atomic>\n#include <cstdlib>\n#include <unistd.h>', "fixture includes")
p0edit(paths["cluster_c"],
'''    h6_p0_trace("M_acquired", 0);
    dJointGroupID group = 0;''',
'''    h6_p0_trace("M_acquired", 0);
    static std::atomic<int> h6_p0_hold_count{0};
    if (std::getenv("H6_P0_HOLD_M") && h6_p0_hold_count.fetch_add(1) < 32) {
      h6_p0_trace("P0_fixture_M_hold", 0);
      usleep(4000);
    }
    dJointGroupID group = 0;''', "controlled M hold while two real workers collide")

assert 'dJointCreateContact(jointWorld, NULL' in paths["cluster_c"].read_text()
print("H6_P0_OVERLAY_COMPLETE",PIN)

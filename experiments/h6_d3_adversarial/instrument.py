#!/usr/bin/env python3
"""Test-only instrumentation for the EXACT pinned PR766 C++ correction.
Do not change the candidate semantics; fail closed on missing anchors.
"""
from pathlib import Path
import sys,subprocess
if len(sys.argv)!=2: raise SystemExit("usage: instrument.py NATIVE_WEBOTS")
root=Path(sys.argv[1])
subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/"h6_standalone"/"patch_corrected.py"),str(root)],check=True)
solid=root/"src/webots/nodes/WbSolid.cpp"
ctx=root/"src/webots/ode/WbOdeContext.cpp"
s=solid.read_text()
c=ctx.read_text()
def one(src,before,after,why):
 if src.count(before)!=1: raise SystemExit(f"REFUSED {why} count {src.count(before)}")
 return src.replace(before,after)
# Log direct WbSolid::reset(const QString&) *actual* call, not any other reset.
a='''  // The historical reset(id) invalidates contacts even in the A test arm.
  // Centralized removal unregisters standalone joints before dJointDestroy.
  if (isSolidMerger())
    WbOdeContext::instance()->detachResetBodyContacts(body());'''
b='''  // The historical reset(id) invalidates contacts even in the A test arm.
  // Centralized removal unregisters standalone joints before dJointDestroy.
  if (isSolidMerger()) {
    std::fprintf(stderr, "H6_D3_ACTUAL_RESET_ID_BEGIN solid=%p body=%p contacts=%d\\n",
                 static_cast<void *>(this), static_cast<void *>(body()), dBodyGetNumJoints(body()));
    WbOdeContext::instance()->detachResetBodyContacts(body());
    std::fprintf(stderr, "H6_D3_ACTUAL_RESET_ID_END solid=%p body=%p contacts=%d\\n",
                 static_cast<void *>(this), static_cast<void *>(body()), dBodyGetNumJoints(body()));
  }'''
s=one(s,a,b,"real WbSolid reset(id) path")
# The entry and exit probes observe registry/attachment counts at the only owning R function.
a='''  mJointGroupCreationMutex->lock();
  int removed = 0;
  for (int i = dBodyGetNumJoints(body) - 1; i >= 0; --i) {'''
b='''  mJointGroupCreationMutex->lock();
  const int before1 = mBodyContacts1.size();
  const int before2 = mBodyContacts2.size();
  const int beforeAttached = dBodyGetNumJoints(body);
  int removed = 0;
  int ownedRemoved = 0;
  for (int i = dBodyGetNumJoints(body) - 1; i >= 0; --i) {'''
c=one(c,a,b,"R registry entry")
a='''    if (!own1 && !own2)
      dJointAttach(joint, nullptr, nullptr); // plugin group-owned joint
    dJointDestroy(joint); // individually free tracked joints
    ++removed;'''
b='''    if (!own1 && !own2)
      dJointAttach(joint, nullptr, nullptr); // plugin group-owned joint
    if (own1 || own2)
      ++ownedRemoved;
    std::fprintf(stderr, "H6_D3_RESET_JOINT joint=%p owned=%d in1=%d in2=%d\\n",
                 static_cast<void *>(joint), int(own1||own2), int(own1), int(own2));
    dJointDestroy(joint); // individually free tracked joints
    ++removed;'''
c=one(c,a,b,"R per joint")
a='''  mJointGroupCreationMutex->unlock();
  if (std::getenv("H6_STANDALONE_TRACE")) {'''
b='''  int remainingAttachedContacts = 0;
  for (int i = 0; i < dBodyGetNumJoints(body); ++i) {
    if (dJointGetType(dBodyGetJoint(body, i)) == dJointTypeContact)
      ++remainingAttachedContacts;
  }
  std::fprintf(stderr,
               "H6_D3_REGISTRY_CHECK body=%p before1=%d before2=%d after1=%d after2=%d"
               " beforeAttached=%d ownedRemoved=%d remainingContacts=%d\\n",
               static_cast<void *>(body), before1, before2, mBodyContacts1.size(), mBodyContacts2.size(),
               beforeAttached, ownedRemoved, remainingAttachedContacts);
  mJointGroupCreationMutex->unlock();
  if (std::getenv("H6_STANDALONE_TRACE")) {'''
c=one(c,a,b,"R registry exit")
# Preserve ordinary retirement logic, emit before/after count after actual buffer sweep.
a='''void WbOdeContext::emptyEnabledBodyContactJointGroups1() {
  h6RetireContacts(mBodyContacts1);
}
void WbOdeContext::emptyEnabledBodyContactJointGroups2() {
  h6RetireContacts(mBodyContacts2);
}'''
b='''void WbOdeContext::emptyEnabledBodyContactJointGroups1() {
  const int before = mBodyContacts1.size();
  h6RetireContacts(mBodyContacts1);
  std::fprintf(stderr,"H6_D3_RETIRE buffer=1 before=%d after=%d\\n",before,mBodyContacts1.size());
}
void WbOdeContext::emptyEnabledBodyContactJointGroups2() {
  const int before = mBodyContacts2.size();
  h6RetireContacts(mBodyContacts2);
  std::fprintf(stderr,"H6_D3_RETIRE buffer=2 before=%d after=%d\\n",before,mBodyContacts2.size());
}'''
c=one(c,a,b,"retirement")
a='''  // All remaining contacts are standalone and must be destroyed explicitly.
  for (dJointID joint : mBodyContacts1.keys())'''
b='''  // All remaining contacts are standalone and must be destroyed explicitly.
  std::fprintf(stderr, "H6_D3_FINAL_CONTEXT_BEGIN count1=%d count2=%d\\n",
               mBodyContacts1.size(), mBodyContacts2.size());
  for (dJointID joint : mBodyContacts1.keys())'''
c=one(c,a,b,"context final entry")
a='''  mBodyContacts1.clear();
  mBodyContacts2.clear();

  dJointGroupDestroy(mPhysicsPluginContactJointGroup1);'''
b='''  mBodyContacts1.clear();
  mBodyContacts2.clear();
  std::fprintf(stderr, "H6_D3_FINAL_CONTEXT_END count1=%d count2=%d\\n",
               mBodyContacts1.size(), mBodyContacts2.size());

  dJointGroupDestroy(mPhysicsPluginContactJointGroup1);'''
c=one(c,a,b,"context final exit")
solid.write_text(s)
ctx.write_text(c)
print("H6_D3_TEST_INSTRUMENTED_TRUE_RESET_ID")

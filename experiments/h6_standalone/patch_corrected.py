#!/usr/bin/env python3
"""Apply *only* H6 D1/D2/D3 repairs on top of the exact PR765 source-pinned C++ patch.

Experimental controls of PR765 remain experimental, not Cyberbotics-ready.
Preserves original Webots/ODE source PIN and the owner-enabled wakeup policy.
"""
from pathlib import Path
import subprocess, sys, hashlib
if len(sys.argv) != 2:
    raise SystemExit("usage: patch_corrected.py NATIVE_WEBOTS_ROOT")
root = Path(sys.argv[1])
subprocess.run([sys.executable,
    str(Path(__file__).with_name("patch_standalone.py")), str(root)], check=True)
ctx = root / "src/webots/ode/WbOdeContext.cpp"
solid = root / "src/webots/nodes/WbSolid.cpp"
c, s = ctx.read_text(), solid.read_text()
def once(string, before, after, label):
    if string.count(before) != 1:
        raise SystemExit(f"REFUSED {label}: expected one anchor, got {string.count(before)}")
    return string.replace(before, after)

# D1: before WbSolidMerger::~WbSolidMerger dBodyDestroy, still have attachment
# identities. Both buffer registries own their joints, regardless of owner A.
c = once(c, '''      if (it.value() == b) {
        dJointDestroy(it.key());
        it.remove();
      }''', '''      dJointID joint = it.key();
      // A sleeping owner may hold an A-B contact while B is being destroyed.
      // ODE's dBodyDestroy would detach, *not* release this standalone joint.
      // An already fully detached tracked contact is also permanently obsolete.
      if (it.value() == b || dJointGetBody(joint, 0) == b ||
          dJointGetBody(joint, 1) == b ||
          (!dJointGetBody(joint, 0) && !dJointGetBody(joint, 1))) {
        it.remove();  // unregister before freeing: no stale pointer after free
        dJointDestroy(joint);
      }''', "D1 foreign-body teardown")
# Safety net for detached tracked contacts that might have been detached by
# a mechanism other than WbSolidMerger; never deref any destroyed joint.
c = once(c, '''    if (dBodyIsEnabled(it.value())) {
      dJointDestroy(it.key());
      it.remove();
    }''', '''    dJointID joint = it.key();
    if ((!dJointGetBody(joint, 0) && !dJointGetBody(joint, 1)) ||
        dBodyIsEnabled(it.value())) {
      it.remove();
      dJointDestroy(joint);
    }''', "D1 orphan retirement")
# D3: non-owning plugin-group joints may still exist on RESET. The one and
# only destructive path for owned standalone contacts removes its registry key
# first. Remove from both buffers without short-circuit; assert unique owner.
c = once(c, '''    const bool own = mBodyContacts1.remove(joint) || mBodyContacts2.remove(joint);
    if (!own)
      dJointAttach(joint, nullptr, nullptr); // foreign/plugin group-owned joint
    dJointDestroy(joint); // exact selective destruction if individually owned''',
'''    const bool own1 = mBodyContacts1.remove(joint) != 0;
    const bool own2 = mBodyContacts2.remove(joint) != 0;
    assert(!(own1 && own2));  // a tracked joint belongs to exactly one buffer
    if (!own1 && !own2)
      dJointAttach(joint, nullptr, nullptr); // plugin group-owned joint
    dJointDestroy(joint); // individually free tracked joints''', "D3 central ownership")
# D2: NEVER invalidate from shared resetSingleSolidPhysics (called by GUI
# resumePhysics without RESET). Keep exact existing reset velocity semantics.
s = once(s, '''void WbSolid::resetSingleSolidPhysics() {
  if (isSolidMerger() && std::getenv("H6_STANDALONE_R") &&
      !std::strcmp(std::getenv("H6_STANDALONE_R"), "1"))
    WbOdeContext::instance()->detachResetBodyContacts(body());
  // check for joints''',
'''void WbSolid::resetSingleSolidPhysics() {
  // The shared helper is used by GUI resumePhysics: do not invalidate here.
  // check for joints''', "D2 shared-helper removal")
# True physical reset. Called by global and per-node Supervisor reset; user
# transform edits also use this path, and invalidate former spatial contacts.
s = once(s, '''void WbSolid::resetPhysics(bool recursive) {
  resetSingleSolidPhysics();''', '''void WbSolid::resetPhysics(bool recursive) {
  if (isSolidMerger() && std::getenv("H6_STANDALONE_R") &&
      !std::strcmp(std::getenv("H6_STANDALONE_R"), "1"))
    WbOdeContext::instance()->detachResetBodyContacts(body());
  resetSingleSolidPhysics();''', "D2 real resetPhysics boundary")
# D3: old WbSolid::reset(id) destroys contacts directly without notifying the
# new registries. Route through the same exact-attachment deletion helper.
# In A arm historically this path still removes contact joints; keeping it
# unconditional preserves the historical reset(id) semantic even with R=0.
s = once(s, '''  // remove contact joints
  if (isSolidMerger()) {
    dBodyID b = body();
    int jointNumber = dBodyGetNumJoints(b);
    dJointID joints[jointNumber];
    for (int i = 0; i < jointNumber; ++i)
      joints[i] = dBodyGetJoint(b, i);
    for (int i = 0; i < jointNumber; ++i) {
      if (dJointGetType(joints[i]) == dJointTypeContact) {
        dJointAttach(joints[i], 0, 0);
        dJointDestroy(joints[i]);
      }
    }
  }''',
'''  // The historical reset(id) invalidates contacts even in the A test arm.
  // Centralized removal unregisters standalone joints before dJointDestroy.
  if (isSolidMerger())
    WbOdeContext::instance()->detachResetBodyContacts(body());''',
"D3 WbSolid reset(id) direct destroy")
# Make the registered owner unique across buffers, caught even when a pointer
# is reused: all tracked destructions remove the entry first.
c = once(c, '''  assert(owner && joint);
  if (buffer1)''', '''  assert(owner && joint);
  assert(!mBodyContacts1.contains(joint) && !mBodyContacts2.contains(joint));
  if (buffer1)''', "D3 registration uniqueness")

# Proof-friendly code-boundary invariants, fail before writing.
assert "H6_STANDALONE_R" not in s.split("void WbSolid::resetSingleSolidPhysics() {",1)[1].split("// check for joints",1)[0]
assert s.count("detachResetBodyContacts(body())") == 2
assert s.count("dJointDestroy(joints[i])") == 0
assert c.count("it.remove();") >= 2
ctx.write_text(c)
solid.write_text(s)
for p in (ctx,solid):
    print("H6_D1D2D3_MODIFIED",p.relative_to(root),hashlib.sha256(p.read_bytes()).hexdigest())
print("H6_D1D2D3_PATCH_APPLIED", "c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b")

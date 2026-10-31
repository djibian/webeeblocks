#!/usr/bin/env python3
"""E5 EXPERIMENTAL overlay on the exact pinned P0 fixture.
Refuse unknown source anchors. No production patch, no ABI rework.
H6_E5_DROP=owner|attached selects the actual body-removal implementation.
"""
from pathlib import Path
import os, sys, hashlib
if len(sys.argv) != 2:
    raise SystemExit("usage: patch_e5.py PINNED_PATCHED_WEBOTS_ROOT")
root = Path(sys.argv[1])
ctx = root / "src/webots/ode/WbOdeContext.cpp"
solid = root / "src/webots/nodes/WbSolid.cpp"
c, s = ctx.read_text(), solid.read_text()
# h6_p0_trace is implemented by the pinned observer; WbSolid does not declare it.
s = s.replace("#include <QtCore/QQueue>", 'extern "C" void h6_p0_trace(const char *, unsigned long long);\n#include <QtCore/QQueue>', 1)
def once(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit("REFUSED E5 anchor %s count=%d" % (label, n))
    return src.replace(old, new)

# Make the E5-A contrast real, not an oracle toggle. H0 applies to every read.
c = once(c, '''      if (it.value() == b) {
        dJointID joint = it.key();
        it.remove();
        h6_p0_trace("P0_unregister", (unsigned long long)(uintptr_t)joint);
        h6_p0_destroy_owned(joint);
      }''', r'''      dJointID joint = it.key(); // LIVE under M; NEVER dereference after free.
      const dBodyID owner = it.value();
      const dBodyID v0 = dJointGetBody(joint, 0);
      const dBodyID v1 = dJointGetBody(joint, 1);
      const char *mode = std::getenv("H6_E5_DROP");
      if (!mode || (std::strcmp(mode, "owner") && std::strcmp(mode, "attached")))
        std::abort();
      const bool attached = (v0 == b || v1 == b);
      // Explicit intervention only; not a claim of spontaneous sleeping owner.
      if (std::getenv("H6_E5_FORCE_SLEEP") && owner != b && attached) {
        dBodyDisable(owner);
        h6_p0_trace("E5_owner_sleep_forced", (unsigned long long)(uintptr_t)joint);
      }
      const bool drop = owner == b ||
        (!std::strcmp(mode, "attached") && (attached || (!v0 && !v1)));
      std::fprintf(stderr, "H6_E5_SCAN mode=%s joint=%p owner=%p victim=%p v0=%p v1=%p owner_enabled=%d drop=%d\n",
                   mode, (void*)joint, (void*)owner, (void*)b,
                   (void*)v0, (void*)v1, dBodyIsEnabled(owner), (int)drop);
      h6_p0_trace(drop ? "E5_drop" : "E5_keep", (unsigned long long)(uintptr_t)joint);
      if (drop) {
        // Other registry must not own this live joint: registered exactly once.
        assert(!(&mBodyContacts1 == map ? mBodyContacts2 : mBodyContacts1).contains(joint));
        it.remove();
        h6_p0_trace("P0_unregister", (unsigned long long)(uintptr_t)joint);
        h6_p0_destroy_owned(joint); // explicit INTERNAL path; M already held
      }''', "body E5 owner versus attachment")
# The actual RESET(id) path is independent of resetPhysics/R. No public gate
# under nonrecursive M; inspect both registries, never short-circuit deletion.
c = once(c, '''    const bool own = mBodyContacts1.remove(joint) || mBodyContacts2.remove(joint);
    if (own) {
      h6_p0_trace("P0_unregister", (unsigned long long)(uintptr_t)joint);
      h6_p0_destroy_owned(joint);
      ++removed;
    }
    // Foreign/plugin contacts MUST NOT be freed or detached by P0.''', '''    const bool own1 = mBodyContacts1.remove(joint) != 0;
    const bool own2 = mBodyContacts2.remove(joint) != 0;
    assert(!(own1 && own2));
    if (own1 || own2) {
      h6_p0_trace("E5_reset_engine", (unsigned long long)(uintptr_t)joint);
      h6_p0_trace("P0_unregister", (unsigned long long)(uintptr_t)joint);
      h6_p0_destroy_owned(joint); // M already held; no public admission
      ++removed;
    } else {
      // Original Webots reset(id): detach plugin group-owned contacts;
      // dJointDestroy was a no-op for group-owned. For standalone plugin
      // contacts, this detachment alone is NOT proven semantically equivalent.
      dJointAttach(joint, nullptr, nullptr);
      h6_p0_trace("E5_reset_plugin_detached", (unsigned long long)(uintptr_t)joint);
    }''', "reset contact engine/plugin distinction")
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
  }''', '''  // True Node.loadState -> WbSolid::reset(id), not ordinary resume.
  h6_p0_trace("E5_reset_id_enter", (unsigned long long)(uintptr_t)body());
  if (isSolidMerger())
    WbOdeContext::instance()->detachResetBodyContacts(body());
  h6_p0_trace("E5_reset_id_exit", (unsigned long long)(uintptr_t)body());''',
    "replace raw reset(id) contact release")
# P0 had inherited a test-only flag R in shared helper; ensure no mistaken
# claim of a true RESET merely because that helper ran.
assert s.count("E5_reset_id_enter") == 1
assert "dJointDestroy(joints[i])" not in s
assert c.count("h6_p0_destroy_owned(joint)") >= 4
ctx.write_text(c)
solid.write_text(s)
for p in (ctx,solid):
    print("E5_PATCHED", p.relative_to(root), hashlib.sha256(p.read_bytes()).hexdigest())
print("H6_E5_OVERLAY_READY research-only; require native execution")

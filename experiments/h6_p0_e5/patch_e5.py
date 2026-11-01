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
      // Intervention occurs once, at the real destructor boundary before M.
      // Neither registry scan nor owner policy changes the physical fixture.
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
      // Original reset(id): group-owned remains (no-op) but a standalone
      // plugin contact is freed. Stage public call only AFTER releasing M.
      dJointAttach(joint, nullptr, nullptr);
      pendingPluginDestroy.push_back(joint);
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
  const dBodyID e5ResetBody = isSolidMerger() ? body() : nullptr;
  h6_p0_trace("E5_reset_id_enter", (unsigned long long)(uintptr_t)e5ResetBody);
  if (e5ResetBody)
    WbOdeContext::instance()->detachResetBodyContacts(e5ResetBody);
  h6_p0_trace("E5_reset_id_exit", (unsigned long long)(uintptr_t)e5ResetBody);''',
    "replace raw reset(id) contact release")
# Restore exact ODE plugin semantics after leaving the nonrecursive M.
# This is a bounded synchronous reset; arbitrary plugin-private threads
# are a separate UNSOLVED H0/phase contract.
c = once(c, "#include <cassert>", "#include <cassert>\n#include <vector>",
         "plugin staged destroy vector include")
c = once(c, '''  h6_p0_trace("P0_reset_M_acquired", 0);
  int removed = 0;''',
'''  h6_p0_trace("P0_reset_M_acquired", 0);
  std::vector<dJointID> pendingPluginDestroy;
  int removed = 0;''',"stage plugin contacts under M")
c = once(c, '''  h6_p0_trace("P0_reset_M_released", 0);
  if (std::getenv("H6_STANDALONE_TRACE"))''',
'''  h6_p0_trace("P0_reset_M_released", 0);
  for (dJointID j : pendingPluginDestroy) {
    h6_p0_trace("E5_reset_plugin_native_destroy", (unsigned long long)(uintptr_t)j);
    dJointDestroy(j);  // native group no-op; standalone individual free
    // NO joint dereference after this call: H0 ends on effective free.
  }
  if (std::getenv("H6_STANDALONE_TRACE"))''',
"plugin native destruction after release")

# P0 had inherited a test-only flag R in shared helper; ensure no mistaken
# claim of a true RESET merely because that helper ran.
assert s.count("E5_reset_id_enter") == 1
assert "dJointDestroy(joints[i])" not in s
assert c.count("h6_p0_destroy_owned(joint)") >= 4
# Instrument the REAL WbSolidMerger destructor before/after dBodyDestroy.
merger = root / "src/webots/nodes/utils/WbSolidMerger.cpp"
m = merger.read_text()
m = once(m, '''WbSolidMerger::~WbSolidMerger() {
  WbOdeContext::instance()->removeBodyContactJointGroup(mBody);
  dBodyDestroy(mBody);''', '''WbSolidMerger::~WbSolidMerger() {
  h6_p0_trace("E5_body_destructor_enter", (unsigned long long)(uintptr_t)mBody);
  // D1 native control #41201953896: sleep the genuinely attached OTHER
  // body at the real body destructor boundary, immediately before cleanup.
  // No mutation of contacts/ownership maps and no fabricated joints.
  if (std::getenv("H6_E5_FORCE_SLEEP") &&
      !std::strcmp(std::getenv("H6_E5_FORCE_SLEEP"), "1")) {
    bool h6FoundForeignContact = false;
    for (int h6i = 0; h6i < dBodyGetNumJoints(mBody); ++h6i) {
      dJointID h6j = dBodyGetJoint(mBody, h6i); // LIVE at destructor entry
      if (dJointGetType(h6j) != dJointTypeContact)
        continue;
      const dBodyID h6b0 = dJointGetBody(h6j, 0), h6b1 = dJointGetBody(h6j, 1);
      const dBodyID h6other = h6b0 == mBody ? h6b1 : h6b0;
      if (!h6other)
        continue; // plugin B-world contact is not the A-B witness
      const int h6before = dBodyIsEnabled(h6other);
      dBodyDisable(h6other);
      h6_p0_trace("E5_owner_sleep_forced_at_destructor",
                  (unsigned long long)(uintptr_t)h6other);
      std::fprintf(stderr, "H6_E5_BOUNDARY_SLEEP victim=%p other=%p before=%d after=%d joint=%p\\n",
                   (void*)mBody, (void*)h6other, h6before,
                   dBodyIsEnabled(h6other), (void*)h6j);
      h6FoundForeignContact = true;
      break;
    }
    if (!h6FoundForeignContact)
      h6_p0_trace("E5_no_foreign_attached_at_destructor",
                  (unsigned long long)(uintptr_t)mBody);
  }
  WbOdeContext::instance()->removeBodyContactJointGroup(mBody);
  h6_p0_trace("E5_before_dBodyDestroy", (unsigned long long)(uintptr_t)mBody);
  dBodyDestroy(mBody);
  h6_p0_trace("E5_after_dBodyDestroy", 0);''',
  "true Webots body destructor")
m = once(m, '#include "WbSolidMerger.hpp"',
 '''extern "C" void h6_p0_trace(const char *, unsigned long long);
#include <cstdlib>
#include <cstring>
#include <cstdio>
#include "WbSolidMerger.hpp"''', "merger trace declaration")
ctx.write_text(c)
solid.write_text(s)
merger.write_text(m)
# Observation only: distinguish ownership created by the native broadphase
# from contacts surviving at the B destructor. NEVER modify owner, joint or
# attachments. Needed because D1 had owner=A but E5 run #41284881130 owner=B.
cluster = root / "src/webots/engine/WbSimulationCluster.cpp"
t = cluster.read_text()
create = "    cl->mContext->registerBodyContactJoint(owner, contactJoint, cl->mSwapJointContactBuffer);"
t = once(t, create, create + r"""
    if (std::getenv("H6_E5_CASE"))
      std::fprintf(stderr,
        "H6_E5_CREATE joint=%p owner=%p b1=%p b2=%p buffer=%d\\n",
        (void*)contactJoint, (void*)owner, (void*)b1, (void*)b2,
        int(cl->mSwapJointContactBuffer));
""", "real-broadphase-creation-provenance")
t = once(t, "#include <atomic>", "#include <atomic>\n#include <cstdio>",
         "creation audit include")
cluster.write_text(t)
for p in (ctx,solid,merger,cluster):
    print("E5_PATCHED", p.relative_to(root), hashlib.sha256(p.read_bytes()).hexdigest())
print("H6_E5_OVERLAY_READY research-only; require native execution")

#!/usr/bin/env python3
"""Fail-closed minimal Webots R2025a RESET-attachment R + retired-buffer G candidate.

The only experimental switches are H6_NATIVE_R/H6_NATIVE_G. Production proposal
is the same two hooks with switches removed. Never alters Webots upstream or ODE
in the repo; patches a separately pinned Webots checkout in GitHub Actions.
"""
from pathlib import Path
import hashlib
import subprocess
import sys

PIN = "c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b"
if len(sys.argv) != 2:
    raise SystemExit("usage: patch_webots_rg.py WEBOTS_SOURCE_ROOT")
root = Path(sys.argv[1])
actual = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
if actual != PIN:
    raise SystemExit(f"REFUSED Webots SHA mismatch {actual}")
if subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True).strip():
    raise SystemExit("REFUSED dirty source checkout")
context = root / "src/webots/ode/WbOdeContext.cpp"
header = root / "src/webots/ode/WbOdeContext.hpp"
solid = root / "src/webots/nodes/WbSolid.cpp"
cluster = root / "src/webots/engine/WbSimulationCluster.cpp"
c, h, s, k = [p.read_text() for p in (context, header, solid, cluster)]

def replace_once(source, old, new, tag):
    n = source.count(old)
    if n != 1:
        raise SystemExit(f"REFUSED {tag}: count {n} != 1")
    return source.replace(old, new)

# Exact existing per-owner groups and per-contact ownership are retained.
h = replace_once(h, "  void removeBodyContactJointGroup(dBodyID b);",
    "  void removeBodyContactJointGroup(dBodyID b);\n  void detachResetBodyContacts(dBodyID body);", "header declaration")
c = replace_once(c, "#include <cassert>",
    "#include <cassert>\n#include <cstdlib>\n#include <cstring>\n#include <cstdio>", "context includes")
needle = "    if (dBodyIsEnabled(it.key()))\n      dJointGroupEmpty(it.value());"
if c.count(needle) != 2:
    raise SystemExit("REFUSED exactly two retired cleanup loops required")
# G applies ONLY to the two already retired buffers in WbSimulationCluster.
g = """    const bool h6G = std::getenv("H6_NATIVE_G") && !std::strcmp(std::getenv("H6_NATIVE_G"), "1");
    const int before = static_cast<int>(dJointGroupGetCount(it.value()));
    if (before && std::getenv("H6_NATIVE_TRACE")) {
      std::fprintf(stderr, "H6_NATIVE_G event=retire owner_enabled=%d count=%d g=%d\\n",
                   static_cast<int>(dBodyIsEnabled(it.key())), before, static_cast<int>(h6G));
      std::fflush(stderr);
    }
    if (dBodyIsEnabled(it.key()) || h6G)
      dJointGroupEmpty(it.value());"""
c = c.replace(needle, g)
# R acts on *attachments*, not the contact-group owner.
anchor = "void WbOdeContext::removeBodyContactJointGroup(dBodyID b) {"
if c.count(anchor) != 1:
    raise SystemExit("REFUSED no unique group disposal anchor")
implementation = """void WbOdeContext::detachResetBodyContacts(dBodyID body) {
  if (!body)
    return;
  // Contact creation already uses this mutex. RESET must not interleave with it.
  mJointGroupCreationMutex->lock();
  int removed = 0;
  // Reverse traversal is stable when the current joint is detached.
  for (int i = dBodyGetNumJoints(body) - 1; i >= 0; --i) {
    dJointID joint = dBodyGetJoint(body, i);
    if (dJointGetType(joint) != dJointTypeContact)
      continue;
    dJointAttach(joint, 0, 0); // group-owned joints remain allocated until retirement
    dJointDestroy(joint);      // ungrouped contact joints, if any, are destroyed
    ++removed;
  }
  mJointGroupCreationMutex->unlock();
  if (std::getenv("H6_NATIVE_TRACE")) {
    std::fprintf(stderr, "H6_NATIVE_R event=detach removed=%d\\n", removed);
    std::fflush(stderr);
  }
}

"""
c = c.replace(anchor, implementation + anchor)
# Both global Supervisor resetPhysics and individual node resetPhysics call this.
# Deliberately leave all permanent joints (non-contact types) intact.
s = replace_once(s, "void WbSolid::resetSingleSolidPhysics() {\n  // check for joints",
    """void WbSolid::resetSingleSolidPhysics() {
  if (isSolidMerger() && std::getenv("H6_NATIVE_R") &&
      !std::strcmp(std::getenv("H6_NATIVE_R"), "1"))
    WbOdeContext::instance()->detachResetBodyContacts(body());
  // check for joints""", "single reset boundary")
s = replace_once(s, "#include <QtCore/QQueue>",
    "#include <cstdlib>\n#include <cstring>\n#include <QtCore/QQueue>", "solid includes")
# This is a post-solver + post-swap boundary. Lock the group cleanup to match
# the mutual exclusion already held by the contact-creation callback.
a = """  if (mSwapJointContactBuffer)
    mContext->emptyEnabledBodyContactJointGroups1();
  else
    mContext->emptyEnabledBodyContactJointGroups2();"""
b = """  cJointCreationMutex->lock();
  if (mSwapJointContactBuffer)
    mContext->emptyEnabledBodyContactJointGroups1();
  else
    mContext->emptyEnabledBodyContactJointGroups2();
  cJointCreationMutex->unlock();"""
k = replace_once(k, a, b, "retired-buffer mutex boundary")
for p, value in ((context,c),(header,h),(solid,s),(cluster,k)):
    p.write_text(value)
    print("H6_NATIVE_PATCH", p.relative_to(root), hashlib.sha256(p.read_bytes()).hexdigest())
assert c.count("void WbOdeContext::detachResetBodyContacts(dBodyID body)") == 1
assert c.count("H6_NATIVE_G event=retire") == 2
assert s.count("H6_NATIVE_R") == 2  # getenv and strcmp
print("H6_NATIVE_RG_PATCH_READY", PIN)

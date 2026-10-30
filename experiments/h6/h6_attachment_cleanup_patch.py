#!/usr/bin/env python3
"""H6-only attachment cleanup substitution: strict source digest and anchors."""
from pathlib import Path
import hashlib
import sys
p=Path(sys.argv[1])/'source/patch_webots_h6.py'
raw=p.read_bytes()
expected='41153c243fdf9cb64df561957e5e59202498b7c4b8fe01d2d526889384dd1cb5'
if hashlib.sha256(raw).hexdigest()!=expected:
    raise SystemExit('H6 REFUSED unexpected generated C++ patcher digest')
s=raw.decode()
start='// H6 candidate: clear only contacts belonging to the body being reset.\n'
end='void WbOdeContext::h6RegisterContact(dJointID joint, dJointGroupID group, dBodyID b1, dBodyID b2,'
if s.count(start)!=1 or s.count(end)!=1 or s.index(end)<=s.index(start):
    raise SystemExit('H6 REFUSED ambiguous cleanup code anchors')
replacement=r'''// H6 R: reset old contacts by actual body attachment; groups stay intact.
void WbOdeContext::clearResetBodyContactJointGroups(dBodyID body) {
  if (!body) return;
  mJointGroupCreationMutex->lock();
  std::vector<dJointID> contacts;
  const int count = dBodyGetNumJoints(body);
  contacts.reserve(count);
  for (int i = 0; i < count; ++i) {
    dJointID joint = dBodyGetJoint(body, i);
    if (dJointGetType(joint) == dJointTypeContact)
      contacts.push_back(joint);
  }
  for (dJointID joint : contacts) {
    // ODE group-owned dJointDestroy alone is a no-op; detach first.
    dJointAttach(joint, 0, 0);
    dJointDestroy(joint);
  }
  mJointGroupCreationMutex->unlock();
  h6Log("H6 event=webots_reset_cleanup body=%p removed=%d\n",
        static_cast<void *>(body), static_cast<int>(contacts.size()));
}

'''
s=s[:s.index(start)]+replacement+s[s.index(end):]
# H6 G candidate: release ONLY retired contact buffer regardless of owner enabled,
# while retaining R's attachment-selective immediate reset invalidation.
# Only the F experiment arm enables G, after the H6 body is armed.
old = "    if (dBodyIsEnabled(it.key()))\\n      dJointGroupEmpty(it.value());''')"
new = "    if (dBodyIsEnabled(it.key()) || (h6ArmedBody && h6Mode() && !std::strcmp(h6Mode(), \\"F\\")))\\n      dJointGroupEmpty(it.value());''')"
if s.count(old) != 2:
    raise SystemExit('H6 REFUSED expected two retired buffer substitutions')
s = s.replace(old, new)

if s.count('void WbOdeContext::clearResetBodyContactJointGroups(dBodyID body)')!=1:
    raise SystemExit('H6 REFUSED multiple cleanup candidates')
p.write_text(s)
print('H6 R PATCH',p,hashlib.sha256(p.read_bytes()).hexdigest())

#!/usr/bin/env python3
"""H6-only authenticated four-arm placebo / Webots-reset lifecycle experiment."""
from pathlib import Path
import hashlib
import sys
root=Path(sys.argv[1])
expected={
'source/patch_webots_h6.py':'a2de4802ac1af045f371db90076d063c393e71a939e316e3078273a1e7a7c212',
'source/run_ab.sh':'7331860705243a781ab364cace44194788bfc2f77ed40e409832a14ef91444d0',
'source/analyze_ab.py':'e024380a25bb73f035a28f332dfc399ff535b2dea307eaa9ae4c0e5f63c8a0fd',
'controllers/h6_supervisor/h6_supervisor.py':'e1ffbe86ba50ea95055530b26928a5a3de8939ddae196a6cf17eae8116af0372',
}
src={}
for p,sha in expected.items():
 b=(root/p).read_bytes()
 if hashlib.sha256(b).hexdigest()!=sha: raise SystemExit(f'H6 REFUSED digest {p}')
 src[p]=b.decode()
def once(p,old,new):
 if src[p].count(old)!=1: raise SystemExit(f'H6 REFUSED anchor {p}: {old[:60]!r}')
 src[p]=src[p].replace(old,new,1)
p='source/patch_webots_h6.py'
once(p,'!std::strcmp(mode, "A") || !std::strcmp(mode, "B")',
       '!std::strcmp(mode, "A") || !std::strcmp(mode, "B") || !std::strcmp(mode, "P") || !std::strcmp(mode, "F")')
once(p,'  void h6ArmReset(dBodyID body);',
       '  void clearResetBodyContactJointGroups(dBodyID body);\n  void h6ArmReset(dBodyID body);')
once(p,'void WbOdeContext::h6RegisterContact(dJointID joint, dJointGroupID group, dBodyID b1, dBodyID b2,',
'''// H6 candidate: clear only contacts belonging to the body being reset.
// Do NOT change the cleanup of other artificially disabled bodies.
void WbOdeContext::clearResetBodyContactJointGroups(dBodyID body) {
  if (!body) return;
  mJointGroupCreationMutex->lock();
  int removed = 0;
  const auto it1 = mBodyContactJointGroupList1.constFind(body);
  if (it1 != mBodyContactJointGroupList1.constEnd()) {
    removed += dJointGroupGetCount(it1.value());
    dJointGroupEmpty(it1.value());
  }
  const auto it2 = mBodyContactJointGroupList2.constFind(body);
  if (it2 != mBodyContactJointGroupList2.constEnd()) {
    removed += dJointGroupGetCount(it2.value());
    dJointGroupEmpty(it2.value());
  }
  mJointGroupCreationMutex->unlock();
  h6Log("H6 event=webots_reset_cleanup body=%p removed=%d\\n", static_cast<void *>(body), removed);
}

void WbOdeContext::h6RegisterContact(dJointID joint, dJointGroupID group, dBodyID b1, dBodyID b2,''')
once(p,'''  if (!std::strcmp(h6Mode(), "B")) {
    // Fail closed:''','''  if (!std::strcmp(h6Mode(), "P")) {
    // Read-only placebo traversal with the same group selection as B.
    const int n = (groups[0] ? dJointGroupGetCount(groups[0]) : 0) +
                  (groups[1] ? dJointGroupGetCount(groups[1]) : 0);
    h6Log("H6 event=placebo_scan step=%llu count=%d\\n", h6StepIndex, n);
  }
  if (!std::strcmp(h6Mode(), "B")) {
    // Fail closed:''')
once(p,'''      WbOdeContext::instance()->h6BeforeResume(mSolidMerger->body());
    if (mSolidMerger)
      mSolidMerger->setBodyArtificiallyDisabled(false);''','''      WbOdeContext::instance()->h6BeforeResume(mSolidMerger->body());
    // F tests the candidate lifecycle repair, independently from B.
    if (mSolidMerger && std::getenv("WEBEE_H6_MODE") &&
        !std::strcmp(std::getenv("WEBEE_H6_MODE"), "F"))
      WbOdeContext::instance()->clearResetBodyContactJointGroups(mSolidMerger->body());
    if (mSolidMerger)
      mSolidMerger->setBodyArtificiallyDisabled(false);''')
once(p, """    solid = 'src/webots/nodes/WbSolid.cpp'
    change(solid, ""","""    solid = 'src/webots/nodes/WbSolid.cpp'
    change(solid, '#include "WbSolid.hpp"', '#include "WbSolid.hpp"\\n#include <cstdlib>\\n#include <cstring>')
    change(solid, """)
p='source/run_ab.sh'
once(p,'for MODE in A B; do','for MODE in A P B F; do')
once(p,"if [[ \"$MODE\" == 'B' ]] && [[ ! -f \"$OUT/A/check-a-approved\" ]]; then",
       'if [[ "$MODE" != A ]] && [[ ! -f "$OUT/A/check-a-approved" ]]; then')
p='controllers/h6_supervisor/h6_supervisor.py'
once(p,"if MODE not in ('A', 'B'):","if MODE not in ('A', 'B', 'P', 'F'):")
for p,s in src.items():
 (root/p).write_text(s)
 print('H6 CONTROL PATCH',p,hashlib.sha256((root/p).read_bytes()).hexdigest())

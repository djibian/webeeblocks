#!/usr/bin/env python3
"""Read-only trace on pinned ORIGINAL Webots reset(id); no ownership mutation."""
from pathlib import Path
import sys
if len(sys.argv) != 2:
    raise SystemExit("usage: patch_baseline_reset_probe.py WEBOTS_ROOT")
p=Path(sys.argv[1])/"src/webots/nodes/WbSolid.cpp"
s=p.read_text()
def once(before, after, label):
    global s
    if s.count(before)!=1:
        raise SystemExit("REFUSED original Webots baseline anchor "+label+" count="+str(s.count(before)))
    s=s.replace(before,after)
once("#include <QtCore/QQueue>",
     'extern "C" void h6_p0_trace(const char *, unsigned long long);\n#include <QtCore/QQueue>',
     "include")
once('''  // remove contact joints
  if (isSolidMerger()) {
    dBodyID b = body();
    int jointNumber = dBodyGetNumJoints(b);''',
'''  // remove contact joints
  if (isSolidMerger()) {
    dBodyID b = body();
    h6_p0_trace("BC_original_reset_enter", (unsigned long long)(uintptr_t)b);
    int jointNumber = dBodyGetNumJoints(b);''',"reset_enter")
once('''        dJointAttach(joints[i], 0, 0);
        dJointDestroy(joints[i]);
      }
    }
  }''','''        dJointAttach(joints[i], 0, 0);
        dJointDestroy(joints[i]);
      }
    }
    h6_p0_trace("BC_original_reset_exit", (unsigned long long)(uintptr_t)b);
  }''',"reset_exit")
p.write_text(s)
print("H6_BC_ORIGINAL_RESET_READ_ONLY_INSTRUMENTATION")

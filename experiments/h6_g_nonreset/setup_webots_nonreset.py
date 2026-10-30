#!/usr/bin/env python3
"""H6 non-RESET Webots experiment: fail-closed source patch + ordinary world."""
from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: setup_webots_nonreset.py WEBOTS_SOURCE_ROOT OUTPUT_ROOT")
root, out = Path(sys.argv[1]), Path(sys.argv[2])
p = root / "src/webots/ode/WbOdeContext.cpp"
s = p.read_text()
needle = "    if (dBodyIsEnabled(it.key()))\n      dJointGroupEmpty(it.value());"
if s.count(needle) != 2:
    raise SystemExit(f"REFUSED: exact pinned cleanup code expected twice, found {s.count(needle)}")
if s.count("#include <cassert>") != 1:
    raise SystemExit("REFUSED: native includes differ")
s = s.replace("#include <cassert>", "#include <cassert>\n#include <cstdlib>\n#include <cstdio>\n#include <cstring>")
replacement = """    const bool ownerEnabled = dBodyIsEnabled(it.key());
    const int count = dJointGroupGetCount(it.value());
    // Purely observational and bounded: identify naturally occurring
    // disabled-owner contact groups before attempting any deletion.
    if (!ownerEnabled && count > 0) {
      static int reported = 0;
      if (reported < 400) {
        int attachedContactJoints = 0, contactsWithEnabledOther = 0;
        const int n = dBodyGetNumJoints(it.key());
        for (int i = 0; i < n; ++i) {
          dJointID j = dBodyGetJoint(it.key(), i);
          if (dJointGetType(j) != dJointTypeContact)
            continue;
          ++attachedContactJoints;
          dBodyID x = dJointGetBody(j, 0), y = dJointGetBody(j, 1);
          dBodyID other = x == it.key() ? y : x;
          if (other && dBodyIsEnabled(other))
            ++contactsWithEnabledOther;
        }
        std::fprintf(stderr,
                     "H6_G_CONTACT owner_disabled=1 group_contacts=%d owner_contacts=%d active_other_contacts=%d arm=%s\\n",
                     count, attachedContactJoints, contactsWithEnabledOther,
                     (std::getenv("WEBOTS_H6_TEST_G") && !std::strcmp(std::getenv("WEBOTS_H6_TEST_G"), "1")) ? "G" : "A");
        ++reported;
      }
    }
    // Exact one-bit intervention: the ordinary enabled-owner behavior stays intact.
    const char *g = std::getenv("WEBOTS_H6_TEST_G");
    if (ownerEnabled || (g && !std::strcmp(g, "1")))
      dJointGroupEmpty(it.value());"""
s = s.replace(needle, replacement)
assert s.count("H6_G_CONTACT") == 2
p.write_text(s)
worlds = out / "worlds"
ctrl = out / "controllers" / "h6_g_nonreset"
worlds.mkdir(parents=True, exist_ok=True)
ctrl.mkdir(parents=True, exist_ok=True)
# Zero gravity allows an unforced body to sleep automatically, while the
# other body travels into it. No teleports, resetPhysics or injected joints.
world = """#VRML_SIM R2025a utf8
WorldInfo {
  basicTimeStep 16
  gravity 0
  physicsDisableTime 0.032
  physicsDisableLinearThreshold 0.005
  physicsDisableAngularThreshold 0.005
}
Viewpoint {
  orientation 0 1 0 1.5708
  position 0 0 2
}
TexturedBackground { }
TexturedBackgroundLight { }
DEF OWNER Solid {
  translation 0 0 0
  name "owner"
  children [
    Shape {
      appearance PBRAppearance { baseColor 0.1 0.1 1 roughness 1 metalness 0 }
      geometry Sphere { radius 0.05 }
    }
  ]
  boundingObject Sphere { radius 0.05 }
  physics Physics { density -1 mass 0.05 }
}
DEF OTHER Solid {
  translation 0.18 0 0
  name "other"
  children [
    Shape {
      appearance PBRAppearance { baseColor 1 0.1 0.1 roughness 1 metalness 0 }
      geometry Sphere { radius 0.05 }
    }
  ]
  boundingObject Sphere { radius 0.05 }
  physics Physics { density -1 mass 0.05 }
}
Robot {
  name "observer"
  supervisor TRUE
  controller "h6_g_nonreset"
}
"""
(worlds / "h6_g_nonreset.wbt").write_text(world)
py = """from controller import Supervisor
import json, math, os, sys
supervisor = Supervisor()
a = supervisor.getFromDef('OWNER')
b = supervisor.getFromDef('OTHER')
if a is None or b is None:
    print('H6_G_FATAL missing bodies', flush=True)
    sys.exit(2)
arm = os.environ.get('WEBOTS_H6_TEST_G', '0')
if arm not in ('0', '1'):
    sys.exit(2)
b.setVelocity([-0.5, 0, 0, 0, 0, 0])  # initial condition, no RESET or contact injection
dt = int(supervisor.getBasicTimeStep())
for frame in range(140):
    code = supervisor.step(dt)
    if code == -1:
        print('H6_G_FATAL terminated early', flush=True)
        sys.exit(2)
    pa, pb = a.getPosition(), b.getPosition()
    va, vb = a.getVelocity(), b.getVelocity()
    if not all(math.isfinite(x) for x in pa + pb + va + vb):
        print('H6_G_FATAL nonfinite physics', flush=True)
        sys.exit(2)
    print('H6_G_STEP ' + json.dumps({
        'arm':arm,'frame':frame,'time':round(supervisor.getTime(), 7),
        'a_position':pa,'b_position':pb,
        'a_velocity':va,'b_velocity':vb
    },sort_keys=True,separators=(',',':')), flush=True)
print('H6_G_NONRESET_DONE arm='+arm, flush=True)
supervisor.simulationQuit(0)
"""
(ctrl / "h6_g_nonreset.py").write_text(py)
print("H6_G_SETUP_OK native source modified, world and supervisor generated")

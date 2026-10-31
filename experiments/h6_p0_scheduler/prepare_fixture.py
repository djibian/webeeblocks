#!/usr/bin/env python3
"""Prepare an independent two-island fixture from the exact historic PR #760 files.

The plugin never creates a new contact. Its public dJointDestroy probe is
deliberately limited to the ORIGINAL Webots group-owned engine contact, where
the native ODE contract makes the call a no-op. Not a standalone-P0 test.
"""
from pathlib import Path
import sys
if len(sys.argv) != 2:
    raise SystemExit("usage: prepare_fixture.py FIXTURE_DIR")
root = Path(sys.argv[1])
world = root / "worlds/h6_g_window.wbt"
plugin = root / "plugins/physics/h6_g_window/h6_g_window.c"
s = world.read_text()
if s.count("Robot {") != 1 or s.count("  optimalThreadCount 1") != 1:
    raise SystemExit("REFUSED unexpected inherited world")
far = """DEF FAR_FLOOR Solid {
  translation 8 0 -0.1
  name "far_floor"
  children [
    Shape {
      appearance PBRAppearance { baseColor 0.25 0.55 0.25 roughness 1 }
      geometry Box { size 3 3 0.2 }
    }
  ]
  boundingObject Box { size 3 3 0.2 }
}
DEF FAR_TARGET Solid {
  translation 8 0 0.105
  name "far_target"
  children [
    Shape {
      appearance PBRAppearance { baseColor 0.75 0.25 0.25 roughness 1 }
      geometry Box { size 0.2 0.2 0.2 }
    }
  ]
  boundingObject Box { size 0.2 0.2 0.2 }
  physics Physics { mass 0.12 }
}
"""
s = s.replace("Robot {", far + "Robot {")
for n in (1,2):
    (root / f"worlds/h6_p0_workers{n}.wbt").write_text(
        s.replace("  optimalThreadCount 1",f"  optimalThreadCount {n}"))
p = plugin.read_text()
if p.count("#include <plugins/physics.h>") != 1 or "webots_physics_collide" in p:
    raise SystemExit("REFUSED unexpected inherited plugin")
p=p.replace("#include <plugins/physics.h>", '#include <plugins/physics.h>\nextern void h6_p0_trace(const char *, unsigned long long);')
p += """
/* Observation on group-owned baseline: engine contact from PRIOR frame only.
   Collision callback is invoked before Webots creates current frame's contact.
   dJointDestroy has original ODE no-op semantics for group-owned joints. */
int webots_physics_collide(dGeomID g1, dGeomID g2) {
  (void)g1;
  (void)g2;
  h6_p0_trace("plugin_callback_enter", 0);
  static unsigned long last_attempt_tick = (unsigned long)-1;
  if (target && tick != last_attempt_tick) {
    int count = dBodyGetNumJoints(target);
    for (int i = 0; i < count; ++i) {
      dJointID j = dBodyGetJoint(target, i);
      if (dJointGetType(j) != dJointTypeContact)
        continue;
      last_attempt_tick = tick;
      h6_p0_trace("plugin_public_attempt", (unsigned long long)(size_t)j);
      dJointDestroy(j);
      h6_p0_trace("plugin_public_return", (unsigned long long)(size_t)j);
      if (dJointGetType(j) != dJointTypeContact)
        abort();
      h6_p0_trace("plugin_baseline_noop", (unsigned long long)(size_t)j);
      break;
    }
  }
  h6_p0_trace("plugin_callback_exit", 0);
  return 0;
}
"""
plugin.write_text(p)
print("H6_P0_TWO_ISLAND_FIXTURE_READY")

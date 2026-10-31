#!/usr/bin/env python3
"""Extend exact #777 two-island fixture with standalone P0 and plugin-owned controls.
No fabricated engine contact; select live contact from dBodyGetJoint in pre-step.
"""
from pathlib import Path
import sys
if len(sys.argv) != 2:
    raise SystemExit("usage: prepare_p0_fixture.py FIXTURE_DIR")
p = Path(sys.argv[1]) / "plugins/physics/h6_g_window/h6_g_window.c"
s = p.read_text()

def once(old,new,label):
    global s
    n=s.count(old)
    if n!=1: raise SystemExit("REFUSED fixture anchor %s count=%s"%(label,n))
    s=s.replace(old,new)

once("static volatile int h6_once = 0;",
     "static volatile int h6_once = 0;\nstatic __thread unsigned int h6_p0_thread_attempts = 0;",
     "TLS is only probe cardinality, NEVER engine authorization")
once("if (h6_selected && __sync_bool_compare_and_swap(&h6_once, 0, 1)) {",
     "if (h6_selected && h6_p0_thread_attempts++ == 0) {",
     "one public attempt per real worker thread")
once('h6_p0_trace("plugin_baseline_noop", (unsigned long long)(size_t)j);',
     'h6_p0_trace("plugin_p0_live", (unsigned long long)(size_t)j);',
     "true live standalone P0 check")
once("  r_enabled = r && strcmp(r, \"1\") == 0;",
'''  // E4: controls owned by plugin, NOT engine. No attached bodies or solver use.
  dWorldID pw = dBodyGetWorld(target);
  dContact pc = {0};
  dJointID standalone = dJointCreateContact(pw, NULL, &pc);
  if (!standalone || dJointGetType(standalone) != dJointTypeContact) abort();
  h6_p0_trace("plugin_standalone_before", (unsigned long long)(size_t)standalone);
  dJointDestroy(standalone);  // Must remain native effective destruction.
  h6_p0_trace("plugin_standalone_destroyed", (unsigned long long)(size_t)standalone);
  dJointGroupID pg = dJointGroupCreate(0);
  dJointID grouped = dJointCreateContact(pw, pg, &pc);
  if (!grouped || dJointGroupGetCount(pg) != 1) abort();
  h6_p0_trace("plugin_group_before", (unsigned long long)(size_t)grouped);
  dJointDestroy(grouped);   // Native group-owned no-op.
  if (dJointGroupGetCount(pg) != 1 || dJointGetType(grouped) != dJointTypeContact) abort();
  h6_p0_trace("plugin_group_noop", (unsigned long long)(size_t)grouped);
  dJointGroupEmpty(pg);
  if (dJointGroupGetCount(pg) != 0) abort();
  h6_p0_trace("plugin_group_empty", (unsigned long long)(size_t)grouped);
  dJointGroupDestroy(pg);
  r_enabled = r && strcmp(r, "1") == 0;''',"plugin-owned controls")
p.write_text(s)
print("H6_P0_FIXTURE_STANDALONE_AND_PLUGIN_CONTROLS_READY")

#!/usr/bin/env python3
"""Source-pinned observation ONLY, without changing contact ownership or lock semantics.

The ONLY deliberate runtime deviation is H6_P0_FORCE_ONE_WORKER=1: Webots normally
turns optimalThreadCount=1 into dToggleODE_MT(0), so no pthread worker exists.
"""
from pathlib import Path
import subprocess
import sys

PIN = "c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b"
if len(sys.argv) != 2:
    raise SystemExit("usage: patch_observe.py WEBOTS_ROOT")
root = Path(sys.argv[1])
if subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip() != PIN:
    raise SystemExit("REFUSED: not pinned Webots")
if subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"], text=True).strip():
    raise SystemExit("REFUSED: original Webots checkout must be clean")

def edit(path, old, new):
    p = root / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"REFUSED anchor count={n} at {path}: {old[:70]!r}")
    p.write_text(s.replace(old, new))

ode = "src/ode/ode/src/ode.cpp"
header = """#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <sys/syscall.h>
#include <unistd.h>
static std::atomic<unsigned long long> h6_p0_seq{0}, h6_p0_step{0};
extern "C" void h6_p0_trace(const char *ev, unsigned long long arg) {
  if (!std::strcmp(ev, "step_enter")) ++h6_p0_step;
  unsigned long long seq = ++h6_p0_seq;
  char line[256];
  int n = std::snprintf(line, sizeof(line),
      "H6_P0 seq=%llu step=%llu tid=%ld event=%s arg=%llu\\n",
      seq, h6_p0_step.load(), (long)syscall(SYS_gettid), ev, arg);
  if (n > 0 && n < (int)sizeof(line))
    (void)write(STDERR_FILENO, line, (size_t)n);
}
"""
p = root / ode
p.write_text(header + p.read_text())  # trace-only exported symbol, experimental build
edit(ode, '    j->contact = *c;\n    return j;', '    j->contact = *c;\n    h6_p0_trace("contact_create", (unsigned long long)(uintptr_t)j);\n    return j;')
edit(ode, 'void dJointDestroy (dxJoint *j)\n{\n    dAASSERT (j);',
     'void dJointDestroy (dxJoint *j)\n{\n    h6_p0_trace("public_destroy_enter", (unsigned long long)(uintptr_t)j);\n    dAASSERT (j);')
edit(ode, '    const size_t num_joints = group->getJointCount();',
     '    const size_t num_joints = group->getJointCount();\n    h6_p0_trace("group_empty", (unsigned long long)num_joints);')
edit(ode, 'void dWorldDestroy_ST (dxWorld *w)\n{',
     'void dWorldDestroy_ST (dxWorld *w)\n{\n    h6_p0_trace("world_destroy", (unsigned long long)(uintptr_t)w);')

mt = "src/ode/ode/src/ode_MT/ode_MT.cpp"
edit(mt, '#include "ode_MT.h"', 'extern "C" void h6_p0_trace(const char *, unsigned long long);\n#include "ode_MT.h"')
edit(mt, 'void dWorldStepAndSpaceCollide (dSpaceID _space, void *_data, dNearCallback *_callback, dxWorld *_world, dReal _stepsize, dWorldStepFunction *_stepFunc, dSpaceUpdateFunction* _spaceUpdateFunc)\n{',
     'void dWorldStepAndSpaceCollide (dSpaceID _space, void *_data, dNearCallback *_callback, dxWorld *_world, dReal _stepsize, dWorldStepFunction *_stepFunc, dSpaceUpdateFunction* _spaceUpdateFunc)\n{\n    h6_p0_trace("step_enter", 0);')
edit(mt, 'void* simLoopChild(int tid, void* args)\n{',
     'void* simLoopChild(int tid, void* args)\n{\n    h6_p0_trace("worker_task_enter", (unsigned long long)tid);')
edit(mt, '  return NULL;\n}\n\nint dAreGeomsSame',
     '  h6_p0_trace("worker_task_exit", (unsigned long long)tid);\n  return NULL;\n}\n\nint dAreGeomsSame')
tm = "src/ode/ode/src/ode_MT/threading/threadManagerPthread.cpp"
edit(tm, '#include "threadManagerPthread.h"', 'extern "C" void h6_p0_trace(const char *, unsigned long long);\n#include "threadManagerPthread.h"')
edit(tm, '        ode_barrier_wait(&mgr->simLoopBarrier1);\n        ODE_PRINT',
     '        h6_p0_trace("worker_b1_before", (unsigned long long)tid);\n        ode_barrier_wait(&mgr->simLoopBarrier1);\n        h6_p0_trace("worker_b1_after", (unsigned long long)tid);\n        ODE_PRINT')
edit(tm, '        ode_barrier_wait(&mgr->simLoopBarrier2);\n    }',
     '        h6_p0_trace("worker_b2_before", (unsigned long long)tid);\n        ode_barrier_wait(&mgr->simLoopBarrier2);\n        h6_p0_trace("worker_b2_after", (unsigned long long)tid);\n    }')
edit(tm, '        ode_barrier_wait(&simLoopBarrier1);\n    /*',
     '        h6_p0_trace("main_b1_before", 0);\n        ode_barrier_wait(&simLoopBarrier1);\n        h6_p0_trace("main_b1_after", 0);\n    /*')
edit(tm, '        ode_barrier_wait(&simLoopBarrier2);\n}',
     '        h6_p0_trace("main_b2_before", 0);\n        ode_barrier_wait(&simLoopBarrier2);\n        h6_p0_trace("main_b2_after", 0);\n}')
cluster = "src/webots/engine/WbSimulationCluster.cpp"
edit(cluster, '#include "WbSimulationCluster.hpp"',
     'extern "C" void h6_p0_trace(const char *, unsigned long long);\n#include "WbSimulationCluster.hpp"')
edit(cluster, '  // every step, we need to save contact points in',
     '  h6_p0_trace("solver_return", 0);\n  // every step, we need to save contact points in')
edit(cluster, '  dJointGroupEmpty(physicsPluginContactJointGroup());',
     '  h6_p0_trace("plugin_group_retire", 0);\n  dJointGroupEmpty(physicsPluginContactJointGroup());')
edit(cluster, '  dImmersionLinkGroupEmpty(immersionLinkGroup());',
     '  dImmersionLinkGroupEmpty(immersionLinkGroup());\n  h6_p0_trace("step_cleanup_done", 0);')
edit(cluster, '    const int pluginContacts = physicsPlugin->collide(o1, o2);',
     '    h6_p0_trace("plugin_collide_before", 0);\n    const int pluginContacts = physicsPlugin->collide(o1, o2);\n    h6_p0_trace("plugin_collide_after", 0);')
edit(cluster, '    cJointCreationMutex->lock();\n    dJointGroupID group = 0;',
     '    h6_p0_trace("M_before", 0);\n    cJointCreationMutex->lock();\n    h6_p0_trace("M_acquired", 0);\n    dJointGroupID group = 0;')
edit(cluster, '    dJointAttach(contactJoint, b1, b2);\n    cJointCreationMutex->unlock();',
     '    dJointAttach(contactJoint, b1, b2);\n    h6_p0_trace("M_release", 0);\n    cJointCreationMutex->unlock();\n    h6_p0_trace("M_released", 0);')
ctx = "src/webots/ode/WbOdeContext.cpp"
edit(ctx, '#include <cassert>', '#include <cassert>\n#include <cstdlib>\nextern "C" void h6_p0_trace(const char *, unsigned long long);')
edit(ctx, '  if (mNumberOfThreads == 1)\n    dToggleODE_MT(0);',
     '  h6_p0_trace("configured_threads", (unsigned long long)n);\n  if (mNumberOfThreads == 1 && !std::getenv("H6_P0_FORCE_ONE_WORKER"))\n    dToggleODE_MT(0);')
edit(ctx, 'void WbOdeContext::removeBodyContactJointGroup(dBodyID b) {',
     'void WbOdeContext::removeBodyContactJointGroup(dBodyID b) {\n  h6_p0_trace("body_contact_retire", (unsigned long long)(uintptr_t)b);')
edit(ctx, 'WbOdeContext::~WbOdeContext() {',
     'WbOdeContext::~WbOdeContext() {\n  h6_p0_trace("context_teardown", 0);')
world = "src/webots/engine/WbSimulationWorld.cpp"
edit(world, '#include "WbSimulationWorld.hpp"',
     'extern "C" void h6_p0_trace(const char *, unsigned long long);\n#include "WbSimulationWorld.hpp"')
edit(world, '  delete mPhysicsPlugin;\n\n  // this will destroy all the geoms',
     '  h6_p0_trace("plugin_teardown_before", 0);\n  delete mPhysicsPlugin;\n  h6_p0_trace("plugin_teardown_after", 0);\n\n  // this will destroy all the geoms')
edit(world, '  delete mCluster;\n\n  // delete (spaces, worlds) etc.',
     '  h6_p0_trace("cluster_teardown_before", 0);\n  delete mCluster;\n  h6_p0_trace("cluster_teardown_after", 0);\n\n  // delete (spaces, worlds) etc.')
edit(world, '  delete mOdeContext;\n\n  mAddedNode.clear();',
     '  delete mOdeContext;\n  h6_p0_trace("context_teardown_after", 0);\n\n  mAddedNode.clear();')
print("H6_P0_OBSERVATION_PATCH_COMPLETE", PIN)

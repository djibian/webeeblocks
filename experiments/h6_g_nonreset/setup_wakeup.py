#!/usr/bin/env python3
"""H6 actual Webots wakeup: only read-only solver observation + ordinary plugin activation."""
from pathlib import Path
import sys
if len(sys.argv) != 3: raise SystemExit("usage: setup_wakeup.py NATIVE_WEBOTS GENERATED_PROJECT")
root, out = map(Path,sys.argv[1:])
header=(root/"include/ode/ode/collision.h").read_text()
if "typedef int dWorldStepFunction(dWorldID, dReal);" not in header:
    raise SystemExit("REFUSED: pinned ODE solver callback return signature changed")
src=root/"src/webots/engine/WbSimulationCluster.cpp"
s=src.read_text()
needle="                            WbWorld::instance()->basicTimeStep() * 0.001, &dWorldStep, spaceUpdateFunc);"
if s.count(needle)!=1: raise SystemExit("REFUSED wrong pinned cluster invocation")
anchor="void WbSimulationCluster::step() {"
if s.count(anchor)!=1: raise SystemExit("REFUSED cluster hook cardinality")
s=s.replace("#include <cassert>", "#include <cassert>\n#include <cstdio>\n#include <cstdlib>")
hook=r'''// H6 WAKEUP ONLY: exact-boundary read-only telemetry of the real solver.
static unsigned long h6WakeTick = 0;
static void h6WakeObserve(dWorldID world, const char *phase) {
  if (!std::getenv("H6_WAKE_CASE")) return;
  WbPhysicsPlugin *const plugin = WbPhysicsPlugin::instance();
  const WbSolid *const solid = plugin ? plugin->findSolidByDef("A") : NULL;
  dBodyID body = solid ? solid->bodyMerger() : NULL;
  if (!body) { std::fprintf(stderr, "H6_WAKE_FATAL missing solver body\n"); std::abort(); }
  const dReal *p=dBodyGetPosition(body), *v=dBodyGetLinearVel(body);
  std::fprintf(stderr,
      "H6_WAKE_SOLVE phase=%s tick=%lu body=%p enabled=%d joints=%d z=%.15g vz=%.15g\n",
      phase,h6WakeTick,(void *)body,dBodyIsEnabled(body),dBodyGetNumJoints(body),(double)p[2],(double)v[2]);
  for (int i=0;i<dBodyGetNumJoints(body);++i) {
    dJointID j=dBodyGetJoint(body,i);
    std::fprintf(stderr, "H6_WAKE_SOLVE_JOINT phase=%s tick=%lu joint=%p type=%d b0=%p b1=%p\n",
       phase,h6WakeTick,(void *)j,dJointGetType(j),
       (void *)dJointGetBody(j,0),(void *)dJointGetBody(j,1));
  }
  std::fflush(stderr);
}
static int h6WakeWorldStep(dWorldID world,dReal dt) {
  ++h6WakeTick;
  h6WakeObserve(world,"pre");
  const int result=dWorldStep(world,dt); // exact original solver, unchanged
  h6WakeObserve(world,"post"); // BEFORE collision detection
  return result; // unchanged original solver result
}

'''
s=s.replace(anchor,hook+anchor).replace(needle,needle.replace("&dWorldStep","&h6WakeWorldStep"))
src.write_text(s)
ctx=root/"src/webots/ode/WbOdeContext.cpp"
c=ctx.read_text()
a="    if (ownerEnabled || (g && !std::strcmp(g, \"1\")))\n      dJointGroupEmpty(it.value());"
if c.count(a)!=2: raise SystemExit("REFUSED expected 2 unchanged G hooks")
extra=r'''    if (std::getenv("H6_WAKE_CASE") && !ownerEnabled && count>0) {
      for(int k=0;k<dBodyGetNumJoints(it.key());++k) {
        dJointID j=dBodyGetJoint(it.key(),k);
        if(dJointGetType(j)!=dJointTypeContact) continue;
        std::fprintf(stderr, "H6_WAKE_RETIRE_JOINT owner=%p group=%p joint=%p b0=%p b1=%p enabled=%d\n",
          (void *)it.key(),(void *)it.value(),(void *)j,
          (void *)dJointGetBody(j,0),(void *)dJointGetBody(j,1),dBodyIsEnabled(it.key()));
      }
    }
'''
c=c.replace(a,extra+a)
ctx.write_text(c)
world=r'''#VRML_SIM R2025a utf8
WorldInfo {
  basicTimeStep 32
  randomSeed 1
  gravity 9.81
  physics "h6_wakeup"
  optimalThreadCount 1
  physicsDisableTime 0
}
Viewpoint {
  orientation 0 1 0 1.57
  position 1.4 0.9 1.5
}
DEF FLOOR Solid {
  translation 0 0 -0.1
  name "floor"
  children [ Shape {
    appearance PBRAppearance { baseColor 0.5 0.5 0.5 roughness 1 }
    geometry Box { size 3 3 0.2 }
  } ]
  boundingObject Box { size 3 3 0.2 }
}
DEF A Solid {
  translation 0 0 0.099
  name "A"
  children [ Shape {
    appearance PBRAppearance { baseColor 0.8 0.2 0.2 roughness 1 }
    geometry Box { size 0.2 0.2 0.2 }
  } ]
  boundingObject Box { size 0.2 0.2 0.2 }
  physics Physics { density -1 mass 0.2 }
}
Robot {
  supervisor TRUE
  name "supervisor"
  controller "h6_wakeup"
}
'''
w=out/"worlds";w.mkdir(parents=True,exist_ok=True)
(w/"h6_wakeup.wbt").write_text(world)
(w/"h6_wakeup_no_initial.wbt").write_text(world.replace("translation 0 0 0.099","translation 0 0 2.0"))
p=out/"plugins/physics/h6_wakeup";p.mkdir(parents=True,exist_ok=True)
(p/"Makefile").write_text("null :=\nspace := $(null) $(null)\nWEBOTS_HOME_PATH?=$(subst $(space),\\ ,$(strip $(subst \\\\,/,$(WEBOTS_HOME))))\ninclude $(WEBOTS_HOME_PATH)/resources/Makefile.include\n")
plugin=r'''#include <plugins/physics.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static dBodyID a=0;
static FILE *f=0;
static unsigned tick=0;
static const char *mode=0;
static void log_body(const char *phase) {
  const dReal *v=dBodyGetLinearVel(a), *x=dBodyGetPosition(a);
  fprintf(f,"H6_WAKE_PLUGIN phase=%s tick=%u enabled=%d z=%.15g vz=%.15g joints=%d\n",
          phase,tick,dBodyIsEnabled(a),(double)x[2],(double)v[2],dBodyGetNumJoints(a));
  for(int i=0;i<dBodyGetNumJoints(a);i++){
    dJointID j=dBodyGetJoint(a,i);
    fprintf(f,"H6_WAKE_PLUGIN_JOINT phase=%s tick=%u joint=%p type=%d b0=%p b1=%p\n",
      phase,tick,(void*)j,dJointGetType(j),(void*)dJointGetBody(j,0),(void*)dJointGetBody(j,1));
  }
  fflush(f);
}
void webots_physics_init(void) {
  mode=getenv("H6_WAKE_CASE");
  const char *path=getenv("H6_WAKE_NATIVE_LOG");
  if(!mode||!path)abort();
  f=fopen(path,"w");if(!f)abort();
  setvbuf(f,NULL,_IOLBF,0);
  a=dWebotsGetBodyFromDEF("A"); if(!a)abort();
  fprintf(f,"H6_WAKE_INIT case=%s body=%p\n",mode,(void*)a);
}
void webots_physics_step(void) {
  ++tick;
  log_body("before");
  if(tick==2 && strcmp(mode,"no_disable")!=0) {
    dBodyDisable(a);
    fprintf(f,"H6_WAKE_ACTION tick=%u op=disable\n",tick);
  } else if(tick==3 && strcmp(mode,"no_wake")!=0) {
    if(strcmp(mode,"no_disable")!=0) {
      dBodyEnable(a);
      fprintf(f,"H6_WAKE_ACTION tick=%u op=enable\n",tick);
    }
    dBodySetLinearVel(a,0,0,-0.5);
    fprintf(f,"H6_WAKE_ACTION tick=%u op=velocity vz=-0.5\n",tick);
  }
  log_body("after");
}
void webots_physics_step_end(void){log_body("step_end_post_collision");}
void webots_physics_cleanup(void){
  if(f){fprintf(f,"H6_WAKE_DONE ticks=%u\n",tick);fclose(f);f=0;}
}
'''
(p/"h6_wakeup.c").write_text(plugin)
ctrl=out/"controllers/h6_wakeup";ctrl.mkdir(parents=True,exist_ok=True)
(ctrl/"h6_wakeup.py").write_text('''from controller import Supervisor
import os,sys,json,math
s=Supervisor()
a=s.getFromDef("A")
assert a is not None
path=os.environ["H6_WAKE_CONTROLLER_LOG"]
with open(path,"w",buffering=1) as f:
    for i in range(12):
        code=s.step(int(s.getBasicTimeStep()))
        if code<0: raise SystemExit("REFUSED early Webots stop")
        row={"frame":i,"time":s.getTime(),"position":a.getPosition(),"velocity":a.getVelocity()}
        if not all(math.isfinite(x) for x in row["position"]+row["velocity"]):
            raise SystemExit("REFUSED nonfinite physics")
        f.write(json.dumps(row,sort_keys=True)+"\\n")
        f.flush();os.fsync(f.fileno())
    f.write("H6_WAKE_CONTROLLER_DONE\\n");f.flush();os.fsync(f.fileno())
print("H6_WAKE_CONTROLLER_DONE",flush=True)
s.simulationQuit(0)
''')
print("H6_WAKEUP_SETUP_OK")

#!/usr/bin/env python3
"""Prepare focused REAL Webots E5 body-delete and Node.loadState fixtures.
Run AFTER pinned #777 prepare_fixture and #780 prepare_p0_fixture.
Plugin group-owned contact and permanent AMotor are genuinely ATTACHED.
All observations are in the same native process while each ID is live.
"""
from pathlib import Path
import sys
if len(sys.argv) != 2:
    raise SystemExit("usage: prepare_e5_fixture.py FIXTURE_ROOT")
root = Path(sys.argv[1])
p = root/"plugins/physics/h6_g_window/h6_g_window.c"
c = p.read_text()
def once(old,new,label):
    global c
    if c.count(old)!=1:
        raise SystemExit("REFUSED E5 fixture %s count=%d"%(label,c.count(old)))
    c = c.replace(old,new)
once("static int r_enabled = 0;", '''static int r_enabled = 0;
static dJointGroupID e5_group = 0;
static dJointID e5_plugin_contact = 0;
static dJointID e5_plugin_permanent = 0;
static dJointFeedback e5_feedback;
static int e5_feedback_this_step = 0;
static const char *e5_case = 0;''',"globals")
once('  r_enabled = r && strcmp(r, "1") == 0;',r'''  e5_case = getenv("H6_E5_CASE");
  if (!e5_case || (strcmp(e5_case, "body") && strcmp(e5_case, "reset")))
    abort();
  dBodyID foreign = dWebotsGetBodyFromDEF("FOREIGN");
  if (!foreign) { fprintf(stderr, "H6_E5_PLUGIN REFUSED missing real FOREIGN body\n"); abort(); }
  dWorldID e5_world = dBodyGetWorld(target);
  e5_group = dJointGroupCreate(0);
  dContact ec = {0};
  ec.surface.mu = 0;
  ec.geom.normal[2] = 1;
  const dBodyID attached = strcmp(e5_case,"body") == 0 ? foreign : target;
  const dReal *pos = dBodyGetPosition(attached);
  for (int k=0;k<3;k++) ec.geom.pos[k]=pos[k];
  ec.geom.depth = 0;
  e5_plugin_contact = dJointCreateContact(e5_world,e5_group,&ec);
  dJointAttach(e5_plugin_contact,attached,0);
  if (dJointGroupGetCount(e5_group)!=1 ||
      dJointGetBody(e5_plugin_contact,0)!=attached) abort();
  h6_p0_trace("E5_plugin_attached_group_before",
              (unsigned long long)(size_t)e5_plugin_contact);
  e5_plugin_permanent = dJointCreateAMotor(e5_world,0);
  dJointAttach(e5_plugin_permanent,target,0);
  if (dJointGetBody(e5_plugin_permanent,0)!=target) abort();
  h6_p0_trace("E5_plugin_permanent_before",
              (unsigned long long)(size_t)e5_plugin_permanent);
  r_enabled = r && strcmp(r, "1") == 0;''',"plugin init real attached witnesses")
once("  ++tick;",r'''  ++tick;
  if (e5_plugin_contact && e5_group) {
    fprintf(stderr,"H6_E5_PLUGIN_STEP case=%s tick=%lu group_count=%d group_b0=%p group_b1=%p motor_b0=%p\n",
            e5_case,tick,dJointGroupGetCount(e5_group),
            (void*)dJointGetBody(e5_plugin_contact,0),
            (void*)dJointGetBody(e5_plugin_contact,1),
            (void*)dJointGetBody(e5_plugin_permanent,0));
    h6_p0_trace("E5_plugin_attached_group_live",
                (unsigned long long)(size_t)e5_plugin_contact);
  }
  // Feedback is stored in plugin-owned stable memory; never dereference
  // the selected joint after solver/retirement.
  e5_feedback_this_step=0;
  memset(&e5_feedback,0,sizeof(e5_feedback));
  for (int i=0;i<dBodyGetNumJoints(target);i++) {
    dJointID j=dBodyGetJoint(target,i);
    if (j==e5_plugin_contact || dJointGetType(j)!=dJointTypeContact)
      continue;
    dBodyID a=dJointGetBody(j,0), b=dJointGetBody(j,1);
    if ((a==target && !b) || (b==target && !a)) {
      dJointSetFeedback(j,&e5_feedback);
      e5_feedback_this_step=1;
      h6_p0_trace("E5_AC_feedback_installed",(unsigned long long)(size_t)j);
      break;
    }
  }
  if (tick>38 && strcmp(e5_case,"body")==0 && !dBodyIsEnabled(target)) {
    dBodyEnable(target); // explicitly forced wakeup, never spontaneous proof
    h6_p0_trace("E5_owner_wakeup_forced",0);
  }''',"contact feedback pre-solver")
once("void webots_physics_step_end(void) {",r'''void webots_physics_step_end(void) {
  if (e5_feedback_this_step) {
    const double f = fabs((double)e5_feedback.f1[0])+
      fabs((double)e5_feedback.f1[1])+fabs((double)e5_feedback.f1[2]);
    fprintf(stderr,"H6_E5_AC_SOLVER case=%s tick=%lu forceL1=%.17g\n",
            e5_case,tick,f);
    h6_p0_trace("E5_AC_solver_feedback",0);
  }''',"feedback post-solver")
once("void webots_physics_cleanup(void) {",r'''void webots_physics_cleanup(void) {
  if (e5_plugin_contact) {
    // Last permitted dereference: both objects still alive, BEFORE group empty.
    fprintf(stderr,"H6_E5_PLUGIN_CLEANUP case=%s count=%d contact_b0=%p contact_b1=%p motor_b0=%p\n",
            e5_case,dJointGroupGetCount(e5_group),
            (void*)dJointGetBody(e5_plugin_contact,0),
            (void*)dJointGetBody(e5_plugin_contact,1),
            (void*)dJointGetBody(e5_plugin_permanent,0));
    if (dJointGroupGetCount(e5_group)!=1) abort();
    dJointGroupEmpty(e5_group);
    h6_p0_trace("E5_plugin_group_empty",0);
    if (dJointGroupGetCount(e5_group)!=0) abort();
    e5_plugin_contact=0; // NEVER inspect the freed ID after group empty.
    dJointGroupDestroy(e5_group);
    e5_group=0;
  }
  if (e5_plugin_permanent) {
    // Native standalone plugin joint: only its legitimate owner deletes it.
    dJointDestroy(e5_plugin_permanent);
    h6_p0_trace("E5_plugin_permanent_destroyed",0);
    e5_plugin_permanent=0;
  }''',"plugin cleanup native")
p.write_text(c)

foreign = '''DEF FOREIGN Solid {
  translation 0 0 0.302
  name "foreign"
  children [
    Shape {
      appearance PBRAppearance { baseColor 0.1 0.3 0.8 roughness 1 }
      geometry Box { size 0.2 0.2 0.2 }
    }
  ]
  boundingObject Box { size 0.2 0.2 0.2 }
  physics Physics { mass 0.12 }
}
'''
for n in (1,2):
    base=root/f"worlds/h6_p0_workers{n}.wbt"
    text=base.read_text()
    if text.count("DEF TARGET Solid {")!=1:
        raise SystemExit("REFUSED target world anchor workers%d"%n)
    for case in ("body","reset"):
        out=root/f"worlds/h6_e5_{case}_workers{n}.wbt"
        out.write_text(text.replace("DEF TARGET Solid {",foreign+"DEF TARGET Solid {"))
        print("E5_WORLD",str(out),n,case)

controller=root/"controllers/h6_g_window/h6_g_window.py"
controller.write_text('''#!/usr/bin/env python3
"""Real Supervisor deletion and Node.loadState; no synthetic reset flag."""
import os
from controller import Supervisor
robot=Supervisor()
target=robot.getFromDef("TARGET")
foreign=robot.getFromDef("FOREIGN")
if target is None or foreign is None: raise SystemExit("E5_REFUSED missing nodes")
case=os.environ.get("H6_E5_CASE")
if case not in ("body","reset"): raise SystemExit("E5_REFUSED case")
dt=int(robot.getBasicTimeStep())
print("H6_E5_CONTROLLER started case="+case,flush=True)
if case=="reset":
    target.saveState("e5_provenance")
    print("H6_E5_CONTROLLER saved_node_state",flush=True)
for i in range(36):
    if robot.step(dt)==-1: raise SystemExit("E5_REFUSED premature stop")
print("H6_E5_CONTROLLER operation_begin case="+case+" t="+str(robot.getTime()),flush=True)
if case=="body":
    foreign.remove()
    print("H6_E5_CONTROLLER foreign_remove_requested",flush=True)
else:
    target.loadState("e5_provenance")
    print("H6_E5_CONTROLLER target_loadState_requested",flush=True)
for i in range(10):
    if robot.step(dt)==-1: raise SystemExit("E5_REFUSED post-operation stop")
print("H6_E5_CONTROLLER operation_complete case="+case,flush=True)
robot.simulationQuit(0)
''')
print("H6_E5_REAL_FIXTURES_READY")

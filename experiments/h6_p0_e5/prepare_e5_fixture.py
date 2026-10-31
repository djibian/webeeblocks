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
static dJointID e5_plugin_standalone = 0;
static dJointID e5_plugin_permanent = 0;
static dJointFeedback e5_feedback[32];
static int e5_feedback_count = 0;
static dBodyID e5_contact_c = 0;
static const char *e5_case = 0;''',"globals")
once('  r_enabled = r && strcmp(r, "1") == 0;',r'''  e5_case = getenv("H6_E5_CASE");
  if (!e5_case || (strcmp(e5_case, "body") && strcmp(e5_case, "reset")))
    abort();
  dBodyID foreign = dWebotsGetBodyFromDEF("FOREIGN");
  if (!foreign) { fprintf(stderr, "H6_E5_PLUGIN REFUSED missing real FOREIGN body\n"); abort(); }
  if (strcmp(e5_case,"body")==0) {
    e5_contact_c=dWebotsGetBodyFromDEF("CONTACT_C");
    if (!e5_contact_c) abort();
  }
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
  // Attached plugin standalone CONTACT: on reset(id) original Webots
  // detaches and individually destroys it, unlike a group-owned contact.
  e5_plugin_standalone = dJointCreateContact(e5_world,0,&ec);
  dJointAttach(e5_plugin_standalone,attached,0);
  if (dJointGetBody(e5_plugin_standalone,0)!=attached) abort();
  h6_p0_trace("E5_plugin_attached_standalone_before",
              (unsigned long long)(size_t)e5_plugin_standalone);
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
  // D1 geometry reused, but all execution is new P0: feedback on REAL A-C.
  // Controlled test-only wake and closing velocity for first solver after B
  // (3 presteps, post-delete tick 4). No engine registry mutation here.
  e5_feedback_count=0;
  if (!strcmp(e5_case,"body") && tick==4) {
    for (int i=0;i<dBodyGetNumJoints(target);i++) {
      dJointID j=dBodyGetJoint(target,i);
      if (j==e5_plugin_contact || j==e5_plugin_standalone ||
          dJointGetType(j)!=dJointTypeContact) continue;
      const dBodyID a=dJointGetBody(j,0), b=dJointGetBody(j,1);
      if (!((a==target && b==e5_contact_c) ||
            (b==target && a==e5_contact_c))) continue;
      if (e5_feedback_count>=32) abort();
      memset(&e5_feedback[e5_feedback_count],0,sizeof(dJointFeedback));
      dJointSetFeedback(j,&e5_feedback[e5_feedback_count]);
      ++e5_feedback_count;
      h6_p0_trace("E5_AC_feedback_installed",(unsigned long long)(size_t)j);
    }
    if (e5_feedback_count) {
      if (!dBodyIsEnabled(target)) {
        dBodyEnable(target);
        h6_p0_trace("E5_owner_wakeup_forced",0);
      }
      const dReal *ap=dBodyGetPosition(target), *cp=dBodyGetPosition(e5_contact_c);
      const double dx=cp[0]-ap[0], dy=cp[1]-ap[1], dz=cp[2]-ap[2];
      const double distance=sqrt(dx*dx+dy*dy+dz*dz);
      if(distance<1e-7)abort();
      dBodySetLinearVel(e5_contact_c,0,0,0);
      dBodySetLinearVel(target,6*dx/distance,6*dy/distance,6*dz/distance);
      h6_p0_trace("E5_AC_excited",(unsigned long long)e5_feedback_count);
    }
  }''',"contact feedback pre-solver")
once("void webots_physics_step_end(void) {",r'''void webots_physics_step_end(void) {
  if (!strcmp(e5_case,"body") && tick==4) {
    double f=0;
    for (int i=0;i<e5_feedback_count;i++) for (int k=0;k<3;k++)
      f += fabs((double)e5_feedback[i].f1[k]);
    fprintf(stderr,"H6_E5_AC_SOLVER case=%s tick=%lu forceL1=%.17g\n",
            e5_case,tick,f);
    h6_p0_trace("E5_AC_solver_feedback",(unsigned long long)e5_feedback_count);
  }
  if (!strcmp(e5_case,"body") && tick==2) {
    // EXACT D1 test-only sleep intervention, not spontaneous
    dBodyDisable(target);
    h6_p0_trace("E5_owner_sleep_forced_before_delete",0);
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
  // In RESET case, original Webots reset(id) already destroyed this
  // standalone contact. Its handle is now stale: NEVER use or dereference it.
  if (e5_plugin_standalone && !strcmp(e5_case,"body")) {
    dJointDestroy(e5_plugin_standalone);
    h6_p0_trace("E5_plugin_standalone_owner_free",0);
  } else if (e5_plugin_standalone && !strcmp(e5_case,"reset")) {
    h6_p0_trace("E5_plugin_standalone_reset_no_use",0);
  }
  e5_plugin_standalone=0;
  if (e5_plugin_permanent) {
    // Native standalone plugin joint: only its legitimate owner deletes it.
    dJointDestroy(e5_plugin_permanent);
    h6_p0_trace("E5_plugin_permanent_destroyed",0);
    e5_plugin_permanent=0;
  }''',"plugin cleanup native")
# E5 is a separate experiment. E1–E4 public worker probes must NOT
# accidentally destroy a plugin-owned live standalone joint selected in
# a previous frame. They have already been qualified on PR #780.
probe = "if (h6_selected && h6_p0_thread_attempts++ == 0) {"
if c.count(probe)!=1:
    raise SystemExit("REFUSED E5 probe-isolation anchor")
c=c.replace(probe,"if (0 && h6_selected && h6_p0_thread_attempts++ == 0) {")
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
# Use the already discriminating D1 geometry/order, not D1's code patch.
# A is TARGET (listed last), B is FOREIGN, C is CONTACT_C; gravity zero.
d1C = '''DEF CONTACT_C Solid {
  translation -0.14 -0.12 0.2
  name "contact_C"
  children [ Shape { appearance PBRAppearance {
    baseColor 0.1 0.1 0.9 roughness 1 }
    geometry Box { size 0.2 0.2 0.2 } } ]
  boundingObject Box { size 0.2 0.2 0.2 }
  physics Physics { mass 0.12 }
}
'''
d1B = '''DEF FOREIGN Solid {
  translation -0.14 0.12 0.2
  name "foreign"
  children [ Shape { appearance PBRAppearance {
    baseColor 0.1 0.9 0.1 roughness 1 }
    geometry Box { size 0.2 0.2 0.2 } } ]
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
        if case=="reset":
            world=text.replace("DEF TARGET Solid {",foreign+"DEF TARGET Solid {")
        else:
            anchor='DEF TARGET Solid {\n  translation 0 0 0.105\n  rotation 0 1 0 0.1'
            if text.count(anchor)!=1 or text.count('  basicTimeStep 32')!=1:
                raise SystemExit("REFUSED D1 source geometry anchors")
            world=text.replace(anchor,d1C+d1B+
                               'DEF TARGET Solid {\n  translation 0 0 0.2\n  rotation 0 1 0 0')
            world=world.replace('  basicTimeStep 32','  basicTimeStep 32\n  gravity 0')
            world=world.replace('DEF FAR_TARGET Solid {\n  translation 8 0 0.105',
                                'DEF FAR_TARGET Solid {\n  translation 8 0 0.09')
        out.write_text(world)
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
for i in range(3 if case=="body" else 36):
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

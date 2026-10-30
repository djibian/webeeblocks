/* Independent native pre-solver observation on real Webots R2025a.
 * Environment H6_G_WINDOW_R=1 adds optional attachment-selective R analogue
 * within a PHYSICS PLUGIN, NOT a Webots core patch. A=0 is strictly read-only.
 * Never interpret this as a test of native G or native R+G.
 */
#include <plugins/physics.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

static dBodyID target = 0;
static FILE *trace = NULL;
static unsigned long tick = 0;
static int r_enabled = 0;
static int reset_seen = 0;
void webots_physics_init(void) {
  const char *p = getenv("H6_G_WINDOW_NATIVE_LOG");
  const char *r = getenv("H6_G_WINDOW_R");
  if (!p || !*p) { fprintf(stderr, "H6_G_WINDOW REFUSED native log path missing\n"); abort(); }
  trace = fopen(p, "a");
  if (!trace) { perror("H6_G_WINDOW native fopen"); abort(); }
  setvbuf(trace, NULL, _IOLBF, 0);
  target = dWebotsGetBodyFromDEF("TARGET");
  if (!target) { fprintf(trace, "H6_G_WINDOW REFUSED target body not found\n"); abort(); }
  r_enabled = r && strcmp(r, "1") == 0;
  fprintf(trace, "H6_G_WINDOW event=plugin_init mode=%s body=%p\n", r_enabled ? "R" : "A", (void *)target);
}
void webots_physics_step(void) {
  if (!target) abort();
  ++tick;
  const dReal *x = dBodyGetPosition(target);
  const dReal *v = dBodyGetLinearVel(target);
  const dReal *w = dBodyGetAngularVel(target);
  int n = dBodyGetNumJoints(target), contacts = 0, foreign = 0;
  int teleported = x[2] > 0.5;
  for (int i = 0; i < n; ++i) {
    dJointID j = dBodyGetJoint(target, i);
    if (dJointGetType(j) != dJointTypeContact) continue;
    ++contacts;
    if (dJointGetBody(j, 0) != target) ++foreign;
    fprintf(trace, "H6_G_WINDOW event=attached tick=%lu pre=%d joint=%p b0=%p b1=%p x=%.9g z=%.9g\n",
            tick, teleported, (void *)j, (void *)dJointGetBody(j, 0),
            (void *)dJointGetBody(j, 1), (double)x[0], (double)x[2]);
  }
  fprintf(trace, "H6_G_WINDOW event=pre tick=%lu reset=%d enabled=%d joints=%d contacts=%d foreign=%d x=%.9g y=%.9g z=%.9g vx=%.12g vy=%.12g vz=%.12g wx=%.12g wy=%.12g wz=%.12g\n",
          tick, teleported, dBodyIsEnabled(target), n, contacts, foreign,
          (double)x[0], (double)x[1], (double)x[2],
          (double)v[0], (double)v[1], (double)v[2],
          (double)w[0], (double)w[1], (double)w[2]);
  if (teleported && !reset_seen) {
    reset_seen = 1;
    fprintf(trace, "H6_G_WINDOW event=reset_boundary tick=%lu active_attached=%d\n", tick, contacts);
  }
  if (teleported && r_enabled) {
    /* Only detached contacts, not motors, body enable state, non-contact joints. */
    for (int i = dBodyGetNumJoints(target) - 1; i >= 0; --i) {
      dJointID j = dBodyGetJoint(target, i);
      if (dJointGetType(j) != dJointTypeContact) continue;
      dJointAttach(j, 0, 0);
      fprintf(trace, "H6_G_WINDOW event=r_detach tick=%lu joint=%p\n", tick, (void *)j);
    }
  }
}
void webots_physics_step_end(void) {
  if (!target) abort();
  const dReal *v = dBodyGetLinearVel(target);
  const dReal *w = dBodyGetAngularVel(target);
  fprintf(trace, "H6_G_WINDOW event=post tick=%lu vx=%.12g vy=%.12g vz=%.12g wx=%.12g wy=%.12g wz=%.12g\n",
          tick, (double)v[0], (double)v[1], (double)v[2], (double)w[0], (double)w[1], (double)w[2]);
}
void webots_physics_cleanup(void) {
  if (trace) {
    fprintf(trace, "H6_G_WINDOW event=plugin_cleanup ticks=%lu reset_seen=%d\n", tick, reset_seen);
    fclose(trace);
    trace = NULL;
  }
}

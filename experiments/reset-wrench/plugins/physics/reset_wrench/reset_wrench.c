/* #637 — lab-only, read-only Webots R2025a / public ODE wrench probe.
 * No callback may modify ODE, trigger collisions, allocate, or perform I/O.
 * Mono-thread only; results do not qualify a product build or RESET repair.
 */
#include <plugins/physics.h>
#include <ode/ode.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CAPACITY 32768
#define JOINT_LIMIT 16

typedef struct {
  int valid, enabled, gravity_mode, joints, contacts, joint_truncated;
  double mass, linear_damping, angular_damping, max_angular_speed;
  double gravity[3], position[3], rotation[12], velocity[3], omega[3];
  double force[3], torque[3], inertia[12];
} Snapshot;
typedef struct {
  double time_ms;
  Snapshot before, after;
  int has_after;
} Frame;
static Frame frames[CAPACITY]; /* fixed storage, about 27 MiB */
static unsigned count, overflow;
static int capture, body_missing;
static dBodyID body;

static void copy_real(double *out, const dReal *in, unsigned n) {
  unsigned i;
  for (i = 0; i < n; ++i)
    out[i] = in[i];
}
static void sample(Snapshot *s) {
  dMass mass;
  unsigned i;
  int n;
  memset(s, 0, sizeof(*s));
  if (!body) {
    body_missing = 1;
    return;
  }
  s->valid = 1;
  s->enabled = dBodyIsEnabled(body);
  s->gravity_mode = dBodyGetGravityMode(body);
  dBodyGetMass(body, &mass);
  s->mass = mass.mass;
  copy_real(s->inertia, mass.I, 12);
  copy_real(s->position, dBodyGetPosition(body), 3);
  copy_real(s->rotation, dBodyGetRotation(body), 12);
  copy_real(s->velocity, dBodyGetLinearVel(body), 3);
  copy_real(s->omega, dBodyGetAngularVel(body), 3);
  copy_real(s->force, dBodyGetForce(body), 3);
  copy_real(s->torque, dBodyGetTorque(body), 3);
  {
    dVector3 gravity;
    dWorldGetGravity(dBodyGetWorld(body), gravity);
    copy_real(s->gravity, gravity, 3);
  }
  s->linear_damping = dBodyGetLinearDamping(body);
  s->angular_damping = dBodyGetAngularDamping(body);
  s->max_angular_speed = dBodyGetMaxAngularSpeed(body);
  n = dBodyGetNumJoints(body);
  s->joints = n;
  s->contacts = 0;
  s->joint_truncated = n > JOINT_LIMIT;
  if (!s->joint_truncated)
    for (i = 0; i < (unsigned)n; ++i)
      if (dJointGetType(dBodyGetJoint(body, (int)i)) == dJointTypeContact)
        ++s->contacts;
}

void webots_physics_init(void) {
  const char *enabled = getenv("WEBEEBLOCKS_WRENCH_CAPTURE");
  const char *name = getenv("WEBEEBLOCKS_WRENCH_DEF");
  capture = enabled && strcmp(enabled, "1") == 0;
  if (capture)
    body = dWebotsGetBodyFromDEF(name && *name ? name : "WRENCH_BODY");
}
void webots_physics_step(void) {
  Frame *f;
  if (!capture)
    return;
  if (count == CAPACITY) {
    ++overflow;
    return;
  }
  f = &frames[count++];
  f->time_ms = dWebotsGetTime();
  sample(&f->before);
}
void webots_physics_step_end(void) {
  if (capture && count && !frames[count - 1].has_after) {
    sample(&frames[count - 1].after);
    frames[count - 1].has_after = 1;
  }
}
static void fields(FILE *out, const char *prefix, unsigned n) {
  unsigned i;
  for (i = 0; i < n; ++i)
    fprintf(out, ",%s%u", prefix, i);
}
static void values(FILE *out, const double *a, unsigned n) {
  unsigned i;
  for (i = 0; i < n; ++i)
    fprintf(out, ",%.17g", a[i]);
}
static void row(FILE *out, unsigned index, const Frame *f,
                const Snapshot *s, const char *phase, int complete) {
  fprintf(out, "%u,%.17g,%s,%d,%d,%d,%d,%d,%d,%d,%.17g,%.17g,%.17g,%.17g",
          index, f->time_ms, phase, complete && s->valid, s->enabled,
          s->gravity_mode, s->joints, s->contacts, s->joint_truncated,
          f->has_after, s->mass, s->linear_damping, s->angular_damping,
          s->max_angular_speed);
  values(out, s->gravity, 3);
  values(out, s->position, 3);
  values(out, s->rotation, 12);
  values(out, s->velocity, 3);
  values(out, s->omega, 3);
  values(out, s->force, 3);
  values(out, s->torque, 3);
  values(out, s->inertia, 12);
  fputc('\n', out);
}
void webots_physics_cleanup(void) {
  unsigned i;
  FILE *out;
  const char *path = getenv("WEBEEBLOCKS_WRENCH_FILE");
  if (!capture || !path || !*path)
    return;
  out = fopen(path, "wx"); /* no silent overwrite */
  if (!out) {
    fprintf(stderr, "WRENCH_CAPTURE_UNAVAILABLE\n");
    return;
  }
  fputs("frame,time_ms,phase,valid,enabled,gravity_mode,joints,contacts,joint_truncated,has_after,mass,linear_damping,angular_damping,max_angular_speed", out);
  fields(out, "g", 3); fields(out, "p", 3); fields(out, "r", 12);
  fields(out, "v", 3); fields(out, "w", 3);
  fields(out, "f", 3); fields(out, "t", 3); fields(out, "I", 12);
  fputc('\n', out);
  for (i = 0; i < count; ++i) {
    row(out, i, &frames[i], &frames[i].before, "pre", 1);
    row(out, i, &frames[i], &frames[i].after, "post", frames[i].has_after);
  }
  fprintf(out, "#frames=%u,overflow=%u,body_missing=%d\n", count, overflow, body_missing);
  if (fclose(out) != 0)
    fprintf(stderr, "WRENCH_CAPTURE_PARTIAL\n");
}

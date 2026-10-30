// H6 independent audit: RESET-local cleanup candidates, actual bundled Webots ODE.
// Not a Webots scheduler proof. Group count, not RSS, is the resource oracle.
#include <ode/ode.h>
#include <ode/ode_MT.h>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <mutex>
#include <vector>

static void require(bool ok, const char *why) {
  if (!ok) { std::fprintf(stderr, "H6_MEMORY_REFUSED %s\n", why); std::exit(2); }
}
static void mass(dBodyID b) {
  dMass m; dMassSetSphereTotal(&m, 0.05, 0.035); dBodySetMass(b, &m);
}
static bool touches(dJointID j, dBodyID b) {
  return dJointGetBody(j, 0) == b || dJointGetBody(j, 1) == b;
}
static dJointID contact(dWorldID w, dJointGroupID g, dGeomID x, dGeomID y,
                        dBodyID a, dBodyID b) {
  dContact c{};
  require(dCollide(x, y, 1, &c.geom, sizeof(dContactGeom)) == 1 && c.geom.depth > 0, "contact geometry");
  c.surface.mode = dContactSoftERP | dContactSoftCFM;
  c.surface.soft_erp = 0.85; c.surface.soft_cfm = 0.00001; c.surface.mu = 0;
  dJointID j = dJointCreateContact(w, g, &c);
  require(j != nullptr, "contact creation");
  dJointAttach(j, a, b);
  return j;
}
static int reset_target(dBodyID b) {
  // Copy first because detaching mutates the body's adjacency list.
  std::vector<dJointID> found;
  for (int i = 0, n = dBodyGetNumJoints(b); i < n; ++i) {
    dJointID j = dBodyGetJoint(b, i);
    if (dJointGetType(j) == dJointTypeContact) found.push_back(j);
  }
  for (dJointID j : found) {
    require(touches(j, b), "RESET selected alien contact");
    dJointAttach(j, nullptr, nullptr);
    dJointDestroy(j);  // In-group joint: deliberately not freed.
  }
  return static_cast<int>(found.size());
}
struct Scene {
  dWorldID w; dJointGroupID g; dBodyID a,b,c;
  dGeomID ga,gb,gc; dJointID permanent;
  Scene() {
    w = dWorldCreate(); require(w != nullptr, "world");
    dWorldSetGravity(w, 0, 0, 0);
    g = dJointGroupCreate(0); require(g != nullptr, "group");
    a = dBodyCreate(w); b = dBodyCreate(w); c = dBodyCreate(w);
    mass(a); mass(b); mass(c);
    dBodySetPosition(a,0,0,0); dBodySetPosition(b,0.05,0,0); dBodySetPosition(c,-0.05,0,0);
    ga=dCreateSphere(0,0.035); gb=dCreateSphere(0,0.035); gc=dCreateSphere(0,0.035);
    dGeomSetBody(ga,a); dGeomSetBody(gb,b); dGeomSetBody(gc,c);
    permanent=dJointCreateBall(w,nullptr);
    require(permanent != nullptr, "permanent");
    dJointAttach(permanent,b,c);
    dBodyDisable(a);
  }
  ~Scene() {
    dJointGroupDestroy(g); dJointDestroy(permanent);
    dGeomDestroy(ga); dGeomDestroy(gb); dGeomDestroy(gc);
    dBodyDestroy(a); dBodyDestroy(b); dBodyDestroy(c); dWorldDestroy(w);
  }
  Scene(const Scene&) = delete; Scene& operator=(const Scene&) = delete;
};
static void memory_arm(const char *name, bool legit, bool clean_all, bool empty_only) {
  Scene s;
  if (legit) contact(s.w,s.g,s.ga,s.gc,s.a,s.c);
  constexpr int N = 8192;
  for (int i=1;i<=N;++i) {
    dBodySetPosition(s.b,0.05,0,0);
    contact(s.w,s.g,s.ga,s.gb,s.a,s.b);
    dBodyDisable(s.a);
    dBodySetPosition(s.b,2,0,0);
    dBodySetLinearVel(s.b,0,0,0); dBodySetAngularVel(s.b,0,0,0);
    require(reset_target(s.b)==1,"R failed to detach target");
    require(dBodyGetNumJoints(s.b)==1 && touches(s.permanent,s.b), "permanent joint altered");
    // Test at a post-solver boundary, not during a solver.
    // The full-group strategy may erase a legitimate A-C contact.
    if (clean_all || (empty_only && !legit)) dJointGroupEmpty(s.g);
    const int expected = clean_all || (empty_only && !legit) ? 0 : i + (legit?1:0);
    require(dJointGroupGetCount(s.g)==expected, "unexpected allocation count");
    if (legit && (clean_all || (empty_only && !legit))) {
      require(dBodyGetNumJoints(s.c)==1, "bad permanent joint count");
    }
    if (i==1 || i==64 || i==512 || i==2048 || i==8192) {
      const bool survives = dBodyGetNumJoints(s.c)==(legit && !clean_all ? 2 : 1);
      std::printf("{\"arm\":\"%s\",\"cycle\":%d,\"group_allocated\":%d,\"legitimate_survives\":%d,\"permanent_survives\":1,\"owner_disabled\":%d}\n",
        name,i,dJointGroupGetCount(s.g),static_cast<int>(survives),!dBodyIsEnabled(s.a));
    }
  }
  if (legit && clean_all) require(dBodyGetNumJoints(s.c)==1, "marked-group negative not reproduced");
  if (legit && !clean_all) require(dBodyGetNumJoints(s.c)==2, "legitimate joint unexpectedly lost");
  std::printf("{\"arm\":\"%s\",\"stage\":\"after_group_empty\",\"before\":%d",name,dJointGroupGetCount(s.g));
  dJointGroupEmpty(s.g);
  require(dJointGroupGetCount(s.g)==0,"group cleanup ineffective");
  std::puts(",\"after\":0}");
}
static double ordinary_speed(bool unconditional_g) {
  dWorldID w=dWorldCreate(); dWorldSetGravity(w,0,0,0);
  dJointGroupID old=dJointGroupCreate(0);
  dBodyID owner=dBodyCreate(w), moving=dBodyCreate(w); mass(owner); mass(moving);
  dBodySetPosition(owner,0,0,0); dBodySetPosition(moving,.05,0,0);
  dGeomID go=dCreateSphere(0,.035), gm=dCreateSphere(0,.035);
  dGeomSetBody(go,owner);dGeomSetBody(gm,moving);
  contact(w,old,go,gm,owner,moving);
  dBodyDisable(owner);
  if(unconditional_g) dJointGroupEmpty(old);
  dWorldStep(w,.01);
  const dReal *v=dBodyGetLinearVel(moving);
  const double speed=std::sqrt(v[0]*v[0]+v[1]*v[1]+v[2]*v[2]);
  std::printf("{\"arm\":\"no_RESET\",\"G\":%d,\"speed\":%.17g,\"group_allocated\":%d}\n",
              int(unconditional_g),speed,dJointGroupGetCount(old));
  dJointGroupDestroy(old);dGeomDestroy(go);dGeomDestroy(gm);
  dBodyDestroy(owner);dBodyDestroy(moving);dWorldDestroy(w);
  return speed;
}
struct MtState {
  dWorldID world; dJointGroupID group; dBodyID a,b;
  std::mutex creation_mutex;
  int created=0;
};
static void near_callback(void *user, dGeomID x, dGeomID y) {
  auto *s=static_cast<MtState*>(user);
  dBodyID a=dGeomGetBody(x), b=dGeomGetBody(y);
  if(!a || !b) return;
  dContact c{};
  if(dCollide(x,y,1,&c.geom,sizeof(dContactGeom))<1) return;
  c.surface.mode=dContactSoftERP|dContactSoftCFM;
  c.surface.soft_erp=.85;c.surface.soft_cfm=.00001;c.surface.mu=0;
  std::lock_guard<std::mutex> lock(s->creation_mutex);
  dJointID j=dJointCreateContact(s->world,s->group,&c);
  require(j!=nullptr,"MT joint");
  dJointAttach(j,a,b);s->created++;
}
static void mt_boundary(int count) {
  dToggleODE_MT(count);
  dWorldID w=dWorldCreate(); dWorldSetGravity(w,0,0,0);
  dSpaceID space=dSimpleSpaceCreate(nullptr);
  dJointGroupID g=dJointGroupCreate(0);
  dBodyID a=dBodyCreate(w), b=dBodyCreate(w);
  mass(a);mass(b);
  dGeomID ga=dCreateSphere(space,.035),gb=dCreateSphere(space,.035);
  dGeomSetBody(ga,a);dGeomSetBody(gb,b);
  MtState ctx{};
  ctx.world=w;ctx.group=g;ctx.a=a;ctx.b=b;
  int invalidated=0, created=0;
  for(int i=0;i<64;++i) {
    dBodySetPosition(a,0,0,0);dBodySetPosition(b,.05,0,0);
    dBodySetLinearVel(a,0,0,0);dBodySetLinearVel(b,0,0,0);
    dWorldStepAndSpaceCollide(space,&ctx,near_callback,w,.01,&dWorldStep,nullptr);
    { std::lock_guard<std::mutex> lock(ctx.creation_mutex);
      const int before=dJointGroupGetCount(g);
      require(before>=1,"MT no callback after completed step");
      invalidated+=reset_target(b);
      require(dBodyGetNumJoints(b)==0,"MT R did not detach");
      dJointGroupEmpty(g);
      require(dJointGroupGetCount(g)==0,"MT group not empty after completed step");
    }
  }
  created=ctx.created;
  require(created==invalidated && created>=64,"MT count mismatch");
  std::printf("{\"arm\":\"step_boundary\",\"threads\":%d,\"steps\":64,\"contacts\":%d,\"reset_detached\":%d,\"end_allocated\":%d}\n",
              count,created,invalidated,dJointGroupGetCount(g));
  dJointGroupDestroy(g);dSpaceDestroy(space);
  dBodyDestroy(a);dBodyDestroy(b);dWorldDestroy(w);
  dToggleODE_MT(0);
}
int main(int argc,char **argv) {
  require(dInitODE2(0)!=0,"ODE init");
  if(argc==2 && argv[1][0]=='m') {
    mt_boundary(1);mt_boundary(2);
  } else {
    require(argc==1,"usage: probe [mt]");
    memory_arm("R_only_disabled_owner",true,false,false);
    memory_arm("R_marked_cleanup_mixed",true,true,false);
    memory_arm("R_empty_only_mixed",true,false,true);
    memory_arm("R_empty_only_simple",false,false,true);
    const double baseline=ordinary_speed(false);
    const double g=ordinary_speed(true);
    require(baseline>0.5 && g==0,"G ordinary physics contrast absent");
  }
  dCloseODE();
  std::puts("H6_MEMORY_NATIVE_COMPLETED");
}

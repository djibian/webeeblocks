// Source-pin ODE ordering probe: observation only, no modification to ODE or Webots.
#include <ode/ode.h>
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

// The pinned Cyberbotics ODE fork exports the MT entry point, not public dHashSpaceCreate.
// This is a test-only call to the same internal hash-space implementation.
extern dSpaceID dHashSpaceCreate_MT(dSpaceID);

struct CaseData {
  dBodyID a = nullptr, b = nullptr, c = nullptr;
  int abCount = 0, acCount = 0;
  char abFirst = '?';
  const char *label = nullptr;
};

static char identify(dBodyID b, const CaseData &d) {
  return b == d.a ? 'A' : (b == d.b ? 'B' : (b == d.c ? 'C' : '?'));
}

static void near(void *ptr, dGeomID o1, dGeomID o2) {
  auto &d = *static_cast<CaseData *>(ptr);
  dBodyID x = dGeomGetBody(o1), y = dGeomGetBody(o2);
  const char p = identify(x, d), q = identify(y, d);
  if (!((p == 'A' && q == 'B') || (p == 'B' && q == 'A') ||
        (p == 'A' && q == 'C') || (p == 'C' && q == 'A')))
    return;
  dContactGeom contacts[16];
  const int n = dCollide(o1, o2, 16, contacts, sizeof(dContactGeom));
  if (n <= 0) return;
  if ((p == 'A' && q == 'B') || (p == 'B' && q == 'A')) {
    d.abCount += n;
    d.abFirst = p;
  } else {
    d.acCount += n;
  }
  std::printf("H6_ODE_PAIR case=%s first=%c second=%c contacts=%d geom1=%p geom2=%p\n",
              d.label, p, q, n, (void *)o1, (void *)o2);
}

static bool run(const char *label, bool hash, const char *order, bool bigB,
                char expectedAB) {
  dWorldID world = dWorldCreate();
  dSpaceID space = hash ? dHashSpaceCreate_MT(nullptr) : dSimpleSpaceCreate(nullptr);
  CaseData d;
  d.label = label;
  struct Object { char id; dBodyID body; dGeomID geom; };
  std::vector<Object> objs;
  for (const char *p = order; *p; ++p) {
    dBodyID body = dBodyCreate(world);
    const bool big = *p == 'B' && bigB;
    dGeomID geom = dCreateBox(space, big ? 2048.2 : 0.2, 0.2, 0.2);
    if (*p == 'A') {
      d.a = body;
      dBodySetPosition(body, 0, 0, .2);
    } else if (*p == 'B') {
      d.b = body;
      dBodySetPosition(body, big ? -1024.16 : -0.14, 0.12, .2);
    } else {
      d.c = body;
      dBodySetPosition(body, .14, -.12, .2);
    }
    dGeomSetBody(geom, body);
    objs.push_back({*p, body, geom});
  }
  dSpaceCollide(space, &d, near);
  const bool ok = d.abCount > 0 && d.acCount > 0 && d.abFirst == expectedAB;
  std::printf("H6_ODE_ORDER case=%s space=%s insertion=%s bigB=%d AB_first=%c expected=%c AB_contacts=%d AC_contacts=%d verdict=%s\n",
              label, hash ? "hash" : "simple", order, int(bigB), d.abFirst,
              expectedAB, d.abCount, d.acCount, ok ? "PASS" : "FAIL");
  dSpaceDestroy(space);
  dWorldDestroy(world);
  return ok;
}

int main() {
  dInitODE();
  bool ok = true;
  ok &= run("simple_ABC", false, "ABC", false, 'B');
  ok &= run("simple_CBA", false, "CBA", false, 'A');
  ok &= run("simple_big_ABC", false, "ABC", true, 'B');
  ok &= run("hash_big_ABC", true, "ABC", true, 'A');
  dCloseODE();
  if (ok) std::puts("H6_ODE_ORDER_HYPOTHESIS_PASS");
  return ok ? 0 : 91;
}

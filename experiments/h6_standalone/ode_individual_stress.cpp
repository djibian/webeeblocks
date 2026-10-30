// Synthetic native bundled-ODE allocator probe for H6 individual contact lifetime.
// This IS NOT a substitute for Webots scheduler/wakeup/MT qualification.
// A-C legitimate contact and permanent B-C hinge survive B RESET; A-B contact
// is individually dJointDestroy-able because it is created with group=nullptr.
#include <ode/ode.h>
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <malloc.h>
#include <unistd.h>
#include <vector>

static void must(bool ok, const char *msg) {
  if (!ok) { std::fprintf(stderr,"H6_INDIVIDUAL_REFUSED %s\n",msg);std::exit(2); }
}
static void mass(dBodyID b) { dMass m; dMassSetSphereTotal(&m,0.1,0.05); dBodySetMass(b,&m); }
static dJointID make_contact(dWorldID w,dBodyID a,dBodyID b) {
  dContact c{};
  c.surface.mode=dContactSoftERP|dContactSoftCFM;
  c.surface.soft_erp=0.85;c.surface.soft_cfm=0.00001;c.surface.mu=0.0;
  c.geom.depth=0.015;
  c.geom.normal[0]=1.0; c.geom.normal[1]=0; c.geom.normal[2]=0;
  dJointID j=dJointCreateContact(w,nullptr,&c);
  must(j!=nullptr,"standalone joint create");
  dJointAttach(j,a,b);
  return j;
}
static int count_contact(dBodyID b) {
  int n=0;for(int i=0;i<dBodyGetNumJoints(b);++i)
    if(dJointGetType(dBodyGetJoint(b,i))==dJointTypeContact)++n;
  return n;
}
static size_t rss() {
  FILE *f=std::fopen("/proc/self/statm","r"); if(!f)return 0;
  unsigned long resident=0,total=0;
  const int n=std::fscanf(f,"%lu %lu",&total,&resident);
  std::fclose(f);return n==2?resident*static_cast<size_t>(sysconf(_SC_PAGESIZE)):0;
}
struct Measure{size_t used,reserved,rss;};
static Measure emit(int n,dBodyID a,dBodyID b,dBodyID c,dJointGroupID g) {
  const struct mallinfo2 s=mallinfo2();
  const Measure m{static_cast<size_t>(s.uordblks),static_cast<size_t>(s.uordblks+s.hblkhd),rss()};
  std::printf("{\"cycle\":%d,\"A_contact\":%d,\"B_contact\":%d,\"C_contact\":%d,"
              "\"group_joints\":%d,\"active_used_bytes\":%zu,\"reserved_bytes\":%zu,\"rss_bytes\":%zu}\n",
     n,count_contact(a),count_contact(b),count_contact(c),dJointGroupGetCount(g),m.used,m.reserved,m.rss);
  std::fflush(stdout);
  return m;
}
int main() {
  must(dInitODE2(0)!=0,"dInitODE2");
  dWorldID w=dWorldCreate();dWorldSetGravity(w,0,0,0);
  dBodyID a=dBodyCreate(w),b=dBodyCreate(w),c=dBodyCreate(w);
  mass(a);mass(b);mass(c);
  dJointGroupID unused=dJointGroupCreate(0);
  dJointID permanent=dJointCreateBall(w,nullptr);dJointAttach(permanent,b,c);
  dJointID ac=make_contact(w,a,c); // unrelated legitimate contact
  must(count_contact(a)==1&&count_contact(c)==1,"initial live contact");
  Measure warm{}; bool warm_found=false;
  emit(0,a,b,c,unused);
  for(int i=1;i<=8192;++i) {
    dJointID ab=make_contact(w,a,b);
    must(count_contact(a)==2&&count_contact(b)==1,"A-B contact created");
    // Exact unit cleanup: a RESET of B invalidates A-B, not A-C.
    dJointDestroy(ab); // real ODE deallocation, no group-owned arena
    must(count_contact(a)==1&&count_contact(b)==0&&count_contact(c)==1,
         "A-C legitimate contact or B contact count altered");
    must(dBodyGetNumJoints(b)==1&&dBodyGetJoint(b,0)==permanent,
         "B-C permanent articulation changed");
    must(dBodyGetJoint(a,0)==ac,"A-C joint pointer changed");
    must(dJointGroupGetCount(unused)==0,"unexpected grouped ODE joint");
    if(i==1||i==64||i==512||i==2048||i==8192) {
      Measure now=emit(i,a,b,c,unused);
      if(i==64){warm=now;warm_found=true;}
      if(i==8192){
        must(warm_found,"no warm baseline");
        must(now.used<=warm.used+262144,"unbounded active glibc allocation in 8192 stress");
        must(now.reserved<=warm.reserved+262144,"unbounded reserved glibc allocation in 8192 stress");
        if(now.rss&&warm.rss)
          must(now.rss<=warm.rss+4*1024*1024,"unexpected RSS growth after warmup");
      }
    }
  }
  dJointDestroy(ac);dJointDestroy(permanent);
  dJointGroupDestroy(unused);dBodyDestroy(a);dBodyDestroy(b);dBodyDestroy(c);
  dWorldDestroy(w);dCloseODE();
  std::puts("H6_INDIVIDUAL_8192_PASS");
}

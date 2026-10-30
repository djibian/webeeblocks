// H6 independent native ODE allocator test: group empty reuses arenas but doesn't free them.
// Exact ODE revision is verified by the workflow. This is a glibc-supported
// allocation observation, alongside the pinned ODE dObStack implementation.
#include <ode/ode.h>
#include <malloc.h>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
static void need(bool v,const char *msg) {
  if(!v) {std::fprintf(stderr,"H6_ARENA_REFUSED %s\n",msg);std::exit(2);}
}
struct M {
  size_t allocated;
  size_t used;
  size_t mmap;
  int count;
};
static M snapshot(const char *phase,dJointGroupID group) {
  const auto x=mallinfo2();
  const M r{x.uordblks+x.hblkhd,x.uordblks,x.hblkhd,group?dJointGroupGetCount(group):-1};
  std::printf("{\"phase\":\"%s\",\"allocated_bytes\":%zu,\"mallinfo_used_bytes\":%zu,\"mallinfo_mmap_bytes\":%zu,\"group_joint_count\":%d}\n",phase,r.allocated,r.used,r.mmap,r.count);
  std::fflush(stdout);
  return r;
}
int main() {
  need(dInitODE2(0)!=0,"init");
  dWorldID w=dWorldCreate();
  dJointGroupID g=dJointGroupCreate(0);
  dBodyID a=dBodyCreate(w),b=dBodyCreate(w);
  need(w && g && a && b,"create");
  dMass m;dMassSetSphereTotal(&m,.05,.035);dBodySetMass(a,&m);dBodySetMass(b,&m);
  const M before=snapshot("before_first",g);
  dContact c{};
  c.surface.mode=dContactSoftERP|dContactSoftCFM;
  c.surface.soft_erp=.85;c.surface.soft_cfm=.00001;c.surface.mu=0;
  constexpr int N=8192;
  for(int i=0;i<N;++i) {
    dJointID j=dJointCreateContact(w,g,&c);
    need(j!=nullptr,"new contact");
    dJointAttach(j,a,b);
    dJointAttach(j,nullptr,nullptr);
    dJointDestroy(j); // no-op for group-owned joint; R analog
  }
  const M filled=snapshot("after_first_8192",g);
  need(filled.count==N,"filled count");
  dJointGroupEmpty(g);
  const M empty=snapshot("after_group_empty",g);
  need(empty.count==0,"empty count");
  // A large number of arenas must remain reserved after group Empty.
  // The object count is not the retained byte count.
  need(empty.allocated+131072>=filled.allocated,"empty unexpectedly deallocated arenas");
  for(int i=0;i<N;++i) {
    dJointID j=dJointCreateContact(w,g,&c);
    need(j!=nullptr,"reuse contact");
    dJointAttach(j,a,b);
    dJointAttach(j,nullptr,nullptr);
  }
  const M refill=snapshot("after_refill_8192",g);
  need(refill.count==N,"refill count");
  // No unbounded growth for steady-state N contacts per step, where N is bounded.
  need(refill.allocated<=filled.allocated+131072,"arenas not reused within allowance");
  dJointGroupEmpty(g);
  const M empty2=snapshot("after_second_empty",g);
  need(empty2.count==0,"empty again");
  dJointGroupDestroy(g);
  const M destroyed=snapshot("after_group_destroy",nullptr);
  need(filled.allocated>before.allocated+131072,"allocator change too small");
  need(empty2.allocated>destroyed.allocated+131072,"destroy did not return arena allocations to allocator");
  dBodyDestroy(a);dBodyDestroy(b);dWorldDestroy(w);
  dCloseODE();
  std::puts("H6_ODE_ARENA_ALLOCATION_PASS");
}

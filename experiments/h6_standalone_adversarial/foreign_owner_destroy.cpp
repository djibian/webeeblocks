// Adversarial independent ODE fixture: Webots standalone-contact registry lifetime.
// Reproduces the two exact PR765 decisions at foreign-body destruction:
//   removeBodyContactJointGroup(b) removes only entries with owner == b;
//   retirement destroys only entries whose registered owner is dBodyIsEnabled.
// ODE dBodyDestroy(b) detaches but does NOT destroy standalone contact joints.
// Never changes PR765. This is an ODE/source-contract falsification fixture,
// not proof that the simulated sequence is reached by the Webots UI scheduler.
#include <ode/ode.h>
#include <malloc.h>
#include <unistd.h>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <unordered_map>
struct Metrics {
  long used, reserved, rss; int retained, detached;
};
static void insist(bool x,const char* why) {
  if (!x) {std::fprintf(stderr,"H6_FOREIGN_DESTROY_REFUSED %s\n",why);std::exit(2);}
}
static long rss_bytes(){
  FILE* f=std::fopen("/proc/self/statm","r");insist(f!=nullptr,"statm");
  unsigned long v=0,r=0;insist(std::fscanf(f,"%lu %lu",&v,&r)==2,"statm parse");
  std::fclose(f);return static_cast<long>(r*sysconf(_SC_PAGESIZE));
}
static void get_metrics(int round,const char* mode,
 const std::unordered_map<dJointID,dBodyID>& contacts){
  auto m=mallinfo2();
  int detached=0;
  for(const auto &x:contacts) {
    insist(x.first!=nullptr,"null joint");
    if(!dJointGetBody(x.first,0)&&!dJointGetBody(x.first,1))++detached;
  }
  std::printf("{\"mode\":\"%s\",\"cycle\":%d,\"registered\":%zu,"
   "\"orphan_detached\":%d,\"used\":%zu,\"reserved\":%zu,\"rss\":%ld}\n",
    mode,round,contacts.size(),detached,
    static_cast<size_t>(m.uordblks),
    static_cast<size_t>(m.arena+m.hblkhd),rss_bytes());
  std::fflush(stdout);
}
static void set_mass(dBodyID body){
 dMass m; dMassSetSphereTotal(&m,0.1,0.05);dBodySetMass(body,&m);
}
int main(int argc,char **argv) {
 insist(argc==2,"usage: binary {disabled|enabled|direct}");
 const bool disabled=std::strcmp(argv[1],"disabled")==0;
 const bool enabled=std::strcmp(argv[1],"enabled")==0;
 const bool direct=std::strcmp(argv[1],"direct")==0;
 insist(disabled||enabled||direct,"unknown mode");
 insist(dInitODE2(0)!=0,"ode init");
 dWorldID world=dWorldCreate();insist(world,"world");
 dWorldSetGravity(world,0,0,0);
 dBodyID owner=dBodyCreate(world);insist(owner,"owner");set_mass(owner);
 dBodySetPosition(owner,0,0,0);
 dGeomID ga=dCreateSphere(nullptr,.05);insist(ga,"owner geom");
 dGeomSetBody(ga,owner);
 std::unordered_map<dJointID,dBodyID> contacts;
 if(!enabled)dBodyDisable(owner);
 const int cycles=8192;
 for(int i=1;i<=cycles;++i){
  dBodyID other=dBodyCreate(world);insist(other,"new body");
  set_mass(other);dBodySetPosition(other,.07,0,0);
  dGeomID gb=dCreateSphere(nullptr,.05);insist(gb,"other geom");
  dGeomSetBody(gb,other);
  dContact c{};
  insist(dCollide(ga,gb,1,&c.geom,sizeof(dContactGeom))==1,"real overlap collision");
  c.surface.mu=0;
  dJointID j=dJointCreateContact(world,nullptr,&c);insist(j,"create standalone");
  dJointAttach(j,owner,other);
  insist(dJointGetBody(j,0)==owner && dJointGetBody(j,1)==other,"actual A-B contact attachment");
  contacts.emplace(j,owner); // exact jointID->owner storage semantic
  // Exact WbOdeContext::removeBodyContactJointGroup(other) ownership selection:
  for(auto it=contacts.begin();it!=contacts.end();){
    if(it->second==other){dJointDestroy(it->first);it=contacts.erase(it);}
    else ++it;
  }
  // Webots WbSolidMerger destructor immediately destroys the removed body:
  dGeomDestroy(gb);dBodyDestroy(other);
  insist(!dJointGetBody(j,0)&&!dJointGetBody(j,1),"ODE body destroy did not orphan joint");
  // Exact retirement predicate; same retired buffer is checked at subsequent steps.
  for(auto it=contacts.begin();it!=contacts.end();){
    if(dBodyIsEnabled(it->second)){dJointDestroy(it->first);it=contacts.erase(it);}
    else ++it;
  }
  // Negative control only: selective retirement on *orphaned* joints,
  // without changing the candidate and after demonstrating original outcome.
  if(direct){
    auto it=contacts.find(j);
    insist(it!=contacts.end(),"control missing orphan");
    dJointDestroy(j);contacts.erase(it);
  }
  if(i==64||i==512||i==2048||i==8192)
     get_metrics(i,argv[1],contacts);
 }
 if(disabled){
  insist(contacts.size()==8192,"disabled owner did not retain all invalid orphan joints");
 } else insist(contacts.empty(),"negative control retained stale joints");
 for(const auto &v:contacts)dJointDestroy(v.first);
 contacts.clear();
 get_metrics(8193,argv[1],contacts);
 dGeomDestroy(ga);dBodyDestroy(owner);dWorldDestroy(world);dCloseODE();
 std::printf("H6_FOREIGN_DESTROY_COMPLETED %s\n",argv[1]);
 return 0;
}

// H6 D1: faithful native pinned-ODE rehearsal of fixed registry body-destruction path.
// No Webots scheduler claim. Exact test invariant: destroy foreign B while owner A
// remains disabled; registered A-B must be freed BEFORE dBodyDestroy(B).
#include <ode/ode.h>
#include <malloc.h>
#include <unistd.h>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <unordered_map>
static void check(bool c,const char *s) {
 if (!c) { std::fprintf(stderr,"H6_D1_REFUSED %s\n",s);std::exit(2); }
}
static void setmass(dBodyID b){dMass m;dMassSetSphereTotal(&m,.1,.05);dBodySetMass(b,&m);}
static int contacts(dBodyID b){
 int n=0;
 for(int i=0;i<dBodyGetNumJoints(b);++i) {
   if(dJointGetType(dBodyGetJoint(b,i))==dJointTypeContact)
     ++n;
 }
 return n;
}
static long rss() {
 FILE*f=std::fopen("/proc/self/statm","r");check(f,"statm");
 unsigned long a=0,b=0;check(std::fscanf(f,"%lu %lu",&a,&b)==2,"parse statm");std::fclose(f);
 return static_cast<long>(b*sysconf(_SC_PAGESIZE));
}
int main(){
 check(dInitODE2(0)!=0,"init ODE");
 dWorldID w=dWorldCreate();dWorldSetGravity(w,0,0,0);
 dBodyID a=dBodyCreate(w),c=dBodyCreate(w);setmass(a);setmass(c);
 dBodySetPosition(a,0,0,0);dBodySetPosition(c,0,.07,0);
 dGeomID ga=dCreateSphere(nullptr,.05),gc=dCreateSphere(nullptr,.05);
 dGeomSetBody(ga,a);dGeomSetBody(gc,c);
 dJointID permanent=dJointCreateBall(w,nullptr);dJointAttach(permanent,a,c);
 dContact contact{};check(dCollide(ga,gc,1,&contact.geom,sizeof(dContactGeom))==1,"A-C real contact");
 contact.surface.mu=0;
 dJointID ac=dJointCreateContact(w,nullptr,&contact);dJointAttach(ac,a,c);
 std::unordered_map<dJointID,dBodyID> reg{{ac,a}};
 dBodyDisable(a);check(!dBodyIsEnabled(a),"A not asleep");
 long baselineActive=0,baselineReserved=0,baselineRss=0;
 for(int i=1;i<=8192;++i){
   dBodyID b=dBodyCreate(w);setmass(b);dBodySetPosition(b,.07,0,0);
   dGeomID gb=dCreateSphere(nullptr,.05);dGeomSetBody(gb,b);
   dContact ab{};check(dCollide(ga,gb,1,&ab.geom,sizeof(dContactGeom))==1,"real A-B collision");
   ab.surface.mu=0;
   dJointID j=dJointCreateContact(w,nullptr,&ab);dJointAttach(j,a,b);
   check(dJointGetBody(j,0)==a&&dJointGetBody(j,1)==b,"bad foreign attachment");
   check(reg.emplace(j,a).second,"duplicate joint key");
   // Corrected WbOdeContext::removeBodyContactJointGroup(b):
   // scan BOTH buffers in production; this fixture uses one buffer.
   for(auto it=reg.begin();it!=reg.end();){
     dJointID k=it->first;
     if(it->second==b || dJointGetBody(k,0)==b || dJointGetBody(k,1)==b ||
        (!dJointGetBody(k,0) && !dJointGetBody(k,1))) {
       it=reg.erase(it);dJointDestroy(k); // erase BEFORE free
     } else ++it;
   }
   dGeomDestroy(gb);dBodyDestroy(b); // old code's order
   check(reg.size()==1&&reg.count(ac)==1,"orphan or missing A-C");
   check(contacts(a)==1&&contacts(c)==1,"lost A-C or leaked A-B");
   check(dBodyGetNumJoints(a)==2,"permanent articulation vanished");
   check(dJointGetType(permanent)==dJointTypeBall,"permanent joint destroyed");
   if(i==1||i==64||i==512||i==2048||i==8192){
     auto m=mallinfo2();auto used=static_cast<long>(m.uordblks);
     auto reserved=static_cast<long>(m.arena+m.hblkhd);
     auto resident=rss();
     std::printf("{\"cycle\":%d,\"registered\":%zu,\"contactA\":%d,"
       "\"active\":%ld,\"reserved\":%ld,\"rss\":%ld}\n",i,reg.size(),contacts(a),used,reserved,resident);
     if(i==64){baselineActive=used;baselineReserved=reserved;baselineRss=resident;}
     if(i==8192){
       check(used<=baselineActive+262144,"active memory grew");
       check(reserved<=baselineReserved+262144,"arena capacity grew");
       check(resident<=baselineRss+4*1024*1024,"RSS grew");
     }
   }
 }
 reg.erase(ac);dJointDestroy(ac);dJointDestroy(permanent);
 dGeomDestroy(ga);dGeomDestroy(gc);dBodyDestroy(a);dBodyDestroy(c);dWorldDestroy(w);dCloseODE();
 std::puts("H6_FOREIGN_CORRECTED_8192_PASS");
}
// Real pinned-ODE ABA refutation: no freed pointer dereferenced.
// If raw address is recycled, a retained tombstone rejects a fresh plugin
// joint; erasing it on allocation lets an OLD handle destroy the new joint.
#include <ode/ode.h>
#include <cstdio>
#include <cstdlib>
#include <string>
extern "C" void h6SetPolicy(int);
extern "C" void h6SetEraseTombstoneOnAllocation(int);
extern "C" int h6IsRetired(dJointID);
extern "C" dJointID h6CreateEngineContact(dWorldID,const dContact*,int);
extern "C" int h6EngineDestroyContact(dJointID);
extern "C" unsigned long h6CountDuplicates();
static void check(bool ok,const char* s){
  if(!ok){std::fprintf(stderr,"H6_ABA_FAIL %s\n",s);std::exit(7);}
}
static dContact sample(){
  dContact c{};
  c.geom.normal[2]=1;
  c.geom.depth=.01;
  c.surface.mu=0;
  return c;
}
int main(int argc,char**argv){
  check(argc==3,"usage: h6_aba_probe sticky|erase p0|p1");
  const std::string mode=argv[1],policy=argv[2];
  check(mode=="sticky"||mode=="erase","invalid mode");
  check(policy=="p0"||policy=="p1","invalid policy");
  check(dInitODE2(0)!=0,"dInitODE2");
  dWorldID world=dWorldCreate();
  dBodyID body=dBodyCreate(world);
  h6SetPolicy(policy=="p1"?1:0);
  h6SetEraseTombstoneOnAllocation(mode=="erase"?1:0);
  dContact c=sample();
  const dJointID old=h6CreateEngineContact(world,&c,0);
  dJointAttach(old,body,nullptr);
  check(dBodyGetNumJoints(body)==1,"original contact missing");
  check(h6EngineDestroyContact(old)==1,"original engine contact not destroyed");
  check(dBodyGetNumJoints(body)==0,"original contact remains");
  dJointID plugin=nullptr;
  int attempts=0;
  for(;attempts<300;++attempts){
    plugin=dJointCreateContact(world,nullptr,&c);
    dJointAttach(plugin,body,nullptr);
    if(plugin==old)break;
    dJointDestroy(plugin);
    check(dBodyGetNumJoints(body)==0,"unrelated probe contact not destroyed");
  }
  const bool reused=(plugin==old);
  if(reused){
    check(dBodyGetNumJoints(body)==1,"fresh plugin contact missing");
    const int tomb=h6IsRetired(plugin);
    const unsigned long beforeDup=h6CountDuplicates();
    // Same raw value is BOTH a stale engine handle and a genuine live plugin
    // handle. With no generation information, ODE cannot distinguish them.
    dJointDestroy(mode=="erase"?old:plugin);
    const bool stillAlive=(dBodyGetNumJoints(body)==1);
    const unsigned long duplicateDelta=h6CountDuplicates()-beforeDup;
    if(mode=="sticky"){
      check(tomb==1 && stillAlive && duplicateDelta==1,
            "sticky tombstone must reveal false positive");
    }else{
      check(tomb==0 && !stillAlive && duplicateDelta==0,
            "cleared tombstone must reveal stale-handle/free collision");
    }
    std::printf("{\"mode\":\"%s\",\"policy\":\"%s\",\"reused\":true,"
       "\"attempts\":%d,\"old\":\"%p\",\"fresh_plugin\":\"%p\","
       "\"tombstone_before\":%d,\"plugin_survives\":%s,"
       "\"duplicate_delta\":%lu,\"counterexample\":\"%s\"}\n",
       mode.c_str(),policy.c_str(),attempts,(void*)old,(void*)plugin,tomb,
       stillAlive?"true":"false",duplicateDelta,
       mode=="sticky"?"VALID_PLUGIN_DESTRUCTION_DENIED":"STALE_HANDLE_DESTROYS_NEW_PLUGIN");
  }else{
    // Experiment inconclusive if allocator does not reuse an address.
    dJointDestroy(plugin);
    std::printf("{\"mode\":\"%s\",\"policy\":\"%s\",\"reused\":false,\"attempts\":%d,"
       "\"counterexample\":\"UNPROVEN_ALLOCATOR_NO_REUSE\"}\n",
       mode.c_str(),policy.c_str(),attempts);
  }
  dBodyDestroy(body);
  dWorldDestroy(world);
  dCloseODE();
  return reused?0:6; // fail closed rather than fabricate allocator behavior.
}

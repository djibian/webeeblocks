#include "grand_prix_u_hook.h"
#include <webots/robot.h>
#include <webots/plugins/robot_window/default.h>
#include <webots/supervisor.h>
#include <cmath>
#include <cstdio>
#include <cstring>
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
#include <charconv>
#include <random>
#include <string>
#endif
extern "C" const char *webeeblocks_file_broker_receive_text(void);
extern "C" void webeeblocks_file_broker_send(const char *, int);
namespace {
long long begin=-1;
unsigned long long attempt=0;
bool expired=false,landed=false,success=false;
bool fileIdle=false;
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
constexpr const char *oracleName="grand-prix-route-v2";
constexpr const char *evaluatorDef="GP_ROUTE_EVALUATOR";
std::string routeConfig,routeEpoch;
unsigned long long routeAttempt=0;
long long routeIssued=-1,routeAlive=-1;
#else
constexpr const char *oracleName="grand-prix-u-v1";
constexpr const char *evaluatorDef="GP_U_EVALUATOR";
#endif
WbFieldRef channel() {
  WbNodeRef node=wb_supervisor_node_get_from_def(evaluatorDef);
  return node ? wb_supervisor_node_get_field(node,"customData") : nullptr;
}
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
template<class T> bool canonicalNumber(const std::string& text,T& result) {
  if(text.empty() || text.size()>20)return false;
  auto parsed=std::from_chars(text.data(),text.data()+text.size(),result);
  return parsed.ec==std::errc() && parsed.ptr==text.data()+text.size() &&
         std::to_string(result)==text;
}
bool routeTime(double now,long long& ms) {
  if(!std::isfinite(now) || now<0 || now>1e12)return false;
  ms=std::llround(now*1000);return true;
}
bool currentAttempt(unsigned long long& current) {
  WbFieldRef f=wb_supervisor_node_get_field(wb_supervisor_node_get_self(),"customData");
  const char *raw=f?wb_supervisor_field_get_sf_string(f):nullptr;
  const std::string prefix="WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 ";
  return raw && !std::strncmp(raw,prefix.c_str(),prefix.size()) &&
         canonicalNumber(std::string(raw+prefix.size()),current) && current>0;
}
bool currentConfig(std::string& config) {
  WbFieldRef f=wb_supervisor_node_get_field(wb_supervisor_node_get_self(),"controllerArgs");
  if(!f || wb_supervisor_field_get_count(f)!=1)return false;
  const char *raw=wb_supervisor_field_get_mf_string(f,0);
  if(!raw || std::strlen(raw)>80 || std::strncmp(raw,"gp-route-v2-",12))return false;
  for(const char *p=raw;*p;++p)
    if(!((*p>='0'&&*p<='9')||(*p>='a'&&*p<='z')||(*p>='A'&&*p<='Z')||*p=='-'))return false;
  config=raw;return true; // The evaluator independently decodes the canonical CoursePlan.
}
void clearRouteEpoch() {routeEpoch.clear();routeConfig.clear();routeAttempt=0;routeIssued=-1;routeAlive=-1;}
void challengeRoute() {
  unsigned long long current=0;std::string config;long long now=0;
  WbFieldRef f=channel();
  if(!f || !routeTime(wb_robot_get_time(),now) || !currentAttempt(current) ||
     !currentConfig(config)) {clearRouteEpoch();return;}
  if(routeEpoch.empty() || current!=routeAttempt || config!=routeConfig) {
    clearRouteEpoch();
    try {
      std::random_device random;
      if(random.entropy()<=0)return; // Unavailable process freshness is never READY.
      char token[33];
      for(int i=0;i<4;++i)std::snprintf(token+i*8,9,"%08x",static_cast<unsigned>(random()));
      routeEpoch=token;routeConfig=config;routeAttempt=current;routeIssued=now;
    } catch(...) {clearRouteEpoch();return;}
  }
  char request[320];
  std::snprintf(request,sizeof(request),"GP_ROUTE_CHALLENGE_V1 attempt=%llu config=%s epoch=%s",
                routeAttempt,routeConfig.c_str(),routeEpoch.c_str());
  wb_supervisor_field_set_sf_string(f,request);
}
bool freshRouteEvidence(const char *kind,long long now) {
  std::string config;
  if(routeEpoch.empty() || !currentConfig(config) || config!=routeConfig)return false;
  WbNodeRef node=wb_supervisor_node_get_from_def(evaluatorDef);
  // One writer per direction: flight owns customData; evaluator owns description.
  WbFieldRef f=node?wb_supervisor_node_get_field(node,"description"):nullptr;
  const char *raw=f?wb_supervisor_field_get_sf_string(f):nullptr;
  const std::string prefix=std::string("GP_ROUTE_")+kind+"_V1 attempt="+
    std::to_string(routeAttempt)+" config="+routeConfig+" epoch="+routeEpoch+" time_ms=";
  long long observed=-1;
  const bool fresh=raw && !std::strncmp(raw,prefix.c_str(),prefix.size()) &&
    canonicalNumber(std::string(raw+prefix.size()),observed) &&
    observed>=routeIssued && observed<=now && now-observed<=32;
  if(!fresh)return false;
  if(!std::strcmp(kind,"ALIVE")) {
    if(observed<=begin || observed<=routeAlive)return false;
    routeAlive=observed;
  }
  return true;
}
#endif
void publish(const char *state) {
  char data[384];
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
  std::snprintf(data,sizeof(data),"GP_ROUTE_START_V1 attempt=%llu config=%s epoch=%s start_ms=%lld state=%s",
                attempt,routeConfig.c_str(),routeEpoch.c_str(),begin,state);
#else
  std::snprintf(data,sizeof(data),"GP_U_START attempt=%llu start_ms=%lld state=%s",attempt,begin,state);
#endif
  WbFieldRef field=channel();
  if(field)wb_supervisor_field_set_sf_string(field,data);
}
void failed_outcome() {
  WbFieldRef field=wb_supervisor_node_get_field(wb_supervisor_node_get_self(),"customData");
  char result[192];
  std::snprintf(result,sizeof(result),"WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=not-achieved",attempt,oracleName);
  if(field)wb_supervisor_field_set_sf_string(field,result);
}
}
extern "C" int gp_u_start(double now) {
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
  unsigned long long current=0;long long observed=0;
  if(!fileIdle || !routeTime(now,observed) || !currentAttempt(current) ||
     current!=routeAttempt || begin>=0 || !freshRouteEvidence("READY",observed)) {
    expired=true;publish("failed");return 0;
  }
#else
  WbFieldRef field=wb_supervisor_node_get_field(wb_supervisor_node_get_self(),"customData");
  unsigned long long current=0;char tail[2]={0};
  const char *value=field?wb_supervisor_field_get_sf_string(field):nullptr;
  if(!value || std::sscanf(value,"WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu %1s",&current,tail)!=1 || current<1 || begin>=0 || !channel()) {
    expired=true;publish("failed");return 0;
  }
#endif
  begin=std::llround(now*1000);attempt=current;expired=false;landed=false;success=false;
  publish("admitted");
  std::printf("GP_U_ADMISSION attempt=%llu start_ms=%lld\n",attempt,begin);std::fflush(stdout);
  return 1;
}
extern "C" int gp_u_deadline(double now,int nativeLanded) {
  landed=nativeLanded!=0;
  if(begin<0 || success)return 0;
  if(expired){failed_outcome();return 0;}
  WbFieldRef field=wb_supervisor_node_get_field(wb_supervisor_node_get_self(),"customData");
  const char *value=field?wb_supervisor_field_get_sf_string(field):nullptr;
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
  long long observed=0;
  if(!routeTime(now,observed) || observed<begin) {
    expired=true;publish("failed");failed_outcome();return 1;
  }
#endif
  // Only a success already latched on an earlier pre-deadline observation
  // may bypass the deadline. The outcome channel has no validation timestamp:
  // first observations at/after expiry fail closed even if delivered late.
  if(std::llround(now*1000)-begin>=210000) {
    expired=true;publish("deadline");
    failed_outcome();
    return 1;
  }
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
  if(observed>begin && !freshRouteEvidence("ALIVE",observed)) {
    expired=true;publish("failed");failed_outcome();
    std::fprintf(stderr,"GP_ROUTE_SAFETY_LAND evaluator-unavailable\n");
    return 1; // The shared flight loop consumes this as the same independent LAND.
  }
#endif
  unsigned long long a=0;char oracle[64]={0},status[32]={0},tail[2]={0};
  success=landed && value && std::sscanf(value,"WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%63s status=%31s %1s",&a,oracle,status,tail)==3 &&
          a==attempt && !std::strcmp(oracle,oracleName) && !std::strcmp(status,"achieved");
  return 0;
}
extern "C" int gp_u_next_step(int normal) {
  if(begin<0 || expired || success)return normal;
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
  long long observed=0;if(!routeTime(wb_robot_get_time(),observed))return normal;
#endif
  const long long left=begin+210000-std::llround(wb_robot_get_time()*1000);
  return left>0 && left<normal ? static_cast<int>(left) : normal;
}
extern "C" void gp_u_reset_complete(void) {
  begin=-1;attempt=0;expired=false;landed=false;success=false;
  fileIdle=false; // Only the next native idle/ground observation reopens files.
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
  clearRouteEpoch();
#endif
  WbFieldRef field=channel();if(field)wb_supervisor_field_set_sf_string(field,"");
}
extern "C" void gp_u_file_idle(int idle) {
  fileIdle=idle!=0;
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
  if(begin<0) {if(fileIdle)challengeRoute();else clearRouteEpoch();}
#endif
}
extern "C" int gp_u_filter_raw(const char *message) {
  if(expired && begin>=0)failed_outcome(); // OUTCOME cannot expose a late overwrite
  // Every broker operation can enter a provider (including creation, metadata,
  // read/write and release). Fence the namespace before that shared path runs.
  // A failed/unfinished attempt stays fenced through confirmed RESET.
  // Verified success disarms the deadline, but still requires fresh landing.
  const char *prefix="WEBEEBLOCKS_FILE_BROKER_V1 ";
  if(message && !std::strncmp(message,prefix,std::strlen(prefix)) &&
     (!fileIdle || (begin>=0 && !(success && landed)))) {
    int fileId=-1;
    if(std::sscanf(message,"WEBEEBLOCKS_FILE_BROKER_V1 REQUEST %d",&fileId)==1 && fileId>=1) {
      char reply[128];
      std::snprintf(reply,sizeof(reply),"WEBEEBLOCKS_FILE_BROKER_V1 RESPONSE %d ERR BUSY",fileId);
      wb_robot_wwi_send_text(reply);
    }
    return 0;
  }
  int id=-1;char cmd[32]={0};
  const bool parsed=message && std::sscanf(message,"WEBEEBLOCKS_RUNTIME_V2 REQUEST %d %31s",&id,cmd)==2;
  // Also fence RESET after an abnormal termination before the deadline.
  // Filtering here precedes the broker's pending-reset/attempt bookkeeping.
  if(begin>=0 && parsed && !std::strcmp(cmd,"RESET") && !landed) {
    char reply[128];std::snprintf(reply,sizeof(reply),"WEBEEBLOCKS_RUNTIME_V2 RESPONSE %d ERR %s",id,expired?"TIME_LIMIT":"LANDING_UNCONFIRMED");
    wb_robot_wwi_send_text(reply);return 0;
  }
  if(expired && parsed && std::strcmp(cmd,"OUTCOME") && !(landed && !std::strcmp(cmd,"RESET"))) {
    char reply[128];std::snprintf(reply,sizeof(reply),"WEBEEBLOCKS_RUNTIME_V2 RESPONSE %d ERR TIME_LIMIT",id);
    wb_robot_wwi_send_text(reply);return 0;
  }
  if(begin>=0 && !expired && parsed && !std::strcmp(cmd,"STOP"))publish("failed");
  return 1;
}
extern "C" const char *gp_u_receive(void) {
  return webeeblocks_file_broker_receive_text();
}
extern "C" void gp_u_send(const char *data,int size) {
  webeeblocks_file_broker_send(data,size);
}

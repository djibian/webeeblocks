#include "grand_prix_u_hook.h"
#include <webots/robot.h>
#include <webots/plugins/robot_window/default.h>
#include <webots/supervisor.h>
#include <cmath>
#include <cstdio>
#include <cstring>
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
#include <algorithm>
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
long long routeIssued=-1,routeAlive=-1,routeObserved=-1;
bool nativeRouteDeadline=false; // Latched only at the real 210000 ms boundary.
// Route-only, non-authoritative clock stream, bound to one private browser nonce.
std::string routeClockNonce;
long long routeClockLastSecond=-1;
// This is a graphical preference, not a flight/AST/mission command.
// Only the flight Supervisor, while physically idle on the ground, can
// change the one WorldInfo.FPS field. A pending change is verified next tick.
std::string routeFpsPendingNonce;
int routeFpsPendingValue=0;
double routeFpsPendingAt=-1.0;
WbFieldRef routeFpsField() {
  WbNodeRef world=wb_supervisor_node_get_from_def("WEBEEBLOCKS_DEDICATED_RUNTIME_WORLD");
  const char *kind=world?wb_supervisor_node_get_type_name(world):nullptr;
  if(!kind || std::strcmp(kind,"WorldInfo"))return nullptr;
  WbFieldRef field=wb_supervisor_node_get_field(world,"FPS");
  if(!field || wb_supervisor_field_get_type(field)!=WB_SF_FLOAT ||
     wb_robot_get_basic_time_step()!=8.0)return nullptr;
  return field;
}
bool routeFpsNonce(const std::string& token) {
  return token.size()==32 && std::all_of(token.begin(),token.end(),
    [](char ch){return (ch>='0'&&ch<='9')||(ch>='a'&&ch<='f');});
}
void routeFpsReply(const char *result,const std::string& token,const char *key,const char *value) {
  char reply[160];
  std::snprintf(reply,sizeof(reply),"GP_ROUTE_FPS_V1 %s nonce=%s %s=%s",
    result,token.c_str(),key,value);
  wb_robot_wwi_send_text(reply);
}
void routeFpsReplyValue(const char *result,const std::string& token,int value) {
  char valueText[16];std::snprintf(valueText,sizeof(valueText),"%d",value);
  routeFpsReply(result,token,"fps",valueText);
}
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
void clearRouteObservation() {
  WbNodeRef node=wb_supervisor_node_get_from_def(evaluatorDef);
  WbFieldRef f=node?wb_supervisor_node_get_field(node,"model"):nullptr;
  if(f)wb_supervisor_field_set_sf_string(f,"");
}
void clearRouteEpoch() {
  routeEpoch.clear();routeConfig.clear();routeAttempt=0;
  routeIssued=-1;routeAlive=-1;routeObserved=-1;clearRouteObservation();
  routeClockNonce.clear();routeClockLastSecond=-1;
}
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
// Terminal causes are attested by the evaluator on description, never by
// flight heuristics or a transport TIME_LIMIT. The pilot alone writes the
// negative outcome into vehicle.customData, including late enrichment.
bool routeTerminalCause(long long now,std::string &cause) {
  cause.clear();
  if(begin<0 || routeEpoch.empty() || routeAttempt!=attempt || now<begin)
    return false;
  std::string config;
  if(!currentConfig(config) || config!=routeConfig)return false;
  WbNodeRef node=wb_supervisor_node_get_from_def(evaluatorDef);
  WbFieldRef field=node?wb_supervisor_node_get_field(node,"description"):nullptr;
  const char *raw=field?wb_supervisor_field_get_sf_string(field):nullptr;
  if(!raw || std::strlen(raw)>383)return false;
  const std::string prefix="GP_ROUTE_TERMINAL_V1 attempt="+
    std::to_string(attempt)+" config="+routeConfig+" epoch="+routeEpoch+" time_ms=";
  const std::string witness(raw);
  if(witness.compare(0,prefix.size(),prefix)!=0)return false;
  const std::string rest=witness.substr(prefix.size());
  const auto split=rest.find(" reason=");
  if(split==std::string::npos)return false;
  long long stamp=-1;
  if(!canonicalNumber(rest.substr(0,split),stamp) ||
     stamp<routeIssued || stamp<begin || stamp>now ||
     stamp>=begin+210000)return false;
  cause=rest.substr(split+8);
  if(cause!="envelope-contact" && cause!="course-boundary" &&
     cause!="altitude" && cause!="low-outside-zone" &&
     cause!="wrong-landing") {
    cause.clear();
    return false;
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
void failed_outcome(const char *cause=nullptr) {
  WbFieldRef field=wb_supervisor_node_get_field(wb_supervisor_node_get_self(),"customData");
  if(!field)return;
  char result[192];
  std::snprintf(result,sizeof(result),"WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=not-achieved",attempt,oracleName);
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
  // One negative-outcome writer: the native pilot. A newer RESET marker or
  // another oracle is never replaced by an older attempt's outcome.
  const char *current=wb_supervisor_field_get_sf_string(field);
  const std::string existing=current?current:"", generic(result);
  if(existing.compare(0,generic.size()+8,generic+" reason=")==0) {
    const std::string first=existing.substr(generic.size()+8);
    if(first=="envelope-contact" || first=="course-boundary" ||
       first=="altitude" || first=="low-outside-zone" ||
       first=="wrong-landing" || first=="time-limit")return;
  }
  const std::string currentMarker="WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 "+std::to_string(attempt);
  if(existing.rfind("WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 ",0)==0 &&
     existing!=currentMarker)return;
  if(existing.rfind("WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=",0)==0 &&
     existing.compare(0,generic.size(),generic)!=0 &&
     existing!="WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt="+std::to_string(attempt)+
       " oracle="+std::string(oracleName)+" status=achieved")return;
  // A generic pilot failure may be enriched after the independent safety
  // LAND. This retry runs in the SAME flight controller as native RESET.
  if(existing==generic && cause!=nullptr)return;
  std::string witnessed;
  long long routeNow=0;
  const bool terminal=cause==nullptr && routeTime(wb_robot_get_time(),routeNow) &&
     routeTerminalCause(routeNow,witnessed);
  if(existing==generic && !terminal)return;
  if(cause && std::strcmp(cause,"time-limit")==0)
    std::strncat(result," reason=time-limit",sizeof(result)-std::strlen(result)-1);
  else if(terminal) {
    std::strncat(result," reason=",sizeof(result)-std::strlen(result)-1);
    std::strncat(result,witnessed.c_str(),sizeof(result)-std::strlen(result)-1);
  }
#else
  (void)cause;
#endif
  wb_supervisor_field_set_sf_string(field,result);
}
}
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
extern "C" void gp_route_observe_native(double now,int controlValid,int ground,const double *ranges) {
  // Called after the native pilot step, with effective device periods checked
  // in the composed C. time_ms is the observation time, not a fabricated device
  // acquisition timestamp. A restart or shortened step can change phase.
  long long observed=0;unsigned long long current=0;std::string config;
  // Crazyflie's inherited description is not exposed by the pinned PROTO;
  // get_base_node_field would be read-only. The plain evaluator Robot's model
  // is an unused writable SFString, owned exclusively by this flight writer.
  WbNodeRef node=wb_supervisor_node_get_from_def(evaluatorDef);
  WbFieldRef f=node?wb_supervisor_node_get_field(node,"model"):nullptr;
  if(!f)return;
  if(controlValid!=1 || (ground!=0 && ground!=1) || !ranges || expired || success ||
     routeEpoch.empty() || !routeTime(now,observed) || observed%8 ||
     observed<routeIssued || observed<=routeObserved ||
     (begin>=0 && observed-begin>=210000) ||
     !currentConfig(config) || config!=routeConfig ||
     (begin<0 && (!fileIdle || !currentAttempt(current) || current!=routeAttempt))) {
    clearRouteObservation();return;
  }
  long long micrometres[5];
  for(int i=0;i<5;++i) {
    if(!std::isfinite(ranges[i]) || ranges[i]<0 || ranges[i]>2.001) {
      clearRouteObservation();return;
    }
    micrometres[i]=std::llround(ranges[i]*1000000);
  }
  char data[384];
  std::snprintf(data,sizeof(data),
    "GP_ROUTE_SAMPLE_V1 attempt=%llu config=%s epoch=%s time_ms=%lld period_ms=32 ground=%d ranges_um=%lld,%lld,%lld,%lld,%lld",
    routeAttempt,routeConfig.c_str(),routeEpoch.c_str(),observed,ground,
    micrometres[0],micrometres[1],micrometres[2],micrometres[3],micrometres[4]);
  routeObserved=observed;wb_supervisor_field_set_sf_string(f,data);
}
#endif
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
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
  nativeRouteDeadline=false;
  routeClockLastSecond=-1; // Retain pre-admission subscription of the current epoch.
#endif
  publish("admitted");
  std::printf("GP_U_ADMISSION attempt=%llu start_ms=%lld\n",attempt,begin);std::fflush(stdout);
  return 1;
}
extern "C" int gp_u_deadline(double now,int nativeLanded) {
  landed=nativeLanded!=0;
  if(begin<0 || success)return 0;
  if(expired){
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
    // Late broker/flight ticks must retain an already attested 210 s failure.
    failed_outcome(nativeRouteDeadline ? "time-limit" : nullptr);
#else
    failed_outcome();
#endif
    return 0;
  }
  WbFieldRef field=wb_supervisor_node_get_field(wb_supervisor_node_get_self(),"customData");
  const char *value=field?wb_supervisor_field_get_sf_string(field):nullptr;
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
  long long observed=0;
  if(!routeTime(now,observed) || observed<begin) {
    expired=true;publish("failed");failed_outcome();return 1;
  }
#endif
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
  // Read-only native time notifications: never derive mission time from wall
  // time or modify the irreversible deadline/oracle. One update per observed
  // simulated-second transition. No notifications before admission or after
  // the actual 210 s limit. Loss of a notification never grants authority.
  if(!routeClockNonce.empty() && observed>=begin && observed<=begin+210000) {
    const long long second=(observed-begin)/1000;
    if(second>routeClockLastSecond) {
      char event[180];
      std::snprintf(event,sizeof(event),
        "GP_ROUTE_CLOCK_V1 TICK nonce=%s attempt=%llu seconds=%lld",
        routeClockNonce.c_str(),attempt,second);
      wb_robot_wwi_send_text(event);
      routeClockLastSecond=second;
    }
  }
#endif
  // Only a success already latched on an earlier pre-deadline observation
  // may bypass the deadline. The outcome channel has no validation timestamp:
  // first observations at/after expiry fail closed even if delivered late.
  if(std::llround(now*1000)-begin>=210000) {
    expired=true;
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
    nativeRouteDeadline=true; // Do not confuse broker TIME_LIMIT with elapsed time.
#endif
    publish("deadline");
    failed_outcome("time-limit");
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
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
  nativeRouteDeadline=false;
  routeClockNonce.clear();routeClockLastSecond=-1;
#endif
  fileIdle=false; // Only the next native idle/ground observation reopens files.
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
  clearRouteEpoch();
#endif
  WbFieldRef field=channel();if(field)wb_supervisor_field_set_sf_string(field,"");
}
extern "C" void gp_u_file_idle(int idle) {
  fileIdle=idle!=0;
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
  // The file-broker loop can call gp_u_file_idle() more than once WITHIN
  // the same robot step. Supervisor SET is deferred: no readback/ACK before
  // native simulation time has advanced. Wait for a subsequent actual step.
  if(!routeFpsPendingNonce.empty()) {
    const double now=wb_robot_get_time();
    if(std::isfinite(now) && now>routeFpsPendingAt) {
      WbFieldRef fps=routeFpsField();
      const double observed=fps?wb_supervisor_field_get_sf_float(fps):NAN;
      bool terminal=false;
      if(!fileIdle || begin>=0 || expired) {
        routeFpsReply("REFUSED",routeFpsPendingNonce,"reason","UNCONFIRMED");
        terminal=true;
      } else if(std::isfinite(observed) && observed==routeFpsPendingValue) {
        routeFpsReplyValue("APPLIED",routeFpsPendingNonce,routeFpsPendingValue);
        terminal=true;
      } else if(now-routeFpsPendingAt>=0.25) {
        // Bounded reconciliation; UNKNOWN is not an assured failed write.
        routeFpsReply("REFUSED",routeFpsPendingNonce,"reason","UNCONFIRMED");
        terminal=true;
      }
      if(terminal) {
        routeFpsPendingNonce.clear();
        routeFpsPendingValue=0;
        routeFpsPendingAt=-1.0;
      }
    }
  }
  if(begin<0) {if(fileIdle)challengeRoute();else clearRouteEpoch();}
#endif
}
extern "C" int gp_u_filter_raw(const char *message) {
  if(expired && begin>=0) {
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
    failed_outcome(nativeRouteDeadline ? "time-limit" : nullptr);
#else
    failed_outcome();
#endif
  } // OUTCOME cannot expose a late overwrite
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
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
  // Dedicated graphical preference, never a Blockly/AST command. Native
  // grounding and flight-attempt state remain authoritative even if the
  // browser is modified or sends a stale request during TAKEOFF/STOP.
  const std::string fpsPrefix="GP_ROUTE_FPS_V1 ";
  if(message && !std::strncmp(message,fpsPrefix.c_str(),fpsPrefix.size())) {
    const std::string request=message+fpsPrefix.size();
    const auto pos=request.find(" nonce=");
    if(pos==std::string::npos)return 0;
    const std::string token=request.substr(pos+7);
    if(!routeFpsNonce(token))return 0;
    const std::string action=request.substr(0,pos);
    if(action=="GET") {
      WbFieldRef field=routeFpsField();
      const double current=field?wb_supervisor_field_get_sf_float(field):NAN;
      if(std::isfinite(current) && current>=1 && current<=60 &&
         current==std::floor(current))
        routeFpsReplyValue("CURRENT",token,static_cast<int>(current));
      else
        routeFpsReply("REFUSED",token,"reason","WORLD_UNAVAILABLE");
      return 0;
    }
    const std::string setPrefix="SET fps=";
    int requested=0;
    if(action.compare(0,setPrefix.size(),setPrefix)!=0 ||
       !canonicalNumber(action.substr(setPrefix.size()),requested) ||
       requested<1 || requested>60) {
      routeFpsReply("REFUSED",token,"reason","INVALID");
      return 0;
    }
    if(!routeFpsPendingNonce.empty() || !fileIdle || begin>=0 || expired) {
      routeFpsReply("REFUSED",token,"reason","BUSY");
      return 0;
    }
    WbFieldRef field=routeFpsField();
    if(!field) {
      routeFpsReply("REFUSED",token,"reason","WORLD_UNAVAILABLE");
      return 0;
    }
    const double current=wb_supervisor_field_get_sf_float(field);
    if(!std::isfinite(current) || current<1 || current>60) {
      routeFpsReply("REFUSED",token,"reason","WORLD_UNAVAILABLE");
      return 0;
    }
    if(current==requested) {
      routeFpsReplyValue("APPLIED",token,requested);
      return 0;
    }
    const double at=wb_robot_get_time();
    if(!std::isfinite(at) || at<0) {
      routeFpsReply("REFUSED",token,"reason","WORLD_UNAVAILABLE");
      return 0;
    }
    routeFpsPendingNonce=token;
    routeFpsPendingValue=requested;
    routeFpsPendingAt=at;
    wb_supervisor_field_set_sf_float(field,static_cast<double>(requested));
    return 0;
  }
  // A new TAKEOFF is forbidden while a requested render change has yet to
  // pass its native next-step readback; never grant flight during uncertainty.
  if(!routeFpsPendingNonce.empty() && message) {
    int requestId=0;
    const std::string takeoffPrefix="WEBEEBLOCKS_RUNTIME_V2 REQUEST ";
    if(!std::strncmp(message,takeoffPrefix.c_str(),takeoffPrefix.size())) {
      const std::string request=message+takeoffPrefix.size();
      const auto space=request.find(' ');
      if(space!=std::string::npos && request.substr(space)==" TAKEOFF" ) {
        if(canonicalNumber(request.substr(0,space),requestId) && requestId>0) {
          char reply[128];
          std::snprintf(reply,sizeof(reply),
            "WEBEEBLOCKS_RUNTIME_V2 RESPONSE %d ERR BUSY",requestId);
          wb_robot_wwi_send_text(reply);
        }
        return 0;
      }
    }
  }
  // The browser can bind an opaque nonce for read-only simulated clock ticks.
  // Strictly route-mode, one currently evidenced attempt/epoch; never an
  // actuator, mission oracle, admission, real-flight or RESET channel.
  const std::string clockPrefix="GP_ROUTE_CLOCK_V1 SUBSCRIBE nonce=";
  if(message && !std::strncmp(message,clockPrefix.c_str(),clockPrefix.size())) {
    const std::string token=message+clockPrefix.size();
    const bool valid=token.size()==32 && std::all_of(token.begin(),token.end(),
      [](char ch){return (ch>='0'&&ch<='9')||(ch>='a'&&ch<='f');});
    unsigned long long current=0;
    if(valid && !expired && !success && !routeEpoch.empty() &&
       currentAttempt(current) && current==routeAttempt &&
       (begin<0 ? fileIdle : current==attempt)) {
      routeClockNonce=token;routeClockLastSecond=-1;
      char ack[160];
      std::snprintf(ack,sizeof(ack),
        "GP_ROUTE_CLOCK_V1 ACK nonce=%s attempt=%llu",
        routeClockNonce.c_str(),current);
      wb_robot_wwi_send_text(ack);
    }
    return 0; // Never forward unsupported clock messages to the flight parser.
  }
  // Host-only, non-actuating readiness peek. Do not consume ALIVE, rotate an
  // epoch, start an attempt or disclose the private evaluator context to WWI.
  const std::string queryPrefix="WEBEEBLOCKS_RUNTIME_V2 REQUEST ";
  if(message && !std::strncmp(message,queryPrefix.c_str(),queryPrefix.size())) {
    const std::string query=message+queryPrefix.size();
    const auto separator=query.find(' ');
    int queryId=0;
    if(separator!=std::string::npos && query.substr(separator)==" ADMISSION" &&
       canonicalNumber(query.substr(0,separator),queryId) && queryId>0) {
      unsigned long long current=0;long long now=0;
      const bool available=begin<0 && !expired && fileIdle &&
        currentAttempt(current) && current==routeAttempt &&
        routeTime(wb_robot_get_time(),now) && freshRouteEvidence("READY",now);
      char reply[128];
      std::snprintf(reply,sizeof(reply),"WEBEEBLOCKS_RUNTIME_V2 RESPONSE %d VALUE %d",
                    queryId,available?1:0);
      wb_robot_wwi_send_text(reply);return 0;
    }
  }
#endif
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
#ifdef WEBEEBLOCKS_GP_ROUTE_MODE
  if(begin>=0 && parsed && !std::strcmp(cmd,"STOP"))routeClockNonce.clear();
#endif
  if(begin>=0 && !expired && parsed && !std::strcmp(cmd,"STOP"))publish("failed");
  return 1;
}
extern "C" const char *gp_u_receive(void) {
  return webeeblocks_file_broker_receive_text();
}
extern "C" void gp_u_send(const char *data,int size) {
  webeeblocks_file_broker_send(data,size);
}

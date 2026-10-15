#include "grand_prix_u_hook.h"
#include <webots/robot.h>
#include <webots/plugins/robot_window/default.h>
#include <webots/supervisor.h>
#include <cmath>
#include <cstdio>
#include <cstring>
extern "C" const char *webeeblocks_file_broker_receive_text(void);
extern "C" void webeeblocks_file_broker_send(const char *, int);
namespace {
long long begin=-1;
unsigned long long attempt=0;
bool expired=false,landed=false,success=false;
bool fileIdle=false;
WbFieldRef channel() {
  WbNodeRef node=wb_supervisor_node_get_from_def("GP_U_EVALUATOR");
  return node ? wb_supervisor_node_get_field(node,"customData") : nullptr;
}
void publish(const char *state) {
  char data[192];
  std::snprintf(data,sizeof(data),"GP_U_START attempt=%llu start_ms=%lld state=%s",attempt,begin,state);
  WbFieldRef field=channel();
  if(field)wb_supervisor_field_set_sf_string(field,data);
}
void failed_outcome() {
  WbFieldRef field=wb_supervisor_node_get_field(wb_supervisor_node_get_self(),"customData");
  char result[192];
  std::snprintf(result,sizeof(result),"WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=grand-prix-u-v1 status=not-achieved",attempt);
  if(field)wb_supervisor_field_set_sf_string(field,result);
}
}
extern "C" int gp_u_start(double now) {
  WbFieldRef field=wb_supervisor_node_get_field(wb_supervisor_node_get_self(),"customData");
  unsigned long long current=0;char tail[2]={0};
  const char *value=field?wb_supervisor_field_get_sf_string(field):nullptr;
  if(!value || std::sscanf(value,"WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu %1s",&current,tail)!=1 || current<1 || begin>=0 || !channel()) {
    expired=true;publish("failed");return 0;
  }
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
  // Only a success already latched on an earlier pre-deadline observation
  // may bypass the deadline. The outcome channel has no validation timestamp:
  // first observations at/after expiry fail closed even if delivered late.
  if(std::llround(now*1000)-begin>=210000) {
    expired=true;publish("deadline");
    failed_outcome();
    return 1;
  }
  unsigned long long a=0;char oracle[64]={0},status[32]={0},tail[2]={0};
  success=landed && value && std::sscanf(value,"WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%63s status=%31s %1s",&a,oracle,status,tail)==3 &&
          a==attempt && !std::strcmp(oracle,"grand-prix-u-v1") && !std::strcmp(status,"achieved");
  return 0;
}
extern "C" int gp_u_next_step(int normal) {
  if(begin<0 || expired || success)return normal;
  const long long left=begin+210000-std::llround(wb_robot_get_time()*1000);
  return left>0 && left<normal ? static_cast<int>(left) : normal;
}
extern "C" void gp_u_reset_complete(void) {
  begin=-1;attempt=0;expired=false;landed=false;success=false;
  fileIdle=false; // Only the next native idle/ground observation reopens files.
  WbFieldRef field=channel();if(field)wb_supervisor_field_set_sf_string(field,"");
}
extern "C" void gp_u_file_idle(int idle) { fileIdle=idle!=0; }
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

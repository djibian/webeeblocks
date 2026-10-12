#include <webots/robot.h>
#include <webots/plugins/robot_window/default.h>
#include <webots/supervisor.h>
#include <cstdio>
#include <cmath>
#include <cstring>
#include <string>
extern "C" const char *webeeblocks_file_broker_receive_text(void);
extern "C" void webeeblocks_file_broker_send(const char *,int);
namespace {
unsigned long long attempt=1;
int pending=-1;
double start=0;
bool debug=false;
bool engaged=false;
bool failed=false;
bool deadlineStopped=false;
bool completed=false;
int reset=-1;
int verticalPending=-1;
double nominalHeight=0,verticalTarget=0,takeoffHeight=0;
void marker(const char *state) {
  if(completed)return;
  if(!std::strcmp(state,"failed"))failed=true;
  if(failed && std::strcmp(state,"failed"))return;
  WbNodeRef node=wb_supervisor_node_get_from_def("GP_EVALUATOR");
  WbFieldRef field=node?wb_supervisor_node_get_field(node,"customData"):nullptr;
  if (!field)return;
  char text[192];
  std::snprintf(text,sizeof(text),"GP_START attempt=%llu time=%.9f debug=%d state=%s",attempt,start,debug?1:0,state);
  wb_supervisor_field_set_sf_string(field,text);
}
}
extern "C" const char *webeeblocks_gp_receive_text(void) {
  // A certified, exact-attempt landed success is terminal until Reset. Merely
  // reaching COMPLETE, a stale result, or a pending takeoff never stops the bound.
  if(engaged && !failed && pending<1 && !completed) {
    WbFieldRef channel=wb_supervisor_node_get_field(wb_supervisor_node_get_self(),"customData");
    unsigned long long resultAttempt=0;char oracle[64]={0},status[32]={0},tail[2]={0};
    const char *result=channel?wb_supervisor_field_get_sf_string(channel):nullptr;
    completed=result && std::sscanf(result,"WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%63s status=%31s %1s",&resultAttempt,oracle,status,tail)==3 && resultAttempt==attempt && !std::strcmp(oracle,"grand-prix-v1") && !std::strcmp(status,"achieved");
  }
  // Simulation deadline remains live while the shared interpreter/browser waits.
  if(engaged && !completed && !deadlineStopped && std::llround(wb_robot_get_time()*1000)-std::llround(start*1000)>600000) {
    deadlineStopped=true;marker("failed");
    return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 2147483647 STOP";
  }
  const char *message;
  while((message=webeeblocks_file_broker_receive_text())!=nullptr) {
    int id=-1,mode=-1;char command[32]={0},extra[2]={0};
    if(std::sscanf(message,"WEBEEBLOCKS_RUNTIME_V2 REQUEST %d %31s",&id,command)!=2)return message;
    if(!std::strcmp(command,"GP_MODE")) {
      const bool valid=id>0 && std::sscanf(message,"WEBEEBLOCKS_RUNTIME_V2 REQUEST %d GP_MODE %d %1s",&id,&mode,extra)==2 && (mode==0||mode==1) && !engaged;
      if(valid)debug=mode==1;else if(engaged)marker("failed");
      char reply[128];std::snprintf(reply,sizeof(reply),"WEBEEBLOCKS_RUNTIME_V2 RESPONSE %d %s",id,valid?"OK":"ERR INVALID_REQUEST");
      wb_robot_wwi_send_text(reply);continue;
    }
    if((failed||completed) && std::strcmp(command,"RESET") && std::strcmp(command,"STOP")) {
      char reply[128];std::snprintf(reply,sizeof(reply),"WEBEEBLOCKS_RUNTIME_V2 RESPONSE %d ERR RESET_REQUIRED",id);
      wb_robot_wwi_send_text(reply);continue;
    }
    if(!std::strcmp(command,"VERTICAL")) {
      double amount=0;char direction[16]={0},tail[2]={0};
      const bool parsed=std::sscanf(message,"WEBEEBLOCKS_RUNTIME_V2 REQUEST %d VERTICAL %15s %lf %1s",&id,direction,&amount,tail)==3;
      const bool down=!std::strcmp(direction,"down"),up=!std::strcmp(direction,"up");
      const double target=nominalHeight+(up?amount:-amount);
      if(!parsed || (!up&&!down) || !std::isfinite(amount) || amount<.1 || amount>.5 || nominalHeight==0 || verticalPending>=1 || target<.3-1e-9 || target>1.1+1e-9) {
        marker("failed");char reply[128];std::snprintf(reply,sizeof(reply),"WEBEEBLOCKS_RUNTIME_V2 RESPONSE %d ERR INVALID_VERTICAL",id);
        wb_robot_wwi_send_text(reply);continue;
      }
      verticalPending=id;verticalTarget=target;
    }
    if(!std::strcmp(command,"TAKEOFF")&&!engaged) {
      double height=0;char tail[2]={0};
      const bool parsed=std::sscanf(message,"WEBEEBLOCKS_RUNTIME_V2 REQUEST %d TAKEOFF %lf %1s",&id,&height,tail)==2;
      if(!parsed || !std::isfinite(height) || height<.3 || height>1.0) {
        marker("failed");char reply[128];std::snprintf(reply,sizeof(reply),"WEBEEBLOCKS_RUNTIME_V2 RESPONSE %d ERR INVALID_TAKEOFF",id);
        wb_robot_wwi_send_text(reply);continue;
      }
      takeoffHeight=height;
      pending=id;engaged=true;start=wb_robot_get_time();marker("pending");
    } else if(!std::strcmp(command,"RESET"))reset=id;
    else if(!std::strcmp(command,"STOP"))marker("failed");
    // Diagnostic only: receipt/admission boundary on the native simulation
    // clock. Never sent to the browser, used by control or subtracted from score.
    std::printf("WEBEEBLOCKS_GP_TIMING time_ms=%lld attempt=%llu phase=request id=%d command=%s\n",
                std::llround(wb_robot_get_time()*1000),attempt,id,command);
    return message;
  }
  return nullptr;
}
extern "C" void webeeblocks_gp_send(const char *data,int size) {
  // Preserve the existing attempt/Reset broker before any observer action.
  webeeblocks_file_broker_send(data,size);
  if(!data||size<1||std::memchr(data,'\0',size)!=data+size-1)return;
  int id=-1;char payload[96]={0};
  if(std::sscanf(data,"WEBEEBLOCKS_RUNTIME_V2 RESPONSE %d %95[^\n]",&id,payload)!=2)return;
  std::printf("WEBEEBLOCKS_GP_TIMING time_ms=%lld attempt=%llu phase=response id=%d payload=%s\n",
              std::llround(wb_robot_get_time()*1000),attempt,id,payload);
  if(id==reset) {
    if(!std::strcmp(payload,"OK")) {
      WbFieldRef channel=wb_supervisor_node_get_field(wb_supervisor_node_get_self(),"customData");
      unsigned long long current=0;
      if(channel && std::sscanf(wb_supervisor_field_get_sf_string(channel),"WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu",&current)==1)attempt=current;
      else {marker("failed");return;}
      pending=-1;reset=-1;engaged=false;debug=false;failed=false;deadlineStopped=false;completed=false;nominalHeight=0;verticalPending=-1;
      WbFieldRef field=wb_supervisor_node_get_field(wb_supervisor_node_get_from_def("GP_EVALUATOR"),"customData");
      if(field)wb_supervisor_field_set_sf_string(field,"");
    }
    if(std::strcmp(payload,"OK") && engaged)marker("failed");
    reset=-1;return;
  }
  if(id==verticalPending) {
    if(!std::strcmp(payload,"OK"))nominalHeight=verticalTarget;else marker("failed");
    verticalPending=-1;
  }
  if(id==pending) {
    if(!std::strcmp(payload,"OK"))nominalHeight=takeoffHeight;
    marker(!std::strcmp(payload,"OK")?"accepted":"failed");pending=-1;
  } else if(engaged&&!std::strncmp(payload,"ERR ",4))marker("failed");
}

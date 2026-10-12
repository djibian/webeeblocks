#include <webots/robot.h>
#include <webots/plugins/robot_window/default.h>
#include <webots/supervisor.h>
#include <cstdio>
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
int reset=-1;
void marker(const char *state) {
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
  // Simulation deadline remains live while the shared interpreter/browser waits.
  if(engaged && !deadlineStopped && wb_robot_get_time()-start>600.0) {
    deadlineStopped=true;marker("failed");
    return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 2147483647 STOP";
  }
  const char *message;
  while((message=webeeblocks_file_broker_receive_text())!=nullptr) {
    int id=-1,mode=-1;char command[32]={0},extra[2]={0};
    if(std::sscanf(message,"WEBEEBLOCKS_RUNTIME_V2 REQUEST %d %31s",&id,command)!=2)return message;
    if(!std::strcmp(command,"GP_MODE")) {
      const bool valid=id>0 && std::sscanf(message,"WEBEEBLOCKS_RUNTIME_V2 REQUEST %d GP_MODE %d %1s",&id,&mode,extra)==2 && (mode==0||mode==1) && !engaged;
      if(valid)debug=mode==1;
      char reply[128];std::snprintf(reply,sizeof(reply),"WEBEEBLOCKS_RUNTIME_V2 RESPONSE %d %s",id,valid?"OK":"ERR INVALID_REQUEST");
      wb_robot_wwi_send_text(reply);continue;
    }
    if(!std::strcmp(command,"TAKEOFF")&&!engaged) {
      pending=id;engaged=true;start=wb_robot_get_time();marker("pending");
    } else if(!std::strcmp(command,"RESET"))reset=id;
    else if(!std::strcmp(command,"STOP"))marker("failed");
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
  if(id==reset) {
    if(!std::strcmp(payload,"OK")) {
      WbFieldRef channel=wb_supervisor_node_get_field(wb_supervisor_node_get_self(),"customData");
      unsigned long long current=0;
      if(channel && std::sscanf(wb_supervisor_field_get_sf_string(channel),"WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu",&current)==1)attempt=current;
      else {marker("failed");return;}
      pending=-1;reset=-1;engaged=false;debug=false;failed=false;deadlineStopped=false;
      WbFieldRef field=wb_supervisor_node_get_field(wb_supervisor_node_get_from_def("GP_EVALUATOR"),"customData");
      if(field)wb_supervisor_field_set_sf_string(field,"");
    }
    reset=-1;return;
  }
  if(id==pending) {
    marker(!std::strcmp(payload,"OK")?"accepted":"failed");pending=-1;
  } else if(engaged&&!std::strncmp(payload,"ERR ",4))marker("failed");
}

// Quarantined protocol stimulus: ONE TAKEOFF, then RESET only AFTER the real
// pilot independently completed its safety LAND. No LAND is injected, no pose,
// sensor, gyro, PID, time, oracle or safety function is replaced.
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

extern "C" const char *__real_wb_robot_wwi_receive_text(void);
extern "C" void __real_gp_u_send(const char *, int);
namespace {
int phase=0;
long long takeoff=-1,land=-1,reset=-1;
void persist() {
  const char *path=std::getenv("GP_ROUTE_PILOT_ACK_OUT");
  if(!path)std::abort();
  const std::string pending=std::string(path)+".pending";
  FILE *f=std::fopen(pending.c_str(),"w");
  if(!f)std::abort();
  std::fprintf(f,"{\"takeoff_ack_ms\":%lld,\"land_ack_ms\":%lld,\"reset_ack_ms\":%lld}\n",takeoff,land,reset);
  if(std::fclose(f))std::abort();
  if(std::rename(pending.c_str(),path))std::abort();
}
}
extern "C" const char *__wrap_wb_robot_wwi_receive_text(void) {
  if(phase==0) {
    WbNodeRef node=wb_supervisor_node_get_from_def("GP_ROUTE_EVALUATOR");
    WbFieldRef f=node?wb_supervisor_node_get_field(node,"description"):nullptr;
    const char *text=f?wb_supervisor_field_get_sf_string(f):nullptr;
    const char *prefix="GP_ROUTE_READY_V1 attempt=1 ";
    if(text && !std::strncmp(text,prefix,std::strlen(prefix))) {
      phase=1;
      std::puts("GP_ROUTE_PILOT_REQUEST id=1 command=TAKEOFF");std::fflush(stdout);
      return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 1 TAKEOFF 0.4";
    }
  } else if(phase==3) {
    phase=4;
    std::puts("GP_ROUTE_PILOT_REQUEST id=2 command=RESET");std::fflush(stdout);
    return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 2 RESET";
  }
  return __real_wb_robot_wwi_receive_text();
}
extern "C" void __wrap_gp_u_send(const char *data,int size) {
  // Broker sees the genuine ACK first; it alone advances RESET attempt state.
  __real_gp_u_send(data,size);
  if(!data || size<1 || data[size-1]!='\0')return;
  const long long now=std::llround(wb_robot_get_time()*1000);
  if(phase==1 && !std::strcmp(data,"WEBEEBLOCKS_RUNTIME_V2 RESPONSE 1 OK")) {
    takeoff=now;phase=2;persist();
    std::printf("GP_ROUTE_PILOT_ACK id=1 time_ms=%lld\n",now);std::fflush(stdout);
  } else if(phase==2 && !std::strcmp(data,"WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2147483646 OK")) {
    land=now;phase=3;persist();
    std::printf("GP_ROUTE_PILOT_ACK id=2147483646 time_ms=%lld\n",now);std::fflush(stdout);
  } else if(phase==4 && !std::strcmp(data,"WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 OK")) {
    reset=now;phase=5;persist();
    std::printf("GP_ROUTE_PILOT_ACK id=2 time_ms=%lld\n",now);std::fflush(stdout);
  }
}

// Quarantined protocol stimulus: ONE TAKEOFF, then RESET only AFTER the real
// pilot independently completed its safety LAND. No LAND is injected, no pose,
// sensor, gyro, PID, time, oracle or safety function is replaced.
#include <webots/robot.h>
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
    // The native evaluator alone writes this test-only cue AFTER observing
    // its real, continuous READY. Never query another synchronized Supervisor
    // from inside the flight controller's WWI receive callback: that can stall
    // the two Webots controller steps. Production admission is still checked
    // independently by gp_u_start; this file grants no flight authority.
    const char *path=std::getenv("GP_ROUTE_PILOT_NATIVE_READY_OUT");
    const char *expected_course=std::getenv("GP_ROUTE_PILOT_COURSE_ID");
    bool observed=false;
    if(path && expected_course) {
      FILE *stream=std::fopen(path,"r");
      if(stream) {
        char line[256]={}, course[160]={}, trailing='\0';
        long long native_ms=-1;
        if(std::fgets(line,sizeof line,stream) &&
           std::sscanf(line,"GP_ROUTE_PROBE_READY_V1 attempt=1 course=%159s time_ms=%lld %c",
                       course,&native_ms,&trailing)==2 &&
           std::strcmp(course,expected_course)==0 && native_ms>=500 && native_ms%8==0)
          observed=true;
        std::fclose(stream);
      }
    }
    if(observed) {
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

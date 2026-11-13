// Quarantined protocol stimulus: TAKEOFF, independent safety LAND, RESET,
// then one fresh TAKEOFF. No LAND is injected and no native flight logic is replaced.
#include <webots/robot.h>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

extern "C" const char *__real_wb_robot_wwi_receive_text(void);
extern "C" void __real_gp_u_send(const char *, int);
namespace {
enum Phase {
  wait_first_ready, first_takeoff_sent, wait_safety_land, send_reset,
  reset_sent, wait_second_ready, second_takeoff_sent, send_negative_move,
  negative_move_sent, finished
};
Phase phase=wait_first_ready;
long long takeoff=-1,land=-1,reset=-1,second_takeoff=-1;
void persist() {
  const char *path=std::getenv("GP_ROUTE_PILOT_ACK_OUT");
  if(!path)std::abort();
  const std::string pending=std::string(path)+".pending";
  FILE *f=std::fopen(pending.c_str(),"w");
  if(!f)std::abort();
  std::fprintf(f,"{\"takeoff_ack_ms\":%lld,\"land_ack_ms\":%lld,"
                 "\"reset_ack_ms\":%lld,\"second_takeoff_ack_ms\":%lld}\n",
               takeoff,land,reset,second_takeoff);
  if(std::fclose(f))std::abort();
  if(std::rename(pending.c_str(),path))std::abort();
}
}
extern "C" const char *__wrap_wb_robot_wwi_receive_text(void) {
  if(phase==wait_first_ready || phase==wait_second_ready) {
    // The native evaluator alone writes this test-only cue AFTER observing
    // its real, continuous READY. Never query another synchronized Supervisor
    // from inside the flight controller's WWI receive callback: that can stall
    // the two Webots controller steps. Production admission is still checked
    // independently by gp_u_start; this file grants no flight authority.
    const char *path=std::getenv("GP_ROUTE_PILOT_NATIVE_READY_OUT");
    const char *expected_course=std::getenv("GP_ROUTE_PILOT_COURSE_ID");
    const bool after_reset=phase==wait_second_ready;
    bool observed=false;
    if(path && expected_course) {
      const std::string marker=std::string(path)+(after_reset?".second":"");
      FILE *stream=std::fopen(marker.c_str(),"r");
      if(stream) {
        char line[256]={}, course[160]={}, trailing='\0';
        int attempt=0;
        long long native_ms=-1;
        if(std::fgets(line,sizeof line,stream) &&
           std::sscanf(line,"GP_ROUTE_PROBE_READY_V1 attempt=%1d course=%159s time_ms=%lld %c",
                       &attempt,course,&native_ms,&trailing)==3 &&
           attempt==(after_reset?2:1) && std::strcmp(course,expected_course)==0 &&
           native_ms>=500 && native_ms%8==0 && (!after_reset || native_ms>reset+500))
          observed=true;
        std::fclose(stream);
      }
    }
    if(observed) {
      if(after_reset) {
        phase=second_takeoff_sent;
        std::puts("GP_ROUTE_PILOT_REQUEST id=3 command=TAKEOFF");std::fflush(stdout);
        return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 3 TAKEOFF 0.4";
      }
      phase=first_takeoff_sent;
      std::puts("GP_ROUTE_PILOT_REQUEST id=1 command=TAKEOFF");std::fflush(stdout);
      return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 1 TAKEOFF 0.4";
    }
  } else if(phase==send_negative_move) {
    // Test-only ordinary Blockly-equivalent lateral request. The genuine C
    // flight controller, native physics and mission evaluator remain in charge.
    phase=negative_move_sent;
    const char *path=std::getenv("GP_ROUTE_PILOT_NEGATIVE_OUT");
    const char *course=std::getenv("GP_ROUTE_PILOT_COURSE_ID");
    if(!path || !course)std::abort();
    const long long now=std::llround(wb_robot_get_time()*1000);
    const std::string pending=std::string(path)+".pending";
    FILE *f=std::fopen(pending.c_str(),"w");if(!f)std::abort();
    if(std::fprintf(f,"GP_ROUTE_PILOT_NEGATIVE_REQUEST_V1 time_ms=%lld course=%s action=MOVE-right-1.2\\n",
                    now,course)<1 || std::fclose(f))std::abort();
    if(std::rename(pending.c_str(),path))std::abort();
    std::puts("GP_ROUTE_PILOT_REQUEST id=2 command=MOVE right 1.2");
    std::fflush(stdout);
    return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 2 MOVE right 1.2";
  } else if(phase==send_reset) {
    phase=reset_sent;
    std::puts("GP_ROUTE_PILOT_REQUEST id=2 command=RESET");std::fflush(stdout);
    return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 2 RESET";
  }
  return __real_wb_robot_wwi_receive_text();
}
extern "C" void __wrap_gp_u_send(const char *data,int size) {
  // Broker sees the genuine ACK first; it alone advances RESET attempt state.
  __real_gp_u_send(data,size);
  // Bounded observation of the REAL outgoing buffer, including startup/error
  // responses. This diagnoses dispatch vs delayed completion without creating
  // an ACK or changing its broker path. No Supervisor query is made here.
  if(data && size>0) {
    std::printf("GP_ROUTE_PILOT_SEND phase=%d size=%d data=%.*s\n",
                phase,size,size<128?size:128,data);
    std::fflush(stdout);
  }
  if(!data || size<1 || data[size-1]!='\0')return;
  const long long now=std::llround(wb_robot_get_time()*1000);
  if(phase==first_takeoff_sent && !std::strcmp(data,"WEBEEBLOCKS_RUNTIME_V2 RESPONSE 1 OK")) {
    takeoff=now;
    phase=std::getenv("GP_ROUTE_PILOT_NEGATIVE_OUT")
          ?send_negative_move:wait_safety_land;
    persist();
    std::printf("GP_ROUTE_PILOT_ACK id=1 time_ms=%lld\n",now);std::fflush(stdout);
  } else if(phase==wait_safety_land && !std::strcmp(data,"WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2147483646 OK")) {
    land=now;phase=send_reset;persist();
    std::printf("GP_ROUTE_PILOT_ACK id=2147483646 time_ms=%lld\n",now);std::fflush(stdout);
  } else if(phase==reset_sent && !std::strcmp(data,"WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 OK")) {
    reset=now;phase=wait_second_ready;persist();
    std::printf("GP_ROUTE_PILOT_ACK id=2 time_ms=%lld\n",now);std::fflush(stdout);
  } else if(phase==second_takeoff_sent && !std::strcmp(data,"WEBEEBLOCKS_RUNTIME_V2 RESPONSE 3 OK")) {
    second_takeoff=now;phase=finished;persist();
    std::printf("GP_ROUTE_PILOT_ACK id=3 time_ms=%lld\n",now);std::fflush(stdout);
  }
}

// Real Webots time/fields, controlled pose/outcome. No flight claim.
#include <webots/robot.h>
#include <webots/supervisor.h>
#include "grand_prix_u_hook.h"
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
extern "C" const char *webeeblocks_file_broker_receive_text(){return nullptr;}
extern "C" void webeeblocks_file_broker_send(const char*,int){}
static bool persist(const char* message){
  const char* path=std::getenv("GP_U_DEADLINE_OUT");
  if(!path)return false;
  FILE* file=std::fopen(path,"w");if(!file)return false;
  const bool written=std::fprintf(file,"%s\n",message)>0 && std::fflush(file)==0;
  return std::fclose(file)==0 && written;
}
static void require(bool condition,const char* why){
  if(!condition){char failure[256];std::snprintf(failure,sizeof(failure),"GP_U_NATIVE_FAIL %s",why);persist(failure);std::fprintf(stderr,"%s\n",failure);wb_supervisor_simulation_quit(1);wb_robot_cleanup();std::exit(1);}
}
int main(int argc,char** argv){
  wb_robot_init();require(argc==2,"case");
  const int mode=std::atoi(argv[1]);
  const char* achieved="WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=1 oracle=grand-prix-u-v1 status=achieved";
  const char* failed="WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=1 oracle=grand-prix-u-v1 status=not-achieved";
  WbFieldRef self=wb_supervisor_node_get_field(wb_supervisor_node_get_self(),"customData");
  WbFieldRef evaluator=wb_supervisor_node_get_field(wb_supervisor_node_get_from_def("GP_U_EVALUATOR"),"customData");
  require(self && evaluator,"channels");
  while(std::llround(wb_robot_get_time()*1000)<2112)require(wb_robot_step(32)!=-1,"startup");
  wb_supervisor_field_set_sf_string(self,"WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1");
  require(gp_u_start(wb_robot_get_time())==1,"admission");
  const long long begin=std::llround(wb_robot_get_time()*1000);
  std::printf("GP_U_NATIVE_START case=%d begin=%lld\n",mode,begin);std::fflush(stdout);
  int triggers=0;long long trigger_ms=-1;bool injected=false,shortened=false;
  while(true){
    int step=gp_u_next_step(32);
    if(step==16)shortened=true;
    // An evaluator write between control ticks, with no acquisition until cap.
    if(mode==3 && std::llround(wb_robot_get_time()*1000)-begin==209984){
      require(step==16,"last shortened step");
      require(wb_robot_step(8)!=-1,"between ticks");
      wb_supervisor_field_set_sf_string(self,achieved);injected=true;
      step=8;
    }
    // Mode 2 delivers success one real base tick after the deadline.
    if(mode==2 && triggers && !injected)step=8;
    require(wb_robot_step(step)!=-1,"step");
    const long long elapsed=std::llround(wb_robot_get_time()*1000)-begin;
    if(elapsed<=32 || elapsed>=209984){std::printf("GP_U_NATIVE_TICK case=%d elapsed=%lld step=%d\n",mode,elapsed,step);std::fflush(stdout);}
    if(!injected && ((mode==0 && elapsed==209984)||(mode==1 && elapsed==210000)||(mode==2 && elapsed==210008))){
      wb_supervisor_field_set_sf_string(self,achieved);injected=true;
    }
    if(gp_u_deadline(wb_robot_get_time(),mode==4?0:1)){++triggers;trigger_ms=elapsed;}
    if(elapsed>=210032)break;
  }
  require(triggers==(mode==0?0:1),"unique LAND trigger");
  require(mode==0 || trigger_ms==210000,"exact deadline");
  require(mode==0 || shortened,"last 16ms step observed");
  if(mode==0)require(!std::strcmp(wb_supervisor_field_get_sf_string(self),achieved),"early success preserved");
  else{
    require(!std::strcmp(wb_supervisor_field_get_sf_string(self),failed),"late success refused");
    require(std::strstr(wb_supervisor_field_get_sf_string(evaluator),"state=deadline"),"evaluator expired");
    wb_supervisor_field_set_sf_string(self,achieved);
    require(gp_u_filter_raw("WEBEEBLOCKS_RUNTIME_V2 REQUEST 2 OUTCOME grand-prix-u-v1")==1,"OUTCOME readable");
    require(!std::strcmp(wb_supervisor_field_get_sf_string(self),failed),"OUTCOME cannot expose late success");
    require(gp_u_filter_raw("WEBEEBLOCKS_RUNTIME_V2 REQUEST 3 MOVE forward 0.1")==0,"late effect denied");
    require(gp_u_filter_raw("WEBEEBLOCKS_RUNTIME_V2 REQUEST 4 RESET")== (mode==4?0:1),"RESET pose gate");
  }
  // Successful completion is resting; expired/unfinished attempts are not.
  // The composed controller supplies IDLE and fresh ground observations.
  gp_u_file_idle(1);
  require(gp_u_filter_raw("WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 41 OPEN")== (mode==0?1:0),"resting file success gate");
  if(mode==0) {
    require(gp_u_deadline(wb_robot_get_time(),0)==0,"no rearmed deadline on pose loss");
    require(gp_u_filter_raw("WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 42 SAVE ref e30=")==0,"lost success pose closes files");
    require(gp_u_deadline(wb_robot_get_time(),1)==0,"no duplicate deadline");
    require(gp_u_filter_raw("WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 43 SAVE ref e30=")==1,"fresh successful resting pose");
  }
  char evidence[256];
  std::snprintf(evidence,sizeof(evidence),"GP_U_NATIVE_DEADLINE case=%d triggers=%d trigger_ms=%lld claim=time-fields-only",mode,triggers,trigger_ms);
  // Webots can terminate before draining the controller's last stdout tick.
  // Persist the assertion result before requesting simulation shutdown.
  require(persist(evidence),"durable native record");
  std::printf("%s\n",evidence);std::fflush(stdout);
  wb_supervisor_simulation_quit(0);wb_robot_cleanup();return 0;
}

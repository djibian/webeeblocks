// Full composed runtime/broker/hook. Native mode uses real Webots sensors/time,
// with controlled Supervisor poses; stub mode isolates causal interleavings.
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <webots/gps.h>
#include <webots/gyro.h>
#include <webots/inertial_unit.h>
#include "file_broker_c.h"
#ifndef GP_NATIVE
extern "C" {
#include "pid_controller.h"
}
#endif
// Webots release builds define NDEBUG. Test assertions must remain executable.
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <cfloat>
extern "C" int gp_runtime_main(void);
static std::string mode, vehicle, evaluator;
static long long tick=0;
static double pos[3]={0,0,.023},rot[4]={1,0,0,0},imu[3]={0,0,0},gyro[3]={0,0,0};
static bool takeoff=false,reset_ok=false;
static int teleports=0,requests_at_tick=0;
static long long receive_tick=-1;
static std::vector<std::string> replies;
static bool reset_case(){return mode.find("reset-")==0;}
static bool flight_case(){return mode.find("flight-")==0;}
static bool reset_success(){return mode=="land" || mode=="error-ground" || mode=="loss-recover" ||
 mode.find("-recover")!=std::string::npos || mode=="reset-queue";}
static bool positive(){return reset_case() || reset_success();}
static bool fault(){return !reset_case() && !flight_case() && mode!="land" && mode!="no-fault" && mode!="timeout" && mode!="land-timeout";}
// Interrupt immediately before the old RESET OK, after a partial valid window.
static bool reset_loss(){
 const long long loss=mode.find("-final-")!=std::string::npos?213264:
  mode.find("-first-")!=std::string::npos?212752:212944;
 return reset_case() && teleports && tick>=loss &&
  (mode.find("-recover")==std::string::npos || tick==loss);
}
static long long fault_tick(){return mode=="early-error"?4096:212048;}
static long long reset_tick(){
 if(mode=="early-error")return 4128;
 if(mode=="timeout")return 27104;
 if(mode=="land-timeout")return 237104;
 if(reset_case() || flight_case() || mode=="land" || mode=="error-ground")return 212720;
 if(mode=="loss-recover")return 212688;
 return 212080;
}
static long long end_tick(){return mode=="land-timeout"?238000:reset_case() && !reset_success()?218000:214000;}
static bool grounds(){
 return positive() || mode=="gps-nan" || mode=="imu-nan" || mode=="gyro-nan" ||
        mode=="bounce" || mode=="moving" || mode=="below-ground";
}
static void set_scene(long long next){
 if(teleports){
  // Continue the same controlled-pose policy through RESET, holding the
  // actual pose requested by the runtime rather than introducing a drift test.
#ifdef GP_NATIVE
  auto self=wb_supervisor_node_get_self();
  wb_supervisor_field_set_sf_vec3f(wb_supervisor_node_get_field(self,"translation"),pos);
  wb_supervisor_field_set_sf_rotation(wb_supervisor_node_get_field(self,"rotation"),rot);
  wb_supervisor_node_reset_physics(self);
#endif
  return;
 }
 pos[0]=0;pos[1]=0;
 pos[2]=!takeoff?.023:mode=="timeout"?.423:.823;
 if(takeoff && grounds() && next>=212112)pos[2]=mode=="below-ground"?-.10:.023;
 if(mode=="bounce" && next>=212512)pos[2]=.823;
 if(mode=="moving" && next>=212112)pos[0]=(next-212112)*.001;
 // IMU sampling is 32 ms: the final 16 ms deadline step retains the
 // preceding sample. Establish the fault at that sample and hold to expiry.
 const long long fault_from=fault_tick()-(fault_tick()==212048?16:0);
 rot[0]=1;rot[1]=0;rot[2]=0;
 rot[3]=fault() && next>=fault_from && next<=fault_tick()?1.3:0;
#ifdef GP_NATIVE
 auto self=wb_supervisor_node_get_self();
 wb_supervisor_field_set_sf_vec3f(wb_supervisor_node_get_field(self,"translation"),pos);
 wb_supervisor_field_set_sf_rotation(wb_supervisor_node_get_field(self,"rotation"),rot);
 wb_supervisor_node_reset_physics(self);
#else
 imu[0]=rot[3];
#endif
}
extern "C" int gp_test_step(int dt){
 // A real longer Webots step creates an observation gap, not a fake sample.
 if(mode=="reset-gap-recover" && tick==212912)dt=64;
 set_scene(tick+dt);
#ifdef GP_NATIVE
 const int result=wb_robot_step(dt);
 if(result==-1)return -1;
 tick=std::llround(wb_robot_get_time()*1000);
#else
 tick+=dt;
#endif
 return tick<end_tick()?0:-1;
}
extern "C" const double* gp_test_gps(int tag){
 static double data[3];
#ifdef GP_NATIVE
 const double* sample=wb_gps_get_values(tag);
#else
 const double* sample=pos;
#endif
 std::memcpy(data,sample,sizeof(data));
 if(teleports && !reset_ok)std::printf("GP_U_POSE_RESET_GPS t=%lld x=%.6f y=%.6f z=%.6f\n",tick,data[0],data[1],data[2]);
 if(tick==212048 || tick==212080)std::printf("GP_U_POSE_GPS t=%lld z=%.6f\n",tick,data[2]);
 if(tick>=212112 && (mode=="gps-nan" || (mode=="loss-recover" && tick==212688)))data[2]=NAN;
 if(reset_loss() && mode=="reset-gps-null")return nullptr;
 if(reset_loss() && mode=="reset-gps-recover")data[0]=NAN;
 return data;
}
extern "C" const double* gp_test_imu(int tag){
 static double data[3];
 static bool invalid_angle_reported=false;
#ifdef GP_NATIVE
 const double* sample=wb_inertial_unit_get_roll_pitch_yaw(tag);
#else
 const double* sample=imu;
#endif
 std::memcpy(data,sample,sizeof(data));
 if(teleports && !reset_ok)std::printf("GP_U_POSE_RESET_IMU t=%lld roll=%.6f pitch=%.6f yaw=%.6f\n",tick,data[0],data[1],data[2]);
 if(tick==fault_tick())std::printf("GP_U_POSE_IMU t=%lld roll=%.6f pitch=%.6f\n",tick,data[0],data[1]);
 if(mode=="imu-nan" && tick>=212112)data[0]=NAN;
 if(reset_loss() && mode=="reset-imu-null")return nullptr;
 if(reset_loss() && mode=="reset-yaw-infinite")data[2]=INFINITY;
 if(reset_loss() && (mode=="reset-yaw-high" || mode=="reset-yaw-recover"))data[2]=0.3;
 if(reset_loss() && mode=="reset-imu-recover")data[1]=NAN;
 const long long flight_loss=mode=="flight-yaw-deadline-recover"?212048:2656;
 const bool bad_angle=(flight_case() && tick>=flight_loss &&
   (mode.find("-recover")==std::string::npos || tick==flight_loss)) || reset_loss();
 if(!bad_angle)invalid_angle_reported=false;
 if(bad_angle && (flight_case() || mode.find("reset-yaw-")==0 ||
    mode=="reset-roll-extreme-loss" || mode=="reset-pitch-extreme-loss")){
  const int axis=mode=="reset-roll-extreme-loss"?0:mode=="reset-pitch-extreme-loss"?1:2;
  if(mode.find("extreme")!=std::string::npos)data[axis]=mode.find("negative")!=std::string::npos?-1e20:1e20;
  if(mode.find("max")!=std::string::npos)data[axis]=DBL_MAX;
  if(mode.find("periodic")!=std::string::npos)data[axis]=2*std::acos(-1.0);
  if(flight_case() && mode.find("infinite")!=std::string::npos)data[axis]=mode.find("negative")!=std::string::npos?-INFINITY:INFINITY;
  if(flight_case() && mode.find("nan")!=std::string::npos)data[axis]=NAN;
  if(mode=="flight-yaw-deadline-recover")data[axis]=INFINITY;
  // Thousands of per-tick console writes can slow the native probe itself.
  // Retain the first loss, every new loss after recovery, and the deadline.
  if(!invalid_angle_reported || tick==212048)
   std::printf("GP_U_POSE_INVALID_ANGLE t=%lld axis=%d value=%g\n",tick,axis,data[axis]);
  invalid_angle_reported=true;
 }
 return data;
}
extern "C" const double* gp_test_gyro(int tag){
 static double data[3];
#ifdef GP_NATIVE
 const double* sample=wb_gyro_get_values(tag);
#else
 const double* sample=gyro;
#endif
 std::memcpy(data,sample,sizeof(data));
 if(mode=="gyro-nan" && tick>=212112)data[0]=NAN;
 if(reset_loss()){
  if(mode=="reset-gyro-null")return nullptr;
  for(int axis=0;axis<3;++axis){
   const std::string prefix=std::string("reset-gyro-")+"xyz"[axis];
   if(mode.find(prefix)==0)data[axis]=mode.find("-high")!=std::string::npos?0.2:NAN;
  }
 }
 return data;
}
extern "C" void gp_test_teleport(WbFieldRef field,const double* value){
 ++teleports;
 std::printf("GP_U_POSE_TELEPORT t=%lld before_z=%.3f after_z=%.3f\n",tick,pos[2],value[2]);
 assert(positive() && tick>212688); // Never before actual stable observations.
 wb_supervisor_field_set_sf_vec3f(field,value);
 std::memcpy(pos,value,sizeof(pos));
}
extern "C" const char* gp_test_receive(){
 if(receive_tick!=tick){receive_tick=tick;requests_at_tick=0;}
 const int index=requests_at_tick++;
 if(tick==2048 && index==0){takeoff=true;return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 1 TAKEOFF 0.8";}
 if(flight_case() && tick==(mode=="flight-yaw-deadline-recover"?212048:2656)){
  if(index==0)return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 41 MOVE forward 0.1";
  if(index==1)return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 42 TAKEOFF 0.8";
  if(index==2)return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 43 RESET";
 }
 if(mode=="early-error" && tick==4064 && index==0)return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 8 WAIT 5";
 if(tick==reset_tick() && index==0)return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 2 RESET";
 if(mode=="loss-recover" && tick==213328 && index==0)return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 3 RESET";
 if(reset_case() && tick==213008){
  if(index==0)return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 31 RESET";
  if(index==1)return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 32 TAKEOFF 0.8";
  if(index==2)return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 33 MOVE forward 0.1";
  if(index==3)return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 34 COMPLETE grand-prix-u-v1";
  if(index==4){
   wb_supervisor_field_set_sf_string(wb_supervisor_node_get_field(wb_supervisor_node_get_self(),"customData"),
    "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=1 oracle=grand-prix-u-v1 status=achieved");
   return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 35 OUTCOME grand-prix-u-v1";
  }
 }
 // Queue RESET both at LAND admission and one tick after the fault.
 if(!positive() && (tick==212048 || tick==212080)){
  if(index==0)return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 21 RESET";
  if(index==1)return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 22 MOVE forward 0.1";
  if(index==2)return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 23 COMPLETE grand-prix-u-v1";
 }
 // A fresh producer tries to overwrite failure after expiry.
 if(tick==212112 && index==0){
  wb_supervisor_field_set_sf_string(wb_supervisor_node_get_field(wb_supervisor_node_get_self(),"customData"),
    "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=1 oracle=grand-prix-u-v1 status=achieved");
  return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 24 OUTCOME grand-prix-u-v1";
 }
 // Stable ground has not happened in these negative cases.
 if(!positive() && tick==213328 && index==0)return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 3 RESET";
 return nullptr;
}
extern "C" void gp_test_send(const char* data,int){
 std::string reply=data?data:"";replies.push_back(reply);
 std::printf("GP_U_POSE_RESPONSE t=%lld %s\n",tick,reply.c_str());
 if(reply=="WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 OK" || reply=="WEBEEBLOCKS_RUNTIME_V2 RESPONSE 3 OK"){
  if(reset_case()){
   assert(reset_success());
   // First valid sample after loss/gap is 212976/213008 respectively.
   const long long earliest=mode=="reset-queue"?213264:mode=="reset-gap-recover"?213520:
    mode.find("-final-")!=std::string::npos?213808:
    mode.find("-first-")!=std::string::npos?213296:213488;
   assert(tick>=earliest);
  }
  reset_ok=true;
 }
}
static bool saw(const std::string& text){
 for(const auto& reply:replies)if(reply==text)return true;
 return false;
}
extern "C" void gp_test_cleanup(){
 const auto self=wb_supervisor_node_get_self();
 const char* result=wb_supervisor_field_get_sf_string(wb_supervisor_node_get_field(self,"customData"));
 const char* authority=wb_supervisor_field_get_sf_string(wb_supervisor_node_get_field(wb_supervisor_node_get_from_def("GP_U_EVALUATOR"),"customData"));
 assert(saw("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 24 STATE not-achieved"));
 assert(teleports==(positive()?1:0) && reset_ok==reset_success());
 if(reset_case()){
  for(int id=31;id<=34;++id)assert(saw("WEBEEBLOCKS_RUNTIME_V2 RESPONSE "+std::to_string(id)+" ERR TIME_LIMIT"));
  assert(saw("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 35 STATE not-achieved"));
  if(!reset_success())assert(saw("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 ERR RESET_TIMEOUT"));
 }
 if(reset_success()){
  assert(!std::strcmp(result,"WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2"));
  assert(!*authority);
  if(mode=="loss-recover")assert(saw("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 ERR TIME_LIMIT"));
 }else{
  assert(std::strstr(result,"status=not-achieved") && std::strstr(authority,"state=deadline"));
  if(!reset_case())assert(saw(std::string("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2 ERR ")+
    ((mode=="early-error" || mode=="timeout")?"LANDING_UNCONFIRMED":"TIME_LIMIT")));
  if(!reset_case())assert(saw("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 3 ERR TIME_LIMIT"));
 }
 if(fault())assert(saw("WEBEEBLOCKS_RUNTIME_V2 RESPONSE "+
   std::string(mode=="early-error"?"8":"2147483646")+" ERR UNSAFE_OR_TIMEOUT"));
 if(mode=="timeout")assert(saw("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 1 ERR UNSAFE_OR_TIMEOUT"));
 if(mode=="land-timeout")assert(saw("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2147483646 ERR UNSAFE_OR_TIMEOUT"));
 if(flight_case()){
  const bool at_deadline=mode=="flight-yaw-deadline-recover";
  for(int id=41;id<=42;++id)assert(saw("WEBEEBLOCKS_RUNTIME_V2 RESPONSE "+std::to_string(id)+
   " ERR "+(at_deadline?"TIME_LIMIT":"UNSAFE_OR_TIMEOUT")));
  assert(saw(std::string("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 43 ERR ")+
   (at_deadline?"TIME_LIMIT":"LANDING_UNCONFIRMED")));
  assert(saw("WEBEEBLOCKS_RUNTIME_V2 RESPONSE "+std::string(mode=="flight-yaw-deadline-recover"?"2147483646":"1")+" ERR UNSAFE_OR_TIMEOUT"));
  if(!reset_success())assert(saw("WEBEEBLOCKS_RUNTIME_V2 RESPONSE 2147483646 ERR UNSAFE_OR_TIMEOUT"));
 }
 char evidence[256];
 std::snprintf(evidence,sizeof(evidence),"GP_U_POSE_PASS case=%s teleports=%d reset_ok=%d claim=controlled-pose-composition",mode.c_str(),teleports,reset_ok);
 const char* path=std::getenv("GP_U_POSE_OUT");
 if(path){FILE* f=std::fopen(path,"w");assert(f);assert(std::fprintf(f,"%s\n",evidence)>0);assert(std::fclose(f)==0);}
 std::puts(evidence);std::fflush(stdout);
#ifdef GP_NATIVE
 wb_supervisor_simulation_quit(0);wb_robot_cleanup();
#endif
}
extern "C" WbFileBroker* wb_file_broker_create_qt(){return nullptr;}
extern "C" void wb_file_broker_destroy(WbFileBroker*){}
extern "C" const char* wb_file_broker_handle_message(WbFileBroker*,const char*){return nullptr;}
#ifndef GP_NATIVE
extern "C" void wb_robot_init(){}
extern "C" double wb_robot_get_time(){return tick/1000.0;}
extern "C" double wb_robot_get_basic_time_step(){return 8;}
extern "C" int wb_robot_get_device(const char*){return 1;}
extern "C" void wb_motor_set_position(int,double){}
extern "C" void wb_motor_set_velocity(int,double value){assert(std::isfinite(value));}
extern "C" void wb_gps_enable(int,int){}
extern "C" void wb_gyro_enable(int,int){}
extern "C" void wb_inertial_unit_enable(int,int){}
extern "C" void wb_distance_sensor_enable(int,int){}
extern "C" double wb_distance_sensor_get_value(int){return 1000;}
extern "C" void wb_led_set(int,int){}
extern "C" void* wb_supervisor_node_get_self(){return (void*)1;}
extern "C" void* wb_supervisor_node_get_from_def(const char*){return (void*)2;}
extern "C" void* wb_supervisor_node_get_field(void* n,const char* name){
 if(!std::strcmp(name,"translation"))return (void*)4;
 if(!std::strcmp(name,"rotation"))return (void*)5;
 return n==(void*)1?(void*)3:(void*)6;
}
extern "C" const char* wb_supervisor_field_get_sf_string(void* f){return (f==(void*)3?vehicle:evaluator).c_str();}
extern "C" void wb_supervisor_field_set_sf_string(void* f,const char* s){(f==(void*)3?vehicle:evaluator)=s;}
extern "C" const double* wb_supervisor_field_get_sf_vec3f(void*){return pos;}
extern "C" const double* wb_supervisor_field_get_sf_rotation(void*){return rot;}
extern "C" void wb_supervisor_field_set_sf_vec3f(void*,const double* v){std::memcpy(pos,v,sizeof(pos));}
extern "C" void wb_supervisor_field_set_sf_rotation(void*,const double* v){std::memcpy(rot,v,sizeof(rot));}
extern "C" void wb_supervisor_node_reset_physics(void*){}
void init_pid_attitude_fixed_height_controller(){}
void pid_velocity_fixed_height_controller(actual_state_t a,desired_state_t* d,gains_pid_t,double,motor_power_t* p){
 assert(std::isfinite(a.roll) && std::isfinite(a.pitch) && std::isfinite(a.yaw_rate) &&
  std::isfinite(a.altitude) && std::isfinite(a.vx) && std::isfinite(a.vy));
 assert(std::isfinite(d->roll) && std::isfinite(d->pitch) && std::isfinite(d->yaw_rate) &&
  std::isfinite(d->altitude) && std::isfinite(d->vx) && std::isfinite(d->vy));
 std::memset(p,0,sizeof(*p));
}
#endif
int main(){
 std::setvbuf(stdout,nullptr,_IONBF,0);
 const char* name=std::getenv("GP_U_POSE_CASE");assert(name);mode=name;
 return gp_runtime_main();
}

// Experimental public-API fixture around the unmodified production controller.
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <webots/motor.h>
#include <webots/gps.h>
#include <webots/gyro.h>
#include <webots/inertial_unit.h>
#include <webots/plugins/robot_window/default.h>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>

static const double prepared[4] = {-43.97307910799943,43.955769775850364,
                                  -43.95630369565706,43.97361302687336};
static WbDeviceTag motors[4], fx_gps, fx_imu, fx_gyro;
static WbNodeRef fx_self, motor_nodes[4];
static WbFieldRef fx_translation, fx_rotation;
static double fx_initial[3], fx_initial_rotation[4], fx_ack=-1, fx_sent_time=-1;
static int fx_phase=0, fx_prepared=0, fx_pending=0, fx_failed=0;
static bool fx_clear=false, fx_takeoff=false;

static void fx_event(const char *event, const char *message="") {
  printf("FX {\"event\":\"%s\",\"time\":%.9f,\"message\":\"%s\"}\n",
         event, wb_robot_get_time(), message); fflush(stdout);
  // The simulator can terminate before relaying its controller's final stdout.
  // Retain the event independently before requesting simulationQuit.
  const char *path=getenv("RESET_CONTRACT_JOURNAL");
  if(path) {
    FILE *f=fopen(path,"a");
    if(!f) {fx_failed=1;return;}
    fprintf(f,"{\"event\":\"%s\",\"time\":%.9f,\"message\":\"%s\"}\n",event,wb_robot_get_time(),message);
    if(fclose(f))fx_failed=1;
  }
}
static void fx_sample() {
  const double *p=wb_gps_get_values(fx_gps), *r=wb_inertial_unit_get_roll_pitch_yaw(fx_imu);
  const double *g=wb_gyro_get_values(fx_gyro);
  printf("FX {\"event\":\"sample\",\"time\":%.9f,\"phase\":%d,\"gps\":[%.17g,%.17g,%.17g],"
         "\"rpy\":[%.17g,%.17g,%.17g],\"gyro\":[%.17g,%.17g,%.17g],",
         wb_robot_get_time(),fx_phase,p[0],p[1],p[2],r[0],r[1],r[2],g[0],g[1],g[2]);
  const double *v=wb_supervisor_node_get_velocity(fx_self);
  printf("\"native_velocity\":[%.17g,%.17g,%.17g,%.17g,%.17g,%.17g]}\n",
         v[0],v[1],v[2],v[3],v[4],v[5]); fflush(stdout);
}
static void fx_motor(WbDeviceTag tag, double velocity) {
  if(fx_phase==1) for(int i=0;i<4;i++) if(tag==motors[i]) velocity=prepared[i];
  printf("FX {\"event\":\"target\",\"time\":%.9f,\"tag\":%d,\"velocity\":%.17g}\n",
         wb_robot_get_time(),tag,velocity);
  wb_motor_set_velocity(tag,velocity);
}
static int fx_step(int ms) {
  if(fx_phase==5 || fx_failed) {
    fx_event(fx_failed ? "FAILED" : "COMPLETE");
    wb_supervisor_simulation_quit(fx_failed ? 80 : 0);
    wb_robot_step(0); return -1;
  }
  int status=wb_robot_step(ms);
  if(status==-1) return status;
  if(fx_phase) fx_sample();
  if(fx_phase==1) {
    wb_supervisor_field_set_sf_vec3f(fx_translation,fx_initial);
    wb_supervisor_field_set_sf_rotation(fx_rotation,fx_initial_rotation);
    wb_supervisor_node_reset_physics(fx_self);
    for(int i=0;i<4;i++) wb_motor_set_velocity(motors[i],prepared[i]);
    ++fx_prepared;
    if(fx_prepared==70) {fx_phase=2;fx_pending=9001;fx_event("PREPARED");}
  }
  if(fx_ack>=0 && !fx_takeoff && wb_robot_get_time()-fx_ack>=1.6) fx_phase=5;
  if(wb_robot_get_time()>65) {fx_event("FIXTURE_DEADLINE");fx_failed=1;}
  return status;
}
static const char *fx_receive() {
  if(!fx_pending || fx_sent_time==wb_robot_get_time()) return NULL;
  fx_sent_time=wb_robot_get_time();
  int id=fx_pending;fx_pending=0;
  if(id==9001) {
    fx_event("INTERVENTION",fx_clear ? "B_load_motor_state" : "A_sham_save_motor_state");
    for(int i=0;i<4;i++) {
      if(fx_clear) wb_supervisor_node_load_state(motor_nodes[i],"fx_zero");
      else wb_supervisor_node_save_state(motor_nodes[i],"fx_sham");
      wb_motor_set_position(motors[i],INFINITY);
      wb_motor_set_velocity(motors[i],0);
    }
    fx_event("REQUEST_RESET"); return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 9001 RESET";
  }
  if(id==9002) {fx_phase=4;fx_event("REQUEST_TAKEOFF");return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 9002 TAKEOFF 0.5";}
  fx_event("REQUEST_LAND");return "WEBEEBLOCKS_RUNTIME_V2 REQUEST 9003 LAND";
}
static void fx_send(const char *message) {
  wb_robot_wwi_send_text(message);
  fx_event("response",message);
  if(strstr(message," ERR ")) {fx_failed=1;return;}
  if(!strcmp(message,"WEBEEBLOCKS_RUNTIME_V2 READY")) {
    const char *variant=getenv("RESET_CONTRACT_VARIANT"), *mode=getenv("RESET_CONTRACT_MODE");
    if(!variant||!mode|| (strcmp(variant,"A")&&strcmp(variant,"B")) ||
       (strcmp(mode,"idle")&&strcmp(mode,"takeoff"))) {fx_failed=1;return;}
    fx_clear=!strcmp(variant,"B");fx_takeoff=!strcmp(mode,"takeoff");
    fx_self=wb_supervisor_node_get_self();
    fx_translation=wb_supervisor_node_get_field(fx_self,"translation");
    fx_rotation=wb_supervisor_node_get_field(fx_self,"rotation");
    const double *p=wb_supervisor_field_get_sf_vec3f(fx_translation);
    for(int i=0;i<3;i++) fx_initial[i]=p[i];
    const double *r=wb_supervisor_field_get_sf_rotation(fx_rotation);
    for(int i=0;i<4;i++) fx_initial_rotation[i]=r[i];
    fx_gps=wb_robot_get_device("gps");fx_imu=wb_robot_get_device("inertial_unit");fx_gyro=wb_robot_get_device("gyro");
    for(int i=0;i<4;i++) {
      char name[32];snprintf(name,sizeof(name),"m%d_motor",i+1);
      motors[i]=wb_robot_get_device(name);motor_nodes[i]=wb_supervisor_node_get_from_device(motors[i]);
      if(!motor_nodes[i]||strcmp(wb_supervisor_node_get_type_name(motor_nodes[i]),"RotationalMotor")) {fx_failed=1;return;}
      wb_supervisor_node_save_state(motor_nodes[i],"fx_zero");
    }
    fx_event("PREPARATION_START");fx_sample();fx_phase=1;
  }
  if(!strcmp(message,"WEBEEBLOCKS_RUNTIME_V2 RESPONSE 9001 OK")) {
    fx_ack=wb_robot_get_time();fx_phase=3;fx_event("ACK_RESET");if(fx_takeoff)fx_pending=9002;
  }
  if(!strcmp(message,"WEBEEBLOCKS_RUNTIME_V2 RESPONSE 9002 OK")) {fx_event("ACK_TAKEOFF");fx_pending=9003;}
  if(!strcmp(message,"WEBEEBLOCKS_RUNTIME_V2 RESPONSE 9003 OK")) {fx_event("ACK_LAND");fx_phase=5;}
}

#define wb_robot_step fx_step
#define wb_robot_wwi_receive_text fx_receive
#undef wb_robot_wwi_send_text
#define wb_robot_wwi_send_text fx_send
#define wb_motor_set_velocity fx_motor
#define main production_main
#include "../../controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c"
#undef main
#undef wb_robot_step
#undef wb_robot_wwi_receive_text
#undef wb_robot_wwi_send_text
#undef wb_motor_set_velocity
int main() {return production_main();}

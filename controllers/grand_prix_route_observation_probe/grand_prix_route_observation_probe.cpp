// Native sensor/field transport probe. No pupil program, motor command or READY.
#include "grand_prix_u_hook.h"
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <webots/distance_sensor.h>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <string>
extern "C" const char *webeeblocks_file_broker_receive_text(){return nullptr;}
extern "C" void webeeblocks_file_broker_send(const char *,int){}
void require(bool ok,const char *why) {
  if(ok)return;
  std::fprintf(stderr,"GP_ROUTE_SAMPLE_FAIL %s\n",why);
  wb_supervisor_simulation_quit(1);wb_robot_cleanup();std::exit(1);
}
int main() {
  wb_robot_init();require(wb_robot_get_basic_time_step()==8,"basic step");
  WbNodeRef self=wb_supervisor_node_get_self();
  WbFieldRef data=wb_supervisor_node_get_field(self,"customData");
  WbFieldRef sample=wb_supervisor_node_get_field(
    wb_supervisor_node_get_from_def("GP_ROUTE_EVALUATOR"),"model");
  WbFieldRef translation=wb_supervisor_node_get_field(self,"translation");
  WbFieldRef phase=wb_supervisor_node_get_field(
    wb_supervisor_node_get_from_def("GP_SAMPLE_PHASE"),"customData");
  require(data&&sample&&translation&&phase,"native fields");
  const char *names[5]={"range_front","range_back","range_left","range_right","range_up"};
  WbDeviceTag devices[5];
  for(int i=0;i<5;++i) {
    devices[i]=wb_robot_get_device(names[i]);require(devices[i],"own device missing");
    wb_distance_sensor_enable(devices[i],32);
  }
  gp_u_reset_complete();
  wb_supervisor_field_set_sf_string(data,"WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1");
  require(wb_robot_step(32)!=-1,"initial marker commit");
  gp_u_file_idle(1);
  const char *phases[7]={"far","near","shifted","invalid","stale","reset","new-epoch"};
  std::string previous;
  for(int stage=0;stage<7;++stage) {
    double position[3]={stage==0?0.:.30,0.,.65};
    wb_supervisor_field_set_sf_vec3f(translation,position);
    wb_supervisor_node_reset_physics(self);
    require(wb_robot_step(stage==2?16:32)!=-1,"native step ended");
    if(stage==1) {
      // Supervisor writes are committed at a later step, not a fake immediate
      // readback. The independent Python reader is the decisive consumer.
      previous=wb_supervisor_field_get_sf_string(sample);
      require(!previous.empty(),"previous native sample missing");
    }
    double ranges[5];
    for(int i=0;i<5;++i) {
      require(wb_distance_sensor_get_sampling_period(devices[i])==32,"native period");
      ranges[i]=wb_distance_sensor_get_value(devices[i])/1000.;
      require(std::isfinite(ranges[i])&&ranges[i]>=0&&ranges[i]<=2.001,"native range unavailable");
    }
    if(stage==3)ranges[0]=std::numeric_limits<double>::quiet_NaN();
    if(stage==4) {
      // Deliberately replay legitimate old data: the remote parser must refuse.
      wb_supervisor_field_set_sf_string(sample,previous.c_str());
    } else if(stage==5) {
      gp_u_reset_complete();
      wb_supervisor_field_set_sf_string(data,"WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2");
    } else {
      if(stage==6) {
        gp_u_file_idle(1);
      }
      // Probe control validity is injected; ground is deliberately unconfirmed.
      // Production instead passes the full native flight predicates, tested separately.
      gp_route_observe_native(wb_robot_get_time(),1,0,ranges);
    }
    wb_supervisor_field_set_sf_string(phase,phases[stage]);
  }
  // The independent reader checks every case and terminates the simulation.
  for(int i=0;i<40&&wb_robot_step(32)!=-1;++i){}
  wb_robot_cleanup();return 0;
}

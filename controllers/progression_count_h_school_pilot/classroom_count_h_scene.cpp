// CI-only A6 motor-flight admission. Never part of the physical or pupil
// product. Flight/PID/STOP/LAND still use untouched runtime-v2 C sources.
// This adapter admits ONE preloaded n=1 scene and then imports a separate
// native observer ONLY after the genuine Crazyflie Robot Window is active.
// A product A6 selector, Blockly solution and genuine mission oracle are NOT
// supplied by this test-only file.
#include "../crazyflie_runtime_v2/activity_scene.h"
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <cmath>
#include <cstring>
#include <cstdio>

namespace {
bool admitted = false;
// CI-only independent observer; no native flight program lives in it.
// Do not preload a second Robot at startup: Webots must open the authentic
// Crazyflie Robot Window before the SCENE request creates this observer.
constexpr const char *kObserver =
    "DEF WEBEEBLOCKS_A6_MOTOR_OBSERVER Robot { "
    "name \"A6 independent motor-flight observer\" "
    "controller \"progression_count_h_flight_observer\" "
    "supervisor TRUE synchronization TRUE }";
bool realObserver() {
  WbNodeRef node=wb_supervisor_node_get_from_def("WEBEEBLOCKS_A6_MOTOR_OBSERVER");
  if(!node||std::strcmp(wb_supervisor_node_get_type_name(node),"Robot"))return false;
  WbFieldRef name=wb_supervisor_node_get_field(node,"name");
  WbFieldRef controller=wb_supervisor_node_get_field(node,"controller");
  WbFieldRef supervisor=wb_supervisor_node_get_field(node,"supervisor");
  const char *n=name?wb_supervisor_field_get_sf_string(name):nullptr;
  const char *c=controller?wb_supervisor_field_get_sf_string(controller):nullptr;
  return n&&c&&supervisor&&
    !std::strcmp(n,"A6 independent motor-flight observer")&&
    !std::strcmp(c,"progression_count_h_flight_observer")&&
    wb_supervisor_field_get_sf_bool(supervisor);
}
bool approx(double a, double b) { return std::isfinite(a) && std::fabs(a-b)<0.000001; }

bool box(const char *def, double x, double y, double z,
         double sx, double sy, double sz) {
  WbNodeRef solid=wb_supervisor_node_get_from_def(def);
  if(!solid || std::strcmp(wb_supervisor_node_get_type_name(solid),"Solid")) return false;
  const double *pos=wb_supervisor_node_get_position(solid);
  WbFieldRef field=wb_supervisor_node_get_field(solid,"boundingObject");
  WbNodeRef shape=field?wb_supervisor_field_get_sf_node(field):nullptr;
  if(!pos||!shape||std::strcmp(wb_supervisor_node_get_type_name(shape),"Box"))return false;
  WbFieldRef size=wb_supervisor_node_get_field(shape,"size");
  const double *actual=size?wb_supervisor_field_get_sf_vec3f(size):nullptr;
  return actual&&approx(pos[0],x)&&approx(pos[1],y)&&approx(pos[2],z)&&
         approx(actual[0],sx)&&approx(actual[1],sy)&&approx(actual[2],sz);
}
bool actual_scene() {
  if(std::strcmp(wb_robot_get_name(),"Crazyflie WebeeBlocks"))return false;
  WbNodeRef w=wb_supervisor_node_get_from_def("WEBEEBLOCKS_CLASSROOM_START_WORLD");
  if(!w||std::strcmp(wb_supervisor_node_get_type_name(w),"WorldInfo"))return false;
  WbNodeRef group=wb_supervisor_node_get_from_def("WEBEEBLOCKS_COUNT_1_SCENE");
  if(!group||std::strcmp(wb_supervisor_node_get_type_name(group),"Group"))return false;
  WbFieldRef children=wb_supervisor_node_get_field(group,"children");
  if(!children||wb_supervisor_field_get_count(children)!=24)return false;
  for(int i=0;i<24;++i)
    if(!wb_supervisor_field_get_mf_node(children,i))return false;
  if(wb_supervisor_node_get_from_def("WEBEEBLOCKS_COUNT_2_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_COUNT_3_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_ALTITUDE_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_SEQUENCE_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_ORIENTATION_SCENE"))return false;
  return box("ACTIVITY6_1_H_1_LEFT",-.85,.30,.50,.07,.065,1.0)&&
         box("ACTIVITY6_1_H_1_RIGHT",-.85,-.30,.50,.07,.065,1.0)&&
         box("ACTIVITY6_1_H_1_BAR",-.85,0,.74,.07,.57,.24)&&
         box("ACTIVITY6_1_FINISH_SCREEN",1.235,0,.76,.07,1.48,.24)&&
         box("ACTIVITY6_1_TERMINAL",1.86,0,.55,.06,1.48,1.10);
}
}
extern "C" int webeeblocks_select_activity_scene(const char *scene) {
  if(!scene||std::strcmp(scene,"count-h-1-v1")||!actual_scene()) {
    admitted=false;
    std::fprintf(stderr,"WEBEEBLOCKS_A6_FLIGHT_SCENE_FATAL scene admission refused\n");
    std::fflush(stderr);
    return 0;
  }
  if(!realObserver()) {
    WbNodeRef root=wb_supervisor_node_get_root();
    WbFieldRef children=root?wb_supervisor_node_get_field(root,"children"):nullptr;
    if(!children) return 0;
    wb_supervisor_field_import_mf_node_from_string(children,-1,kObserver);
  }
  admitted=realObserver();
  if(!admitted)
    std::fprintf(stderr,"WEBEEBLOCKS_A6_FLIGHT_SCENE_FATAL independent native observer refused\n");
  else
    std::fprintf(stdout,"WEBEEBLOCKS_A6_FLIGHT_SCENE_OK variant=1 native_colliders=5\n");
  std::fflush(admitted?stdout:stderr);
  return admitted?1:0;
}
extern "C" int webeeblocks_activity_scene_ready(void) {
  return admitted&&actual_scene()&&realObserver()?1:0;
}

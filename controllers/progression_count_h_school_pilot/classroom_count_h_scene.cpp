// CI-only A6 motor-flight admission. Never part of the physical or pupil
// product. Flight/PID/STOP/LAND still use untouched runtime-v2 C sources.
// This adapter attests exactly ONE preloaded n=1/2/3 scene, then imports a separate
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
int admittedVariant = 0;
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
  // A rotated wall changes physical collision even with identical local Box.
  const double *orientation=wb_supervisor_node_get_orientation(solid);
  if(!actual||!orientation)return false;
  for(int row=0;row<3;++row)
    for(int col=0;col<3;++col)
      if(!approx(orientation[3*row+col],row==col?1.0:0.0))
        return false;
  return approx(pos[0],x)&&approx(pos[1],y)&&approx(pos[2],z)&&
         approx(actual[0],sx)&&approx(actual[1],sy)&&approx(actual[2],sz);
}
// CI-only admission accepts the three strictly identified classroom scenes.
// The selected variant is not inferred from a pupil program, sensor or AST.
int sceneVariant(const char *scene) {
  if(!scene)return 0;
  for(int n=1;n<=3;++n) {
    char id[32];
    std::snprintf(id,sizeof(id),"count-h-%d-v1",n);
    if(!std::strcmp(id,scene))return n;
  }
  return 0;
}
bool actual_scene(int variant) {
  if(variant<1||variant>3||
     std::strcmp(wb_robot_get_name(),"Crazyflie WebeeBlocks"))return false;
  WbNodeRef world=wb_supervisor_node_get_from_def("WEBEEBLOCKS_CLASSROOM_START_WORLD");
  if(!world||std::strcmp(wb_supervisor_node_get_type_name(world),"WorldInfo"))return false;
  for(int n=1;n<=3;++n) {
    char name[48];
    std::snprintf(name,sizeof(name),"WEBEEBLOCKS_COUNT_%d_SCENE",n);
    WbNodeRef group=wb_supervisor_node_get_from_def(name);
    if(n!=variant) {
      if(group)return false; // no second candidate scene may remain loaded
      continue;
    }
    if(!group||std::strcmp(wb_supervisor_node_get_type_name(group),"Group"))return false;
    WbFieldRef children=wb_supervisor_node_get_field(group,"children");
    // A6: 19/20/21 visual Poses + 5/8/11 independent collision Solids.
    const int expected=24+4*(n-1);
    if(!children||wb_supervisor_field_get_count(children)!=expected)return false;
    for(int k=0;k<expected;++k)
      if(!wb_supervisor_field_get_mf_node(children,k))return false;
  }
  if(wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_ALTITUDE_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_SEQUENCE_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_ORIENTATION_SCENE"))return false;
  for(int i=1;i<=variant;++i) {
    const double x=-0.850+0.850*(i-1);
    char left[48],right[48],bar[48];
    std::snprintf(left,sizeof(left),"ACTIVITY6_%d_H_%d_LEFT",variant,i);
    std::snprintf(right,sizeof(right),"ACTIVITY6_%d_H_%d_RIGHT",variant,i);
    std::snprintf(bar,sizeof(bar),"ACTIVITY6_%d_H_%d_BAR",variant,i);
    if(!box(left,x,.30,.50,.07,.065,1.0)||
       !box(right,x,-.30,.50,.07,.065,1.0)||
       !box(bar,x,0,.74,.07,.57,.24))return false;
  }
  char screen[48],terminal[48];
  std::snprintf(screen,sizeof(screen),"ACTIVITY6_%d_FINISH_SCREEN",variant);
  std::snprintf(terminal,sizeof(terminal),"ACTIVITY6_%d_TERMINAL",variant);
  return box(screen,1.235,0,.76,.07,1.48,.24)&&
         box(terminal,1.86,0,.55,.06,1.48,1.10);
}
}
extern "C" int webeeblocks_select_activity_scene(const char *scene) {
  const int requested=sceneVariant(scene);
  if(!requested||!actual_scene(requested)) {
    admitted=false;
    admittedVariant=0;
    std::fprintf(stderr,"WEBEEBLOCKS_A6_FLIGHT_SCENE_FATAL scene admission refused\n");
    std::fflush(stderr);
    return 0;
  }
  if(!realObserver()) {
    WbNodeRef root=wb_supervisor_node_get_root();
    WbFieldRef children=root?wb_supervisor_node_get_field(root,"children"):nullptr;
    if(!children)return 0;
    wb_supervisor_field_import_mf_node_from_string(children,-1,kObserver);
  }
  admitted=realObserver();
  admittedVariant=admitted?requested:0;
  if(!admitted)
    std::fprintf(stderr,"WEBEEBLOCKS_A6_FLIGHT_SCENE_FATAL independent native observer refused\n");
  else
    std::fprintf(stdout,"WEBEEBLOCKS_A6_FLIGHT_SCENE_OK variant=%d native_colliders=%d\n",
                 requested,3*requested+2);
  std::fflush(admitted?stdout:stderr);
  return admitted?1:0;
}
extern "C" int webeeblocks_activity_scene_ready(void) {
  return admitted&&admittedVariant>=1&&admittedVariant<=3&&
    actual_scene(admittedVariant)&&realObserver()?1:0;
}

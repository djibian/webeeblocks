/* A5 factor-G motor feasibility, Draft-only, original R2025a motor PID. */
#include "../crazyflie_runtime_v2/activity_scene.h"
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <cstdio>
#include <cstring>
#include <cmath>
namespace {
int selected=0;
bool near(double a,double b){return std::isfinite(a)&&std::fabs(a-b)<.000001;}
bool box(const char *name,double x,double y,double z,double sx,double sy,double sz){
  WbNodeRef node=wb_supervisor_node_get_from_def(name);
  if(!node||std::strcmp(wb_supervisor_node_get_type_name(node),"Solid"))return false;
  const double *p=wb_supervisor_node_get_position(node);
  const double *o=wb_supervisor_node_get_orientation(node);
  WbFieldRef b=wb_supervisor_node_get_field(node,"boundingObject");
  WbNodeRef geom=b?wb_supervisor_field_get_sf_node(b):nullptr;
  if(!p||!o||!geom||std::strcmp(wb_supervisor_node_get_type_name(geom),"Box"))
    return false;
  WbFieldRef field=wb_supervisor_node_get_field(geom,"size");
  const double *s=field?wb_supervisor_field_get_sf_vec3f(field):nullptr;
  if(!s||!near(p[0],x)||!near(p[1],y)||!near(p[2],z)||
     !near(s[0],sx)||!near(s[1],sy)||!near(s[2],sz))return false;
  for(int i=0;i<3;i++)for(int j=0;j<3;j++)
    if(!near(o[i*3+j],i==j?1:0))return false;
  return true;
}
bool attest(int v){
  if((v<1||v>4)||std::strcmp(wb_robot_get_name(),"Crazyflie WebeeBlocks")||
      (int)wb_robot_get_basic_time_step()!=32)return false;
  WbNodeRef world=wb_supervisor_node_get_from_def("WEBEEBLOCKS_CLASSROOM_START_WORLD");
  if(!world||std::strcmp(wb_supervisor_node_get_type_name(world),"WorldInfo"))return false;
  const bool L=(v==1||v==3);
  const bool far=(v==3||v==4);
  const char *yes=L?"WEBEEBLOCKS_A5_FACTOR_GL_SCENE":
                     "WEBEEBLOCKS_A5_FACTOR_GR_SCENE";
  const char *no=L?"WEBEEBLOCKS_A5_FACTOR_GR_SCENE":
                    "WEBEEBLOCKS_A5_FACTOR_GL_SCENE";
  WbNodeRef group=wb_supervisor_node_get_from_def(yes);
  WbFieldRef members=group?wb_supervisor_node_get_field(group,"children"):nullptr;
  if(!group||std::strcmp(wb_supervisor_node_get_type_name(group),"Group")||
     !members||wb_supervisor_field_get_count(members)!=11||
     wb_supervisor_node_get_from_def(no)||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_MINI_GP_L_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_MINI_GP_R_SCENE"))return false;
  for(int i=0;i<11;i++)if(!wb_supervisor_field_get_mf_node(members,i))return false;
  return box("A5_FACTOR_H_CUE_ARM",0,far?1.18:.58,.55,.40,.08,1.10)&&
     box("A5_FACTOR_H_CUE_TIP",.20,far?1.38:.78,.55,.08,.48,1.10)&&
     box("A5_FACTOR_G_LOWER",3.10,L?-.55:-1.16,.55,.08,L?1.70:.48,1.10)&&
     box("A5_FACTOR_G_UPPER",3.10,L?1.16:.55,.55,.08,L?.48:1.70,1.10)&&
     box("A5_FACTOR_G_SIDE_ARM",2.45,L?-.58:.58,.55,.70,.08,1.10)&&
     box("A5_FACTOR_G_LEFT_BOUNDARY",3.0,1.45,.55,2.40,.08,1.10)&&
     box("A5_FACTOR_G_RIGHT_BOUNDARY",3.0,-1.45,.55,2.40,.08,1.10);
}
}
extern "C" int webeeblocks_select_activity_scene(const char *scene){
  int v=scene&&std::strcmp(scene,"a5-factor-g-left-proto")==0?1:
        scene&&std::strcmp(scene,"a5-factor-g-right-proto")==0?2:
        scene&&std::strcmp(scene,"a5-factor-hfar-g-left-proto")==0?3:
        scene&&std::strcmp(scene,"a5-factor-hfar-g-right-proto")==0?4:0;
  selected=attest(v)?v:0;
  if(!selected){
    std::fprintf(stderr,"WEBEEBLOCKS_A5_FACTOR_MOTOR_FATAL untrusted scene\n");
    std::fflush(stderr);return 0;
  }
  std::printf("WEBEEBLOCKS_A5_FACTOR_MOTOR_SCENE_OK variant=%c "
              "physics=32ms colliders=7 test_only=true\n",'A'+v-1);
  std::fflush(stdout);return 1;
}
extern "C" int webeeblocks_activity_scene_ready(void){
  return selected&&attest(selected)?1:0;
}

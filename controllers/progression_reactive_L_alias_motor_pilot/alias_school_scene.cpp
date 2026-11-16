/* Private A5 R2025a motor feasibility: physical scene attestation only.
 * No scenario oracle, external flight authority, or pupil catalogue admission.
 * Shared runtime/PID code is included by Makefile without source changes.
 */
#include "../crazyflie_runtime_v2/activity_scene.h"
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <cstdio>
#include <cstring>
#include <cmath>

namespace {
int selected=0;
bool near(double a,double b) {return std::isfinite(a)&&std::fabs(a-b)<0.000001;}
bool box(const char *name,double x,double y,double z,
         double sx,double sy,double sz) {
  WbNodeRef node=wb_supervisor_node_get_from_def(name);
  if(!node||std::strcmp(wb_supervisor_node_get_type_name(node),"Solid"))return false;
  const double *p=wb_supervisor_node_get_position(node);
  const double *o=wb_supervisor_node_get_orientation(node);
  WbFieldRef field=wb_supervisor_node_get_field(node,"boundingObject");
  WbNodeRef geom=field?wb_supervisor_field_get_sf_node(field):nullptr;
  if(!p||!o||!geom||std::strcmp(wb_supervisor_node_get_type_name(geom),"Box"))
    return false;
  WbFieldRef size=wb_supervisor_node_get_field(geom,"size");
  const double *s=size?wb_supervisor_field_get_sf_vec3f(size):nullptr;
  if(!s||!near(p[0],x)||!near(p[1],y)||!near(p[2],z)||
     !near(s[0],sx)||!near(s[1],sy)||!near(s[2],sz))return false;
  for(int i=0;i<3;i++)
    for(int j=0;j<3;j++)
      if(!near(o[i*3+j],i==j?1:0))return false;
  return true;
}
bool attested(int v) {
  if(v!=1&&v!=2)return false;
  if(std::strcmp(wb_robot_get_name(),"Crazyflie WebeeBlocks")||
     (int)wb_robot_get_basic_time_step()!=32)return false;
  WbNodeRef world=wb_supervisor_node_get_from_def("WEBEEBLOCKS_CLASSROOM_START_WORLD");
  if(!world||std::strcmp(wb_supervisor_node_get_type_name(world),"WorldInfo"))
    return false;
  const char *right=v==1?"WEBEEBLOCKS_A5_ALIAS_A_SCENE":
                           "WEBEEBLOCKS_A5_ALIAS_B_SCENE";
  const char *wrong=v==1?"WEBEEBLOCKS_A5_ALIAS_B_SCENE":
                           "WEBEEBLOCKS_A5_ALIAS_A_SCENE";
  WbNodeRef group=wb_supervisor_node_get_from_def(right);
  WbFieldRef members=group?wb_supervisor_node_get_field(group,"children"):nullptr;
  if(!group||std::strcmp(wb_supervisor_node_get_type_name(group),"Group")||
     !members||wb_supervisor_field_get_count(members)!=7||
     wb_supervisor_node_get_from_def(wrong)||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_ALTITUDE_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_DECISION_A_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_DECISION_B_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_MINI_GP_L_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_MINI_GP_R_SCENE"))
    return false;
  for(int i=0;i<7;i++)
    if(!wb_supervisor_field_get_mf_node(members,i))return false;
  const char c=v==1?'A':'B';
  const double cue=v==1?.58:1.18;
  char name[80];
  std::snprintf(name,sizeof name,"A5_ALIAS_%c_CUE_ARM",c);
  if(!box(name,0,cue,.55,.40,.08,1.10))return false;
  std::snprintf(name,sizeof name,"A5_ALIAS_%c_CUE_TIP",c);
  if(!box(name,.20,cue+.20,.55,.08,.48,1.10))return false;
  std::snprintf(name,sizeof name,"A5_ALIAS_%c_TERMINAL",c);
  return box(name,2.10,0,.55,.08,.82,1.10);
}
}
extern "C" int webeeblocks_select_activity_scene(const char *scene) {
  const int v=scene&&std::strcmp(scene,"a5-memory-alias-a-proto")==0?1:
              scene&&std::strcmp(scene,"a5-memory-alias-b-proto")==0?2:0;
  selected=attested(v)?v:0;
  if(!selected){
    std::fprintf(stderr,"WEBEEBLOCKS_A5_ALIAS_MOTOR_FATAL untrusted scene\n");
    std::fflush(stderr);return 0;
  }
  std::printf("WEBEEBLOCKS_A5_ALIAS_MOTOR_SCENE_OK variant=%c "
              "physics=32ms colliders=3 test_only=true\n",
              v==1?'A':'B');
  std::fflush(stdout);return 1;
}
extern "C" int webeeblocks_activity_scene_ready(void) {
  return selected&&attested(selected)?1:0;
}

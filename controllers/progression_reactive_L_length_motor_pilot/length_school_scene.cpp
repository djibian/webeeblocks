/* Private A5 length x side motor source admission, Webots R2025a.
 * Original Crazyflie+PID; no product scene or pupil release. */
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

bool pose(WbFieldRef children,int i,double x,double y,double z){
  WbNodeRef n=wb_supervisor_field_get_mf_node(children,i);
  if(!n||std::strcmp(wb_supervisor_node_get_type_name(n),"Pose"))return false;
  WbFieldRef t=wb_supervisor_node_get_field(n,"translation");
  const double *p=t?wb_supervisor_field_get_sf_vec3f(t):nullptr;
  return p&&near(p[0],x)&&near(p[1],y)&&near(p[2],z);
}
bool attest(int v){
  if(v<1||v>4||std::strcmp(wb_robot_get_name(),"Crazyflie WebeeBlocks")||
     (int)wb_robot_get_basic_time_step()!=32)return false;
  WbNodeRef wi=wb_supervisor_node_get_from_def("WEBEEBLOCKS_CLASSROOM_START_WORLD");
  if(!wi||std::strcmp(wb_supervisor_node_get_type_name(wi),"WorldInfo"))return false;
  const bool isLong=v>=3, gateLeft=v==1||v==3;
  const char *const names[4]={
    "WEBEEBLOCKS_A5_LENGTH_SHORT_GL_SCENE",
    "WEBEEBLOCKS_A5_LENGTH_SHORT_GR_SCENE",
    "WEBEEBLOCKS_A5_LENGTH_LONG_GL_SCENE",
    "WEBEEBLOCKS_A5_LENGTH_LONG_GR_SCENE"};
  WbNodeRef group=nullptr;
  for(int i=0;i<4;i++){
    WbNodeRef n=wb_supervisor_node_get_from_def(names[i]);
    if((i==v-1)!=(n!=nullptr))return false;
    if(i==v-1)group=n;
  }
  if(wb_supervisor_node_get_from_def("WEBEEBLOCKS_A5_FACTOR_GL_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_A5_FACTOR_GR_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_MINI_GP_L_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_MINI_GP_R_SCENE"))return false;
  if(!group||std::strcmp(wb_supervisor_node_get_type_name(group),"Group"))return false;
  WbFieldRef children=wb_supervisor_node_get_field(group,"children");
  if(!children||wb_supervisor_field_get_count(children)!=11)return false;
  const double gate=isLong?3.3:2.9;
  const double arm=isLong?2.175:1.975;
  const double length=isLong?1.65:1.25;
  const double boundary=isLong?3.2:2.8;
  const double pad=isLong?4.35:3.95;
  const double marker=isLong?2.7:2.3;
  return pose(children,0,0,0,.002)&&
    pose(children,1,marker,0,.002)&&
    pose(children,2,pad,.62,.002)&&
    pose(children,3,pad,-.62,.002)&&
    box("A5_FACTOR_H_CUE_ARM",0,.58,.55,.40,.08,1.10)&&
    box("A5_FACTOR_H_CUE_TIP",.20,.78,.55,.08,.48,1.10)&&
    box("A5_FACTOR_G_LOWER",gate,gateLeft?-.55:-1.16,.55,
        .08,gateLeft?1.70:.48,1.10)&&
    box("A5_FACTOR_G_UPPER",gate,gateLeft?1.16:.55,.55,
        .08,gateLeft?.48:1.70,1.10)&&
    box("A5_FACTOR_G_SIDE_ARM",arm,gateLeft?-.58:.58,.55,
        length,.08,1.10)&&
    box("A5_FACTOR_G_LEFT_BOUNDARY",boundary,1.45,.55,2.40,.08,1.10)&&
    box("A5_FACTOR_G_RIGHT_BOUNDARY",boundary,-1.45,.55,2.40,.08,1.10);
}
}
extern "C" int webeeblocks_select_activity_scene(const char *scene){
  const int v=scene&&std::strcmp(scene,"a5-length-short-g-left-proto")==0?1:
              scene&&std::strcmp(scene,"a5-length-short-g-right-proto")==0?2:
              scene&&std::strcmp(scene,"a5-length-long-g-left-proto")==0?3:
              scene&&std::strcmp(scene,"a5-length-long-g-right-proto")==0?4:0;
  selected=attest(v)?v:0;
  if(!selected){
    std::fprintf(stderr,"WEBEEBLOCKS_A5_LENGTH_MOTOR_FATAL untrusted scene\n");
    std::fflush(stderr);return 0;
  }
  std::printf("WEBEEBLOCKS_A5_LENGTH_MOTOR_SCENE_OK variant=%c physics=32ms "
              "colliders=7 length=%s gate=%s test_only=true\n",
              'A'+v-1,v>=3?"long":"short",v==1||v==3?"left":"right");
  std::fflush(stdout);return 1;
}
extern "C" int webeeblocks_activity_scene_ready(void){
  return selected&&attest(selected)?1:0;
}

#ifndef WEBEEBLOCKS_SCHOOL_MINI_GP_SCENE_GATE_H
#define WEBEEBLOCKS_SCHOOL_MINI_GP_SCENE_GATE_H
/* A7 classroom-only native scene admission. The actual Webots nodes,
 * not the WBO text or the presence of 29 children, are authoritative.
 * Independent of pupil Blockly, motors, and the hardware flight runtime. */
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <cmath>
#include <cstdio>
#include <cstring>

namespace webeeblocks_a7_gate {
constexpr int kChildren = 29; // 20 Pose glyphs + nine real Solid colliders.
constexpr const char *kObserver = "Mini Grand Prix native evaluator";
constexpr const char *kController = "progression_mini_grand_prix_v1";

inline bool near(double v,double expected) {
  return std::isfinite(v)&&std::fabs(v-expected)<=0.000001;
}
inline bool textIs(WbNodeRef node,const char *field,const char *expected) {
  WbFieldRef f=node?wb_supervisor_node_get_field(node,field):nullptr;
  const char *v=f?wb_supervisor_field_get_sf_string(f):nullptr;
  return v && !std::strcmp(v,expected);
}
inline bool typedObserver(WbNodeRef group) {
  WbFieldRef children=group?wb_supervisor_node_get_field(group,"children"):nullptr;
  if(!children||wb_supervisor_field_get_count(children)!=kChildren)return false;
  for(int i=0;i<kChildren;i++) {
    WbNodeRef node=wb_supervisor_field_get_mf_node(children,i);
    const char *type=node?wb_supervisor_node_get_type_name(node):nullptr;
    if(!type||std::strcmp(type,i<20?"Pose":"Solid"))return false;
    if(i>=20)continue;
    WbFieldRef nested=wb_supervisor_node_get_field(node,"children");
    if(!nested||wb_supervisor_field_get_count(nested)!=(i==0?2:1))return false;
    WbNodeRef marker=wb_supervisor_field_get_mf_node(nested,0);
    const char *glyph=marker?wb_supervisor_node_get_type_name(marker):nullptr;
    if(!glyph||std::strcmp(glyph,"Shape"))return false;
    if(i!=0)continue;
    WbNodeRef observer=wb_supervisor_field_get_mf_node(nested,1);
    const char *kind=observer?wb_supervisor_node_get_type_name(observer):nullptr;
    if(!kind||std::strcmp(kind,"Robot")||
       !textIs(observer,"name",kObserver)||
       !textIs(observer,"controller",kController))return false;
    WbFieldRef sup=wb_supervisor_node_get_field(observer,"supervisor");
    WbFieldRef sync=wb_supervisor_node_get_field(observer,"synchronization");
    if(!sup||!sync||!wb_supervisor_field_get_sf_bool(sup)||
       !wb_supervisor_field_get_sf_bool(sync))return false;
  }
  return true;
}
inline bool collider(const char *def,const double pos[3],const double dimensions[3]) {
  WbNodeRef node=wb_supervisor_node_get_from_def(def);
  const char *type=node?wb_supervisor_node_get_type_name(node):nullptr;
  if(!type||std::strcmp(type,"Solid"))return false;
  const double *p=wb_supervisor_node_get_position(node);
  const double *rot=wb_supervisor_node_get_orientation(node);
  WbFieldRef b=wb_supervisor_node_get_field(node,"boundingObject");
  WbNodeRef box=b?wb_supervisor_field_get_sf_node(b):nullptr;
  const char *bt=box?wb_supervisor_node_get_type_name(box):nullptr;
  if(!bt||std::strcmp(bt,"Box"))return false;
  WbFieldRef f=wb_supervisor_node_get_field(box,"size");
  const double *sz=f?wb_supervisor_field_get_sf_vec3f(f):nullptr;
  if(!p||!rot||!sz)return false;
  for(int k=0;k<3;++k)
    if(!near(p[k],pos[k])||!near(sz[k],dimensions[k])||sz[k]<=0)return false;
  for(int k=0;k<9;++k)
    if(!near(rot[k],k%4==0?1.0:0.0))return false;
  return true;
}
inline bool valid(char variant) {
  if(variant!='L'&&variant!='R')return false;
  WbNodeRef world=wb_supervisor_node_get_from_def("WEBEEBLOCKS_CLASSROOM_START_WORLD");
  const char *worldType=world?wb_supervisor_node_get_type_name(world):nullptr;
  if(!worldType||std::strcmp(worldType,"WorldInfo"))return false;
  const char *def=variant=='L'?"WEBEEBLOCKS_MINI_GP_L_SCENE":
                                 "WEBEEBLOCKS_MINI_GP_R_SCENE";
  WbNodeRef group=wb_supervisor_node_get_from_def(def);
  const char *type=group?wb_supervisor_node_get_type_name(group):nullptr;
  if(!type||std::strcmp(type,"Group")||!typedObserver(group))return false;
  const double h=variant=='L'?-0.750:-0.450;
  const double turn=variant=='L'?0.200:0.500;
  const double side=variant=='L'?1.0:-1.0;
  const char *const labels[]={
    "OPEN_LEFT","OPEN_RIGHT","OPEN_BAR","CORNER_FRONT","CORNER_SIDE",
    "CLOSED_LEFT","CLOSED_RIGHT","CLOSED_BAR","CLOSED_PANEL"
  };
  const double p[9][3]={
    {h, .300,.500},{h,-.300,.500},{h,0,.740},
    {turn+.220,0,.550},{turn,-side*.320,.550},
    {turn-.300,side*1.420,.650},{turn+.300,side*1.420,.650},
    {turn,side*1.420,.900},{turn,side*1.420,.650}
  };
  const double sizes[9][3]={
    {.070,.065,1.00},{.070,.065,1.00},{.070,.570,.240},
    {.080,.640,1.10},{.480,.080,1.10},
    {.065,.080,1.30},{.065,.080,1.30},
    {.570,.080,.300},{.570,.080,1.30}
  };
  for(int i=0;i<9;++i){
    char name[100];
    const int n=std::snprintf(name,sizeof name,"ACTIVITY7_%c_%s",variant,labels[i]);
    if(n<=0||static_cast<size_t>(n)>=sizeof name||!collider(name,p[i],sizes[i]))
      return false;
  }
  return true;
}
} // namespace webeeblocks_a7_gate
#endif

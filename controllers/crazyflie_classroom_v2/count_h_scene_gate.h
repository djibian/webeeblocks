#ifndef WEBEEBLOCKS_SCHOOL_COUNT_H_SCENE_GATE_H
#define WEBEEBLOCKS_SCHOOL_COUNT_H_SCENE_GATE_H
/* A6 classroom-only native admission. No AST, pupil program or motor commands
 * are inspected. Physical geometry, scene and observer identities are read
 * from the real Webots R2025a graph; liveness comes from the native observer.
 * The separate real-Crazyflie backend never links this school gate.
 */
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <initializer_list>

namespace webeeblocks_a6_gate {
constexpr const char *kObserverDef="WEBEEBLOCKS_A6_MOTOR_OBSERVER";
constexpr const char *kObserverName="A6 independent motor-flight observer";
constexpr const char *kObserverController="progression_count_h_flight_observer";
constexpr const char *kObserverSource=
  "DEF WEBEEBLOCKS_A6_MOTOR_OBSERVER Robot { "
  "name \"A6 independent motor-flight observer\" "
  "controller \"progression_count_h_flight_observer\" "
  "supervisor TRUE synchronization TRUE }";

inline bool near(double a,double b) {
  return std::isfinite(a)&&std::fabs(a-b)<=0.000001;
}
inline bool textField(WbNodeRef node,const char *name,const char *expected) {
  WbFieldRef field=node?wb_supervisor_node_get_field(node,name):nullptr;
  const char *value=field?wb_supervisor_field_get_sf_string(field):nullptr;
  return value&&!std::strcmp(value,expected);
}
inline bool box(const char *def,const double wanted[3],const double dimensions[3]) {
  WbNodeRef node=wb_supervisor_node_get_from_def(def);
  const char *type=node?wb_supervisor_node_get_type_name(node):nullptr;
  if(!type||std::strcmp(type,"Solid"))return false;
  const double *position=wb_supervisor_node_get_position(node);
  const double *rotation=wb_supervisor_node_get_orientation(node);
  WbFieldRef b=wb_supervisor_node_get_field(node,"boundingObject");
  WbNodeRef shape=b?wb_supervisor_field_get_sf_node(b):nullptr;
  const char *t=shape?wb_supervisor_node_get_type_name(shape):nullptr;
  WbFieldRef size=shape?wb_supervisor_node_get_field(shape,"size"):nullptr;
  const double *actual=size?wb_supervisor_field_get_sf_vec3f(size):nullptr;
  if(!t||std::strcmp(t,"Box")||!position||!rotation||!actual)return false;
  for(int i=0;i<3;i++)
    if(!near(position[i],wanted[i])||!near(actual[i],dimensions[i])||
       actual[i]<=0)return false;
  for(int i=0;i<9;i++)
    if(!near(rotation[i],i%4==0?1.0:0.0))return false;
  return true;
}
inline int sceneNumber(const char *scene) {
  if(!scene)return 0;
  for(int n=1;n<=3;n++) {
    char name[32];
    std::snprintf(name,sizeof name,"count-h-%d-v1",n);
    if(!std::strcmp(scene,name))return n;
  }
  return 0;
}
/* The current generic school world starts at x=0, while the qualified A6
 * witness starts at x=-1.40. Never silently teleport the craft or mutate
 * Runtime v2's protected reset origin to pretend these worlds are equivalent.
 * Refuse A6 BEFORE removing a prior scenario when its launch pose is wrong. */
inline bool blueOrigin() {
  WbNodeRef craft=wb_supervisor_node_get_self();
  const double *p=craft?wb_supervisor_node_get_position(craft):nullptr;
  return p&&std::isfinite(p[0])&&std::isfinite(p[1])&&std::isfinite(p[2])&&
    std::fabs(p[0]+1.40)<=.025&&std::fabs(p[1])<=.025&&
    p[2]>=.012&&p[2]<=.075;
}
inline bool realObserver() {
  WbNodeRef node=wb_supervisor_node_get_from_def(kObserverDef);
  const char *type=node?wb_supervisor_node_get_type_name(node):nullptr;
  if(!type||std::strcmp(type,"Robot")||
     !textField(node,"name",kObserverName)||
     !textField(node,"controller",kObserverController))return false;
  WbFieldRef supervisor=wb_supervisor_node_get_field(node,"supervisor");
  WbFieldRef sync=wb_supervisor_node_get_field(node,"synchronization");
  return supervisor&&sync&&wb_supervisor_field_get_sf_bool(supervisor)&&
    wb_supervisor_field_get_sf_bool(sync);
}
/* Node identity alone cannot authorize TAKEOFF. The observer must produce a
 * recent, canonical heartbeat for the broker's current native attempt. */
inline bool currentObserver(int variant) {
  if(variant<1||variant>3||!realObserver())return false;
  WbNodeRef observer=wb_supervisor_node_get_from_def(kObserverDef);
  WbFieldRef field=wb_supervisor_node_get_field(observer,"customData");
  const char *token=field?wb_supervisor_field_get_sf_string(field):nullptr;
  unsigned long long epoch=0;int observedVariant=0;double at=-1.0;char extra=0;
  if(!token||std::sscanf(token,
       "WEBEEBLOCKS_A6_NATIVE_OBSERVER_LIVE_V1 epoch=%llu variant=%d time=%lf%c",
       &epoch,&observedVariant,&at,&extra)!=3||epoch==0||
       observedVariant!=variant||!std::isfinite(at))return false;
  char exact[192];
  const int n=std::snprintf(exact,sizeof exact,
      "WEBEEBLOCKS_A6_NATIVE_OBSERVER_LIVE_V1 epoch=%llu variant=%d time=%.6f",
      epoch,observedVariant,at);
  if(n<=0||static_cast<size_t>(n)>=sizeof exact||std::strcmp(token,exact))
    return false;
  const double now=wb_robot_get_time();
  if(!std::isfinite(now)||at>now+.032||now-at>.128)return false;
  WbNodeRef craft=wb_supervisor_node_get_self();
  WbFieldRef data=craft?wb_supervisor_node_get_field(craft,"customData"):nullptr;
  const char *broker=data?wb_supervisor_field_get_sf_string(data):nullptr;
  unsigned long long active=0;char tail=0;
  if(!broker||std::sscanf(broker,"WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu%c",
                          &active,&tail)!=1||active!=epoch)return false;
  char canonical[128];
  const int size=std::snprintf(canonical,sizeof canonical,
                              "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu",active);
  return size>0&&static_cast<size_t>(size)<sizeof canonical&&
    !std::strcmp(broker,canonical);
}
inline bool valid(int variant) {
  const char *craftName=wb_robot_get_name();
  if(variant<1||variant>3||!craftName||
     std::strcmp(craftName,"Crazyflie WebeeBlocks")||!blueOrigin())return false;
  WbNodeRef world=wb_supervisor_node_get_from_def("WEBEEBLOCKS_CLASSROOM_START_WORLD");
  const char *type=world?wb_supervisor_node_get_type_name(world):nullptr;
  if(!type||std::strcmp(type,"WorldInfo"))return false;
  for(const char *foreign : {
    "WEBEEBLOCKS_LEGACY_SCENE","WEBEEBLOCKS_LEGACY_EVALUATORS",
    "WEBEEBLOCKS_SEQUENCE_SCENE","WEBEEBLOCKS_ALTITUDE_SCENE",
    "WEBEEBLOCKS_ORIENTATION_SCENE",
    "WEBEEBLOCKS_DECISION_A_SCENE","WEBEEBLOCKS_DECISION_B_SCENE",
    "WEBEEBLOCKS_MINI_GP_L_SCENE","WEBEEBLOCKS_MINI_GP_R_SCENE"
  })
    if(wb_supervisor_node_get_from_def(foreign))return false;
  for(int n=1;n<=3;n++) {
    char name[48];
    std::snprintf(name,sizeof name,"WEBEEBLOCKS_COUNT_%d_SCENE",n);
    WbNodeRef group=wb_supervisor_node_get_from_def(name);
    if(n!=variant) {
      if(group)return false; // No second H count in an admitted world.
      continue;
    }
    const char *groupType=group?wb_supervisor_node_get_type_name(group):nullptr;
    if(!groupType||std::strcmp(groupType,"Group"))return false;
    WbFieldRef children=wb_supervisor_node_get_field(group,"children");
    const int poses=18+n,expected=poses+3*n+2;
    if(!children||wb_supervisor_field_get_count(children)!=expected)return false;
    for(int i=0;i<expected;i++) {
      WbNodeRef node=wb_supervisor_field_get_mf_node(children,i);
      const char *item=node?wb_supervisor_node_get_type_name(node):nullptr;
      if(!item||std::strcmp(item,i<poses?"Pose":"Solid"))return false;
    }
  }
  for(int i=1;i<=variant;i++) {
    const double x=-.850+.850*(i-1);
    const double left[3]={x,.300,.500},right[3]={x,-.300,.500},bar[3]={x,0,.740};
    const double upright[3]={.070,.065,1.00},crossbar[3]={.070,.570,.240};
    char name[80];
    std::snprintf(name,sizeof name,"ACTIVITY6_%d_H_%d_LEFT",variant,i);
    if(!box(name,left,upright))return false;
    std::snprintf(name,sizeof name,"ACTIVITY6_%d_H_%d_RIGHT",variant,i);
    if(!box(name,right,upright))return false;
    std::snprintf(name,sizeof name,"ACTIVITY6_%d_H_%d_BAR",variant,i);
    if(!box(name,bar,crossbar))return false;
  }
  const double finish[3]={1.235,0,.760},finishSize[3]={.070,1.48,.240};
  const double end[3]={1.86,0,.550},endSize[3]={.060,1.48,1.10};
  char name[80];
  std::snprintf(name,sizeof name,"ACTIVITY6_%d_FINISH_SCREEN",variant);
  if(!box(name,finish,finishSize))return false;
  std::snprintf(name,sizeof name,"ACTIVITY6_%d_TERMINAL",variant);
  return box(name,end,endSize);
}
} // namespace webeeblocks_a6_gate
#endif

/* Draft Activity 7: isolated R2025a Supervisor for one Mini Grand Prix scene.
 * Provides observed pose, yaw, velocity, contacts, and one-shot attempt epochs
 * to the behavioral C oracle. It NEVER writes motors, pupil AST or physical
 * Crazyflie authority. Real student motor flights are NOT proven by build.
 */
#include "mini_core.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <webots/contact_point.h>
#include <webots/robot.h>
#include <webots/supervisor.h>

#define WB_A7_OBSERVER "Mini Grand Prix native evaluator"
#define WB_A7_CONTROLLER "progression_mini_grand_prix_v1"
#define WB_A7_CRAFT "Crazyflie WebeeBlocks"
#define WB_A7_ORACLE "progression-mini-grand-prix-v1"
#define WB_A7_SCENE_CHILDREN 29

typedef struct {
  const char *name;
  double position[3];
  double dimensions[3];
} expected_solid;

static int within(double actual,double expected) {
  return isfinite(actual)&&fabs(actual-expected)<0.000001;
}
static int field_is(WbNodeRef node,const char *key,const char *expected) {
  WbFieldRef f=node?wb_supervisor_node_get_field(node,key):NULL;
  const char *text=f?wb_supervisor_field_get_sf_string(f):NULL;
  return text&&strcmp(text,expected)==0;
}
static int solid_at(const expected_solid *expected) {
  WbNodeRef node=wb_supervisor_node_get_from_def(expected->name);
  if(!node||strcmp(wb_supervisor_node_get_type_name(node),"Solid"))return 0;
  const double *p=wb_supervisor_node_get_position(node);
  const double *rot=wb_supervisor_node_get_orientation(node);
  WbFieldRef field=wb_supervisor_node_get_field(node,"boundingObject");
  WbNodeRef geometry=field?wb_supervisor_field_get_sf_node(field):NULL;
  if(!geometry||strcmp(wb_supervisor_node_get_type_name(geometry),"Box"))return 0;
  WbFieldRef sf=wb_supervisor_node_get_field(geometry,"size");
  const double *size=sf?wb_supervisor_field_get_sf_vec3f(sf):NULL;
  if(!p||!rot||!size)return 0;
  for(int i=0;i<3;++i)
    if(!within(p[i],expected->position[i])||
       !within(size[i],expected->dimensions[i])||size[i]<=0)return 0;
  for(int i=0;i<9;++i)
    if(!within(rot[i],i%4==0?1.0:0.0))return 0;
  return 1;
}
static int attest_scene(char *variant) {
  WbNodeRef left=wb_supervisor_node_get_from_def("WEBEEBLOCKS_MINI_GP_L_SCENE");
  WbNodeRef right=wb_supervisor_node_get_from_def("WEBEEBLOCKS_MINI_GP_R_SCENE");
  WbNodeRef world=wb_supervisor_node_get_from_def("WEBEEBLOCKS_CLASSROOM_START_WORLD");
  if(!variant||(!left&&!right)||(left&&right)||!world||
     strcmp(wb_supervisor_node_get_type_name(world),"WorldInfo")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_SEQUENCE_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_ALTITUDE_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_ORIENTATION_SCENE")||
     /* A4 scenes are now integrated into main: reject mixed mission worlds. */
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_DECISION_A_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_DECISION_B_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_EVALUATORS"))
    return 0;
  *variant=left?'L':'R';
  WbNodeRef scene=left?left:right;
  WbFieldRef children=wb_supervisor_node_get_field(scene,"children");
  if(strcmp(wb_supervisor_node_get_type_name(scene),"Group")||!children||
     wb_supervisor_field_get_count(children)!=WB_A7_SCENE_CHILDREN)return 0;
  for(int i=0;i<WB_A7_SCENE_CHILDREN;++i){
    WbNodeRef child=wb_supervisor_field_get_mf_node(children,i);
    if(!child||strcmp(wb_supervisor_node_get_type_name(child),
                        i<20?"Pose":"Solid"))return 0;
  }
  WbNodeRef first=wb_supervisor_field_get_mf_node(children,0);
  WbFieldRef nested=wb_supervisor_node_get_field(first,"children");
  if(!nested||wb_supervisor_field_get_count(nested)!=2)return 0;
  WbNodeRef marker=wb_supervisor_field_get_mf_node(nested,0);
  WbNodeRef observer=wb_supervisor_field_get_mf_node(nested,1);
  WbFieldRef sup=observer?wb_supervisor_node_get_field(observer,"supervisor"):NULL;
  WbFieldRef sync=observer?wb_supervisor_node_get_field(observer,"synchronization"):NULL;
  const char *self=wb_robot_get_name();
  if(!marker||strcmp(wb_supervisor_node_get_type_name(marker),"Shape")||
     !observer||strcmp(wb_supervisor_node_get_type_name(observer),"Robot")||
     !field_is(observer,"name",WB_A7_OBSERVER)||
     !field_is(observer,"controller",WB_A7_CONTROLLER)||
     !sup||!sync||!wb_supervisor_field_get_sf_bool(sup)||
     !wb_supervisor_field_get_sf_bool(sync)||
     !self||strcmp(self,WB_A7_OBSERVER))return 0;
  const double h=wb_mini_h_x(*variant);
  const double turn=wb_mini_turn_x(*variant);
  const double side=*variant=='L'?1.0:-1.0;
  const expected_solid expected[]={
    {"", {h,.300,.500},{.070,.065,1.00}},
    {"", {h,-.300,.500},{.070,.065,1.00}},
    {"", {h,0,.740},{.070,.570,.240}},
    {"", {turn+.220,0,.550},{.080,.640,1.10}},
    {"", {turn,-side*.320,.550},{.480,.080,1.10}},
    {"", {turn-.300,side*1.420,.650},{.065,.080,1.30}},
    {"", {turn+.300,side*1.420,.650},{.065,.080,1.30}},
    {"", {turn,side*1.420,.900},{.570,.080,.300}},
    {"", {turn,side*1.420,.650},{.570,.080,1.30}}
  };
  const char *const names[]={
    "OPEN_LEFT","OPEN_RIGHT","OPEN_BAR","CORNER_FRONT","CORNER_SIDE",
    "CLOSED_LEFT","CLOSED_RIGHT","CLOSED_BAR","CLOSED_PANEL"
  };
  for(int i=0;i<9;++i){
    char def[96];
    const int n=snprintf(def,sizeof(def),"ACTIVITY7_%c_%s",*variant,names[i]);
    if(n<=0||(size_t)n>=sizeof(def))return 0;
    expected_solid check=expected[i];check.name=def;
    if(!solid_at(&check))return 0;
  }
  return 1;
}
static WbNodeRef unique_vehicle(void) {
  WbNodeRef root=wb_supervisor_node_get_root();
  WbFieldRef children=root?wb_supervisor_node_get_field(root,"children"):NULL;
  WbNodeRef found=NULL;
  for(int i=0;children&&i<wb_supervisor_field_get_count(children);++i){
    WbNodeRef node=wb_supervisor_field_get_mf_node(children,i);
    if(!field_is(node,"name",WB_A7_CRAFT))continue;
    if(found)return NULL;
    found=node;
  }
  return found;
}
static int attempt_token(const char *data,unsigned long long *out) {
  unsigned long long attempt=0;char extra=0;
  if(!data||!out||sscanf(data,"WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu%c",
                         &attempt,&extra)!=1||attempt==0)return 0;
  char canonical[96];
  const int n=snprintf(canonical,sizeof(canonical),
                 "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu",attempt);
  if(n<=0||(size_t)n>=sizeof(canonical)||strcmp(data,canonical))return 0;
  *out=attempt;return 1;
}
static int completed_token(const char *data,unsigned long long attempt) {
  char expected[192];
  const int n=snprintf(expected,sizeof(expected),
    "WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=%llu oracle=%s",
    attempt,WB_A7_ORACLE);
  return data&&n>0&&(size_t)n<sizeof(expected)&&!strcmp(expected,data);
}
static int native_contact(WbNodeRef craft) {
  int count=-1;
  const WbContactPoint *points=
    wb_supervisor_node_get_contact_points(craft,true,&count);
  if(count<0||(count>0&&!points))return -1;
  for(int i=0;i<count;++i){
    const double *p=points[i].point;
    if(!isfinite(p[0])||!isfinite(p[1])||!isfinite(p[2]))return -1;
    /* Floor is allowed during departure/touchdown; only non-floor
     * collision contacts are obstacle failures. */
    if(fabs(p[2])>0.025)return 1;
  }
  return 0;
}
static void publish(WbFieldRef channel,const wb_mini_mission *m) {
  const char *status=m->verdict==WB_MINI_ACHIEVED?"achieved":"not-achieved";
  char message[192];
  const int n=snprintf(message,sizeof(message),
    "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=%s",
    m->attempt,WB_A7_ORACLE,status);
  if(n>0&&(size_t)n<sizeof(message))
    wb_supervisor_field_set_sf_string(channel,message);
  printf("WB_MINI_NATIVE_RESULT variant=%c attempt=%llu status=%s crossed=%d turned=%d\n",
         m->variant,m->attempt,status,m->crossed,m->turned);
  fflush(stdout);
}
int main(void) {
  wb_robot_init();
  const int step=(int)wb_robot_get_basic_time_step();
  char variant=0;
  /* The landing oracle requires contiguous 32-ms native observations.
   * Other physics cadences cannot establish a valid 250-ms stable landing.
   * Reject before READY rather than weakening the 40-ms gap guard. */
  if(step!=32||!attest_scene(&variant)){
    fprintf(stderr,"WB_MINI_NATIVE_FATAL invalid native scene, colliders, observer or timestep\n");
    wb_robot_cleanup();return 2;
  }
  WbNodeRef craft=unique_vehicle();
  WbFieldRef channel=craft?wb_supervisor_node_get_field(craft,"customData"):NULL;
  const double *origin=craft?wb_supervisor_node_get_position(craft):NULL;
  if(!channel||!origin||!isfinite(origin[2])){
    fprintf(stderr,"WB_MINI_NATIVE_FATAL missing or ambiguous physical craft\n");
    wb_robot_cleanup();return 2;
  }
  const double origin_z=origin[2];
  wb_supervisor_node_enable_contact_points_tracking(craft,step,true);
  wb_mini_mission mission={0};
  unsigned long long last_attempt=0;
  printf("WB_MINI_NATIVE_READY variant=%c oracle=%s origin_z=%.9f step=%d\n",
         variant,WB_A7_ORACLE,origin_z,step);
  fflush(stdout);
  while(wb_robot_step(step)!=-1){
    const char *data=wb_supervisor_field_get_sf_string(channel);
    unsigned long long attempt=0;
    if(attempt_token(data,&attempt)&&attempt>last_attempt){
      wb_mini_reset(&mission,attempt,variant,origin_z);
      last_attempt=attempt;
      printf("WB_MINI_NATIVE_ATTEMPT variant=%c attempt=%llu\n",variant,attempt);
      fflush(stdout);
    }
    if(!last_attempt||mission.verdict!=WB_MINI_WAIT)continue;
    wb_mini_sample sample={0};
    sample.time=wb_robot_get_time();
    sample.contact=native_contact(craft);
    sample.completed=completed_token(data,mission.attempt);
    const double *p=wb_supervisor_node_get_position(craft);
    const double *v=wb_supervisor_node_get_velocity(craft);
    const double *o=wb_supervisor_node_get_orientation(craft);
    if(!p||!v||!o){
      sample.x=NAN;
    }else{
      sample.x=p[0];sample.y=p[1];sample.z=p[2];
      sample.vx=v[0];sample.vy=v[1];sample.vz=v[2];
      sample.yaw=atan2(o[3],o[0]);
    }
    if(!mission.previous_valid){
      printf("WB_MINI_NATIVE_FIRST variant=%c attempt=%llu time=%.9f "
             "x=%.9f y=%.9f z=%.9f contact=%d "
             "vx=%.9f vy=%.9f vz=%.9f\n",
             variant,mission.attempt,sample.time,sample.x,sample.y,
             sample.z,sample.contact,sample.vx,sample.vy,sample.vz);
      fflush(stdout);
    }
    if(wb_mini_sample_mission(&mission,&sample)!=WB_MINI_WAIT)
      publish(channel,&mission);
  }
  wb_robot_cleanup();
  return 0;
}

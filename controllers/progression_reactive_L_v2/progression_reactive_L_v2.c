/* Activity 5 v2 Draft: Webots R2025a native observation-only evaluator.
 * It NEVER commands the craft, reads Blockly code or links physical runtime.
 * Only a separate pupil flight and its ordinary customData attempt may
 * produce an outcome. Not yet wired to the pupil scene selection.
 */
#include "reactive_core_v2.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <webots/contact_point.h>
#include <webots/robot.h>
#include <webots/supervisor.h>

#define WB_RL2_CRAFT "Crazyflie WebeeBlocks"
static int close_native(double a,double b){
  return isfinite(a)&&fabs(a-b)<=0.000001;
}
static int attest_box(const char *def,const wb_rl2_box *box){
  WbNodeRef node=wb_supervisor_node_get_from_def(def);
  if(!node||strcmp(wb_supervisor_node_get_type_name(node),"Solid"))return 0;
  const double *pos=wb_supervisor_node_get_position(node);
  WbFieldRef boundary=wb_supervisor_node_get_field(node,"boundingObject");
  WbNodeRef geometry=boundary?wb_supervisor_field_get_sf_node(boundary):NULL;
  if(!pos||!geometry||
     strcmp(wb_supervisor_node_get_type_name(geometry),"Box"))return 0;
  WbFieldRef field=wb_supervisor_node_get_field(geometry,"size");
  const double *size=field?wb_supervisor_field_get_sf_vec3f(field):NULL;
  if(!size)return 0;
  const double p[]={box->x,box->y,box->z};
  const double d[]={box->sx,box->sy,box->sz};
  for(int i=0;i<3;++i)
    if(!close_native(pos[i],p[i])||!close_native(size[i],d[i]))
      return 0;
  /* A rotated Solid preserves both its translation and local Box size, but
   * changes the world-space collider. Attest the actual native orientation.
   * This is a startup check for the trusted STATIC classroom scene only. */
  const double *orientation=wb_supervisor_node_get_orientation(node);
  if(!orientation)return 0;
  for(int i=0;i<9;++i){
    const double expected=(i%4==0)?1.0:0.0;
    if(!close_native(orientation[i],expected))return 0;
  }
  return 1;
}
static int attest_scene(char *variant){
  *variant=0;
  WbNodeRef scene=NULL;
  for(char v='A';v<='C';++v){
    char def[90];
    snprintf(def,sizeof(def),"WEBEEBLOCKS_REACTIVE_L_V2_%c_SCENE",v);
    WbNodeRef candidate=wb_supervisor_node_get_from_def(def);
    if(candidate){
      if(*variant)return 0; /* two active variants is ambiguous */
      *variant=v;scene=candidate;
    }
  }
  if(!scene||!wb_rl2_variant(*variant)||
     strcmp(wb_supervisor_node_get_type_name(scene),"Group"))return 0;
  WbFieldRef children=wb_supervisor_node_get_field(scene,"children");
  const int expected=*variant=='C'?28:25;
  if(!children||wb_supervisor_field_get_count(children)!=expected)return 0;
  for(int i=0;i<expected;++i)
    if(!wb_supervisor_field_get_mf_node(children,i))return 0;
  /* The visually marked start, two junctions and target must match the
   * independent mission manifest, not just have the right child count. */
  const double marks[5][2]={
    {0,0},{.8,0},{.8,1.0},
    {*variant=='C'?-0.45:wb_rl2_pad_x(*variant),1.0},
    {wb_rl2_pad_x(*variant),wb_rl2_pad_y(*variant)}
  };
  for(int i=0;i<(*variant=='C'?5:4);++i){
    WbNodeRef pose=wb_supervisor_field_get_mf_node(children,i);
    if(strcmp(wb_supervisor_node_get_type_name(pose),"Pose"))return 0;
    const double *p=wb_supervisor_node_get_position(pose);
    const double x=(*variant=='C'||i!=3)?marks[i][0]:wb_rl2_pad_x(*variant);
    const double y=(*variant=='C'||i!=3)?marks[i][1]:wb_rl2_pad_y(*variant);
    if(!p||!close_native(p[0],x)||!close_native(p[1],y)||
       !close_native(p[2],.002))return 0;
  }
  const char *suffix[7]={
    "L1_FRONT","L1_SIDE","L2_FRONT","L2_SIDE",
    *variant=='C'?"L3_FRONT":"TERMINAL","L3_SIDE","TERMINAL"
  };
  wb_rl2_box boxes[7];int n=wb_rl2_boxes(*variant,boxes);
  for(int i=0;i<n;++i){
    char def[90];
    snprintf(def,sizeof(def),"ACTIVITY5_V2_%c_%s",*variant,suffix[i]);
    if(!attest_box(def,&boxes[i]))return 0;
  }
  if(wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_SEQUENCE_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_ORIENTATION_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_ALTITUDE_SCENE")||
     /* A4 is on main: reject another independently evaluated course. */
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_DECISION_A_SCENE")||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_DECISION_B_SCENE"))
    return 0;
  return 1;
}
static WbNodeRef unique_craft(void){
  WbNodeRef root=wb_supervisor_node_get_root();
  WbFieldRef children=root?wb_supervisor_node_get_field(root,"children"):NULL;
  if(!children)return NULL;
  WbNodeRef found=NULL;
  for(int i=0;i<wb_supervisor_field_get_count(children);++i){
    WbNodeRef node=wb_supervisor_field_get_mf_node(children,i);
    WbFieldRef name=node?wb_supervisor_node_get_field(node,"name"):NULL;
    const char *n=name?wb_supervisor_field_get_sf_string(name):NULL;
    if(n&&strcmp(n,WB_RL2_CRAFT)==0){
      if(found)return NULL;
      found=node;
    }
  }
  return found;
}
static int parse_attempt(const char *value,unsigned long long *out){
  unsigned long long n=0;char extra='\0';
  if(!value||!out||sscanf(value,"WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu%c",
                          &n,&extra)!=1||!n)return 0;
  char canonical[110];
  int len=snprintf(canonical,sizeof(canonical),
                   "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu",n);
  if(len<1||(size_t)len>=sizeof(canonical)||
     strcmp(value,canonical))return 0;
  *out=n;return 1;
}
static int parse_completion(const char *value,unsigned long long attempt){
  char canonical[200];
  int len=snprintf(canonical,sizeof(canonical),
                   "WEBEEBLOCKS_ACTIVITY_COMPLETION_V1 attempt=%llu oracle=%s",
                   attempt,WB_RL2_ORACLE);
  return value&&len>0&&(size_t)len<sizeof(canonical)&&
         strcmp(value,canonical)==0;
}
static int native_obstacles_contact(WbNodeRef craft,double ground){
  int count=-1;
  const WbContactPoint *points=
    wb_supervisor_node_get_contact_points(craft,true,&count);
  if(count<0||(count>0&&!points))return -1;
  for(int i=0;i<count;++i){
    const double *xyz=points[i].point;
    if(!isfinite(xyz[0])||!isfinite(xyz[1])||
       !isfinite(xyz[2]))return -1;
    /* Floor touchdown below 12 cm does not cancel valid stable landing.
     * A high contact is a collision, regardless of how Blockly was built. */
    if(xyz[2]>ground+.12)return 1;
  }
  return 0;
}
static int native_yaw(const double orientation[9],double *out){
  if(!orientation||!out)return 0;
  for(int i=0;i<9;++i)
    if(!isfinite(orientation[i]))return 0;
  if(hypot(orientation[0],orientation[3])<.5)return 0;
  *out=atan2(orientation[3],orientation[0]);
  return isfinite(*out);
}
static void publish(WbFieldRef channel,const wb_rl2_mission *m){
  const char *status=m->verdict==WB_RL2_ACHIEVED?"achieved":"not-achieved";
  char marker[210];
  int len=snprintf(marker,sizeof(marker),
        "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=%s",
        m->attempt,WB_RL2_ORACLE,status);
  if(len<=0||(size_t)len>=sizeof(marker))return;
  wb_supervisor_field_set_sf_string(channel,marker);
  printf("WEBEEBLOCKS_A5_V2_RESULT attempt=%llu status=%s stage=%d variant=%c\n",
         m->attempt,status,m->stage,m->variant);
  fflush(stdout);
}
int main(void){
  wb_robot_init();
  const int step=(int)wb_robot_get_basic_time_step();
  char variant=0;
  /* A5 classroom geometry and the independent 48-ms dwell-gap witness
   * are qualified for an exact 32-ms physics/observer cadence, not 64 ms. */
  if(step!=32||!attest_scene(&variant)){
    fprintf(stderr,"WEBEEBLOCKS_A5_V2_FATAL native scene geometry/identity\n");
    wb_robot_cleanup();return 2;
  }
  WbNodeRef craft=unique_craft();
  WbFieldRef channel=craft?wb_supervisor_node_get_field(craft,"customData"):NULL;
  const double *start=craft?wb_supervisor_node_get_position(craft):NULL;
  if(!channel||!start||!isfinite(start[0])||!isfinite(start[1])||
     fabs(start[0])>.15||fabs(start[1])>.15||!isfinite(start[2])||
     start[2]<WB_RL2_START_MIN_Z||start[2]>WB_RL2_START_MAX_Z){
    fprintf(stderr,"WEBEEBLOCKS_A5_V2_FATAL vehicle identity/initial pose\n");
    wb_robot_cleanup();return 2;
  }
  const double origin_z=start[2];
  wb_supervisor_node_enable_contact_points_tracking(craft,step,true);
  wb_rl2_mission mission={0};unsigned long long last_attempt=0;
  printf("WEBEEBLOCKS_A5_V2_NATIVE_C_READY scene=%c oracle=%s\n",
         variant,WB_RL2_ORACLE);fflush(stdout);
  while(wb_robot_step(step)!=-1){
    const char *value=wb_supervisor_field_get_sf_string(channel);
    unsigned long long attempt=0;
    if(parse_attempt(value,&attempt)&&attempt>last_attempt){
      wb_rl2_reset(&mission,attempt,variant,origin_z);
      last_attempt=attempt;
      printf("WEBEEBLOCKS_A5_V2_ATTEMPT attempt=%llu\n",attempt);
      fflush(stdout);
    }
    if(!last_attempt||mission.verdict!=WB_RL2_WAIT)continue;
    wb_rl2_sample s={0};
    s.time=wb_robot_get_time();
    s.completed=parse_completion(value,mission.attempt);
    const double *pos=wb_supervisor_node_get_position(craft);
    const double *vel=wb_supervisor_node_get_velocity(craft);
    const double *orientation=wb_supervisor_node_get_orientation(craft);
    const int contact=native_obstacles_contact(craft,origin_z);
    if(!pos||!vel||contact<0||!native_yaw(orientation,&s.yaw)){
      s.x=NAN; /* Real native unknown state is a terminal failure. */
    }else{
      s.x=pos[0];s.y=pos[1];s.z=pos[2];
      s.vx=vel[0];s.vy=vel[1];s.vz=vel[2];
      s.contact=contact;
    }
    const wb_rl2_verdict before=mission.verdict;
    wb_rl2_sample_mission(&mission,&s);
    if(before==WB_RL2_WAIT&&mission.verdict!=WB_RL2_WAIT)
      publish(channel,&mission);
  }
  wb_robot_cleanup();
  return 0;
}

/* A6 bounded three-variant physical observer for genuine Webots R2025a flight.
 * Separate observer Robot: does not command flight, read pupil JS or AST,
 * or publish a product mission verdict. Only a CI physical witness.
 * Product Grand Prix and real Crazyflie safety binaries are not linked.
 */
#include "../progression_count_h_v1/count_core.h"
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <webots/contact_point.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static WbNodeRef find_craft(void) {
  WbNodeRef root=wb_supervisor_node_get_root();
  WbFieldRef children=root?wb_supervisor_node_get_field(root,"children"):NULL;
  WbNodeRef craft=NULL;
  if(!children)return NULL;
  for(int i=0;i<wb_supervisor_field_get_count(children);++i) {
    WbNodeRef node=wb_supervisor_field_get_mf_node(children,i);
    WbFieldRef name=node?wb_supervisor_node_get_field(node,"name"):NULL;
    const char *actual=name?wb_supervisor_field_get_sf_string(name):NULL;
    if(actual&&!strcmp(actual,"Crazyflie WebeeBlocks")) {
      if(craft)return NULL;
      craft=node;
    }
  }
  return craft;
}
static int box(const char *def,double x,double y,double z,
               double sx,double sy,double sz,WbNodeRef *result) {
  WbNodeRef solid=wb_supervisor_node_get_from_def(def);
  if(!solid||strcmp(wb_supervisor_node_get_type_name(solid),"Solid"))return 0;
  const double *p=wb_supervisor_node_get_position(solid);
  WbFieldRef ref=wb_supervisor_node_get_field(solid,"boundingObject");
  WbNodeRef geom=ref?wb_supervisor_field_get_sf_node(ref):NULL;
  if(!p||!geom||strcmp(wb_supervisor_node_get_type_name(geom),"Box"))return 0;
  WbFieldRef size=wb_supervisor_node_get_field(geom,"size");
  const double *s=size?wb_supervisor_field_get_sf_vec3f(size):NULL;
  const double a[]={x,y,z},b[]={sx,sy,sz};
  if(!s)return 0;
  for(int i=0;i<3;++i)
    if(!isfinite(p[i])||fabs(p[i]-a[i])>.000001||
       !isfinite(s[i])||fabs(s[i]-b[i])>.000001)return 0;
  const double *orientation=wb_supervisor_node_get_orientation(solid);
  if(!orientation)return 0;
  for(int row=0;row<3;++row)
    for(int col=0;col<3;++col) {
      const double expected=row==col?1.0:0.0;
      const double actual=orientation[3*row+col];
      if(!isfinite(actual)||fabs(actual-expected)>.000001)return 0;
    }
  *result=solid;
  return 1;
}
static int fail(const char *reason) {
  fprintf(stderr,"WEBEEBLOCKS_A6_MOTOR_FATAL %s\n",reason);
  fflush(stderr);
  wb_robot_cleanup();
  return 2;
}
int main(void) {
  wb_robot_init();
  const int step=(int)wb_robot_get_basic_time_step();
  if(step!=32||strcmp(wb_robot_get_name(),"A6 independent motor-flight observer"))
    return fail("observer identity/timestep");
  /* A6 native scene is self-identifying. Exactly one numbered scene is
   * accepted, with every physical Solid checked before any flight verdict. */
  int variant=0;
  for(int n=1;n<=3;++n) {
    char group[48];
    snprintf(group,sizeof(group),"WEBEEBLOCKS_COUNT_%d_SCENE",n);
    if(wb_supervisor_node_get_from_def(group)) {
      if(variant)return fail("multiple numbered scenes in observer world");
      variant=n;
    }
  }
  if(!variant)return fail("no numbered physical scene");
  WbNodeRef obstacle[11]={0};
  int collider_count=0;
  for(int n=1;n<=variant;++n) {
    const double x=wb_count_gate_x((unsigned)n-1);
    char left[48],right[48],bar[48];
    snprintf(left,sizeof(left),"ACTIVITY6_%d_H_%d_LEFT",variant,n);
    snprintf(right,sizeof(right),"ACTIVITY6_%d_H_%d_RIGHT",variant,n);
    snprintf(bar,sizeof(bar),"ACTIVITY6_%d_H_%d_BAR",variant,n);
    if(!box(left,x,.30,.50,.07,.065,1.0,&obstacle[collider_count++])||
       !box(right,x,-.30,.50,.07,.065,1.0,&obstacle[collider_count++])||
       !box(bar,x,0,.74,.07,.57,.24,&obstacle[collider_count++]))
      return fail("H collider geometry not native-attested");
  }
  char screen[48],terminal[48];
  snprintf(screen,sizeof(screen),"ACTIVITY6_%d_FINISH_SCREEN",variant);
  snprintf(terminal,sizeof(terminal),"ACTIVITY6_%d_TERMINAL",variant);
  if(!box(screen,1.235,0,.76,.07,1.48,.24,&obstacle[collider_count++])||
     !box(terminal,1.86,0,.55,.06,1.48,1.10,&obstacle[collider_count++])||
     collider_count!=3*variant+2)
    return fail("finish screen, terminal or collider count not attested");
  WbNodeRef craft=find_craft();
  const double *origin=craft?wb_supervisor_node_get_position(craft):NULL;
  const double *start_velocity=craft?wb_supervisor_node_get_velocity(craft):NULL;
  /* The authentic R2025a Crazyflie has a 0.030 m high cylinder collider:
   * its settled centre on Floor is z~0.015 m, not the 0.055 m spawn pose.
   * Accept only the bounded resting/initial zone and a stationary craft. */
  if(!origin||!start_velocity||!isfinite(origin[2])||
     fabs(origin[0]+1.40)>.025||fabs(origin[1])>.025||
     origin[2]<0.012||origin[2]>0.075||
     !isfinite(start_velocity[0])||!isfinite(start_velocity[1])||
     !isfinite(start_velocity[2])||
     hypot(start_velocity[0],start_velocity[1])>.12||
     fabs(start_velocity[2])>.12)
    return fail("motor flight did not start at authentic stationary blue zone");
  const double origin_z=origin[2];
  WbFieldRef channel=wb_supervisor_node_get_field(craft,"customData");
  if(!channel)return fail("missing native runtime-v2 completion channel");
  wb_count_mission m={0};
  wb_count_reset(&m,1,(unsigned)variant,origin_z);
  for(int i=0;i<collider_count;++i)
    wb_supervisor_node_enable_contact_points_tracking(obstacle[i],step,false);
  wb_supervisor_node_enable_contact_points_tracking(craft,step,true);
  double last_x=-1.4,last_y=0,last_z=origin_z;
  int previous=0, reported_cross=0, screen_seen=0, observations=0;
  printf("WEBEEBLOCKS_A6_MOTOR_READY n=%d origin_z=%.9f colliders=%d\n",
         variant,origin_z,collider_count);
  fflush(stdout);
  while(wb_robot_step(step)!=-1) {
    const double *pos=wb_supervisor_node_get_position(craft);
    const double *velocity=wb_supervisor_node_get_velocity(craft);
    if(!pos||!velocity)return fail("missing native motor flight kinematics");
    wb_count_sample sample={0};
    sample.time=wb_robot_get_time();
    sample.x=pos[0]; sample.y=pos[1]; sample.z=pos[2];
    sample.vx=velocity[0];sample.vy=velocity[1];sample.vz=velocity[2];
    if(!wb_count_valid_sample(&(wb_count_sample){.time=sample.time,
       .x=sample.x,.y=sample.y,.z=sample.z,.vx=sample.vx,
       .vy=sample.vy,.vz=sample.vz,.obstacle_contact=0,.completed=0,
       .floor_contact=0}))
      return fail("nonfinite native flight observation");
    if(previous&&
       (fabs(pos[0]-last_x)>.075||fabs(pos[1]-last_y)>.075||
        fabs(pos[2]-last_z)>.100))
      return fail("unphysical supervisor pose discontinuity");
    last_x=pos[0];last_y=pos[1];last_z=pos[2];previous=1;
    ++observations;
    if(sample.time>145.0)return fail("bounded native motor flight timeout");
    for(int i=0;i<collider_count;++i) {
      int n=-1;
      const WbContactPoint *points=
        wb_supervisor_node_get_contact_points(obstacle[i],false,&n);
      if(n<0||(n>0&&!points))return fail("missing native collision evidence");
      if(n) {
        fprintf(stderr,"WEBEEBLOCKS_A6_MOTOR_FATAL physical_contact collider=%d "
                       "count=%d x=%.6f y=%.6f z=%.6f\n",
                       i,n,sample.x,sample.y,sample.z);
        fflush(stderr);
        wb_robot_cleanup();
        return 2;
      }
    }
    /* All attested obstacle-side contacts were rejected above, including
     * low z. Query separate physical craft contacts to attest actual Floor. */
    int craft_count=-1;
    const WbContactPoint *craft_hits=
      wb_supervisor_node_get_contact_points(craft,true,&craft_count);
    if(craft_count<0||(craft_count>0&&!craft_hits))
      return fail("missing native craft contact evidence");
    sample.floor_contact=0;
    for(int i=0;i<craft_count;++i) {
      const double *pt=craft_hits[i].point;
      if(!isfinite(pt[0])||!isfinite(pt[1])||!isfinite(pt[2]))
        return fail("nonfinite native craft contact point");
      if(fabs(pt[2])<=.025)sample.floor_contact=1;
      else return fail("unclassified non-Floor craft contact");
    }
    if(fabs(sample.x-1.235)<=.03 && sample.x>0 &&
       fabs(sample.y)<=.10 && sample.z<=.53)screen_seen=1;
    /* Mission completion must be published by the native runtime broker
     * for the active attempt, never guessed from the pad pose. */
    sample.completed=wb_count_exact_completion(
      wb_supervisor_field_get_sf_string(channel),m.attempt);
    if(sample.completed&&!m.completion_seen) {
      printf("WEBEEBLOCKS_A6_MOTOR_NATIVE_COMPLETION attempt=%llu oracle=%s time=%.3f\n",
             m.attempt,WB_COUNT_ORACLE,sample.time);
      fflush(stdout);
    }
    sample.obstacle_contact=0;
    wb_count_verdict result=wb_count_sample_mission(&m,&sample);
    if(m.crossed>(unsigned)reported_cross) {
      printf("WEBEEBLOCKS_A6_MOTOR_CROSSED n=%d crossed=%u x=%.6f z=%.6f time=%.3f\n",
             variant,m.crossed,sample.x,sample.z,sample.time);
      fflush(stdout);reported_cross=(int)m.crossed;
    }
    if(result==WB_COUNT_NOT_ACHIEVED)return fail("native behavioral oracle rejected flight");
    if(result==WB_COUNT_ACHIEVED) {
      if(sample.floor_contact!=1)
        return fail("achievement without actual Floor contact");
      printf("WEBEEBLOCKS_A6_MOTOR_NATIVE_FLOOR_CONTACT n=%d time=%.3f z=%.6f\n",
             variant,sample.time,sample.z);
      fflush(stdout);
      if(!screen_seen||reported_cross!=variant||observations<20)
        return fail("native flight lacks credible full corridor passage");
      printf("WEBEEBLOCKS_A6_MOTOR_RESULT status=achieved n=%d "
             "crossed=%u screen=%d observations=%d "
             "x=%.6f y=%.6f z=%.6f\n",
             variant,m.crossed,screen_seen,observations,
             sample.x,sample.y,sample.z);
      fflush(stdout);
      wb_robot_cleanup();
      return 0;
    }
    if(observations%100==0) {
      printf("WEBEEBLOCKS_A6_MOTOR_TRACE time=%.3f x=%.6f y=%.6f "
             "z=%.6f vx=%.6f crossed=%u\n",
             sample.time,sample.x,sample.y,sample.z,sample.vx,m.crossed);
      fflush(stdout);
    }
  }
  return fail("native Webots terminated before flight result");
}

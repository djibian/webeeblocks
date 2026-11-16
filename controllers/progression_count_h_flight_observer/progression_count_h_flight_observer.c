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
/* Broker-controlled epochs arrive on the craft's native customData channel.
 * A RESET does not restart this Robot; only a fresh exact marker may rearm.
 * No pupil AST, pad pose or visible "READY" event grants an epoch. */
static int new_epoch_marker(const char *data,unsigned long long *out) {
  if(!data||!out)return 0;
  unsigned long long epoch=0;char tail='\0';
  if(sscanf(data,"WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu%c",
            &epoch,&tail)!=1||epoch==0)return 0;
  char exact[128];
  int n=snprintf(exact,sizeof(exact),
                 "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %llu",epoch);
  if(n<=0||(size_t)n>=sizeof(exact)||strcmp(exact,data))return 0;
  *out=epoch;
  return 1;
}
/* The heartbeat is authored by the still-running native observer, not
 * by the browser or the flight controller. It expires without fresh steps. */
static void publish_liveness(WbFieldRef health,unsigned long long epoch,
                             int variant,double time) {
  char token[192];
  snprintf(token,sizeof(token),
    "WEBEEBLOCKS_A6_NATIVE_OBSERVER_LIVE_V1 epoch=%llu variant=%d time=%.6f",
    epoch,variant,time);
  wb_supervisor_field_set_sf_string(health,token);
}
static void publish_attempt_verdict(WbFieldRef channel,
                                    unsigned long long epoch,int achieved) {
  char marker[192];
  snprintf(marker,sizeof(marker),
    "WEBEEBLOCKS_ACTIVITY_OUTCOME_V1 attempt=%llu oracle=%s status=%s",
    epoch,WB_COUNT_ORACLE,achieved?"achieved":"not-achieved");
  wb_supervisor_field_set_sf_string(channel,marker);
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
  WbNodeRef observer=wb_supervisor_node_get_self();
  WbFieldRef health=observer?
    wb_supervisor_node_get_field(observer,"customData"):NULL;
  if(!health)return fail("missing native observer heartbeat channel");
  /* Dynamic classroom imports may happen after earlier activities have
   * advanced the same native broker to epoch > 1. Derive the initial epoch
   * exclusively from the canonical current broker token; successive RESETs
   * of this already-running observer must still advance exactly by one.
   * Missing, stale/malformed or forged epoch text does NOT authorize READY. */
  const char *initial=wb_supervisor_field_get_sf_string(channel);
  unsigned long long initial_epoch=0;
  if(!new_epoch_marker(initial,&initial_epoch))
    return fail("initial canonical broker epoch missing");
  wb_count_mission m={0};
  wb_count_reset(&m,initial_epoch,(unsigned)variant,origin_z);
  for(int i=0;i<collider_count;++i)
    wb_supervisor_node_enable_contact_points_tracking(obstacle[i],step,false);
  wb_supervisor_node_enable_contact_points_tracking(craft,step,true);
  double epoch_start_time=wb_robot_get_time();
  double last_x=-1.4,last_y=0,last_z=origin_z;
  int previous=0, reported_cross=0, screen_seen=0, observations=0;
  printf("WEBEEBLOCKS_A6_MOTOR_READY n=%d origin_z=%.9f colliders=%d\n",
         variant,origin_z,collider_count);
  fflush(stdout);
  while(wb_robot_step(step)!=-1) {
    const char *native_state=wb_supervisor_field_get_sf_string(channel);
    unsigned long long next_epoch=0;
    if(new_epoch_marker(native_state,&next_epoch) && next_epoch!=m.attempt) {
      if(next_epoch<=m.attempt||next_epoch!=m.attempt+1)
        return fail("non-monotonic or skipped broker RESET epoch");
      const double *reset_pos=wb_supervisor_node_get_position(craft);
      const double *reset_vel=wb_supervisor_node_get_velocity(craft);
      if(!reset_pos||!reset_vel||
         fabs(reset_pos[0]+1.40)>.025||fabs(reset_pos[1])>.025||
         reset_pos[2]<0.012||reset_pos[2]>0.075||
         !isfinite(reset_vel[0])||!isfinite(reset_vel[1])||
         !isfinite(reset_vel[2])||
         hypot(reset_vel[0],reset_vel[1])>.12||
         fabs(reset_vel[2])>.12)
        return fail("broker RESET ACK without actual grounded origin");
      wb_count_reset(&m,next_epoch,(unsigned)variant,origin_z);
      epoch_start_time=wb_robot_get_time();
      last_x=reset_pos[0];last_y=reset_pos[1];last_z=reset_pos[2];
      previous=0;reported_cross=0;screen_seen=0;observations=0;
      printf("WEBEEBLOCKS_A6_MOTOR_FRESH_EPOCH attempt=%llu variant=%d\n",
             next_epoch,variant);
      fflush(stdout);
    }
    publish_liveness(health,m.attempt,variant,wb_robot_get_time());
    /* Terminal results remain latched but the observer stays alive across
     * RESET. A new attempt is never inferred from drone proximity. */
    if(m.verdict!=WB_COUNT_WAIT)continue;
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
        fabs(pos[2]-last_z)>.100)) {
      /* Native RESET teleports this same craft BEFORE the broker's RESET
       * ACK publishes epoch N+1. Park the old attempt (never award it)
       * until the exact new broker token arrives. Unknown teleports fail. */
      if(fabs(pos[0]+1.40)<=.035&&fabs(pos[1])<=.035&&
         isfinite(pos[2])&&pos[2]>=-.04&&pos[2]<=.10) {
        m.verdict=WB_COUNT_NOT_ACHIEVED;
        printf("WEBEEBLOCKS_A6_MOTOR_RESET_TRANSITION old_attempt=%llu\n",
               m.attempt);
        fflush(stdout);
        continue;
      }
      return fail("unphysical supervisor pose discontinuity");
    }
    last_x=pos[0];last_y=pos[1];last_z=pos[2];previous=1;
    ++observations;
    if(sample.time-epoch_start_time>145.0)
      return fail("bounded native motor flight attempt timeout");
    int physical_collision=-1;
    for(int i=0;i<collider_count;++i) {
      int n=-1;
      const WbContactPoint *points=
        wb_supervisor_node_get_contact_points(obstacle[i],false,&n);
      if(n<0||(n>0&&!points))return fail("missing native collision evidence");
      if(n) { physical_collision=i; break; }
    }
    if(physical_collision>=0) {
      m.verdict=WB_COUNT_NOT_ACHIEVED;
      publish_attempt_verdict(channel,m.attempt,0);
      printf("WEBEEBLOCKS_A6_MOTOR_REJECT attempt=%llu collider=%d "
             "x=%.6f y=%.6f z=%.6f\n",
             m.attempt,physical_collision,sample.x,sample.y,sample.z);
      fflush(stdout);
      continue;
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
      native_state,m.attempt);
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
    if(result==WB_COUNT_NOT_ACHIEVED) {
      publish_attempt_verdict(channel,m.attempt,0);
      printf("WEBEEBLOCKS_A6_MOTOR_REJECT attempt=%llu behavioral_oracle=1\n",
             m.attempt);
      fflush(stdout);
      continue;
    }
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
      publish_attempt_verdict(channel,m.attempt,1);
      /* Do not terminate: RESET must rearm the same live observer. */
      continue;
    }
    if(observations%100==0) {
      printf("WEBEEBLOCKS_A6_MOTOR_TRACE time=%.3f x=%.6f y=%.6f "
             "z=%.6f vx=%.6f crossed=%u\n",
             sample.time,sample.x,sample.y,sample.z,sample.vx,m.crossed);
      fflush(stdout);
    }
  }
  if(m.verdict==WB_COUNT_WAIT)
    return fail("native Webots terminated before flight result");
  wb_robot_cleanup();
  return 0;
}

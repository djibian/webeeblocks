/* Private, native-only A5 R2025a PID safety observer.
 * This translation unit wraps the unmodified product wb_robot_step exactly
 * once. It never commands motors or creates an oracle/Blockly authority.
 *
 * Observe all seven authenticated physical obstacles and the craft on EVERY
 * physics tick, not just during low landing. Native obstacle-side contacts
 * take precedence even when they happen at floor z=0. An independent swept
 * path AABB check rejects thin-obstacle tunnelling between samples.
 */
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <webots/robot.h>
#include <webots/gps.h>
#include <webots/contact_point.h>
#include <webots/supervisor.h>
extern int __real_wb_robot_step(int duration);

static WbDeviceTag gps = 0;
static WbNodeRef craft = 0;
static WbNodeRef obstacles[7] = {0};
static unsigned long count = 0;
static int started = 0, failed = 0, floor_emitted = 0, airborne = 0;
static double last_t = -1, prev[3] = {0,0,0};
static char variant = 0;
static int far_h = 0, gate_left = 0;
static const char *const types[7] = {
  "H_CUE_ARM","H_CUE_TIP","G_LOWER","G_UPPER","G_SIDE_ARM",
  "G_LEFT_BOUNDARY","G_RIGHT_BOUNDARY"
};

static void fatal(const char *reason,double t) {
  if(!failed) {
    fprintf(stderr,"WEBEEBLOCKS_A5_FACTOR_MOTOR_FATAL reason=%s t=%.6f tick=%lu\n",
            reason,t,count);
    fflush(stderr);
  }
  failed=1;
}

static int segment_hits(double a[3],const double b[3],
                        const double center[3],const double half[3]) {
  /* Model a conservative swept craft body, not merely a zero-radius point.
   * The robot's exact swept dynamics are NOT certified by this diagnostic. */
  const double inflate[3]={.105,.105,.060};
  double lower=0.0,upper=1.0;
  for(int k=0;k<3;k++) {
    const double min=center[k]-half[k]-inflate[k];
    const double max=center[k]+half[k]+inflate[k];
    const double delta=b[k]-a[k];
    if(fabs(delta)<1e-12) {
      if(a[k]<min||a[k]>max)return 0;
    } else {
      double enter=(min-a[k])/delta;
      double exit=(max-a[k])/delta;
      if(enter>exit){const double tmp=enter;enter=exit;exit=tmp;}
      if(enter>lower)lower=enter;
      if(exit<upper)upper=exit;
      if(lower>upper)return 0;
    }
  }
  return 1;
}

static int init_monitor(int duration) {
  const WbNodeRef a=wb_supervisor_node_get_from_def("WEBEEBLOCKS_A5_FACTOR_GL_SCENE");
  const WbNodeRef b=wb_supervisor_node_get_from_def("WEBEEBLOCKS_A5_FACTOR_GR_SCENE");
  if((!!a)+(!!b)!=1)return 0;
  WbNodeRef arm=wb_supervisor_node_get_from_def("A5_FACTOR_H_CUE_ARM");
  WbNodeRef tip=wb_supervisor_node_get_from_def("A5_FACTOR_H_CUE_TIP");
  const double *a_pos=arm?wb_supervisor_node_get_position(arm):NULL;
  if(!a_pos||!isfinite(a_pos[1]))return 0;
  const double arm_y=a_pos[1];
  const double *tip_pos=tip?wb_supervisor_node_get_position(tip):NULL;
  if(!tip_pos||!isfinite(tip_pos[1]))return 0;
  const int near=fabs(arm_y-.58)<.000001&&fabs(tip_pos[1]-.78)<.000001;
  far_h=fabs(arm_y-1.18)<.000001&&fabs(tip_pos[1]-1.38)<.000001;
  if(near==far_h)return 0;
  /* Gate geometry comes from the actual native scene, not a letter
   * whose ordinal changes when the H factor is added. */
  gate_left=a!=NULL;
  variant=gate_left?(far_h?'C':'A'):(far_h?'D':'B');
  craft=wb_supervisor_node_get_self();
  gps=wb_robot_get_device("gps");
  if(!craft||!gps||duration!=32)return 0;
  for(int i=0;i<7;i++) {
    char name[64];
    const int n=snprintf(name,sizeof name,"A5_FACTOR_%s",types[i]);
    if(n<=0||(size_t)n>=sizeof name)return 0;
    obstacles[i]=wb_supervisor_node_get_from_def(name);
    if(!obstacles[i]||
       strcmp(wb_supervisor_node_get_type_name(obstacles[i]),"Solid"))
      return 0;
  }
  wb_supervisor_node_enable_contact_points_tracking(craft,32,true);
  for(int i=0;i<7;i++)
    wb_supervisor_node_enable_contact_points_tracking(obstacles[i],32,false);
  /* Webots starts contact tracking at the next native physics step. */
  started=1;
  return 1;
}

int __wrap_wb_robot_step(int duration) {
  const int result=__real_wb_robot_step(duration);
  if(result<0||failed)return result;
  const double t=wb_robot_get_time();
  if(duration!=32||!isfinite(t)||t<0) {
    fatal("native_clock_or_step",t);
    return result;
  }
  if(!started) {
    if(!init_monitor(duration))fatal("missing_craft_or_attested_obstacles",t);
    return result;
  }
  const double *xyz=wb_gps_get_values(gps);
  if(!xyz||!isfinite(xyz[0])||!isfinite(xyz[1])||!isfinite(xyz[2])) {
    fatal("invalid_native_gps",t);
    return result;
  }
  if(last_t>=0&&(t<=last_t||t-last_t>.048)) {
    fatal("native_sample_gap",t);
    return result;
  }
  const double position[3]={xyz[0],xyz[1],xyz[2]};
  ++count;
  /* Independently inspect the OBSTACLE sides before classifying any craft
   * contact as Floor. In particular a low collision must never count as LAND. */
  for(int i=0;i<7;i++) {
    int n=-1;
    const WbContactPoint *hits=
      wb_supervisor_node_get_contact_points(obstacles[i],false,&n);
    if(n<0||(n>0&&!hits)) {
      fatal("obstacle_contact_stream_unavailable",t);
      return result;
    }
    if(n>0) {
      fprintf(stderr,"WEBEEBLOCKS_A5_FACTOR_MOTOR_OBSTACLE_CONTACT "
              "variant=%c collider=%s t=%.6f n=%d\n",
              variant,types[i],t,n);
      fflush(stderr);
      fatal("native_obstacle_contact",t);
      return result;
    }
    const double center[7][3]={
      {0,far_h?1.18:.58,.55},{.20,far_h?1.38:.78,.55},
      {3.10,gate_left?-.55:-1.16,.55},
      {3.10,gate_left?1.16:.55,.55},
      {2.45,gate_left?-.58:.58,.55},
      {3.00,1.45,.55},{3.00,-1.45,.55}
    };
    const double half[7][3]={
      {.20,.04,.55},{.04,.24,.55},
      {.04,gate_left?.85:.24,.55},
      {.04,gate_left?.24:.85,.55},
      {.35,.04,.55},{1.20,.04,.55},{1.20,.04,.55}
    };
    double start[3]={prev[0],prev[1],prev[2]};
    if(last_t>=0&&segment_hits(start,position,center[i],half[i])) {
      fprintf(stderr,"WEBEEBLOCKS_A5_FACTOR_MOTOR_SWEPT_COLLISION "
              "variant=%c collider=%s t=%.6f\n",variant,types[i],t);
      fflush(stderr);
      fatal("swept_physical_box_intersection",t);
      return result;
    }
  }
  int n=-1;
  const WbContactPoint *contacts=
    wb_supervisor_node_get_contact_points(craft,true,&n);
  if(n<0||(n>0&&!contacts)) {
    fatal("craft_contact_stream_unavailable",t);
    return result;
  }
  int floor=0;
  for(int i=0;i<n;i++) {
    const double *point=contacts[i].point;
    if(!isfinite(point[0])||!isfinite(point[1])||
       !isfinite(point[2])) {
      fatal("nonfinite_contact",t);
      return result;
    }
    if(fabs(point[2])>.025) {
      fprintf(stderr,"WEBEEBLOCKS_A5_FACTOR_MOTOR_OBSTACLE_CONTACT "
              "variant=%c collider=UNKNOWN t=%.6f contact_z=%.6f\n",
              variant,t,point[2]);
      fflush(stderr);
      fatal("unknown_nonfloor_contact",t);
      return result;
    }
    floor=1;
  }
  if(position[2]>.18)airborne=1;
  const double target_y=far_h?-.62:.62;
  const int target=fabs(position[0]-4.15)<=.10&&
                   fabs(position[1]-target_y)<=.10;
  if(airborne&&floor&&!target) {
    fatal("premature_floor_contact",t);
    return result;
  }
  last_t=t;
  memcpy(prev,position,sizeof prev);
  if(count%16==0) {
    printf("WEBEEBLOCKS_A5_FACTOR_MOTOR_MONITOR variant=%c "
           "ticks=%lu t=%.6f no_obstacle_contacts=true\n",
           variant,count,t);
    printf("WEBEEBLOCKS_A5_FACTOR_MOTOR_POSE variant=%c t=%.6f "
           "x=%.9f y=%.9f z=%.9f step=%d\n",
           variant,t,position[0],position[1],position[2],duration);
    fflush(stdout);
  }
  if(floor&&!floor_emitted&&airborne&&target&&
     position[2]>=0&&position[2]<=.025) {
    floor_emitted=1;
    printf("WEBEEBLOCKS_A5_FACTOR_MOTOR_NATIVE_FLOOR variant=%c "
           "x=%.9f y=%.9f z=%.9f t=%.6f\n",
           variant,position[0],position[1],position[2],t);
    printf("WEBEEBLOCKS_A5_FACTOR_MOTOR_MONITOR_COMPLETE "
           "variant=%c native_ticks=%lu all_contacts_checked=true "
           "swept_boxes_checked=7\n",variant,count);
    fflush(stdout);
  }
  return result;
}

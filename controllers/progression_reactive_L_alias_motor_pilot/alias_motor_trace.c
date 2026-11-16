/* Private, native-only A5 R2025a PID safety observer.
 * This translation unit wraps the unmodified product wb_robot_step exactly
 * once. It never commands motors or creates an oracle/Blockly authority.
 *
 * Observe all three authenticated physical obstacles and the craft on EVERY
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
static WbNodeRef obstacles[3] = {0};
static unsigned long count = 0;
static int started = 0, failed = 0, floor_emitted = 0, airborne = 0;
static double last_t = -1, prev[3] = {0,0,0};
static char variant = 0;
static const char *const types[3] = {"CUE_ARM","CUE_TIP","TERMINAL"};

static void fatal(const char *reason,double t) {
  if(!failed) {
    fprintf(stderr,"WEBEEBLOCKS_A5_ALIAS_MOTOR_FATAL reason=%s t=%.6f tick=%lu\n",
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
  const WbNodeRef a=wb_supervisor_node_get_from_def("WEBEEBLOCKS_A5_ALIAS_A_SCENE");
  const WbNodeRef b=wb_supervisor_node_get_from_def("WEBEEBLOCKS_A5_ALIAS_B_SCENE");
  if((!!a)+(!!b)!=1)return 0;
  variant=a?'A':'B';
  craft=wb_supervisor_node_get_self();
  gps=wb_robot_get_device("gps");
  if(!craft||!gps||duration!=32)return 0;
  const char *c=variant=='A'?"A":"B";
  for(int i=0;i<3;i++) {
    char name[64];
    const int n=snprintf(name,sizeof name,"A5_ALIAS_%s_%s",c,types[i]);
    if(n<=0||(size_t)n>=sizeof name)return 0;
    obstacles[i]=wb_supervisor_node_get_from_def(name);
    if(!obstacles[i]||
       strcmp(wb_supervisor_node_get_type_name(obstacles[i]),"Solid"))
      return 0;
  }
  wb_supervisor_node_enable_contact_points_tracking(craft,32,true);
  for(int i=0;i<3;i++)
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
  for(int i=0;i<3;i++) {
    int n=-1;
    const WbContactPoint *hits=
      wb_supervisor_node_get_contact_points(obstacles[i],false,&n);
    if(n<0||(n>0&&!hits)) {
      fatal("obstacle_contact_stream_unavailable",t);
      return result;
    }
    if(n>0) {
      fprintf(stderr,"WEBEEBLOCKS_A5_ALIAS_MOTOR_OBSTACLE_CONTACT "
              "variant=%c collider=%s t=%.6f n=%d\n",
              variant,types[i],t,n);
      fflush(stderr);
      fatal("native_obstacle_contact",t);
      return result;
    }
    const double cx=i==0?0:i==1?.20:2.10;
    const double cy=i==0?(variant=='A'?.58:1.18):
                    i==1?(variant=='A'?.78:1.38):0;
    const double center[3]={cx,cy,.55};
    const double half[3]={i==0?.20:.04,
      i==0?.04:i==1?.24:.41,.55};
    double start[3]={prev[0],prev[1],prev[2]};
    if(last_t>=0&&segment_hits(start,position,center,half)) {
      fprintf(stderr,"WEBEEBLOCKS_A5_ALIAS_MOTOR_SWEPT_COLLISION "
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
      fprintf(stderr,"WEBEEBLOCKS_A5_ALIAS_MOTOR_OBSTACLE_CONTACT "
              "variant=%c collider=UNKNOWN t=%.6f contact_z=%.6f\n",
              variant,t,point[2]);
      fflush(stderr);
      fatal("unknown_nonfloor_contact",t);
      return result;
    }
    floor=1;
  }
  if(position[2]>.18)airborne=1;
  const double target_y=variant=='A'?.62:-.62;
  const int target=fabs(position[0]-1.50)<=.075&&
                   fabs(position[1]-target_y)<=.075;
  if(airborne&&floor&&!target) {
    fatal("premature_floor_contact",t);
    return result;
  }
  last_t=t;
  memcpy(prev,position,sizeof prev);
  if(count%16==0) {
    printf("WEBEEBLOCKS_A5_ALIAS_MOTOR_MONITOR variant=%c "
           "ticks=%lu t=%.6f no_obstacle_contacts=true\n",
           variant,count,t);
    printf("WEBEEBLOCKS_A5_ALIAS_MOTOR_POSE variant=%c t=%.6f "
           "x=%.9f y=%.9f z=%.9f step=%d\n",
           variant,t,position[0],position[1],position[2],duration);
    fflush(stdout);
  }
  if(floor&&!floor_emitted&&airborne&&target&&
     position[2]>=0&&position[2]<=.025) {
    floor_emitted=1;
    printf("WEBEEBLOCKS_A5_ALIAS_MOTOR_NATIVE_FLOOR variant=%c "
           "x=%.9f y=%.9f z=%.9f t=%.6f\n",
           variant,position[0],position[1],position[2],t);
    printf("WEBEEBLOCKS_A5_ALIAS_MOTOR_MONITOR_COMPLETE "
           "variant=%c native_ticks=%lu all_contacts_checked=true "
           "swept_boxes_checked=3\n",variant,count);
    fflush(stdout);
  }
  return result;
}

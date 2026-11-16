/* Draft-only observational wrapper. The original runtime/PID motors execute
 * unchanged; each native wb_robot_step is called exactly once.
 * True physical Floor contacts and off-floor collisions are observed via
 * the Webots Supervisor API, never inferred from Blockly or height alone.
 */
#include <math.h>
#include <stdio.h>
#include <webots/robot.h>
#include <webots/gps.h>
#include <webots/contact_point.h>
#include <webots/supervisor.h>
extern int __real_wb_robot_step(int duration);
int __wrap_wb_robot_step(int duration) {
  const int result=__real_wb_robot_step(duration);
  if(result<0)return result;
  static WbDeviceTag gps=0;
  static WbNodeRef craft=0;
  static unsigned tick=0;
  static int floor_emitted=0;
  if(!gps)gps=wb_robot_get_device("gps");
  if(!craft) {
    craft=wb_supervisor_node_get_self();
    if(craft)wb_supervisor_node_enable_contact_points_tracking(craft,32,true);
  }
  if(!gps||!craft)return result;
  const double *p=wb_gps_get_values(gps);
  const double t=wb_robot_get_time();
  if(!p||!isfinite(t)||!isfinite(p[0])||!isfinite(p[1])||
     !isfinite(p[2]))return result;
  const int variant=wb_supervisor_node_get_from_def(
    "WEBEEBLOCKS_A5_ALIAS_A_SCENE")?1:
    wb_supervisor_node_get_from_def("WEBEEBLOCKS_A5_ALIAS_B_SCENE")?2:0;
  if(!variant)return result;
  if(++tick%16==0) {
    printf("WEBEEBLOCKS_A5_ALIAS_MOTOR_POSE variant=%c t=%.6f "
           "x=%.9f y=%.9f z=%.9f step=%d\n",
           variant==1?'A':'B',t,p[0],p[1],p[2],duration);
    fflush(stdout);
  }
  if(p[2]>=.08||floor_emitted||t<1.0)return result;
  int n=-1;
  const WbContactPoint *contacts=
    wb_supervisor_node_get_contact_points(craft,true,&n);
  if(n<0||(n>0&&!contacts)){
    printf("WEBEEBLOCKS_A5_ALIAS_MOTOR_CONTACT_UNAVAILABLE count=%d\n",n);
    fflush(stdout);return result;
  }
  int floor=0,non_floor=0;
  for(int i=0;i<n;i++){
    const double *point=contacts[i].point;
    if(!isfinite(point[0])||!isfinite(point[1])||
       !isfinite(point[2])) {non_floor=1;break;}
    if(fabs(point[2])<=.025)floor=1;
    else non_floor=1;
  }
  if(non_floor) {
    printf("WEBEEBLOCKS_A5_ALIAS_MOTOR_OBSTACLE_CONTACT t=%.6f "
           "x=%.6f y=%.6f z=%.6f\n",t,p[0],p[1],p[2]);
    fflush(stdout);return result;
  }
  if(floor&&fabs(p[0]-1.50)<=.075&&
     fabs(p[1]-(variant==1?.62:-.62))<=.075&&p[2]<=.025){
    printf("WEBEEBLOCKS_A5_ALIAS_MOTOR_NATIVE_FLOOR variant=%c "
           "x=%.9f y=%.9f z=%.9f t=%.6f\n",
           variant==1?'A':'B',p[0],p[1],p[2],t);
    fflush(stdout);floor_emitted=1;
  }
  return result;
}

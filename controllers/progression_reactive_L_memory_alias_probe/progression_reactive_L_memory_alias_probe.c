/* A5 information-aliasing experiment on genuine Webots R2025a sensors.
 * This controller uses Supervisor TELEPORT to isolate perception. It does NOT
 * fly the motors, validate a pupil project, or provide an activity oracle.
 * Both physical worlds must share their late decision geometry; the only
 * source-distinguishing physical cue is an early L-shaped obstacle.
 */
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <webots/distance_sensor.h>
#define PI 3.14159265358979323846
static int refuse(const char *why) {
  fprintf(stderr,"WEBEEBLOCKS_A5_ALIAS_FATAL %s\n",why);
  fflush(stderr); wb_robot_cleanup(); return 2;
}
static int box(const char *name,const double pos[3],const double size[3]) {
  WbNodeRef node=wb_supervisor_node_get_from_def(name);
  if(!node || strcmp(wb_supervisor_node_get_type_name(node),"Solid"))return 0;
  const double *p=wb_supervisor_node_get_position(node);
  WbFieldRef b=wb_supervisor_node_get_field(node,"boundingObject");
  WbNodeRef shape=b?wb_supervisor_field_get_sf_node(b):NULL;
  if(!p||!shape||strcmp(wb_supervisor_node_get_type_name(shape),"Box"))return 0;
  WbFieldRef dim=wb_supervisor_node_get_field(shape,"size");
  const double *d=dim?wb_supervisor_field_get_sf_vec3f(dim):NULL;
  if(!d)return 0;
  for(int i=0;i<3;i++)
    if(!isfinite(p[i])||!isfinite(d[i])||
       fabs(p[i]-pos[i])>1e-6||fabs(d[i]-size[i])>1e-6)return 0;
  return 1;
}
static int sample(WbNodeRef self,WbFieldRef translation,WbFieldRef rotation,
                  WbDeviceTag front,WbDeviceTag left,WbDeviceTag right,
                  char variant,int late,int index,double yaw,int step) {
  const double pos[3]={late?1.50:0.0,0.0,0.50};
  const double orientation[4]={0,0,1,yaw};
  wb_supervisor_field_set_sf_vec3f(translation,pos);
  wb_supervisor_field_set_sf_rotation(rotation,orientation);
  wb_supervisor_node_reset_physics(self);
  for(int t=0;t<2;t++)if(wb_robot_step(step)==-1)return 0;
  const double *seen=wb_supervisor_node_get_position(self);
  const double *matrix=wb_supervisor_node_get_orientation(self);
  if(!seen||!matrix||fabs(seen[0]-pos[0])>.035||
     fabs(seen[1]-pos[1])>.035||fabs(seen[2]-pos[2])>.09||
     fabs(matrix[0]-cos(yaw))>.10||fabs(matrix[3]-sin(yaw))>.10)return 0;
  const double f=wb_distance_sensor_get_value(front)/1000.0;
  const double l=wb_distance_sensor_get_value(left)/1000.0;
  const double r=wb_distance_sensor_get_value(right)/1000.0;
  if(!isfinite(f)||!isfinite(l)||!isfinite(r)||
     f<0||l<0||r<0||f>2.001||l>2.001||r>2.001)return 0;
  printf("WEBEEBLOCKS_A5_ALIAS_SAMPLE variant=%c phase=%s turn=%d "
         "front=%.9f left=%.9f right=%.9f "
         "x=%.9f y=%.9f z=%.9f time=%.9f\n",
         variant,late?"late":"early",index,f,l,r,
         seen[0],seen[1],seen[2],wb_robot_get_time());
  fflush(stdout);
  return 1;
}
int main(void) {
  wb_robot_init();
  const int step=(int)wb_robot_get_basic_time_step();
  if(step!=32||strcmp(wb_robot_get_name(),"Crazyflie WebeeBlocks"))
    return refuse("unattested native craft identity or physics cadence");
  const int a=wb_supervisor_node_get_from_def("WEBEEBLOCKS_A5_ALIAS_A_SCENE")!=NULL;
  const int b=wb_supervisor_node_get_from_def("WEBEEBLOCKS_A5_ALIAS_B_SCENE")!=NULL;
  if(a==b)return refuse("exactly one A5 alias scene required");
  const char variant=a?'A':'B';
  WbNodeRef group=wb_supervisor_node_get_from_def(
    a?"WEBEEBLOCKS_A5_ALIAS_A_SCENE":"WEBEEBLOCKS_A5_ALIAS_B_SCENE");
  WbFieldRef children=group?wb_supervisor_node_get_field(group,"children"):NULL;
  if(!children||wb_supervisor_field_get_count(children)!=7)
    return refuse("unattested scene group inventory");
  const double y=a?.58:1.18;
  const double cue1[3]={0,y,.55},cue2[3]={.20,y+.20,.55};
  const double terminal[3]={2.10,0,.55};
  const double s1[3]={.40,.08,1.10},s2[3]={.08,.48,1.10};
  const double sw[3]={.08,.82,1.10};
  char id[72];
  snprintf(id,sizeof id,"A5_ALIAS_%c_CUE_ARM",variant);
  if(!box(id,cue1,s1))return refuse("early cue arm has altered physical box");
  snprintf(id,sizeof id,"A5_ALIAS_%c_CUE_TIP",variant);
  if(!box(id,cue2,s2))return refuse("early cue perpendicular arm altered");
  snprintf(id,sizeof id,"A5_ALIAS_%c_TERMINAL",variant);
  if(!box(id,terminal,sw))return refuse("common late terminal wall altered");
  WbNodeRef self=wb_supervisor_node_get_self();
  WbFieldRef tr=self?wb_supervisor_node_get_field(self,"translation"):NULL;
  WbFieldRef rot=self?wb_supervisor_node_get_field(self,"rotation"):NULL;
  WbDeviceTag front=wb_robot_get_device("range_front");
  WbDeviceTag left=wb_robot_get_device("range_left");
  WbDeviceTag right=wb_robot_get_device("range_right");
  if(!self||!tr||!rot||!front||!left||!right)
    return refuse("required original native Multi-ranger or Supervisor missing");
  wb_distance_sensor_enable(front,step);
  wb_distance_sensor_enable(left,step);
  wb_distance_sensor_enable(right,step);
  if(wb_robot_step(step)==-1)return refuse("native sensor activation failed");
  if(!sample(self,tr,rot,front,left,right,variant,0,0,0,step))
    return refuse("early physical clue unavailable");
  for(int i=0;i<4;i++)
    if(!sample(self,tr,rot,front,left,right,variant,1,i,i*PI/2,step))
      return refuse("late 90-degree scan unavailable");
  printf("WEBEEBLOCKS_A5_ALIAS_DONE variant=%c early=true late_scans=4 "
         "teleport_only=true motorized_flight=false\n",variant);
  fflush(stdout);
  wb_robot_cleanup();
  return 0;
}

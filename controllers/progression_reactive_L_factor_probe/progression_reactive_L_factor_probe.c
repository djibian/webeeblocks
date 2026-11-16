/* A5 experimental fixed-H / variable-G physical-sensor probe, R2025a only.
 * Supervisor poses are isolated readings, never pupil or motorized missions.
 * The original Crazyflie and its unmodified Multi-ranger supply every ray. */
#include <webots/robot.h>
#include <webots/distance_sensor.h>
#include <webots/supervisor.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#define EPS 0.0001
static int refuse(const char *why) {
  fprintf(stderr,"WEBEEBLOCKS_A5_FACTOR_FATAL %s\n",why);fflush(stderr);
  wb_robot_cleanup();return 4;
}
static int box(const char *id,const double center[3],const double size[3]) {
  WbNodeRef node=wb_supervisor_node_get_from_def(id);
  if(!node)return 0;
  const double *p=wb_supervisor_node_get_position(node);
  WbFieldRef field=wb_supervisor_node_get_field(node,"boundingObject");
  WbNodeRef shape=field?wb_supervisor_field_get_sf_node(field):NULL;
  WbFieldRef sizeField=shape?wb_supervisor_node_get_field(shape,"size"):NULL;
  const double *s=sizeField?wb_supervisor_field_get_sf_vec3f(sizeField):NULL;
  if(!p||!s)return 0;
  for(int i=0;i<3;i++)
    if(fabs(p[i]-center[i])>EPS||fabs(s[i]-size[i])>EPS)return 0;
  return 1;
}
static int sample(WbNodeRef self,WbFieldRef tr,WbFieldRef rot,
                  WbDeviceTag front,WbDeviceTag left,WbDeviceTag right,
                  char variant,const char *phase,double x,double y,int step) {
  const double desired[3]={x,y,.50},yaw[4]={0,0,1,0};
  wb_supervisor_field_set_sf_vec3f(tr,desired);
  wb_supervisor_field_set_sf_rotation(rot,yaw);
  wb_supervisor_node_reset_physics(self);
  for(int n=0;n<2;n++)if(wb_robot_step(step)==-1)return 0;
  const double *p=wb_supervisor_node_get_position(self);
  const double *orientation=wb_supervisor_node_get_orientation(self);
  const double f=wb_distance_sensor_get_value(front)/1000.0;
  const double l=wb_distance_sensor_get_value(left)/1000.0;
  const double r=wb_distance_sensor_get_value(right)/1000.0;
  if(!p||!orientation||fabs(p[0]-x)>.035||fabs(p[1]-y)>.035||
     fabs(p[2]-.5)>.09||fabs(orientation[0]-1)>.10||
     !isfinite(f)||!isfinite(l)||!isfinite(r)||
     f<0||l<0||r<0||f>2.001||l>2.001||r>2.001)return 0;
  printf("WEBEEBLOCKS_A5_FACTOR_SAMPLE variant=%c phase=%s "
         "front=%.9f left=%.9f right=%.9f "
         "x=%.9f y=%.9f z=%.9f time=%.9f\n",
         variant,phase,f,l,r,p[0],p[1],p[2],wb_robot_get_time());
  fflush(stdout);return 1;
}
int main(void) {
  wb_robot_init();
  const int step=(int)wb_robot_get_basic_time_step();
  if(step!=32||strcmp(wb_robot_get_name(),"Crazyflie WebeeBlocks"))
    return refuse("untrusted original Crazyflie or time step");
  const int L=wb_supervisor_node_get_from_def("WEBEEBLOCKS_A5_FACTOR_GL_SCENE")!=NULL;
  const int R=wb_supervisor_node_get_from_def("WEBEEBLOCKS_A5_FACTOR_GR_SCENE")!=NULL;
  if(L==R)return refuse("exactly one G scene must be present");
  char variant=L?'L':'R';
  WbNodeRef group=wb_supervisor_node_get_from_def(
    L?"WEBEEBLOCKS_A5_FACTOR_GL_SCENE":"WEBEEBLOCKS_A5_FACTOR_GR_SCENE");
  WbFieldRef children=group?wb_supervisor_node_get_field(group,"children"):NULL;
  if(!children||wb_supervisor_field_get_count(children)!=11)
    return refuse("source group or child count altered");
  const double h1[3]={0,.58,.55},h2[3]={.20,.78,.55};
  const double lower[3]={3.10,L?-.55:-1.16,.55};
  const double upper[3]={3.10,L?1.16:.55,.55};
  const double arm[3]={2.45,L?-.58:.58,.55};
  const double wallLeft[3]={3,1.45,.55},wallRight[3]={3,-1.45,.55};
  const double sh1[3]={.40,.08,1.10},sh2[3]={.08,.48,1.10};
  const double sl[3]={.08,L?1.70:.48,1.10},su[3]={.08,L?.48:1.70,1.10};
  const double sa[3]={.70,.08,1.10},sw[3]={2.40,.08,1.10};
  if(!box("A5_FACTOR_H_CUE_ARM",h1,sh1)||
     !box("A5_FACTOR_H_CUE_TIP",h2,sh2)||
     !box("A5_FACTOR_G_LOWER",lower,sl)||
     !box("A5_FACTOR_G_UPPER",upper,su)||
     !box("A5_FACTOR_G_SIDE_ARM",arm,sa)||
     !box("A5_FACTOR_G_LEFT_BOUNDARY",wallLeft,sw)||
     !box("A5_FACTOR_G_RIGHT_BOUNDARY",wallRight,sw))
    return refuse("physical Solid center or boundingObject changed");
  WbNodeRef self=wb_supervisor_node_get_self();
  WbFieldRef tr=self?wb_supervisor_node_get_field(self,"translation"):NULL;
  WbFieldRef rot=self?wb_supervisor_node_get_field(self,"rotation"):NULL;
  WbDeviceTag front=wb_robot_get_device("range_front");
  WbDeviceTag left=wb_robot_get_device("range_left");
  WbDeviceTag right=wb_robot_get_device("range_right");
  if(!self||!tr||!rot||!front||!left||!right)
    return refuse("original native Multi-ranger unavailable");
  wb_distance_sensor_enable(front,step);
  wb_distance_sensor_enable(left,step);
  wb_distance_sensor_enable(right,step);
  if(wb_robot_step(step)==-1)return refuse("sensor activation failed");
  if(!sample(self,tr,rot,front,left,right,variant,"early",0,0,step)||
     !sample(self,tr,rot,front,left,right,variant,"approach",2.50,0,step)||
     !sample(self,tr,rot,front,left,right,variant,"gap_left",2.50,.80,step)||
     !sample(self,tr,rot,front,left,right,variant,"gap_right",2.50,-.80,step))
    return refuse("missing native sample or pose");
  printf("WEBEEBLOCKS_A5_FACTOR_DONE variant=%c samples=4 "
         "teleport_only=true motorized=false\n",variant);fflush(stdout);
  wb_robot_cleanup();return 0;
}

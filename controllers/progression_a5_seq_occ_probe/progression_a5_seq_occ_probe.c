/* A5 PRIVATE: real Webots R2025a five Multi-ranger sensors, two Ls.
 * Supervisor-only pose study, no motors, student algorithm or mission oracle.
 * Four worlds cross independently mirrored first and second L openings.
 * Two bits of information are sampled at different places by real sensors.
 * Native-attested lateral walls and terminal are shared laboratory fixtures.
 */
#include <webots/robot.h>
#include <webots/distance_sensor.h>
#include <webots/supervisor.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static int invalid(const char *reason) {
  fprintf(stderr,"A5_SEQ_OCC_FATAL reason=%s\n",reason);
  fflush(stderr); wb_robot_cleanup(); return 3;
}
static int eq(double a,double b) {
  return isfinite(a)&&fabs(a-b)<.0001;
}
static int box(const char *name,double x,double y,double z,
               double sx,double sy,double sz) {
  WbNodeRef node=wb_supervisor_node_get_from_def(name);
  if(!node||strcmp(wb_supervisor_node_get_type_name(node),"Solid"))return 0;
  const double *p=wb_supervisor_node_get_position(node);
  const double *rot=wb_supervisor_node_get_orientation(node);
  WbFieldRef bounding=wb_supervisor_node_get_field(node,"boundingObject");
  WbNodeRef shape=bounding?wb_supervisor_field_get_sf_node(bounding):NULL;
  WbFieldRef size=shape?wb_supervisor_node_get_field(shape,"size"):NULL;
  const double *s=size?wb_supervisor_field_get_sf_vec3f(size):NULL;
  if(!p||!rot||!shape||!s||
     strcmp(wb_supervisor_node_get_type_name(shape),"Box")||
     !eq(p[0],x)||!eq(p[1],y)||!eq(p[2],z)||
     !eq(s[0],sx)||!eq(s[1],sy)||!eq(s[2],sz))return 0;
  for(int i=0;i<3;i++)for(int j=0;j<3;j++)
    if(!eq(rot[3*i+j],i==j?1.:0.))return 0;
  return 1;
}
static int sample(WbNodeRef self,WbFieldRef tr,WbFieldRef rot,
                  const WbDeviceTag device[5],char v,const char *phase,
                  double x,double y,int step) {
  const double desired[3]={x,y,.50},heading[4]={0.,0.,1.,0.};
  wb_supervisor_field_set_sf_vec3f(tr,desired);
  wb_supervisor_field_set_sf_rotation(rot,heading);
  wb_supervisor_node_reset_physics(self);
  for(int i=0;i<2;i++)if(wb_robot_step(step)<0)return 0;
  const double *p=wb_supervisor_node_get_position(self);
  const double *o=wb_supervisor_node_get_orientation(self);
  int contacts=-1;
  const WbContactPoint *points=wb_supervisor_node_get_contact_points(
      self,true,&contacts);
  if(contacts!=0||(contacts>0&&points==NULL)||!p||!o||
     fabs(p[0]-x)>.035||fabs(p[1]-y)>.035||
     fabs(p[2]-.5)>.09||fabs(o[0]-1)>.1||fabs(o[3])>.1)return 0;
  double a[5];
  for(int i=0;i<5;i++) {
    a[i]=wb_distance_sensor_get_value(device[i])/1000.;
    if(!isfinite(a[i])||a[i]<0||a[i]>2.001)return 0;
  }
  printf("A5_SEQ_OCC_RAYS variant=%c phase=%s front=%.9f back=%.9f "
         "left=%.9f right=%.9f up=%.9f x=%.9f y=%.9f z=%.9f\n",
         v,phase,a[0],a[1],a[2],a[3],a[4],p[0],p[1],p[2]);
  fflush(stdout);return 1;
}
int main(void) {
  wb_robot_init();
  const int step=(int)wb_robot_get_basic_time_step();
  if(step!=32||strcmp(wb_robot_get_name(),"Crazyflie WebeeBlocks"))
    return invalid("original_crazyflie_or_clock_missing");
  WbNodeRef world=wb_supervisor_node_get_from_def("WEBEEBLOCKS_CLASSROOM_START_WORLD");
  WbNodeRef A=wb_supervisor_node_get_from_def("WEBEEBLOCKS_A5_SEQ_OCC_A_SCENE");
  WbNodeRef B=wb_supervisor_node_get_from_def("WEBEEBLOCKS_A5_SEQ_OCC_B_SCENE");
  WbNodeRef C=wb_supervisor_node_get_from_def("WEBEEBLOCKS_A5_SEQ_OCC_C_SCENE");
  WbNodeRef D=wb_supervisor_node_get_from_def("WEBEEBLOCKS_A5_SEQ_OCC_D_SCENE");
  if(!world||strcmp(wb_supervisor_node_get_type_name(world),"WorldInfo")||
     (!!A)+(!!B)+(!!C)+(!!D)!=1)return invalid("missing_or_ambiguous_world");
  const char v=A?'A':B?'B':C?'C':'D';
  WbNodeRef group=A?A:B?B:C?C:D;
  WbFieldRef children=wb_supervisor_node_get_field(group,"children");
  if(strcmp(wb_supervisor_node_get_type_name(group),"Group")||!children||
     wb_supervisor_field_get_count(children)!=9)
    return invalid("untrusted_group");
  const int first_positive=(v=='A'||v=='B');
  const int second_positive=(v=='A'||v=='C');
  const double first_y=first_positive?-.30:.30;
  const double first_arm_y=first_positive?.275:-.275;
  const double sample_side=first_positive?.45:-.45;
  const double sample_late=first_positive?.60:-.60;
  const double second_y=second_positive?.45:-.45;
  const double arm_y=second_positive?1.125:-1.125;
  if(!box("A5_SEQ_L1_POST",1.,first_y,.55,.08,1.15,1.1)||
     !box("A5_SEQ_L1_ARM",.65,first_arm_y,.55,.70,.08,1.1)||
     !box("A5_SEQ_L2_POST",3.2,second_y,.55,.08,1.20,1.1)||
     !box("A5_SEQ_L2_ARM",2.85,arm_y,.55,.70,.23,1.1)||
     !box("A5_SEQ_CORRIDOR_POS",1.8,1.26,.55,4.3,.08,1.1)||
     !box("A5_SEQ_CORRIDOR_NEG",1.8,-1.26,.55,4.3,.08,1.1)||
     !box("A5_SEQ_CORRIDOR_BACK",-.35,0,.55,.08,2.6,1.1)||
     !box("A5_SEQ_CORRIDOR_ROOF",1.79,0,1.14,4.4,2.6,.12)||
     !box("A5_SEQ_TERMINAL",3.92,0,.55,.08,2.3,1.1))
    return invalid("physical_colliders_or_dimensions_modified");
  WbNodeRef self=wb_supervisor_node_get_self();
  WbFieldRef trans=self?wb_supervisor_node_get_field(self,"translation"):NULL;
  WbFieldRef rot=self?wb_supervisor_node_get_field(self,"rotation"):NULL;
  const char *const names[5]={
    "range_front","range_back","range_left","range_right","range_up"};
  WbDeviceTag devices[5];
  for(int i=0;i<5;i++){
    devices[i]=wb_robot_get_device(names[i]);
    if(!devices[i])return invalid("genuine_multiranger_missing");
    wb_distance_sensor_enable(devices[i],step);
  }
  if(!self||!trans||!rot||wb_robot_step(step)<0)
    return invalid("native_startup_or_pose_missing");
  wb_supervisor_node_enable_contact_points_tracking(self,step,true);
  if(!sample(self,trans,rot,devices,v,"before_far",.40,0,step)||
     !sample(self,trans,rot,devices,v,"before_near",.70,0,step)||
     !sample(self,trans,rot,devices,v,"before_peek",.60,sample_side,step)||
     !sample(self,trans,rot,devices,v,"before_corner",.98,sample_side,step)||
     !sample(self,trans,rot,devices,v,"after_far",2.00,sample_late,step)||
     !sample(self,trans,rot,devices,v,"after_near",2.30,sample_late,step))
    return invalid("native_sensor_or_pose_sample_missing");
  printf("A5_SEQ_OCC_DONE variant=%c samples=6 native_multiranger=true "
         "supervisor_only=true motorized=false pupil_pass=false\n",v);
  fflush(stdout);wb_robot_cleanup();return 0;
}

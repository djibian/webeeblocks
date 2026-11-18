/* PRIVATE A5 LENGTH x OPENING SENSOR TEST, Webots R2025a.
 * Genuine original Crazyflie Multi-ranger and Supervisor poses, NO motors,
 * NO mission oracle, NO student solution. Each collision box is attested.
 */
#include <webots/robot.h>
#include <webots/distance_sensor.h>
#include <webots/supervisor.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#define E 0.0001
static int fail(const char *why) {
  fprintf(stderr,"WEBEEBLOCKS_A5_LENGTH_FATAL reason=%s\n",why);
  fflush(stderr);wb_robot_cleanup();return 5;
}
static int eq(double a,double b) {
  return isfinite(a)&&fabs(a-b)<E;
}
static int box(const char *name,double x,double y,double z,
               double w,double d,double h) {
  WbNodeRef n=wb_supervisor_node_get_from_def(name);
  if(!n||strcmp(wb_supervisor_node_get_type_name(n),"Solid"))return 0;
  const double *p=wb_supervisor_node_get_position(n);
  const double *o=wb_supervisor_node_get_orientation(n);
  WbFieldRef f=wb_supervisor_node_get_field(n,"boundingObject");
  WbNodeRef g=f?wb_supervisor_field_get_sf_node(f):NULL;
  WbFieldRef sz=g?wb_supervisor_node_get_field(g,"size"):NULL;
  const double *s=sz?wb_supervisor_field_get_sf_vec3f(sz):NULL;
  if(!p||!o||!s||!g||strcmp(wb_supervisor_node_get_type_name(g),"Box")||
     !eq(p[0],x)||!eq(p[1],y)||!eq(p[2],z)||
     !eq(s[0],w)||!eq(s[1],d)||!eq(s[2],h))return 0;
  for(int i=0;i<3;i++)for(int j=0;j<3;j++)
    if(!eq(o[i*3+j],i==j?1.0:0.0))return 0;
  return 1;
}
static int pose(WbFieldRef children,int index,double x,double y,
                double z) {
  WbNodeRef n=wb_supervisor_field_get_mf_node(children,index);
  if(!n||strcmp(wb_supervisor_node_get_type_name(n),"Pose"))return 0;
  WbFieldRef t=wb_supervisor_node_get_field(n,"translation");
  const double *p=t?wb_supervisor_field_get_sf_vec3f(t):NULL;
  return p&&eq(p[0],x)&&eq(p[1],y)&&eq(p[2],z);
}
static int sample(WbNodeRef self,WbFieldRef translation,WbFieldRef rotation,
                  WbDeviceTag front,WbDeviceTag left,WbDeviceTag right,
                  char len,char side,const char *label,
                  double x,double y,int step) {
  const double target[3]={x,y,.50},rot[4]={0.,0.,1.,0.};
  wb_supervisor_field_set_sf_vec3f(translation,target);
  wb_supervisor_field_set_sf_rotation(rotation,rot);
  wb_supervisor_node_reset_physics(self);
  for(int i=0;i<2;i++)if(wb_robot_step(step)==-1)return 0;
  const double *p=wb_supervisor_node_get_position(self);
  const double *matrix=wb_supervisor_node_get_orientation(self);
  const double f=wb_distance_sensor_get_value(front)/1000.0;
  const double l=wb_distance_sensor_get_value(left)/1000.0;
  const double r=wb_distance_sensor_get_value(right)/1000.0;
  if(!p||!matrix||fabs(p[0]-x)>.035||fabs(p[1]-y)>.035||
     fabs(p[2]-.5)>.09||fabs(matrix[0]-1)>.10||
     !isfinite(f)||!isfinite(l)||!isfinite(r)||
     f<0||l<0||r<0||f>2.001||l>2.001||r>2.001)return 0;
  printf("WEBEEBLOCKS_A5_LENGTH_SAMPLE length=%c side=%c phase=%s "
         "front=%.9f left=%.9f right=%.9f "
         "x=%.9f y=%.9f z=%.9f time=%.9f\n",
         len,side,label,f,l,r,p[0],p[1],p[2],wb_robot_get_time());
  fflush(stdout);return 1;
}
int main(void) {
  wb_robot_init();
  int step=(int)wb_robot_get_basic_time_step();
  if(step!=32||strcmp(wb_robot_get_name(),"Crazyflie WebeeBlocks"))
    return fail("untrusted_robot_or_step");
  WbNodeRef world=wb_supervisor_node_get_from_def("WEBEEBLOCKS_CLASSROOM_START_WORLD");
  if(!world||strcmp(wb_supervisor_node_get_type_name(world),"WorldInfo"))
    return fail("missing_original_classroom_world");
  const char *const names[]={
    "WEBEEBLOCKS_A5_LENGTH_SHORT_GL_SCENE",
    "WEBEEBLOCKS_A5_LENGTH_SHORT_GR_SCENE",
    "WEBEEBLOCKS_A5_LENGTH_LONG_GL_SCENE",
    "WEBEEBLOCKS_A5_LENGTH_LONG_GR_SCENE"};
  int selected=-1,count=0;
  for(int i=0;i<4;i++)if(wb_supervisor_node_get_from_def(names[i])){
    selected=i;count++;
  }
  if(count!=1 || wb_supervisor_node_get_from_def("WEBEEBLOCKS_A5_FACTOR_GL_SCENE") ||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_A5_FACTOR_GR_SCENE") ||
     wb_supervisor_node_get_from_def("WEBEEBLOCKS_LEGACY_SCENE"))
    return fail("ambiguous_or_wrong_scene");
  const int shortL=selected<2, left=(selected%2)==0;
  const char len=shortL?'S':'L', side=left?'L':'R';
  const double gate=shortL?2.9:3.3;
  const double armX=shortL?1.975:2.175;
  const double armWidth=shortL?1.25:1.65;
  const double boundary=shortL?2.8:3.2;
  const double pad=shortL?3.95:4.35;
  const double mark=shortL?2.3:2.7;
  WbNodeRef group=wb_supervisor_node_get_from_def(names[selected]);
  WbFieldRef children=group?wb_supervisor_node_get_field(group,"children"):NULL;
  if(!group||strcmp(wb_supervisor_node_get_type_name(group),"Group")||
     !children||wb_supervisor_field_get_count(children)!=11||
     !pose(children,0,0,0,.002)||
     !pose(children,1,mark,0,.002)||
     !pose(children,2,pad,.62,.002)||
     !pose(children,3,pad,-.62,.002))
    return fail("untrusted_scene_markers_or_children");
  if(!box("A5_FACTOR_H_CUE_ARM",0,.58,.55,.40,.08,1.10)||
     !box("A5_FACTOR_H_CUE_TIP",.2,.78,.55,.08,.48,1.10)||
     !box("A5_FACTOR_G_LOWER",gate,left?-.55:-1.16,.55,
          .08,left?1.70:.48,1.10)||
     !box("A5_FACTOR_G_UPPER",gate,left?1.16:.55,.55,
          .08,left?.48:1.70,1.10)||
     !box("A5_FACTOR_G_SIDE_ARM",armX,left?-.58:.58,.55,
          armWidth,.08,1.10)||
     !box("A5_FACTOR_G_LEFT_BOUNDARY",boundary,1.45,.55,2.4,.08,1.10)||
     !box("A5_FACTOR_G_RIGHT_BOUNDARY",boundary,-1.45,.55,2.4,.08,1.10))
    return fail("untrusted_physical_L_boxes");
  WbNodeRef self=wb_supervisor_node_get_self();
  WbFieldRef translation=self?wb_supervisor_node_get_field(self,"translation"):NULL;
  WbFieldRef rotation=self?wb_supervisor_node_get_field(self,"rotation"):NULL;
  WbDeviceTag front=wb_robot_get_device("range_front");
  WbDeviceTag leftSensor=wb_robot_get_device("range_left");
  WbDeviceTag rightSensor=wb_robot_get_device("range_right");
  if(!self||!translation||!rotation||!front||!leftSensor||!rightSensor)
    return fail("missing_original_multiranger");
  wb_distance_sensor_enable(front,step);
  wb_distance_sensor_enable(leftSensor,step);
  wb_distance_sensor_enable(rightSensor,step);
  if(wb_robot_step(step)==-1)return fail("sensor_startup");
  if(!sample(self,translation,rotation,front,leftSensor,rightSensor,
             len,side,"early",0,0,step)||
     !sample(self,translation,rotation,front,leftSensor,rightSensor,
             len,side,"survey",1.8,0,step)||
     !sample(self,translation,rotation,front,leftSensor,rightSensor,
             len,side,"decision",2.25,0,step)||
     !sample(self,translation,rotation,front,leftSensor,rightSensor,
             len,side,"gap_left",gate-.6,.8,step)||
     !sample(self,translation,rotation,front,leftSensor,rightSensor,
             len,side,"gap_right",gate-.6,-.8,step))
    return fail("native_measurement_or_pose_missing");
  printf("WEBEEBLOCKS_A5_LENGTH_DONE length=%c side=%c "
         "samples=5 supervisor_only=true motors=false\n",len,side);
  fflush(stdout);wb_robot_cleanup();return 0;
}

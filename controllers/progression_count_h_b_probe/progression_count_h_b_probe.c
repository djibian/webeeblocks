/* PRIVATE A6-B R2025a: native collider/ray witness, NOT pupil or motor. */
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <webots/distance_sensor.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
static const double H[2][3][3]={
 {{.36,0,0},{-.85,.36,0},{-.85,-.31,.36}},
 {{.48,0,0},{-.80,.48,0},{-.80,-.16,.48}}
};
static int eq(double x,double y,double eps){return isfinite(x)&&fabs(x-y)<eps;}
static int fatal(const char *why){fprintf(stderr,"A6_B_NATIVE_FATAL %s\n",why);fflush(stderr);wb_robot_cleanup();return 2;}
int main(void){
 wb_robot_init();
 int step=(int)wb_robot_get_basic_time_step(),n=0;char key[96];
 if(step<=0||step>64||!wb_robot_get_name()||
    strcmp(wb_robot_get_name(),"Crazyflie WebeeBlocks"))return fatal("craft/step");
 for(int v=1;v<=3;v++){snprintf(key,sizeof key,"WEBEEBLOCKS_COUNT_%d_SCENE",v);
  if(wb_supervisor_node_get_from_def(key)){if(n)return fatal("ambiguous scene");n=v;}}
 if(!n)return fatal("no scene");
 snprintf(key,sizeof key,"ACTIVITY6_%d_H_%d_BAR",n,n);
 WbNodeRef last=wb_supervisor_node_get_from_def(key);
 WbFieldRef fld=last?wb_supervisor_node_get_field(last,"translation"):NULL;
 const double *xyz=fld?wb_supervisor_field_get_sf_vec3f(fld):NULL;
 if(!xyz)return fatal("last H absent");
 int family=eq(xyz[0],.36,.002)?0:eq(xyz[0],.48,.002)?1:-1;
 if(family<0)return fatal("unknown holdout");
 const char *part[]={"LEFT","RIGHT","BAR"};
 for(int i=0;i<n;i++)for(int j=0;j<3;j++){
  snprintf(key,sizeof key,"ACTIVITY6_%d_H_%d_%s",n,i+1,part[j]);
  WbNodeRef node=wb_supervisor_node_get_from_def(key);
  WbFieldRef pf=node?wb_supervisor_node_get_field(node,"translation"):NULL;
  WbFieldRef bf=node?wb_supervisor_node_get_field(node,"boundingObject"):NULL;
  WbNodeRef box=bf?wb_supervisor_field_get_sf_node(bf):NULL;
  WbFieldRef sf=box?wb_supervisor_node_get_field(box,"size"):NULL;
  const double *p=pf?wb_supervisor_field_get_sf_vec3f(pf):NULL;
  const double *sz=sf?wb_supervisor_field_get_sf_vec3f(sf):NULL;
  if(!p||!sz||!node||!box||
     strcmp(wb_supervisor_node_get_type_name(node),"Solid")||
     strcmp(wb_supervisor_node_get_type_name(box),"Box")||
     !eq(p[0],H[family][n-1][i],.002)||
     !eq(p[1],j==0?.3:j==1?-.3:0,.002)||
     !eq(p[2],j==2?.74:.50,.002)||
     !eq(sz[0],.07,.0001)||!eq(sz[1],j==2?.57:.065,.0001)||
     !eq(sz[2],j==2?.24:1.,.0001))return fatal("H physical identity/box");
 }
 snprintf(key,sizeof key,"ACTIVITY6_%d_FINISH_SCREEN",n);
 WbNodeRef screen=wb_supervisor_node_get_from_def(key);
 WbFieldRef bound=screen?wb_supervisor_node_get_field(screen,"boundingObject"):NULL;
 WbNodeRef box=bound?wb_supervisor_field_get_sf_node(bound):NULL;
 WbFieldRef size=box?wb_supervisor_node_get_field(box,"size"):NULL;
 WbFieldRef spos=screen?wb_supervisor_node_get_field(screen,"translation"):NULL;
 const double *dims=size?wb_supervisor_field_get_sf_vec3f(size):NULL;
 const double *loc=spos?wb_supervisor_field_get_sf_vec3f(spos):NULL;
 if(!loc||!dims||!eq(loc[0],1.235,.002)||!eq(loc[1],0,.002)||
    !eq(loc[2],.76,.002)||!eq(dims[0],.07,.0001)||
    !eq(dims[1],1.48,.0001)||!eq(dims[2],.24,.0001))
   return fatal("finish physical box");
 WbNodeRef craft=wb_supervisor_node_get_self();
 WbFieldRef pos=craft?wb_supervisor_node_get_field(craft,"translation"):NULL;
 WbFieldRef rot=craft?wb_supervisor_node_get_field(craft,"rotation"):NULL;
 WbDeviceTag up=wb_robot_get_device("range_up");
 WbDeviceTag front=wb_robot_get_device("range_front");
 if(!craft||!pos||!rot||!up||!front)return fatal("real pose/range missing");
 wb_distance_sensor_enable(up,step);wb_distance_sensor_enable(front,step);
 wb_supervisor_node_enable_contact_points_tracking(craft,step,true);
 const double yaw[]={0,0,1,0};int slot=0;
 for(int k=0;k<n+5;k++)for(int j=0;j<(k<n?3:1);j++){
  int gate=k<n;
  double x=gate?H[family][n-1][k]+.04*(j-1):
    k==n?-.85:k==n+1?-.31:k==n+2?0:k==n+3?.85:1.48;
  const double target[]={x,0,.415};
  wb_supervisor_field_set_sf_vec3f(pos,target);
  wb_supervisor_field_set_sf_rotation(rot,yaw);
  wb_supervisor_node_reset_physics(craft);
  if(wb_robot_step(step)<0)return fatal("missing physics frame");
  const double *actual=wb_supervisor_node_get_position(craft);
  double u=wb_distance_sensor_get_value(up)/1000.;
  double f=wb_distance_sensor_get_value(front)/1000.;
  int contacts=-1;wb_supervisor_node_get_contact_points(craft,true,&contacts);
  if(!actual||!eq(actual[0],x,.035)||!eq(actual[1],0,.035)||
     !eq(actual[2],.415,.045)||!isfinite(u)||u<0||u>2.001||
     !isfinite(f)||f<0||f>2.001||contacts!=0)
    return fatal("pose/contact/sensor invalid");
  if(gate&&j==1&&u>.55)return fatal("H center not seen by real range_up");
  printf("A6_B_NATIVE_RAY family=%d n=%d slot=%d kind=%d gate=%d offset=%d "
         "x=%.9f up=%.9f front=%.9f contact=%d\n",
         family,n,slot,gate,k,j-1,actual[0],u,f,contacts);
  fflush(stdout);slot++;
 }
 if(slot!=3*n+5)return fatal("sample count");
 printf("A6_B_NATIVE_RANGE_PASS family=%d n=%d samples=%d "
        "physical_h=true motor=false pupil=false\n",family,n,slot);
 fflush(stdout);wb_robot_cleanup();return 0;
}

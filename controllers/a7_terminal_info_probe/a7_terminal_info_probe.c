/* A7 PRIVATE native information experiment: immutable near/far terminal worlds.
 * Original R2025a Crazyflie, five genuine Multi-rangers, supervisor-only poses.
 * No motors, pupil code, mission verdict, real flight or publication.
 */
#include <webots/robot.h>
#include <webots/distance_sensor.h>
#include <webots/supervisor.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#define PI 3.14159265358979323846

static int fail(const char *why) {
  fprintf(stderr,"A7_TERMINAL_INFO_FATAL %s\n",why);
  fflush(stderr); wb_robot_cleanup(); return 3;
}
static int close_to(double a,double b) {
  return isfinite(a) && fabs(a-b)<.0001;
}
static int box(const char *name,double x,double y,double z,
               double sx,double sy,double sz) {
  WbNodeRef node=wb_supervisor_node_get_from_def(name);
  if(!node||strcmp(wb_supervisor_node_get_type_name(node),"Solid"))return 0;
  const double *p=wb_supervisor_node_get_position(node);
  const double *o=wb_supervisor_node_get_orientation(node);
  WbFieldRef f=wb_supervisor_node_get_field(node,"boundingObject");
  WbNodeRef geom=f?wb_supervisor_field_get_sf_node(f):NULL;
  WbFieldRef size=geom?wb_supervisor_node_get_field(geom,"size"):NULL;
  const double *s=size?wb_supervisor_field_get_sf_vec3f(size):NULL;
  if(!p||!o||!geom||!s||strcmp(wb_supervisor_node_get_type_name(geom),"Box"))
    return 0;
  const double ep[3]={x,y,z}, es[3]={sx,sy,sz};
  for(int i=0;i<3;++i) if(!close_to(p[i],ep[i])||!close_to(s[i],es[i]))
    return 0;
  for(int i=0;i<3;++i) for(int j=0;j<3;++j)
    if(!close_to(o[3*i+j],i==j?1.:0.)) return 0;
  return 1;
}
static int attest(double closed_y) {
  return
    box("ACTIVITY7_L_OPEN_LEFT",-.750,.300,.50,.07,.065,1.) &&
    box("ACTIVITY7_L_OPEN_RIGHT",-.750,-.300,.50,.07,.065,1.) &&
    box("ACTIVITY7_L_OPEN_BAR",-.750,0.,.74,.07,.57,.24) &&
    box("ACTIVITY7_L_CORNER_FRONT",.420,0.,.55,.08,.64,1.10) &&
    box("ACTIVITY7_L_CORNER_SIDE",.200,-.320,.55,.48,.08,1.10) &&
    box("ACTIVITY7_L_CLOSED_LEFT",-.100,closed_y,.65,.065,.08,1.30) &&
    box("ACTIVITY7_L_CLOSED_RIGHT",.500,closed_y,.65,.065,.08,1.30) &&
    box("ACTIVITY7_L_CLOSED_BAR",.200,closed_y,.90,.57,.08,.30) &&
    box("ACTIVITY7_L_CLOSED_PANEL",.200,closed_y,.65,.57,.08,1.30);
}
static int sample(WbNodeRef self,WbFieldRef translation,WbFieldRef rotation,
                  const WbDeviceTag devices[5],char variant,
                  const char *stage,double x,double y,double yaw,int step) {
  const double pos[3]={x,y,.50},rot[4]={0.,0.,1.,yaw};
  wb_supervisor_field_set_sf_vec3f(translation,pos);
  wb_supervisor_field_set_sf_rotation(rotation,rot);
  wb_supervisor_node_reset_physics(self);
  for(int i=0;i<2;++i)if(wb_robot_step(step)<0)return 0;
  const double *p=wb_supervisor_node_get_position(self);
  const double *o=wb_supervisor_node_get_orientation(self);
  int contacts=-1;
  const WbContactPoint *points=wb_supervisor_node_get_contact_points(
      self,true,&contacts);
  if(!p||!o||contacts!=0||points==NULL&&contacts>0||
     fabs(p[0]-x)>.035||fabs(p[1]-y)>.035||fabs(p[2]-.50)>.09||
     fabs(o[0]-cos(yaw))>.12||fabs(o[3]-sin(yaw))>.12)
    return 0;
  double rays[5];
  for(int i=0;i<5;++i) {
    rays[i]=wb_distance_sensor_get_value(devices[i])/1000.;
    if(!isfinite(rays[i])||rays[i]<0.||rays[i]>2.001)return 0;
  }
  printf("A7_TERMINAL_INFO_SAMPLE variant=%c stage=%s "
         "front=%.9f back=%.9f left=%.9f right=%.9f up=%.9f "
         "x=%.9f y=%.9f z=%.9f yaw=%.9f\n",
         variant,stage,rays[0],rays[1],rays[2],rays[3],rays[4],
         p[0],p[1],p[2],yaw);
  fflush(stdout);return 1;
}
int main(void) {
  wb_robot_init();
  const int step=(int)wb_robot_get_basic_time_step();
  if(step!=32||strcmp(wb_robot_get_name(),"Crazyflie WebeeBlocks"))
    return fail("real_32ms_classroom_crazyflie_required");
  WbNodeRef scene=wb_supervisor_node_get_from_def("WEBEEBLOCKS_MINI_GP_L_SCENE");
  WbNodeRef world=wb_supervisor_node_get_from_def("WEBEEBLOCKS_CLASSROOM_START_WORLD");
  if(!scene||!world||strcmp(wb_supervisor_node_get_type_name(scene),"Group")||
     strcmp(wb_supervisor_node_get_type_name(world),"WorldInfo"))
    return fail("private_scene_or_world_not_attested");
  WbFieldRef children=wb_supervisor_node_get_field(scene,"children");
  if(!children||wb_supervisor_field_get_count(children)!=29)
    return fail("unexpected_immutable_L_scene_children");
  WbNodeRef panel=wb_supervisor_node_get_from_def("ACTIVITY7_L_CLOSED_PANEL");
  const double *p=panel?wb_supervisor_node_get_position(panel):NULL;
  if(!p||!isfinite(p[1]))return fail("missing_terminal_panel");
  const char variant=fabs(p[1]-1.22)<.0001?'N':
                     (fabs(p[1]-1.62)<.0001?'F':'?');
  if(variant=='?'||!attest(variant=='N'?1.22:1.62))
    return fail("terminal_colliders_not_original_or_shifted");
  WbNodeRef self=wb_supervisor_node_get_self();
  WbFieldRef translation=self?wb_supervisor_node_get_field(self,"translation"):NULL;
  WbFieldRef rotation=self?wb_supervisor_node_get_field(self,"rotation"):NULL;
  WbDeviceTag devices[5];
  const char *const names[5]={"range_front","range_back","range_left",
                              "range_right","range_up"};
  for(int i=0;i<5;++i) {
    devices[i]=wb_robot_get_device(names[i]);
    if(!devices[i])return fail("multiranger_missing");
    wb_distance_sensor_enable(devices[i],step);
  }
  if(!self||!translation||!rotation||wb_robot_step(step)<0)
    return fail("native_probe_initialization");
  wb_supervisor_node_enable_contact_points_tracking(self,step,true);
  if(!sample(self,translation,rotation,devices,variant,
             "early_far",-1.25,0.,0.,step)||
     !sample(self,translation,rotation,devices,variant,
             "early_near",-.90,0.,0.,step)||
     !sample(self,translation,rotation,devices,variant,
             "late_far",.20,.40,PI/2,step)||
     !sample(self,translation,rotation,devices,variant,
             "late_near",.20,.60,PI/2,step))
    return fail("physical_range_or_pose_missing");
  printf("A7_TERMINAL_INFO_DONE variant=%c samples=4 native=true "
         "supervisor_only=true motorized=false pupil_wbb=false\n",variant);
  fflush(stdout);wb_robot_cleanup();return 0;
}

/* Draft-only Webots R2025a physical geometry witness for Mini Grand Prix.
 * An unmodified classroom Crazyflie PROTO is teleported by its test-only
 * Supervisor at measured poses; NO motors, Blockly, mission PASS or real flight.
 * Prove genuine colliders, two independent gravity-contact controls and a
 * contact-free geometric low corridor, never dynamic pupil reachability.
 */
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <webots/distance_sensor.h>

#define WB_A7_PI 3.14159265358979323846

static int fail(const char *message) {
  fprintf(stderr, "WEBEEBLOCKS_A7_NATIVE_FATAL %s\n", message);
  fflush(stderr);
  wb_robot_cleanup();
  return 2;
}

static int box(const char *def, double x, double y, double z,
               double sx, double sy, double sz) {
  WbNodeRef node = wb_supervisor_node_get_from_def(def);
  if (!node || strcmp(wb_supervisor_node_get_type_name(node), "Solid"))
    return 0;
  const double *p = wb_supervisor_node_get_position(node);
  WbFieldRef b = wb_supervisor_node_get_field(node, "boundingObject");
  WbNodeRef g = b ? wb_supervisor_field_get_sf_node(b) : NULL;
  if (!p || !g || strcmp(wb_supervisor_node_get_type_name(g), "Box"))
    return 0;
  WbFieldRef f = wb_supervisor_node_get_field(g, "size");
  const double *s = f ? wb_supervisor_field_get_sf_vec3f(f) : NULL;
  if (!s) return 0;
  const double expected_p[3] = {x,y,z};
  const double expected_s[3] = {sx,sy,sz};
  for (int i=0; i<3; ++i)
    if (!isfinite(p[i]) || !isfinite(s[i]) ||
        fabs(p[i]-expected_p[i])>1e-6 ||
        fabs(s[i]-expected_s[i])>1e-6) return 0;
  return 1;
}

static int attest_boxes(char variant, double gate, double turn, double side) {
  char k[96];
#define CHECK_BOX(part, x,y,z, sx,sy,sz) do { \
  snprintf(k,sizeof k,"ACTIVITY7_%c_%s",variant,part); \
  if (!box(k,x,y,z,sx,sy,sz)) return 0; \
} while (0)
  CHECK_BOX("OPEN_LEFT", gate, 0.300, 0.50, .07, .065, 1.00);
  CHECK_BOX("OPEN_RIGHT", gate, -0.300, 0.50, .07, .065, 1.00);
  CHECK_BOX("OPEN_BAR", gate, 0.0, 0.74, .07, .57, .24);
  CHECK_BOX("CORNER_FRONT", turn+.220, 0.0, 0.55, .08, .64, 1.10);
  CHECK_BOX("CORNER_SIDE", turn, -side*.320, 0.55, .48, .08, 1.10);
  CHECK_BOX("CLOSED_LEFT", turn-.300, side*1.420, 0.65, .065, .08, 1.30);
  CHECK_BOX("CLOSED_RIGHT", turn+.300, side*1.420, 0.65, .065, .08, 1.30);
  CHECK_BOX("CLOSED_BAR", turn, side*1.420, .90, .57, .08, .30);
  CHECK_BOX("CLOSED_PANEL", turn, side*1.420, .65, .57, .08, 1.30);
#undef CHECK_BOX
  return 1;
}

static WbNodeRef craft;
static WbFieldRef position, rotation;
static int step;
static int place(double x, double y, double z, double yaw,
                 int *contact_count) {
  const double p[3]={x,y,z};
  const double r[4]={0.0,0.0,1.0,yaw};
  wb_supervisor_field_set_sf_vec3f(position,p);
  wb_supervisor_field_set_sf_rotation(rotation,r);
  wb_supervisor_node_reset_physics(craft);
  if (wb_robot_step(step)<0) return 0;
  const double *actual=wb_supervisor_node_get_position(craft);
  int n=-1;
  const WbContactPoint *points=wb_supervisor_node_get_contact_points(
    craft,true,&n);
  if (!actual || !isfinite(actual[0]) || !isfinite(actual[1]) ||
      !isfinite(actual[2]) || fabs(actual[0]-x)>.045 ||
      fabs(actual[1]-y)>.045 || fabs(actual[2]-z)>.06 || n<0 ||
      (n>0 && !points)) return 0;
  if (contact_count) *contact_count=n;
  return 1;
}

static int gravity_contact(WbNodeRef obstacle, double x, double y,
                           double initial_z, int *hits) {
  int ignored=0;
  if (!place(x,y,initial_z,0.0,&ignored)) return 0;
  int largest=0;
  for (int i=0;i<85;++i) {
    if (wb_robot_step(step)<0) return 0;
    int n=-1;
    const WbContactPoint *points=wb_supervisor_node_get_contact_points(
      obstacle,false,&n);
    if (n<0 || (n>0 && !points)) return 0;
    if (n>largest) largest=n;
  }
  *hits=largest;
  return largest>0;
}

int main(void) {
  wb_robot_init();
  step=(int)wb_robot_get_basic_time_step();
  if (step!=32 || !wb_robot_get_name() ||
      strcmp(wb_robot_get_name(),"Crazyflie WebeeBlocks"))
    return fail("untrusted 32-ms isolated classroom robot or controller");
  char variant=0;
  for (char v='L';v<='R';v+=6) {
    char key[80];
    snprintf(key,sizeof key,"WEBEEBLOCKS_MINI_GP_%c_SCENE",v);
    if (wb_supervisor_node_get_from_def(key)) {
      if (variant) return fail("multiple scene variants imported together");
      variant=v;
    }
  }
  if (!variant) return fail("no attested Mini Grand Prix scene");
  const double gate=(variant=='L')?-.750:-.450;
  const double turn=(variant=='L')?.200:.500;
  const double side=(variant=='L')?1.0:-1.0;
  if (!attest_boxes(variant,gate,turn,side))
    return fail("native Solid/collider dimensions or poses differ from oracle");

  craft=wb_supervisor_node_get_self();
  position=craft?wb_supervisor_node_get_field(craft,"translation"):NULL;
  rotation=craft?wb_supervisor_node_get_field(craft,"rotation"):NULL;
  WbDeviceTag front=wb_robot_get_device("range_front");
  if (!craft || !position || !rotation || !front)
    return fail("missing native Crazyflie supervisor or range_front device");
  char bar_def[90], panel_def[90];
  snprintf(bar_def,sizeof bar_def,"ACTIVITY7_%c_OPEN_BAR",variant);
  snprintf(panel_def,sizeof panel_def,"ACTIVITY7_%c_CLOSED_PANEL",variant);
  WbNodeRef bar=wb_supervisor_node_get_from_def(bar_def);
  WbNodeRef panel=wb_supervisor_node_get_from_def(panel_def);
  if (!bar || !panel) return fail("missing physical control colliders");
  wb_distance_sensor_enable(front,step);
  wb_supervisor_node_enable_contact_points_tracking(craft,step,true);
  wb_supervisor_node_enable_contact_points_tracking(bar,step,false);
  wb_supervisor_node_enable_contact_points_tracking(panel,step,false);

  /* CI-ONLY: proof of a REAL floor start with no teleportation or motors.
   * This branch is entered exclusively by an isolated test world seeded
   * with a preflight token, not by any pupil or ordinary geometry run.
   * A valid ATTEMPT is released only after 40 actual physics ticks. */
  WbFieldRef test_data=wb_supervisor_node_get_field(craft,"customData");
  const char *ground_token=test_data?
      wb_supervisor_field_get_sf_string(test_data):NULL;
  if(ground_token&&!strcmp(ground_token,"WEBEEBLOCKS_A7_GROUND_PREFLIGHT_V1")) {
    const double *initial=wb_supervisor_node_get_position(craft);
    if(!initial||fabs(initial[0]+1.400)>.030||
       fabs(initial[1])>.030||initial[2]<-.015||initial[2]>.055)
      return fail("ground-control craft is not on genuine blue start");
    const double initial_z=initial[2];
    int floor_hits=0;
    for(int i=0;i<48;++i) {
      if(wb_robot_step(step)<0)return fail("ground-control simulator stopped");
      const double *p=wb_supervisor_node_get_position(craft);
      const double *v=wb_supervisor_node_get_velocity(craft);
      int n=-1;
      const WbContactPoint *points=wb_supervisor_node_get_contact_points(craft,true,&n);
      if(!p||!v||n<0||(n>0&&!points)||
         !isfinite(p[0])||!isfinite(p[1])||!isfinite(p[2])||
         !isfinite(v[0])||!isfinite(v[1])||!isfinite(v[2])||
         fabs(p[0]+1.400)>.050||fabs(p[1])>.050||
         p[2]<-.015||p[2]>.065)
        return fail("ground-control position or contact observation invalid");
      for(int j=0;j<n;++j){
        if(!isfinite(points[j].point[2])||fabs(points[j].point[2])>.025)
          return fail("ground-control detected non-floor contact");
        ++floor_hits;
      }
      if(i==39) {
        /* The FIRST 32-ms tick moves the unpowered craft as gravity
         * settles it (about 0.31 m/s vertically). Do not authorize an
         * attempt from that transient. Wait for native floor contacts,
         * a low actual velocity and 40 consecutive Webots steps. */
        if(hypot(v[0],v[1])>.120||fabs(v[2])>.120||
           floor_hits<1)return fail("ground-control not physically settled");
        wb_supervisor_field_set_sf_string(
            test_data,"WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 2");
        printf("A7_NATIVE_GROUND_TOKEN_RELEASED variant=%c tick=40 "
               "time=%.9f floor_contacts=%d\n",
               variant,wb_robot_get_time(),floor_hits);
        fflush(stdout);
      }
      if(i==47){
        if(hypot(v[0],v[1])>.120||fabs(v[2])>.120||
           floor_hits<1)return fail("ground-control not physically settled");
        printf("A7_NATIVE_GROUND_VALID variant=%c idle_steps=48 "
               "start_z=%.9f end_z=%.9f floor_contacts=%d motors=OFF\n",
               variant,initial_z,p[2],floor_hits);
        fflush(stdout);
      }
    }
    wb_robot_cleanup();
    return 0;
  }

  int contacts=0;
  if (!place(-1.40,0,.40,0.0,&contacts) || contacts)
    return fail("not freely positioned at low departure");
  const double low=wb_distance_sensor_get_value(front)/1000.0;
  if (!place(-1.40,0,.75,0.0,&contacts) || contacts)
    return fail("not freely positioned at high departure");
  const double high=wb_distance_sensor_get_value(front)/1000.0;
  if (!place(turn,side*.95,.40,side*WB_A7_PI/2,&contacts) || contacts)
    return fail("not freely positioned before the closed H");
  const double end=wb_distance_sensor_get_value(front)/1000.0;
  if (!isfinite(low) || !isfinite(high) || !isfinite(end) ||
      low<1.3 || low>2.001 || high<.20 || high>1.25 ||
      low-high<.35 || end<.20 || end>.70)
    return fail("native forward ray cannot distinguish H/open/closed");

  int safe=0;
  const int nforward=(variant=='L')?80:95;
  for (int i=0;i<=nforward;++i) {
    const double x=-1.40+(turn+1.40)*i/nforward;
    if (!place(x,0.0,.40,0.0,&contacts) || contacts) {
      fprintf(stderr,"WEBEEBLOCKS_A7_NATIVE_SWEEP_FAIL variant=%c leg=1 i=%d contacts=%d\n",
              variant,i,contacts);
      return fail("unexpected obstacle overlap in low first leg");
    }
    ++safe;
  }
  for (int i=0;i<=48;++i) {
    const double y=side*.95*i/48;
    if (!place(turn,y,.40,side*WB_A7_PI/2,&contacts) || contacts) {
      fprintf(stderr,"WEBEEBLOCKS_A7_NATIVE_SWEEP_FAIL variant=%c leg=2 i=%d contacts=%d\n",
              variant,i,contacts);
      return fail("unexpected obstacle overlap after 90-degree corner");
    }
    ++safe;
  }

  int bar_hits=0,panel_hits=0;
  if (!gravity_contact(bar,gate,0.0,1.25,&bar_hits))
    return fail("falling physical drone did not contact open-H overhead bar");
  if (!gravity_contact(panel,turn,side*1.42,1.65,&panel_hits))
    return fail("falling physical drone did not contact final closed panel");
  printf("WEBEEBLOCKS_A7_NATIVE_PASS variant=%c safe=%d bar_contact=%d "
         "closed_contact=%d front_low_m=%.9f front_high_m=%.9f "
         "closed_front_m=%.9f motors=OFF pupil_wbb=UNPROVEN\n",
         variant,safe,bar_hits,panel_hits,low,high,end);
  fflush(stdout);
  wb_robot_cleanup();
  return 0;
}

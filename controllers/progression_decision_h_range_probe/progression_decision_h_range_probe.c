/* CI-only Webots R2025a front-range falsification at identical native pose.
 * Replaces the pupil flight controller in disposable CI worlds. No motors,
 * AST, Blockly project or physical Crazyflie qualification dependency.
 */
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <webots/contact_point.h>
#include <webots/distance_sensor.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#define WB_DH_RANGE_SENSOR "range_front"
#define WB_DH_CRAFT "Crazyflie WebeeBlocks"

static int invalid(const char *why) {
  fprintf(stderr, "WEBEEBLOCKS_DECISION_H_RANGE_FATAL %s\n", why);
  fflush(stderr);
  wb_robot_cleanup();
  return 2;
}

int main(void) {
  wb_robot_init();
  const int step = (int)wb_robot_get_basic_time_step();
  const char *name = wb_robot_get_name();
  if (step <= 0 || !name || strcmp(name, WB_DH_CRAFT) != 0)
    return invalid("invalid basic time step or craft identity");
  WbNodeRef a = wb_supervisor_node_get_from_def("WEBEEBLOCKS_DECISION_A_SCENE");
  WbNodeRef b = wb_supervisor_node_get_from_def("WEBEEBLOCKS_DECISION_B_SCENE");
  if ((!a && !b) || (a && b))
    return invalid("ambiguous scene identity");
  WbNodeRef self = wb_supervisor_node_get_self();
  WbFieldRef position_field = self ? wb_supervisor_node_get_field(self, "translation") : NULL;
  WbFieldRef rotation_field = self ? wb_supervisor_node_get_field(self, "rotation") : NULL;
  WbDeviceTag front = wb_robot_get_device(WB_DH_RANGE_SENSOR);
  if (!self || !position_field || !rotation_field || !front)
    return invalid("missing supervisor pose or real front sensor");

  /* CI-only contact witness; the production range experiment below is
   * unchanged. This never powers motors or validates a pupil's algorithm.
   * It observes real R2025a Solid contacts independently of A4 outcome. */
  WbFieldRef data_field = wb_supervisor_node_get_field(self, "customData");
  const char *token = data_field ? wb_supervisor_field_get_sf_string(data_field) : NULL;
  if (token && !strcmp(token, "WEBEEBLOCKS_A4_LOW_CONTACT_V1")) {
    if (step != 32) return invalid("low-contact fixture needs 32-ms physics");
    const char variant = a ? 'A' : 'B';
    const char *names[] = {"H_LEFT", "THRESHOLD", "CORRIDOR_LEFT"};
    const double hx = a ? .750 : 1.350;
    const double tx = a ? 1.350 : .750;
    const double x0[] = {hx, tx-.05-.09, .700};
    const double y0[] = {.300-.0325-.09, 0.0, .420-.04-.09};
    const double dz[] = {1.0, 0.0, 1.0};
    const double offsets[] = {0.,.025,.050,.075,.100,.125,.150,.170};
    WbNodeRef colliders[3]={0};
    for(int j=0;j<3;++j) {
      char def[96];
      const int n=snprintf(def,sizeof(def),"ACTIVITY4_%c_%s",variant,names[j]);
      colliders[j]=(n>0&&(size_t)n<sizeof(def)) ?
        wb_supervisor_node_get_from_def(def):NULL;
      if(!colliders[j] || wb_supervisor_node_get_id(colliders[j])<=0)
        return invalid("missing genuine obstacle collider for contact probe");
      wb_supervisor_node_enable_contact_points_tracking(colliders[j],step,false);
    }
    /* Real floor-only preflight, first sample at a stable blue launch.
     * Require measured native floor contact, not merely a near-ground pose.
     * No attempt was active while the robot settled. */
    wb_supervisor_node_enable_contact_points_tracking(self,step,true);
    for(int i=0;i<45;++i)
      if(wb_robot_step(step)<0)return invalid("floor preflight interrupted");
    const double *floor_pose=wb_supervisor_node_get_position(self);
    const double *floor_speed=wb_supervisor_node_get_velocity(self);
    int nf=-1;
    const WbContactPoint *floor_points=
        wb_supervisor_node_get_contact_points(self,true,&nf);
    if(!floor_pose||!floor_speed||nf<1||!floor_points||
       fabs(floor_pose[0])>.040||fabs(floor_pose[1])>.040||
       floor_pose[2]<0.0||floor_pose[2]>.030||
       hypot(floor_speed[0],floor_speed[1])>.120||
       fabs(floor_speed[2])>.120)
      return invalid("floor-only physical sample not settled");
    int floor_contacts=0;
    for(int i=0;i<nf;++i) {
      if(!isfinite(floor_points[i].point[2]) ||
         fabs(floor_points[i].point[2])>.025)
        return invalid("nonfloor physical preflight contact");
      ++floor_contacts;
    }
    if(!floor_contacts)return invalid("no actual Floor contacts");
    printf("WEBEEBLOCKS_DECISION_H_FLOOR_ONLY variant=%c "
           "floor_contacts=%d center_z=%.9f motors=OFF\n",
           variant,floor_contacts,floor_pose[2]);
    fflush(stdout);
    wb_supervisor_field_set_sf_string(data_field,
        "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 1");
    if(wb_robot_step(step)<0)return invalid("floor attempt interrupted");
    int physical[3]={0};
    for(int j=0;j<3;++j) {
      for(int k=0;k<8;++k) {
        const double p[3]={x0[j]+(dz[j]?0.0:offsets[k]),
                           y0[j]+(dz[j]?offsets[k]:0.0),.015};
        wb_supervisor_field_set_sf_vec3f(position_field,p);
        wb_supervisor_node_reset_physics(self);
        if(wb_robot_step(step)<0)
          return invalid("physical contact positioning interrupted");
        char attempt[100];
        snprintf(attempt,sizeof(attempt),
            "WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 %d",100+j*10+k);
        wb_supervisor_field_set_sf_string(data_field,attempt);
        if(wb_robot_step(step)<0)
          return invalid("physical contact observation interrupted");
        int n=-1;
        const WbContactPoint *pts=
            wb_supervisor_node_get_contact_points(colliders[j],false,&n);
        if(n<0||(n>0&&!pts))
          return invalid("physical collider contact points unavailable");
        const int obstacle_id=wb_supervisor_node_get_id(colliders[j]);
        for(int i=0;i<n;++i){
          if(!isfinite(pts[i].point[2]))
            return invalid("nonfinite contact altitude");
          if(fabs(pts[i].point[2])<=.025) {
            ++physical[j];
            printf("WEBEEBLOCKS_DECISION_H_LOW_PHYSICAL variant=%c "
                "type=%s z=%.9f node_id=%d obstacle_id=%d\n",
                variant,names[j],pts[i].point[2],pts[i].node_id,obstacle_id);
            fflush(stdout);
          }
        }
      }
      printf("WEBEEBLOCKS_DECISION_H_LOW_END variant=%c type=%s "
          "low_contacts=%d motors=OFF\n",variant,names[j],physical[j]);
      fflush(stdout);
      if(!physical[j])
        return invalid("no real low-altitude contact with required obstacle");
    }
    wb_robot_cleanup();
    return 0;
  }

  const double pose[3] = {0.20, 0.0, 0.750};
  const double facing[4] = {0.0, 0.0, 1.0, 0.0};
  wb_supervisor_field_set_sf_vec3f(position_field, pose);
  wb_supervisor_field_set_sf_rotation(rotation_field, facing);
  wb_supervisor_node_reset_physics(self);
  wb_distance_sensor_enable(front, step);

  /* The first post-enable native step is fresh. Delay would allow gravity
   * to drop the sensor below the H-bar (underside z=0.620). */
  if (wb_robot_step(step) < 0)
    return invalid("first post-enable native step unavailable");
  const double *world = wb_supervisor_node_get_position(self);
  const double measured_m = wb_distance_sensor_get_value(front) / 1000.0;
  if (!world || !isfinite(world[0]) || !isfinite(world[1]) || !isfinite(world[2]) ||
      fabs(world[0] - pose[0]) > 0.035 || fabs(world[1]) > 0.035 ||
      fabs(world[2] - pose[2]) > 0.045 || !isfinite(measured_m) ||
      measured_m < 0.0 || measured_m > 2.001)
    return invalid("invalid fresh pose or sensor sample");

  /* Distinct physical bands with a 0.15 m gap; theoretical 0.515/1.115 m
   * cannot substitute for a genuine native multi-ranger measurement. */
  const int acceptable = a ? (measured_m >= 0.35 && measured_m <= 0.75) :
                            (measured_m >= 0.90 && measured_m <= 1.35);
  if (!acceptable) {
    fprintf(stderr,
      "WEBEEBLOCKS_DECISION_H_RANGE_FATAL variant=%c observed_m=%.9f\n",
      a ? 'a' : 'b', measured_m);
    fflush(stderr);
    wb_robot_cleanup();
    return 2;
  }
  printf("WEBEEBLOCKS_DECISION_H_RANGE_PASS variant=%c observed_m=%.9f "
         "pose_x=%.9f pose_y=%.9f pose_z=%.9f\n",
         a ? 'a' : 'b', measured_m, world[0], world[1], world[2]);
  fflush(stdout);
  wb_robot_cleanup();
  return 0;
}

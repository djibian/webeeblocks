#include <math.h>
#include <stdio.h>
#include <webots/gps.h>
#include <webots/gyro.h>
#include <webots/inertial_unit.h>
#include <webots/motor.h>
#include <webots/robot.h>
#include <webots/supervisor.h>
#include "pid_controller.h"

#define PI 3.14159265358979323846
#define TARGET_Z_DELTA 1.0
#define LEG_M 1.0
#define VX 0.35
#define YAW_RATE 0.7
#define TIMEOUT 60.0

typedef enum { TAKEOFF, LEG, TURN, LAND } phase_t;

static double wrap(double a) {
  while (a > PI) a -= 2 * PI;
  while (a < -PI) a += 2 * PI;
  return a;
}
static double motor(double v) { return v < 0 ? 0 : (v > 600 ? 600 : v); }
static void stop(WbDeviceTag a, WbDeviceTag b, WbDeviceTag c, WbDeviceTag d) {
  wb_motor_set_velocity(a,0); wb_motor_set_velocity(b,0); wb_motor_set_velocity(c,0); wb_motor_set_velocity(d,0);
}
static const char *phase_name(phase_t phase) {
  switch (phase) {
    case TAKEOFF: return "TAKEOFF";
    case LEG: return "LEG";
    case TURN: return "TURN";
    case LAND: return "LAND";
  }
  return "UNKNOWN";
}
static void log_state(const char *event, phase_t phase, int leg, double t, double x, double y, double z,
                      double yaw, double roll, double pitch, double vz) {
  printf("WEBEEBLOCKS_CF_SQUARE_%s phase=%s leg=%d t=%.3f x=%.6f y=%.6f z=%.6f yaw=%.6f roll=%.6f pitch=%.6f vz=%.6f\n",
         event, phase_name(phase), leg, t, x, y, z, yaw, roll, pitch, vz);
  fflush(stdout);
}

int main(void) {
  wb_robot_init();
  const int step=(int)wb_robot_get_basic_time_step();
  WbDeviceTag m1=wb_robot_get_device("m1_motor"),m2=wb_robot_get_device("m2_motor");
  WbDeviceTag m3=wb_robot_get_device("m3_motor"),m4=wb_robot_get_device("m4_motor");
  WbDeviceTag gps=wb_robot_get_device("gps"),imu=wb_robot_get_device("inertial_unit"),gyro=wb_robot_get_device("gyro");
  wb_motor_set_position(m1,INFINITY); wb_motor_set_position(m2,INFINITY); wb_motor_set_position(m3,INFINITY); wb_motor_set_position(m4,INFINITY);
  wb_motor_set_velocity(m1,-1); wb_motor_set_velocity(m2,1); wb_motor_set_velocity(m3,-1); wb_motor_set_velocity(m4,1);
  wb_gps_enable(gps,step); wb_inertial_unit_enable(imu,step); wb_gyro_enable(gyro,step);
  while(wb_robot_step(step)!=-1 && wb_robot_get_time()<2.0){}

  const double *p=wb_gps_get_values(gps),*r=wb_inertial_unit_get_roll_pitch_yaw(imu);
  const double sx=p[0],sy=p[1],sz=p[2],syaw=r[2],target_z=sz+TARGET_Z_DELTA;
  double min_z=sz,max_z=sz,px=sx,py=sy,pz=sz,pt=wb_robot_get_time(),leg_x=sx,leg_y=sy,prev_yaw=syaw,turn_angle=0,stable=-1;
  const double t0=pt;
  double next_heartbeat=t0;
  int leg=0; phase_t phase=TAKEOFF;
  gains_pid_t g={0}; g.kp_att_y=1;g.kd_att_y=.5;g.kp_att_rp=.5;g.kd_att_rp=.1;g.kp_vel_xy=2;g.kd_vel_xy=.5;g.kp_z=10;g.ki_z=5;g.kd_z=5;
  init_pid_attitude_fixed_height_controller();
  actual_state_t a={0}; desired_state_t d={0}; motor_power_t power={0};
  printf("WEBEEBLOCKS_CF_SQUARE_STARTED x=%.6f y=%.6f z=%.6f yaw=%.6f\n",sx,sy,sz,syaw);
  fflush(stdout);
  log_state("PHASE_ENTER", phase, leg, 0.0, sx, sy, sz, syaw, r[0], r[1], 0.0);

  int step_result;
  while((step_result=wb_robot_step(step))!=-1){
    double now=wb_robot_get_time(),dt=now-pt; if(dt<=0) continue;
    p=wb_gps_get_values(gps);r=wb_inertial_unit_get_roll_pitch_yaw(imu);const double *gv=wb_gyro_get_values(gyro);
    double x=p[0],y=p[1],z=p[2],yaw=r[2],vz=(z-pz)/dt,vxg=(x-px)/dt,vyg=(y-py)/dt,cy=cos(yaw),syy=sin(yaw);
    if(z<min_z)min_z=z;if(z>max_z)max_z=z;
    a.roll=r[0];a.pitch=r[1];a.yaw_rate=gv[2];a.altitude=z;a.vx=vxg*cy+vyg*syy;a.vy=-vxg*syy+vyg*cy;
    d.roll=0;d.pitch=0;d.vx=0;d.vy=0;d.yaw_rate=0;d.altitude=target_z;

    if(now>=next_heartbeat){
      log_state("HEARTBEAT", phase, leg, now-t0, x, y, z, yaw, a.roll, a.pitch, vz);
      next_heartbeat=now+1.0;
    }

    if(fabs(a.roll)>1.2||fabs(a.pitch)>1.2||now-t0>TIMEOUT){
      const char *reason=(fabs(a.roll)>1.2||fabs(a.pitch)>1.2)?"tilt":"internal-timeout";
      printf("WEBEEBLOCKS_CF_SQUARE_QUIT reason=%s phase=%s leg=%d t=%.3f\n",reason,phase_name(phase),leg,now-t0);
      printf("WEBEEBLOCKS_CF_SQUARE_FAILED phase=%d leg=%d t=%.3f\n",phase,leg,now-t0);
      fflush(stdout);stop(m1,m2,m3,m4);wb_supervisor_simulation_quit(2);break;
    }
    if(phase==TAKEOFF){
      if(fabs(z-target_z)<.05&&fabs(vz)<.15){
        if(stable<0)stable=now;
        if(now-stable>.5){
          phase=LEG;leg_x=x;leg_y=y;stable=-1;
          log_state("PHASE_ENTER", phase, leg, now-t0, x, y, z, yaw, a.roll, a.pitch, vz);
        }
      }else stable=-1;
    }else if(phase==LEG){
      d.vx=VX;
      if(hypot(x-leg_x,y-leg_y)>=LEG_M){
        phase=TURN;turn_angle=0;prev_yaw=yaw;
        log_state("PHASE_ENTER", phase, leg, now-t0, x, y, z, yaw, a.roll, a.pitch, vz);
      }
    }else if(phase==TURN){
      d.yaw_rate=YAW_RATE;turn_angle+=wrap(yaw-prev_yaw);prev_yaw=yaw;
      if(turn_angle>=PI/2){
        leg++;
        if(leg==4){phase=LAND;stable=-1;}
        else{phase=LEG;leg_x=x;leg_y=y;}
        log_state("PHASE_ENTER", phase, leg, now-t0, x, y, z, yaw, a.roll, a.pitch, vz);
      }
    }else{
      d.altitude=sz;
      if(z<=sz+.05&&fabs(vz)<.15){
        if(stable<0)stable=now;
        if(now-stable>.5){
          double err=hypot(x-sx,y-sy),yawerr=fabs(wrap(yaw-syaw))*180/PI;
          printf("WEBEEBLOCKS_CF_SQUARE_RESULT status=success error_xy=%.6f yaw_error_deg=%.6f altitude_min=%.6f altitude_max=%.6f total_s=%.3f legs=%d\n",err,yawerr,min_z,max_z,now-t0,leg);
          printf("WEBEEBLOCKS_CF_SQUARE_QUIT reason=success phase=%s leg=%d t=%.3f\n",phase_name(phase),leg,now-t0);
          stop(m1,m2,m3,m4);fflush(stdout);wb_supervisor_simulation_quit(0);break;
        }
      }else stable=-1;
    }
    pid_velocity_fixed_height_controller(a,&d,g,dt,&power);
    wb_motor_set_velocity(m1,-motor(power.m1));wb_motor_set_velocity(m2,motor(power.m2));wb_motor_set_velocity(m3,-motor(power.m3));wb_motor_set_velocity(m4,motor(power.m4));
    pt=now;px=x;py=y;pz=z;
  }
  printf("WEBEEBLOCKS_CF_SQUARE_LOOP_EXIT step_result=%d t=%.3f phase=%s leg=%d\n",step_result,wb_robot_get_time()-t0,phase_name(phase),leg);
  fflush(stdout);
  stop(m1,m2,m3,m4);wb_robot_cleanup();return 0;
}

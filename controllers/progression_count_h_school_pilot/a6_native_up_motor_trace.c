/* CI-ONLY A6 school pilot measurement: GNU ld --wrap on wb_robot_step.
 * This compilation unit belongs ONLY to progression_count_h_school_pilot.
 * __real_wb_robot_step is invoked ONCE with the original duration; no
 * motor/physics/PID command is changed. No pupil JavaScript or AST is read.
 * A PASS here only attests a measured ray while the original native pilot
 * flies. It does NOT establish a generic student .wbb or accurate counting.
 */
#include <webots/robot.h>
#include <webots/distance_sensor.h>
#include <webots/gps.h>
#include <math.h>
#include <stdio.h>

extern int __real_wb_robot_step(int duration);

int __wrap_wb_robot_step(int duration) {
  const int result=__real_wb_robot_step(duration);
  if(result<0)return result;
  static WbDeviceTag native_up=0;
  static WbDeviceTag native_gps=0;
  if(!native_up)native_up=wb_robot_get_device("range_up");
  if(!native_gps)native_gps=wb_robot_get_device("gps");
  if(!native_up||!native_gps)return result;
  const double *pose=wb_gps_get_values(native_gps);
  const double upper=wb_distance_sensor_get_value(native_up)/1000.0;
  const double now=wb_robot_get_time();
  if(pose&&isfinite(now)&&isfinite(pose[0])&&isfinite(pose[1])&&
     isfinite(pose[2])&&isfinite(upper)&&upper>=0.0&&upper<=2.001) {
    printf("WEBEEBLOCKS_A6_UP_MOTOR t=%.6f x=%.9f y=%.9f "
           "z=%.9f up=%.9f step=%d\n",
           now,pose[0],pose[1],pose[2],upper,duration);
    /* Flush bounded by 16 physics ticks; the runner also waits for the
     * native final LAND response before ending the Webots process. */
    static unsigned sample_count=0;
    if(++sample_count%16==0)fflush(stdout);
  } else {
    fprintf(stderr,"WEBEEBLOCKS_A6_UP_MOTOR_UNAVAILABLE\n");
    fflush(stderr);
  }
  return result;
}

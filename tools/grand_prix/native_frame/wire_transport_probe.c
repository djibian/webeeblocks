/* Test client for the exact R2025a Controller C API and scheduler. */
#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <webots/distance_sensor.h>
#include <webots/robot.h>
#include <webots/supervisor.h>
#include "messages.h"

int main(int argc, char **argv) {
  if (argc == 2 && strcmp(argv[1], "--describe") == 0) {
    printf("%d %d %d %d %d %d %d %d\n", WB_SUPERVISOR_PHYSICS_FRAME_VERSION, WB_NODE_ROBOT,
           WB_NODE_DISTANCE_SENSOR, C_CONFIGURE, C_ROBOT_TIME, C_DISTANCE_SENSOR_DATA,
           C_SUPERVISOR_PHYSICS_FRAME, WB_SUPERVISOR_SIMULATION_MODE_FAST);
    return 0;
  }

  wb_robot_init();
  const WbDeviceTag sensor = wb_robot_get_device("distance");
  if (!sensor || !wb_robot_get_supervisor() || wb_robot_get_basic_time_step() != 8.0)
    return 1;
  wb_distance_sensor_enable(sensor, 8);
  for (int step = 1; step <= 12; ++step) {
    WbSupervisorPhysicsFrame frame;
    memset(&frame, 0, sizeof(frame));
    if (!wb_supervisor_physics_frame_request(2) || wb_robot_step(8) < 0)
      return 2;
    const bool received = wb_supervisor_physics_frame_read(&frame);
    const double time = wb_robot_get_time();
    const double value = wb_distance_sensor_get_value(sensor);
    printf("{\"tick\":%d,\"time_ms\":%.0f,\"distance\":%.3f,\"frame\":%s}\n",
           step, time * 1000.0, value, received ? "true" : "false");
    fflush(stdout);
    if (fabs(time * 1000.0 - step * 8.0) > 1e-8 || value != 100.0 + step ||
        received != (step % 2 == 1) || wb_supervisor_physics_frame_read(&frame) ||
        (received && (frame.time_ms != step * 8.0 || frame.solid_id != 2 ||
                      frame.supervisor_id != 1 || frame.contact_count != 0)))
      return 3;
  }
  wb_robot_cleanup();
  return 0;
}

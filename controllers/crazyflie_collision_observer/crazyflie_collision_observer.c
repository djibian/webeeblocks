#include <math.h>
#include <stdio.h>
#include <webots/contact_point.h>
#include <webots/robot.h>
#include <webots/supervisor.h>

#define OBSTACLE_X 1.25
#define OBSTACLE_HALF_THICKNESS 0.025
#define OBSTACLE_HALF_WIDTH 0.15
#define OBSTACLE_MIN_Z 0.0
#define OBSTACLE_MAX_Z 1.40
#define CONTACT_TOLERANCE 0.003

static int point_is_on_obstacle(const double point[3]) {
  return fabs(point[0] - OBSTACLE_X) <= OBSTACLE_HALF_THICKNESS + CONTACT_TOLERANCE &&
         fabs(point[1]) <= OBSTACLE_HALF_WIDTH + CONTACT_TOLERANCE &&
         point[2] >= OBSTACLE_MIN_Z - CONTACT_TOLERANCE &&
         point[2] <= OBSTACLE_MAX_Z + CONTACT_TOLERANCE;
}

int main(void) {
  wb_robot_init();
  const int step = (int)wb_robot_get_basic_time_step();
  WbNodeRef obstacle = wb_supervisor_node_get_from_def("OBSTACLE");
  WbNodeRef crazyflie = wb_supervisor_node_get_from_def("CRAZYFLIE");
  if (!obstacle || !crazyflie) {
    fprintf(stderr, "WEBEEBLOCKS_OBSTACLE_OBSERVER_ERROR missing DEF node\n");
    wb_robot_cleanup();
    return 2;
  }

  /*
   * Track the dynamic Crazyflie rather than the static obstacle.  The Webots
   * contact-point API guarantees that these are physical collision contacts;
   * the point location then identifies the pre-registered obstacle and filters
   * normal floor contacts during takeoff/landing.
   */
  wb_supervisor_node_enable_contact_points_tracking(crazyflie, step, true);
  printf("WEBEEBLOCKS_OBSTACLE_OBSERVER_READY\n");
  fflush(stdout);

  while (wb_robot_step(step) != -1) {
    int count = 0;
    WbContactPoint *points = wb_supervisor_node_get_contact_points(crazyflie, true, &count);
    for (int i = 0; i < count; ++i) {
      if (!point_is_on_obstacle(points[i].point))
        continue;

      char path[4096];
      snprintf(path, sizeof(path), "%s/ci-artifacts/crazyflie-obstacle-contact.txt",
               wb_robot_get_project_path());
      FILE *file = fopen(path, "w");
      if (file) {
        fprintf(file,
                "WEBEEBLOCKS_OBSTACLE_RESULT status=COLLISION time=%.3f x=%.6f y=%.6f z=%.6f node_id=%d\n",
                wb_robot_get_time(),
                points[i].point[0], points[i].point[1], points[i].point[2],
                points[i].node_id);
        fflush(file);
        fclose(file);
      }
      printf("WEBEEBLOCKS_OBSTACLE_RESULT status=COLLISION time=%.3f x=%.6f y=%.6f z=%.6f\n",
             wb_robot_get_time(), points[i].point[0], points[i].point[1], points[i].point[2]);
      fflush(stdout);
      wb_supervisor_simulation_quit(0);
      wb_robot_cleanup();
      return 0;
    }
  }

  wb_robot_cleanup();
  return 0;
}

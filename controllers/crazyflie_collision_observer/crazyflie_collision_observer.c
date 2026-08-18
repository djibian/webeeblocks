#include <stdio.h>
#include <webots/contact_point.h>
#include <webots/robot.h>
#include <webots/supervisor.h>

static int belongs_to(WbNodeRef node, WbNodeRef ancestor) {
  while (node) {
    if (node == ancestor)
      return 1;
    node = wb_supervisor_node_get_parent_node(node);
  }
  return 0;
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

  wb_supervisor_node_enable_contact_points_tracking(obstacle, step, true);
  printf("WEBEEBLOCKS_OBSTACLE_OBSERVER_READY\n");
  fflush(stdout);

  while (wb_robot_step(step) != -1) {
    int count = 0;
    WbContactPoint *points = wb_supervisor_node_get_contact_points(obstacle, true, &count);
    for (int i = 0; i < count; ++i) {
      WbNodeRef contacting = wb_supervisor_node_get_from_id(points[i].node_id);
      if (!contacting || !belongs_to(contacting, crazyflie))
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
      printf("WEBEEBLOCKS_OBSTACLE_RESULT status=COLLISION time=%.3f\n", wb_robot_get_time());
      fflush(stdout);
      wb_supervisor_simulation_quit(0);
      wb_robot_cleanup();
      return 0;
    }
  }

  wb_robot_cleanup();
  return 0;
}

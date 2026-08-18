#ifndef WEBEEBLOCKS_PRIMITIVES_H
#define WEBEEBLOCKS_PRIMITIVES_H

#include <math.h>

#ifndef WEBEEBLOCKS_PI
#define WEBEEBLOCKS_PI 3.14159265358979323846
#endif

typedef struct {
  double x;
  double y;
  double z;
  double yaw;
} webeeblocks_target_t;

static inline double webeeblocks_wrap_yaw(double yaw) {
  while (yaw > WEBEEBLOCKS_PI)
    yaw -= 2.0 * WEBEEBLOCKS_PI;
  while (yaw < -WEBEEBLOCKS_PI)
    yaw += 2.0 * WEBEEBLOCKS_PI;
  return yaw;
}

/*
 * Internal pedagogical navigation contract for backend B.
 *
 * These functions only translate a student-facing primitive into the next
 * absolute navigation target. PID gains, speed/yaw caps and completion
 * criteria remain owned by the existing backend B controller.
 */
static inline webeeblocks_target_t webeeblocks_takeoff(double x, double y, double ground_z,
                                                         double yaw, double height) {
  const webeeblocks_target_t target = {x, y, ground_z + height, yaw};
  return target;
}

static inline webeeblocks_target_t webeeblocks_forward(double x, double y, double z,
                                                         double yaw, double distance) {
  const webeeblocks_target_t target = {
    x + distance * cos(yaw),
    y + distance * sin(yaw),
    z,
    yaw,
  };
  return target;
}

static inline webeeblocks_target_t webeeblocks_turn(double x, double y, double z,
                                                      double yaw, double angle) {
  const webeeblocks_target_t target = {
    x,
    y,
    z,
    webeeblocks_wrap_yaw(yaw + angle),
  };
  return target;
}

static inline webeeblocks_target_t webeeblocks_land(double x, double y, double ground_z,
                                                      double yaw) {
  const webeeblocks_target_t target = {x, y, ground_z, yaw};
  return target;
}

#endif

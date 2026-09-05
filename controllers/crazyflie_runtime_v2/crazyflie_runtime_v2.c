#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <webots/distance_sensor.h>
#include <webots/gps.h>
#include <webots/gyro.h>
#include <webots/inertial_unit.h>
#include <webots/motor.h>
#include <webots/plugins/robot_window/default.h>
#include <webots/robot.h>
#include <webots/supervisor.h>

#include "pid_controller.h"

#define PI 3.14159265358979323846
#define PREFIX "WEBEEBLOCKS_RUNTIME_V2"
#define VX_MAX 0.35
#define POSITION_KP 1.0
#define YAW_KP 1.5
#define YAW_RATE_MAX 0.7
#define POSITION_TOL 0.03
#define YAW_TOL (2.0 * PI / 180.0)
#define SPEED_TOL 0.12
#define YAW_RATE_TOL 0.10
#define VZ_TOL 0.15
#define ALT_TOL 0.05
#define STOP_WINDOW 0.5
#define RESET_WINDOW 0.25
#define RESET_TIMEOUT 5.0
#define ACTION_TIMEOUT 25.0

typedef enum {
  CMD_IDLE,
  CMD_TAKEOFF,
  CMD_MOVE,
  CMD_VERTICAL,
  CMD_LAND,
  CMD_RESET
} command_t;

typedef enum {
  REQUEST_INVALID,
  REQUEST_TAKEOFF,
  REQUEST_MOVE,
  REQUEST_VERTICAL,
  REQUEST_LAND,
  REQUEST_RANGE,
  REQUEST_RESET,
  REQUEST_STOP
} request_kind_t;

typedef struct {
  int id;
  request_kind_t kind;
  char direction[32];
  double value;
} request_t;

static double clip(double value, double limit) {
  if (value > limit)
    return limit;
  if (value < -limit)
    return -limit;
  return value;
}

static void clip_vector(double *x, double *y, double limit) {
  const double magnitude = hypot(*x, *y);
  if (magnitude > limit && magnitude > 0.0) {
    const double scale = limit / magnitude;
    *x *= scale;
    *y *= scale;
  }
}

static double motor_power(double value) {
  if (value < 0.0)
    return 0.0;
  if (value > 600.0)
    return 600.0;
  return value;
}

static double wrap_angle(double angle) {
  while (angle > PI)
    angle -= 2.0 * PI;
  while (angle <= -PI)
    angle += 2.0 * PI;
  return angle;
}

static void stop_motors(WbDeviceTag m1, WbDeviceTag m2, WbDeviceTag m3, WbDeviceTag m4) {
  wb_motor_set_velocity(m1, 0.0);
  wb_motor_set_velocity(m2, 0.0);
  wb_motor_set_velocity(m3, 0.0);
  wb_motor_set_velocity(m4, 0.0);
}

static void send_text(const char *text) {
  wb_robot_wwi_send_text(text);
  printf("%s\n", text);
  fflush(stdout);
}

static void response_ok(int id) {
  char message[128];
  snprintf(message, sizeof(message), PREFIX " RESPONSE %d OK", id);
  send_text(message);
}

static void response_value(int id, double value) {
  char message[160];
  snprintf(message, sizeof(message), PREFIX " RESPONSE %d VALUE %.9f", id, value);
  send_text(message);
}

static void response_error(int id, const char *reason) {
  char message[160];
  snprintf(message, sizeof(message), PREFIX " RESPONSE %d ERR %s", id, reason);
  send_text(message);
}

static int extract_id(const char *message) {
  int id = -1;
  if (message)
    sscanf(message, PREFIX " REQUEST %d", &id);
  return id;
}

static request_t parse_request(const char *message) {
  request_t request;
  memset(&request, 0, sizeof(request));
  request.id = -1;
  request.kind = REQUEST_INVALID;

  int id = -1;
  double value = 0.0;
  char direction[32] = {0};
  char command[32] = {0};
  char extra[2] = {0};

  if (sscanf(message, PREFIX " REQUEST %d TAKEOFF %lf %1s", &id, &value, extra) == 2) {
    request.id = id;
    request.kind = REQUEST_TAKEOFF;
    request.value = value;
    return request;
  }
  if (sscanf(message, PREFIX " REQUEST %d MOVE %31s %lf %1s", &id, direction, &value, extra) == 3) {
    request.id = id;
    request.kind = REQUEST_MOVE;
    request.value = value;
    strncpy(request.direction, direction, sizeof(request.direction) - 1);
    return request;
  }
  if (sscanf(message, PREFIX " REQUEST %d VERTICAL %31s %lf %1s", &id, direction, &value, extra) == 3) {
    request.id = id;
    request.kind = REQUEST_VERTICAL;
    request.value = value;
    strncpy(request.direction, direction, sizeof(request.direction) - 1);
    return request;
  }
  if (sscanf(message, PREFIX " REQUEST %d RANGE %31s %1s", &id, direction, extra) == 2) {
    request.id = id;
    request.kind = REQUEST_RANGE;
    strncpy(request.direction, direction, sizeof(request.direction) - 1);
    return request;
  }
  if (sscanf(message, PREFIX " REQUEST %d %31s %1s", &id, command, extra) == 2) {
    request.id = id;
    if (strcmp(command, "LAND") == 0)
      request.kind = REQUEST_LAND;
    else if (strcmp(command, "RESET") == 0)
      request.kind = REQUEST_RESET;
    else if (strcmp(command, "STOP") == 0)
      request.kind = REQUEST_STOP;
    return request;
  }

  request.id = extract_id(message);
  return request;
}

static void trace_range(const char *direction, double value) {
  printf(PREFIX " TRACE RANGE %s value=%.9f\n", direction, value);
  fflush(stdout);
}

static void trace_takeoff(double value) {
  printf(PREFIX " TRACE TAKEOFF height=%.9f stop=1\n", value);
  fflush(stdout);
}

static void trace_move(const char *direction, double value) {
  printf(PREFIX " TRACE MOVE %s distance=%.9f stop=1\n", direction, value);
  fflush(stdout);
}

static void trace_vertical(const char *direction, double value) {
  printf(PREFIX " TRACE VERTICAL %s distance=%.9f stop=1\n", direction, value);
  fflush(stdout);
}

static void trace_land(void) {
  printf(PREFIX " TRACE LAND stop=1\n");
  fflush(stdout);
}

static void trace_reset(double x, double y, double z, double origin_x, double origin_y, double origin_z) {
  printf(PREFIX " TRACE RESET x=%.9f y=%.9f z=%.9f origin_x=%.9f origin_y=%.9f origin_z=%.9f\n",
         x, y, z, origin_x, origin_y, origin_z);
  fflush(stdout);
}

int main(void) {
  wb_robot_init();
  const int step = (int)wb_robot_get_basic_time_step();

  WbDeviceTag m1 = wb_robot_get_device("m1_motor");
  WbDeviceTag m2 = wb_robot_get_device("m2_motor");
  WbDeviceTag m3 = wb_robot_get_device("m3_motor");
  WbDeviceTag m4 = wb_robot_get_device("m4_motor");
  WbDeviceTag gps = wb_robot_get_device("gps");
  WbDeviceTag imu = wb_robot_get_device("inertial_unit");
  WbDeviceTag gyro = wb_robot_get_device("gyro");
  WbDeviceTag range_front = wb_robot_get_device("range_front");
  WbDeviceTag range_left = wb_robot_get_device("range_left");
  WbDeviceTag range_right = wb_robot_get_device("range_right");

  if (!m1 || !m2 || !m3 || !m4 || !gps || !imu || !gyro || !range_front || !range_left || !range_right) {
    fprintf(stderr, PREFIX " FATAL missing required Webots device\n");
    wb_robot_cleanup();
    return 1;
  }

  WbNodeRef self_node = wb_supervisor_node_get_self();
  WbFieldRef translation_field = self_node ? wb_supervisor_node_get_field(self_node, "translation") : 0;
  WbFieldRef rotation_field = self_node ? wb_supervisor_node_get_field(self_node, "rotation") : 0;
  if (!self_node || !translation_field || !rotation_field) {
    fprintf(stderr, PREFIX " FATAL supervisor reset fields unavailable\n");
    wb_robot_cleanup();
    return 1;
  }
  const double *initial_translation_ref = wb_supervisor_field_get_sf_vec3f(translation_field);
  const double *initial_rotation_ref = wb_supervisor_field_get_sf_rotation(rotation_field);
  double initial_translation[3] = {initial_translation_ref[0], initial_translation_ref[1], initial_translation_ref[2]};
  double initial_rotation[4] = {initial_rotation_ref[0], initial_rotation_ref[1], initial_rotation_ref[2], initial_rotation_ref[3]};

  wb_motor_set_position(m1, INFINITY);
  wb_motor_set_position(m2, INFINITY);
  wb_motor_set_position(m3, INFINITY);
  wb_motor_set_position(m4, INFINITY);
  stop_motors(m1, m2, m3, m4);

  wb_gps_enable(gps, step);
  wb_inertial_unit_enable(imu, step);
  wb_gyro_enable(gyro, step);
  wb_distance_sensor_enable(range_front, step);
  wb_distance_sensor_enable(range_left, step);
  wb_distance_sensor_enable(range_right, step);

  while (wb_robot_step(step) != -1 && wb_robot_get_time() < 2.0) {
  }

  const double *position = wb_gps_get_values(gps);
  const double *rpy = wb_inertial_unit_get_roll_pitch_yaw(imu);
  const double origin_x = position[0];
  const double origin_y = position[1];
  const double origin_z = position[2];
  const double origin_roll = rpy[0];
  const double origin_pitch = rpy[1];
  const double origin_yaw = rpy[2];
  double target_x = origin_x;
  double target_y = origin_y;
  double target_z = origin_z;
  double target_yaw = origin_yaw;

  double previous_x = position[0];
  double previous_y = position[1];
  double previous_z = position[2];
  double previous_time = wb_robot_get_time();

  int airborne = 0;
  int failsafe_latched = 0;
  command_t command = CMD_IDLE;
  int active_id = -1;
  double active_value = 0.0;
  char active_direction[32] = {0};
  double stable_since = -1.0;
  double action_start = 0.0;

  gains_pid_t gains;
  memset(&gains, 0, sizeof(gains));
  gains.kp_att_y = 1.0;
  gains.kd_att_y = 0.5;
  gains.kp_att_rp = 0.5;
  gains.kd_att_rp = 0.1;
  gains.kp_vel_xy = 2.0;
  gains.kd_vel_xy = 0.5;
  gains.kp_z = 10.0;
  gains.ki_z = 5.0;
  gains.kd_z = 5.0;
  init_pid_attitude_fixed_height_controller();

  actual_state_t actual;
  desired_state_t desired;
  motor_power_t power;
  memset(&actual, 0, sizeof(actual));
  memset(&desired, 0, sizeof(desired));
  memset(&power, 0, sizeof(power));

  send_text(PREFIX " READY");

  while (wb_robot_step(step) != -1) {
    const double now = wb_robot_get_time();
    const double dt = now - previous_time;
    if (dt <= 0.0)
      continue;

    position = wb_gps_get_values(gps);
    rpy = wb_inertial_unit_get_roll_pitch_yaw(imu);
    const double *gyro_values = wb_gyro_get_values(gyro);
    const double x = position[0];
    const double y = position[1];
    const double z = position[2];
    const double yaw = rpy[2];
    const double vx_global = (x - previous_x) / dt;
    const double vy_global = (y - previous_y) / dt;
    const double vz = (z - previous_z) / dt;
    const double cy = cos(yaw);
    const double sy = sin(yaw);

    actual.roll = rpy[0];
    actual.pitch = rpy[1];
    actual.yaw_rate = gyro_values[2];
    actual.altitude = z;
    actual.vx = vx_global * cy + vy_global * sy;
    actual.vy = -vx_global * sy + vy_global * cy;

    desired.roll = 0.0;
    desired.pitch = 0.0;
    desired.vx = 0.0;
    desired.vy = 0.0;
    desired.yaw_rate = 0.0;
    desired.altitude = airborne ? target_z : origin_z;

    const char *message;
    while ((message = wb_robot_wwi_receive_text()) != NULL) {
      if (strncmp(message, PREFIX " REQUEST ", strlen(PREFIX " REQUEST ")) != 0)
        continue;
      request_t request = parse_request(message);
      if (request.id < 1)
        continue;
      if (request.kind == REQUEST_INVALID) {
        response_error(request.id, "INVALID_REQUEST");
        continue;
      }
      if (request.kind == REQUEST_STOP) {
        if (command == CMD_RESET) {
          response_error(request.id, "NOT_RUNNING");
          continue;
        }
        if (active_id >= 1)
          response_error(active_id, "USER_STOPPED");
        target_x = x;
        target_y = y;
        target_z = z;
        target_yaw = yaw;
        airborne = z > origin_z + ALT_TOL ? 1 : 0;
        failsafe_latched = 1;
        command = CMD_IDLE;
        active_id = -1;
        active_value = 0.0;
        active_direction[0] = '\0';
        stable_since = -1.0;
        response_ok(request.id);
        if (!airborne)
          stop_motors(m1, m2, m3, m4);
        continue;
      }
      if (command != CMD_IDLE) {
        response_error(request.id, "BUSY");
        continue;
      }
      if (request.kind == REQUEST_RESET) {
        stop_motors(m1, m2, m3, m4);
        wb_supervisor_field_set_sf_vec3f(translation_field, initial_translation);
        wb_supervisor_field_set_sf_rotation(rotation_field, initial_rotation);
        wb_supervisor_node_reset_physics(self_node);
        init_pid_attitude_fixed_height_controller();
        airborne = 0;
        failsafe_latched = 0;
        target_x = origin_x;
        target_y = origin_y;
        target_z = origin_z;
        target_yaw = origin_yaw;
        active_id = request.id;
        active_value = 0.0;
        active_direction[0] = '\0';
        command = CMD_RESET;
        stable_since = -1.0;
        action_start = now;
        continue;
      }
      if (failsafe_latched) {
        response_error(request.id, "RESET_REQUIRED");
        continue;
      }
      if (request.kind == REQUEST_RANGE) {
        WbDeviceTag range_sensor = 0;
        if (strcmp(request.direction, "front") == 0)
          range_sensor = range_front;
        else if (strcmp(request.direction, "left") == 0)
          range_sensor = range_left;
        else if (strcmp(request.direction, "right") == 0)
          range_sensor = range_right;
        if (!range_sensor) {
          response_error(request.id, "CAPABILITY_UNAVAILABLE");
          continue;
        }
        const double range_m = wb_distance_sensor_get_value(range_sensor) / 1000.0;
        if (!isfinite(range_m) || range_m < 0.0 || range_m > 2.001) {
          response_error(request.id, "INVALID_RANGE_SAMPLE");
          continue;
        }
        trace_range(request.direction, range_m);
        response_value(request.id, range_m);
        continue;
      }
      if (request.kind == REQUEST_TAKEOFF) {
        if (airborne || !isfinite(request.value) || request.value < 0.2 || request.value > 1.5) {
          response_error(request.id, "INVALID_TAKEOFF");
          continue;
        }
        active_id = request.id;
        active_value = request.value;
        active_direction[0] = '\0';
        target_x = x;
        target_y = y;
        target_yaw = yaw;
        target_z = origin_z + request.value;
        command = CMD_TAKEOFF;
        stable_since = -1.0;
        action_start = now;
        continue;
      }
      if (request.kind == REQUEST_MOVE) {
        if (!airborne || !isfinite(request.value) || request.value < 0.1 || request.value > 2.0 ||
            (strcmp(request.direction, "forward") != 0 && strcmp(request.direction, "back") != 0 &&
             strcmp(request.direction, "left") != 0 && strcmp(request.direction, "right") != 0)) {
          response_error(request.id, "INVALID_MOVE");
          continue;
        }
        active_id = request.id;
        active_value = request.value;
        strncpy(active_direction, request.direction, sizeof(active_direction) - 1);
        active_direction[sizeof(active_direction) - 1] = '\0';
        target_yaw = yaw;
        if (strcmp(request.direction, "forward") == 0) {
          target_x = x + cos(yaw) * request.value;
          target_y = y + sin(yaw) * request.value;
        } else if (strcmp(request.direction, "back") == 0) {
          target_x = x - cos(yaw) * request.value;
          target_y = y - sin(yaw) * request.value;
        } else if (strcmp(request.direction, "left") == 0) {
          target_x = x - sin(yaw) * request.value;
          target_y = y + cos(yaw) * request.value;
        } else {
          target_x = x + sin(yaw) * request.value;
          target_y = y - cos(yaw) * request.value;
        }
        command = CMD_MOVE;
        stable_since = -1.0;
        action_start = now;
        continue;
      }
      if (request.kind == REQUEST_VERTICAL) {
        if (!airborne || !isfinite(request.value) || request.value < 0.1 || request.value > 0.8 ||
            (strcmp(request.direction, "up") != 0 && strcmp(request.direction, "down") != 0)) {
          response_error(request.id, "INVALID_VERTICAL");
          continue;
        }
        const double next_target_z = z + (strcmp(request.direction, "up") == 0 ? request.value : -request.value);
        if (next_target_z < origin_z + 0.2 || next_target_z > origin_z + 1.5) {
          response_error(request.id, "VERTICAL_LIMIT");
          continue;
        }
        active_id = request.id;
        active_value = request.value;
        strncpy(active_direction, request.direction, sizeof(active_direction) - 1);
        active_direction[sizeof(active_direction) - 1] = '\0';
        target_x = x;
        target_y = y;
        target_yaw = yaw;
        target_z = next_target_z;
        command = CMD_VERTICAL;
        stable_since = -1.0;
        action_start = now;
        continue;
      }
      if (request.kind == REQUEST_LAND) {
        if (!airborne) {
          response_error(request.id, "INVALID_LAND");
          continue;
        }
        active_id = request.id;
        active_value = 0.0;
        active_direction[0] = '\0';
        target_z = origin_z;
        command = CMD_LAND;
        stable_since = -1.0;
        action_start = now;
      }
    }

    if (command != CMD_IDLE && command != CMD_RESET &&
        (fabs(actual.roll) > 1.2 || fabs(actual.pitch) > 1.2 || now - action_start > ACTION_TIMEOUT)) {
      response_error(active_id, "UNSAFE_OR_TIMEOUT");
      fprintf(stderr, PREFIX " FATAL unsafe attitude or action timeout\n");
      stop_motors(m1, m2, m3, m4);
      airborne = 0;
      failsafe_latched = 1;
      command = CMD_IDLE;
      active_id = -1;
      stable_since = -1.0;
      previous_time = now;
      previous_x = x;
      previous_y = y;
      previous_z = z;
      continue;
    }

    if (command == CMD_RESET && now - action_start > RESET_TIMEOUT) {
      response_error(active_id, "RESET_TIMEOUT");
      stop_motors(m1, m2, m3, m4);
      airborne = 0;
      failsafe_latched = 1;
      command = CMD_IDLE;
      active_id = -1;
      stable_since = -1.0;
      previous_time = now;
      previous_x = x;
      previous_y = y;
      previous_z = z;
      continue;
    }

    if (command == CMD_RESET) {
      stop_motors(m1, m2, m3, m4);
      const int pose_ready = fabs(x - origin_x) < POSITION_TOL && fabs(y - origin_y) < POSITION_TOL &&
                             fabs(z - origin_z) < ALT_TOL && fabs(rpy[0] - origin_roll) < YAW_TOL &&
                             fabs(rpy[1] - origin_pitch) < YAW_TOL && fabs(wrap_angle(yaw - origin_yaw)) < YAW_TOL;
      const int motion_ready = hypot(actual.vx, actual.vy) < SPEED_TOL && fabs(vz) < VZ_TOL &&
                               fabs(actual.yaw_rate) < YAW_RATE_TOL;
      if (pose_ready && motion_ready) {
        if (stable_since < 0.0)
          stable_since = now;
        if (now - stable_since >= RESET_WINDOW) {
          trace_reset(x, y, z, origin_x, origin_y, origin_z);
          response_ok(active_id);
          command = CMD_IDLE;
          active_id = -1;
          stable_since = -1.0;
        }
      } else {
        stable_since = -1.0;
      }
      previous_time = now;
      previous_x = x;
      previous_y = y;
      previous_z = z;
      continue;
    }

    if (command == CMD_TAKEOFF) {
      desired.altitude = target_z;
      if (fabs(z - target_z) < ALT_TOL && fabs(vz) < VZ_TOL && hypot(actual.vx, actual.vy) < SPEED_TOL &&
          fabs(actual.yaw_rate) < YAW_RATE_TOL) {
        if (stable_since < 0.0)
          stable_since = now;
        if (now - stable_since >= STOP_WINDOW) {
          airborne = 1;
          trace_takeoff(active_value);
          response_ok(active_id);
          command = CMD_IDLE;
          stable_since = -1.0;
        }
      } else {
        stable_since = -1.0;
      }
    } else if (command == CMD_MOVE) {
      const double error_x = target_x - x;
      const double error_y = target_y - y;
      const double body_x = error_x * cy + error_y * sy;
      const double body_y = -error_x * sy + error_y * cy;
      desired.vx = POSITION_KP * body_x;
      desired.vy = POSITION_KP * body_y;
      clip_vector(&desired.vx, &desired.vy, VX_MAX);
      desired.yaw_rate = clip(YAW_KP * wrap_angle(target_yaw - yaw), YAW_RATE_MAX);
      desired.altitude = target_z;
      if (hypot(error_x, error_y) <= POSITION_TOL && fabs(wrap_angle(target_yaw - yaw)) <= YAW_TOL &&
          hypot(actual.vx, actual.vy) < SPEED_TOL && fabs(actual.yaw_rate) < YAW_RATE_TOL && fabs(vz) < VZ_TOL &&
          fabs(z - target_z) < ALT_TOL) {
        if (stable_since < 0.0)
          stable_since = now;
        if (now - stable_since >= STOP_WINDOW) {
          trace_move(active_direction, active_value);
          response_ok(active_id);
          command = CMD_IDLE;
          stable_since = -1.0;
        }
      } else {
        stable_since = -1.0;
      }
    } else if (command == CMD_VERTICAL) {
      const double error_x = target_x - x;
      const double error_y = target_y - y;
      const double body_x = error_x * cy + error_y * sy;
      const double body_y = -error_x * sy + error_y * cy;
      desired.vx = POSITION_KP * body_x;
      desired.vy = POSITION_KP * body_y;
      clip_vector(&desired.vx, &desired.vy, VX_MAX);
      desired.yaw_rate = clip(YAW_KP * wrap_angle(target_yaw - yaw), YAW_RATE_MAX);
      desired.altitude = target_z;
      if (hypot(error_x, error_y) <= POSITION_TOL && fabs(wrap_angle(target_yaw - yaw)) <= YAW_TOL &&
          hypot(actual.vx, actual.vy) < SPEED_TOL && fabs(actual.yaw_rate) < YAW_RATE_TOL && fabs(vz) < VZ_TOL &&
          fabs(z - target_z) < ALT_TOL) {
        if (stable_since < 0.0)
          stable_since = now;
        if (now - stable_since >= STOP_WINDOW) {
          trace_vertical(active_direction, active_value);
          response_ok(active_id);
          command = CMD_IDLE;
          stable_since = -1.0;
        }
      } else {
        stable_since = -1.0;
      }
    } else if (command == CMD_LAND) {
      desired.altitude = origin_z;
      if (z <= origin_z + ALT_TOL && fabs(vz) < VZ_TOL) {
        if (stable_since < 0.0)
          stable_since = now;
        if (now - stable_since >= STOP_WINDOW) {
          stop_motors(m1, m2, m3, m4);
          airborne = 0;
          trace_land();
          response_ok(active_id);
          command = CMD_IDLE;
          stable_since = -1.0;
          previous_time = now;
          previous_x = x;
          previous_y = y;
          previous_z = z;
          continue;
        }
      } else {
        stable_since = -1.0;
      }
    } else if (airborne) {
      const double error_x = target_x - x;
      const double error_y = target_y - y;
      const double body_x = error_x * cy + error_y * sy;
      const double body_y = -error_x * sy + error_y * cy;
      desired.vx = POSITION_KP * body_x;
      desired.vy = POSITION_KP * body_y;
      clip_vector(&desired.vx, &desired.vy, VX_MAX);
      desired.yaw_rate = clip(YAW_KP * wrap_angle(target_yaw - yaw), YAW_RATE_MAX);
      desired.altitude = target_z;
    }

    if (airborne || command != CMD_IDLE) {
      pid_velocity_fixed_height_controller(actual, &desired, gains, dt, &power);
      wb_motor_set_velocity(m1, -motor_power(power.m1));
      wb_motor_set_velocity(m2, motor_power(power.m2));
      wb_motor_set_velocity(m3, -motor_power(power.m3));
      wb_motor_set_velocity(m4, motor_power(power.m4));
    } else {
      stop_motors(m1, m2, m3, m4);
    }

    previous_time = now;
    previous_x = x;
    previous_y = y;
    previous_z = z;
  }

  stop_motors(m1, m2, m3, m4);
  wb_robot_cleanup();
  return 0;
}

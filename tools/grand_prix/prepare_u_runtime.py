"""Bounded build-time extension of CURRENT shared simulation flight source.
No shared controller or physical source is edited. Changed anchors refuse.
"""
import hashlib
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
def prepare(output_dir=None, *, legacy_worlds=True, route_observations=False):
    source=(ROOT/'controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c').read_text()
    edits=[
      ('''        if (now - stable_since >= STOP_WINDOW) {
          stop_motors(m1, m2, m3, m4);''',
       '''        /* LAND must not ACK on vertical-only stability before the full
           independent ground observation that RESET already requires. */
        if (now - stable_since >= STOP_WINDOW && gp_ground_sample &&
            gp_ground_since >= 0.0 && now - gp_ground_since >= STOP_WINDOW) {
          stop_motors(m1, m2, m3, m4);
          printf("GP_U_LAND_GROUND_READY t=%.9f window=%.9f\\n",
                 now, now - gp_ground_since);
          fflush(stdout);'''),
      ('''static double wrap_angle(double angle) {
  while (angle > PI)
    angle -= 2.0 * PI;
  while (angle <= -PI)
    angle += 2.0 * PI;
  return angle;
}''', '''/* Every composed angle path must terminate, including malformed input.
   Do not normalize an invalid IMU observation into a plausible attitude. */
static int gp_valid_attitude(const double *rpy) {
  return rpy && isfinite(rpy[0]) && isfinite(rpy[1]) && isfinite(rpy[2]) &&
    fabs(rpy[0]) <= PI && fabs(rpy[1]) <= PI / 2.0 && fabs(rpy[2]) <= PI;
}
static double wrap_angle(double angle) {
  if (!isfinite(angle)) return NAN;
  angle = fmod(angle, 2.0 * PI);
  if (angle > PI) angle -= 2.0 * PI;
  if (angle <= -PI) angle += 2.0 * PI;
  return angle;
}'''),
      ('  const double origin_x = position[0];', '''  if (!position || !isfinite(position[0]) || !isfinite(position[1]) ||
      !isfinite(position[2]) || !gp_valid_attitude(rpy)) {
    fprintf(stderr, "GP_U_PREPARE_ERROR invalid_initial_pose\\n");
    wb_robot_cleanup(); return 1;
  }
  const double origin_x = position[0];'''),
      ('  double land_start_z = origin_z;',
       '''  /* Native LAND contact diagnostics: observational, never decision authority. */
  double gp_land_diag_at = -1.0;
  int gp_land_diag_id = -1;
  unsigned long gp_land_diag_count = 0;
  unsigned long gp_land_diag_fails[9] = {0};
  double land_start_z = origin_z;'''),
      ('  double stable_since = -1.0;',
       '  double stable_since = -1.0;\n  double gp_ground_since = -1.0;'),
      ('  const int step = (int)wb_robot_get_basic_time_step();',
       '  const int step = 32; /* Preserve the shared PID/sensor update period. */'),
      ('  while (wb_robot_step(step) != -1) {',
       '  while (wb_robot_step(gp_u_next_step(step)) != -1) {'),
      ('    if (dt <= 0.0)\n      continue;',
       '    if (dt <= 0.0) {\n      gp_ground_since = -1.0;\n      stable_since = -1.0;\n      continue;\n    }'),
      ('    const double x = position[0];', '''    /* Unavailable native measurements must revoke confirmation, not crash. */
    const double gp_missing[3] = {NAN, NAN, NAN};
    if (!position) position = gp_missing;
    if (!gp_valid_attitude(rpy)) rpy = gp_missing;
    if (!gyro_values) gyro_values = gp_missing;
    const double x = position[0];'''),
      ('  send_text(PREFIX " READY");', '''  if ((long long)llround(wb_robot_get_basic_time_step()) != 8) {
    fprintf(stderr, "GP_U_PREPARE_ERROR required_basic_step_ms=8\\n");
    wb_robot_cleanup(); return 1;
  }
  send_text(PREFIX " READY");'''),
      ('    const char *message;\n    while ((message = wb_robot_wwi_receive_text()) != NULL) {', '''    /* IDLE/airborne=0 also follows UNSAFE_OR_TIMEOUT: it is not a pose.
       Confirm fresh, finite ground observations independently of command state.
       A lost sample/gap revokes the whole continuous stability window. */
    const int gp_control_sample = isfinite(now) && isfinite(dt) && dt <= 0.032001 &&
      isfinite(x) && isfinite(y) && isfinite(z) && isfinite(origin_z) &&
      isfinite(vx_global) && isfinite(vy_global) && isfinite(vz) &&
      isfinite(rpy[0]) && isfinite(rpy[1]) && isfinite(rpy[2]) &&
      isfinite(gyro_values[0]) && isfinite(gyro_values[1]) && isfinite(gyro_values[2]);
    const int gp_ground_sample = gp_control_sample &&
      fabs(z - origin_z) < ALT_TOL && hypot(vx_global, vy_global) < SPEED_TOL &&
      fabs(vz) < VZ_TOL && fabs(rpy[0] - origin_roll) < YAW_TOL &&
      fabs(rpy[1] - origin_pitch) < YAW_TOL &&
      fabs(gyro_values[0]) < YAW_RATE_TOL && fabs(gyro_values[1]) < YAW_RATE_TOL &&
      fabs(gyro_values[2]) < YAW_RATE_TOL;
    if (!gp_ground_sample) gp_ground_since = -1.0;
    else if (gp_ground_since < 0.0) gp_ground_since = now;
    const int gp_pose_confirmed = !airborne && command == CMD_IDLE &&
      gp_ground_since >= 0.0 && now - gp_ground_since >= STOP_WINDOW;
    if (gp_u_deadline(now, gp_pose_confirmed)) {
      simulation_clock_revoke(&program_clock);
      const int interrupted_id = active_id;
      if (active_id >= 1) response_error(active_id, "TIME_LIMIT");
      target_x = x; target_y = y; target_yaw = yaw; target_z = origin_z;
      land_start_z = z; /* Immediate LAND reference starts at the expiry pose. */
      land_touchdown = 0;
      airborne = 1; /* Native LAND also completes if already grounded. */
      command = CMD_LAND; active_id = 2147483646;
      active_value = 0.0; active_direction[0] = '\\0';
      stable_since = -1.0; action_start = now;
      printf("GP_U_DEADLINE time_ms=%lld command=LAND interrupted_id=%d\\n",
             (long long)llround(now * 1000.0), interrupted_id);
      fflush(stdout);
    }
    const char *message;
    /* Re-evaluate after each runtime request, before draining the broker.
       An admitted TAKEOFF/RESET in this same tick must close file access. */
    while ((gp_u_file_idle(command == CMD_IDLE && !airborne && gp_ground_sample),
            (message = wb_robot_wwi_receive_text())) != NULL) {'''),
      ('    const int gp_pose_confirmed = !airborne',
       '''    /* After genuine touchdown, compare exact raw sensor inputs with each
       * unchanged GP ground predicate. Counts include intermediate failures
       * (which a half-second snapshot alone could miss). Not used by control. */
    if (command == CMD_LAND && land_touchdown) {
      if (gp_land_diag_id != active_id) {
        gp_land_diag_id = active_id;
        gp_land_diag_at = -1.0;
        gp_land_diag_count = 0;
        for (int k = 0; k < 9; ++k) gp_land_diag_fails[k] = 0;
      }
      const int gp_land_bad[9] = {
        !gp_control_sample,
        !(fabs(z - origin_z) < ALT_TOL),
        !(hypot(vx_global, vy_global) < SPEED_TOL),
        !(fabs(vz) < VZ_TOL),
        !(fabs(rpy[0] - origin_roll) < YAW_TOL),
        !(fabs(rpy[1] - origin_pitch) < YAW_TOL),
        !(fabs(gyro_values[0]) < YAW_RATE_TOL),
        !(fabs(gyro_values[1]) < YAW_RATE_TOL),
        !(fabs(gyro_values[2]) < YAW_RATE_TOL)
      };
      ++gp_land_diag_count;
      for (int k = 0; k < 9; ++k)
        if (gp_land_bad[k]) ++gp_land_diag_fails[k];
      if (gp_land_diag_at < 0.0 || now - gp_land_diag_at >= 0.5) {
        int gp_contact_count = 0;
        const WbContactPoint *gp_contacts =
          wb_supervisor_node_get_contact_points(self_node, true, &gp_contact_count);
        double gp_lowest_contact = NAN;
        for (int k = 0; gp_contacts && k < gp_contact_count; ++k)
          if (isfinite(gp_contacts[k].point[2]) &&
              (!isfinite(gp_lowest_contact) || gp_contacts[k].point[2] < gp_lowest_contact))
            gp_lowest_contact = gp_contacts[k].point[2];
        printf("GP_U_LAND_DIAG t=%.6f id=%d ground=%d window=%.6f "
               "dt=%.6f z=%.8f origin_z=%.8f vx=%.6f vy=%.6f vz=%.6f "
               "roll=%.6f pitch=%.6f origin_roll=%.6f origin_pitch=%.6f "
               "gyro=%.6f,%.6f,%.6f contacts=%d lowest_contact=%.8f "
               "samples=%lu reject=control:%lu,z:%lu,xy:%lu,vz:%lu,"
               "roll:%lu,pitch:%lu,gx:%lu,gy:%lu,gz:%lu\\n",
               now, active_id, gp_ground_sample,
               gp_ground_since < 0.0 ? -1.0 : now - gp_ground_since,
               dt, z, origin_z, vx_global, vy_global, vz,
               rpy[0], rpy[1], origin_roll, origin_pitch,
               gyro_values[0], gyro_values[1], gyro_values[2],
               gp_contact_count, gp_lowest_contact, gp_land_diag_count,
               gp_land_diag_fails[0], gp_land_diag_fails[1],
               gp_land_diag_fails[2], gp_land_diag_fails[3],
               gp_land_diag_fails[4], gp_land_diag_fails[5],
               gp_land_diag_fails[6], gp_land_diag_fails[7], gp_land_diag_fails[8]);
        fflush(stdout);
        gp_land_diag_at = now;
        gp_land_diag_count = 0;
        for (int k = 0; k < 9; ++k) gp_land_diag_fails[k] = 0;
      }
    }
    const int gp_pose_confirmed = !airborne'''),
      ('        simulation_clock_begin(&program_clock, now);\n        command = CMD_TAKEOFF;', '''        simulation_clock_begin(&program_clock, now);
        if (!gp_u_start(now)) {
          simulation_clock_revoke(&program_clock);
          response_error(active_id, "INVALID_ATTEMPT");
          active_id = -1; command = CMD_IDLE;
          continue;
        }
        gp_ground_since = -1.0;
        command = CMD_TAKEOFF;'''),
      ('      if (request.kind == REQUEST_STOP) {', '''      /* The deadline already ran for this tick. Refuse malformed samples
         before any command can consume them; RESET still times out natively. */
      if (!gp_control_sample) {
        response_error(request.id, "UNSAFE_OR_TIMEOUT");
        continue;
      }
      if (request.kind == REQUEST_STOP) {'''),
      ('''    if (command != CMD_IDLE && command != CMD_RESET &&
        (fabs(actual.roll) > 1.2 || fabs(actual.pitch) > 1.2 || now - action_start > ACTION_TIMEOUT)) {''',
       '''    if (command != CMD_RESET &&
        ((!gp_control_sample && (airborne || command != CMD_IDLE)) ||
         (command != CMD_IDLE && (fabs(actual.roll) > 1.2 || fabs(actual.pitch) > 1.2 || now - action_start > ACTION_TIMEOUT)))) {'''),
      ('        command = CMD_RESET;',
       '        gp_ground_since = -1.0; /* Require post-teleport observations. */\n        command = CMD_RESET;'),
      ('      if (pose_ready && motion_ready) {',
       '      if (pose_ready && motion_ready && gp_ground_sample && now > action_start) {'),
      ('      const int pose_ready = fabs(x - origin_x)',
       '      const int pose_ready = gp_ground_sample && fabs(x - origin_x)'),
      ('        if (now - stable_since >= RESET_WINDOW) {',
       '''        /* The administrative RESET window cannot finalize recovery.
           Every observation since teleport/loss must confirm the full pose. */
        if (now - stable_since >= STOP_WINDOW) {'''),
      ('          trace_reset(x, y, z, origin_x, origin_y, origin_z);\n          response_ok(active_id);',
       '          trace_reset(x, y, z, origin_x, origin_y, origin_z);\n          response_ok(active_id);\n          gp_ground_since = -1.0;\n          gp_u_reset_complete();')]
    result=source
    for old,new in edits:
        if result.count(old)!=1:raise RuntimeError('shared Runtime anchor changed; revalidation required')
        result=result.replace(old,new)
    if route_observations:
        anchor='    if (gp_u_deadline(now, gp_pose_confirmed)) {'
        if result.count(anchor)!=1:
            raise RuntimeError('native route observation anchor changed; revalidation required')
        result=result.replace(anchor, '''    /* Host-only evidence, measured on this Robot, after the native step.
       Verify the effective 32-ms device periods without assuming phase zero. */
    const double gp_route_ranges[5] = {
      wb_distance_sensor_get_value(range_front) / 1000.0,
      wb_distance_sensor_get_value(range_back) / 1000.0,
      wb_distance_sensor_get_value(range_left) / 1000.0,
      wb_distance_sensor_get_value(range_right) / 1000.0,
      wb_distance_sensor_get_value(range_up) / 1000.0
    };
    const int gp_route_periods_valid =
      wb_distance_sensor_get_sampling_period(range_front) == step &&
      wb_distance_sensor_get_sampling_period(range_back) == step &&
      wb_distance_sensor_get_sampling_period(range_left) == step &&
      wb_distance_sensor_get_sampling_period(range_right) == step &&
      wb_distance_sensor_get_sampling_period(range_up) == step;
    gp_route_observe_native(now, gp_control_sample && gp_route_periods_valid,
                            gp_pose_confirmed, gp_route_ranges);
''' + anchor, 1)
    if route_observations:
        # A continuous native-feedback reference for every valid TAKEOFF
        # altitude. Critically, the legacy U and shared PID sources are intact.
        # Changing these exact anchors must fail closed on composition.
        route_edits = [
          ('#include "pid_controller.h"',
           '#include "pid_controller.h"\n#include "../gp_route_takeoff_profile.h"'),
          ('  double target_z = origin_z;',
           '  double target_z = origin_z;\n'
           '  gp_route_takeoff_profile_t gp_route_takeoff = {origin_z, 0.0};'),
          ('        target_z = origin_z + request.value;\n'
           '        simulation_clock_begin(&program_clock, now);',
           '        target_z = origin_z + request.value;\n'
           '        gp_route_takeoff_begin(&gp_route_takeoff, z);\n'
           '        simulation_clock_begin(&program_clock, now);'),
          ('    if (command == CMD_TAKEOFF) {\n      desired.altitude = target_z;',
           '    if (command == CMD_TAKEOFF) {\n'
           '      desired.altitude = gp_route_takeoff_next(&gp_route_takeoff,\n'
           '        target_z, z, vz, dt);\n'
           '      if (!isfinite(desired.altitude)) {\n'
           '        response_error(active_id, "UNSAFE_OR_TIMEOUT");\n'
           '        stop_motors(m1, m2, m3, m4);\n'
           '        airborne = 0; simulation_clock_revoke(&program_clock);\n'
           '        failsafe_latched = 1; command = CMD_IDLE; active_id = -1;\n'
           '        stable_since = -1.0;\n'
           '        previous_time = now; previous_x = x; previous_y = y; previous_z = z;\n'
           '        continue;\n'
           '      }'),
        ]
        for old, new in route_edits:
            if result.count(old) != 1:
                raise RuntimeError('route TAKEOFF composition anchor changed; revalidation required')
            result = result.replace(old, new, 1)
        # A normal LAND directly after an acknowledged MOVE can keep the
        # horizontal reference already active in hover. Bound reuse by the
        # existing MOVE position tolerance at LAND receipt. The independent
        # forced LAND above still takes its XY from the current observation.
        handoff_edits = (
          ('  double land_start_z = origin_z;',
           '  int gp_route_move_completed = 0;\n'
           '  double land_start_z = origin_z;'),
          ('    // The PID also drives motors while airborne with no active request.',
           '    if (command != CMD_IDLE) gp_route_move_completed = 0;\n\n'
           '    // The PID also drives motors while airborne with no active request.'),
          ('          trace_move(active_direction, active_value);',
           '          gp_route_move_completed = 1;\n'
           '          trace_move(active_direction, active_value);'),
          ('''        target_x = x;
        target_y = y;
        target_yaw = yaw;
        target_z = origin_z;
        land_start_z = z;''',
           '''        const int gp_keep_move_target = gp_route_move_completed &&
          hypot(target_x - x, target_y - y) <= POSITION_TOL;
        if (!gp_keep_move_target) {
          target_x = x;
          target_y = y;
        }
        target_yaw = yaw;
        target_z = origin_z;
        land_start_z = z;'''),
        )
        for old, new in handoff_edits:
            if result.count(old) != 1:
                raise RuntimeError('route MOVE to LAND composition anchor changed')
            result = result.replace(old, new, 1)
        # Route-mode only. Preserve legacy U and the shared Crazyflie runtime.
        from tools.grand_prix.route_vertical_product import compose_route_vertical_product
        result = compose_route_vertical_product(result)
        # Contact is sampled before deadline and WWI can change LAND ownership.
        # The cutoff is route-wide and monotone through STOP, timeout, loss of
        # contact, and independent LAND. Only confirmed RESET/admitted TAKEOFF
        # can clear it. The new owner must earn its own contact/ACK window.
        latch_edits = (
          ('    /* After genuine touchdown, compare exact raw sensor inputs',
           '    const int gp_land_contact_sampled = command == CMD_LAND;\n'
           '    const int gp_land_contact_before_requests = gp_land_contact_sampled && land_has_ground_contact(z, origin_z);\n'
           '    if (gp_land_contact_before_requests && !land_touchdown) {\n'
           '      land_touchdown = 1;\n'
           '      stop_motors(m1, m2, m3, m4);\n'
           '      printf(PREFIX " TRACE LAND_TOUCHDOWN time=%.9f\\n", now);\n'
           '      fflush(stdout);\n'
           '    }\n'
           '    /* After genuine touchdown, compare exact raw sensor inputs'),
          ('      land_touchdown = 0;\n      airborne = 1;',
           '      /* Preserve any earlier motor cutoff, even after a mode change. */\n'
           '      gp_land_contact_since = -1.0;\n'
           '      airborne = 1;'),
          ('        if (active_id >= 1)\n          response_error(active_id, "USER_STOPPED");',
           '        if (command == CMD_LAND && active_id == 2147483646) {\n'
           '          response_error(request.id, "TIME_LIMIT");\n'
           '          continue;\n'
           '        }\n'
           '        if (active_id >= 1)\n          response_error(active_id, "USER_STOPPED");\n'
           '        if (command == CMD_LAND && active_id != 2147483646) {\n'
           '          if (active_id >= 1) gp_route_stop_land();\n'
           '          active_id = -1; failsafe_latched = 1;\n'
           '          stable_since = -1.0;\n'
           '          gp_land_contact_since = -1.0;\n'
           '          response_ok(request.id);\n'
           '          continue; /* Retain LAND until independent ownership, including pre-contact STOP. */\n'
           '        }'),
          ('        land_touchdown = 0;\n        command = CMD_LAND;',
           '        /* A LAND request cannot clear a previous cutoff. */\n'
           '        command = CMD_LAND;'),
          ('        gp_ground_since = -1.0;\n        command = CMD_TAKEOFF;',
           '        land_touchdown = 0; /* New admitted TAKEOFF only. */\n'
           '        gp_ground_since = -1.0;\n        command = CMD_TAKEOFF;'),
          ('          gp_u_reset_complete();',
           '          land_touchdown = 0; /* Qualified RESET only. */\n'
           '          gp_u_reset_complete();'),
          ('if (now - stable_since >= STOP_WINDOW && gp_ground_sample &&\n'
           '            land_touchdown && gp_land_contact_since >= 0.0',
           'if (active_id >= 1 && now - stable_since >= STOP_WINDOW && gp_ground_sample &&\n'
           '            land_touchdown && gp_land_contact_since >= 0.0'),
          ('      const int gp_contact_now = land_has_ground_contact(z, origin_z);',
           '      const int gp_contact_now = gp_land_contact_sampled ? gp_land_contact_before_requests : land_has_ground_contact(z, origin_z);'),
          ('    if (command == CMD_LAND && land_touchdown) {\n'
           '      // Latch through loss of contact during a rebound.',
           '    if (land_touchdown) {\n'
           '      // Latch through loss of contact during a rebound.'),
        )
        for old, new in latch_edits:
            if result.count(old) != 1:
                raise RuntimeError('route LAND motor latch composition anchor changed')
            result = result.replace(old, new, 1)
        # A frontal envelope failure can precede physical contact with the H
        # crossbar. Backtrack a bounded part of the interrupted forward move
        # while the independent LAND begins its usual descent.
        recovery_state = '  double land_start_z = origin_z;'
        recovery_origin = '      target_x = x; target_y = y; target_yaw = yaw; target_z = origin_z;'
        if result.count(recovery_state) != 1 or result.count(recovery_origin) != 1:
            raise RuntimeError('route-only recovery origin changed')
        result = result.replace(recovery_state, (
            '  double gp_a6_recovery_speed = 0.0;\n'
            '  double gp_a7_recovery_speed = 0.0;\n' + recovery_state
        ), 1)
        result = result.replace(recovery_origin, '''      gp_a6_recovery_speed = 0.0;
      gp_a7_recovery_speed = 0.0;
      const double retreat_distance = 0.12;
      const double move_cos = cos(target_yaw), move_sin = sin(target_yaw);
      const double to_target_x = target_x - x, to_target_y = target_y - y;
      const double remaining = to_target_x * move_cos + to_target_y * move_sin;
      const double sideways = to_target_y * move_cos - to_target_x * move_sin;
      const int backtrack = gp_control_sample && gp_route_periods_valid &&
        command == CMD_MOVE && strcmp(active_direction, "forward") == 0 &&
        fabs(wrap_angle(yaw - target_yaw)) < YAW_TOL &&
        fabs(sideways) < POSITION_TOL && active_value - remaining >= retreat_distance &&
        gp_route_ranges[0] >= 0.0 && gp_route_ranges[0] < 0.12 &&
        gp_route_ranges[1] > 0.25 && gp_route_ranges[1] <= 2.001 &&
        gp_route_a6_envelope_contact(now);
      target_x = x; target_y = y; target_yaw = yaw; target_z = origin_z;
      if (backtrack) {
        target_x -= retreat_distance * move_cos;
        target_y -= retreat_distance * move_sin;
        gp_a6_recovery_speed = fmin(0.14, move_speed_limit);
        printf("GP_U_A6_RETREAT t=%.9f front=%.9f back=%.9f\\n",
               now, gp_route_ranges[0], gp_route_ranges[1]);
        fflush(stdout);
      }
      if (gp_control_sample && gp_route_periods_valid &&
          command == CMD_MOVE && strcmp(active_direction, "forward") == 0 &&
          gp_route_ranges[0] >= 0.0 && gp_route_ranges[0] < 0.12 &&
          gp_route_ranges[1] > 0.25 && gp_route_ranges[1] <= 2.001 &&
          hypot(vx_global, vy_global) <= 0.15 && fabs(vz) <= 0.03) {
        const int direction = gp_route_a7_retreat(now);
        if (direction >= 0 &&
            fabs(wrap_angle(yaw - direction * PI / 2.0)) < YAW_TOL) {
          const int forward_x[] = {1, 0, -1, 0}, forward_y[] = {0, 1, 0, -1};
          target_x -= retreat_distance * forward_x[direction];
          target_y -= retreat_distance * forward_y[direction];
          gp_a7_recovery_speed = fmin(0.14, move_speed_limit);
          printf("GP_U_A7_RETREAT t=%.9f x=%.9f y=%.9f target_x=%.9f target_y=%.9f\\n",
                 now, x, y, target_x, target_y);
          fflush(stdout);
        }
      }''', 1)
        gp_forced_land_hold = (
            "      desired.vx = POSITION_KP * body_x;\n"
            "      desired.vy = POSITION_KP * body_y;\n"
            "      clip_vector(&desired.vx, &desired.vy, VX_MAX);\n"
            "      desired.yaw_rate = clip(YAW_KP * wrap_angle(target_yaw - yaw), YAW_RATE_MAX);\n"
            "      desired.altitude = land_altitude_reference(land_start_z, origin_z, now - action_start);"
        )
        if result.count(gp_forced_land_hold) != 1:
            raise RuntimeError('route-only forced LAND anchor changed')
        result = result.replace(gp_forced_land_hold, (
            "      if (active_id == 2147483646 && gp_route_a6_forced_land()) {\n"
            "        desired.vx = POSITION_KP * body_x;\n"
            "        desired.vy = POSITION_KP * body_y;\n"
            "        clip_vector(&desired.vx, &desired.vy, gp_a6_recovery_speed);\n"
            "      } else {\n"
            "        desired.vx = POSITION_KP * body_x;\n"
            "        desired.vy = POSITION_KP * body_y;\n"
            "        clip_vector(&desired.vx, &desired.vy,\n"
            "                    active_id == 2147483646 && gp_a7_recovery_speed > 0.0\n"
            "                    ? gp_a7_recovery_speed : VX_MAX);\n"
            "      }\n"
            "      desired.yaw_rate = clip(YAW_KP * wrap_angle(target_yaw - yaw), YAW_RATE_MAX);\n"
            "      desired.altitude = land_altitude_reference(land_start_z, origin_z, now - action_start);"
        ), 1)
        # Experimental paired A/B witness only; no new native observations.
        for old, new in (
            ("        command = CMD_MOVE;", "        command = CMD_MOVE;\n        printf(\"GP_HORIZONTAL_START id=%d t=%.9f x=%.9f y=%.9f gx=%.9f gy=%.9f yaw=%.9f speed=%.9f vx=%.9f vy=%.9f\\n\",\n               active_id, now, x, y, target_x, target_y, yaw, move_speed_limit, vx_global, vy_global);\n        fflush(stdout);"),
            ("          trace_move(active_direction, active_value);", "          printf(\"GP_HORIZONTAL_ACK id=%d t=%.9f x=%.9f y=%.9f gx=%.9f gy=%.9f vx=%.9f vy=%.9f\\n\",\n                 active_id, now, x, y, target_x, target_y, vx_global, vy_global);\n          fflush(stdout);\n          trace_move(active_direction, active_value);"),
        ):
            if result.count(old) != 1:
                raise RuntimeError("horizontal experiment trace anchor drift")
            result = result.replace(old, new, 1)
        # EXPERIMENT ONLY: same trace and native gates as paired baseline.
        # Reference starts from the measured XY, with existing P and velocity PID.
        for old, new in (
            ("static double wrap_angle(double angle) {", "/* Derived from the endpoint constraints of Bitcraze pptraj.c poly7_nojerk,\n * firmware 2026.08, 54f31e243a0b28b67efef5ba20dbb6d9890a5478.\n * Original algorithm: Wolfgang Hoenig and James Alan Preiss (2018), MIT.\n * This normalized, speed-capped piecewise adaptation is not firmware timing.\n */\nstatic double gp_move_ramp_position(double u) {\n  return u*u*u*u * (1.0 + u*(0.6 + u*(-2.0 + u*(6.0/7.0))));\n}\nstatic double gp_move_ramp_speed(double u) {\n  return u*u*u * (4.0 + u*(3.0 + u*(-12.0 + 6.0*u)));\n}\nstatic void gp_motion_reference(double distance, double limit, double elapsed,\n                              double *fraction, double *speed, double *duration) {\n  const double ramp = 1.0 / POSITION_KP;\n  const double ratio = 16.0 / 35.0;\n  const double travel = distance / limit;\n  elapsed = fmax(0.0, elapsed);\n  if (travel <= 2.0 * ratio * ramp) {\n    /* Preserve the two-ramp time scale even for tiny moves. A speed-only\n     * duration collapses as distance tends to zero and excites the velocity\n     * loop (native A7 run 45599318202, 4 cm command / >0.50 m/s actual). */\n    *duration = fmax(2.0 * ramp, travel / ratio);\n    const double u = fmin(1.0, elapsed / *duration);\n    const double q = 1.0 - u;\n    *fraction = u*u*u*u * (35.0 + u*(-84.0 + u*(70.0 - 20.0*u)));\n    *speed = (distance / *duration) * 140.0*u*u*u*q*q*q;\n  } else {\n    const double cruise = travel - 2.0 * ratio * ramp;\n    *duration = 2.0 * ramp + cruise;\n    if (elapsed < ramp) {\n      const double u = elapsed / ramp;\n      *fraction = limit*ramp*gp_move_ramp_position(u) / distance;\n      *speed = limit*gp_move_ramp_speed(u);\n    } else if (elapsed < ramp + cruise) {\n      *fraction = limit*(ratio*ramp + elapsed - ramp) / distance;\n      *speed = limit;\n    } else {\n      const double u = fmax(0.0, (*duration - elapsed) / ramp);\n      *fraction = 1.0 - limit*ramp*gp_move_ramp_position(u) / distance;\n      *speed = limit*gp_move_ramp_speed(u);\n    }\n  }\n  if (elapsed >= *duration) { *fraction = 1.0; *speed = 0.0; }\n}\n\nstatic double wrap_angle(double angle) {"),
            ("  double move_speed_limit = VX_MAX;", "  double gp_move_start_x = origin_x, gp_move_start_y = origin_y;\n  double move_speed_limit = VX_MAX;"),
            ("        command = CMD_MOVE;", "        gp_move_start_x = x;\n        gp_move_start_y = y;\n        command = CMD_MOVE;"),
            ("    } else if (command == CMD_MOVE) {\n      const double error_x = target_x - x;\n      const double error_y = target_y - y;\n      const double body_x = error_x * cy + error_y * sy;\n      const double body_y = -error_x * sy + error_y * cy;\n      desired.vx = POSITION_KP * body_x;\n      desired.vy = POSITION_KP * body_y;\n      clip_vector(&desired.vx, &desired.vy, move_speed_limit);\n      desired.yaw_rate = clip(YAW_KP * wrap_angle(target_yaw - yaw), YAW_RATE_MAX);\n      desired.altitude = target_z;\n      if (hypot(error_x, error_y) <= POSITION_TOL", "    } else if (command == CMD_MOVE) {\n      const double error_x = target_x - x;\n      const double error_y = target_y - y;\n      const double dx = target_x - gp_move_start_x, dy = target_y - gp_move_start_y;\n      double fraction, reference_speed, reference_duration;\n      gp_motion_reference(active_value, move_speed_limit, now - action_start,\n                        &fraction, &reference_speed, &reference_duration);\n      const double reference_x = gp_move_start_x + fraction * dx;\n      const double reference_y = gp_move_start_y + fraction * dy;\n      const double world_vx = POSITION_KP * (reference_x - x) + reference_speed * dx / active_value;\n      const double world_vy = POSITION_KP * (reference_y - y) + reference_speed * dy / active_value;\n      desired.vx = world_vx * cy + world_vy * sy;\n      desired.vy = -world_vx * sy + world_vy * cy;\n      clip_vector(&desired.vx, &desired.vy, move_speed_limit);\n      desired.yaw_rate = clip(YAW_KP * wrap_angle(target_yaw - yaw), YAW_RATE_MAX);\n      desired.altitude = target_z;\n      if (now - action_start >= reference_duration &&\n          hypot(error_x, error_y) <= POSITION_TOL"),
        ):
            if result.count(old) != 1:
                raise RuntimeError("horizontal experiment control anchor drift")
            result = result.replace(old, new, 1)
        # EXPERIMENT C: reuse the same bounded profile for signed yaw.
        # A/B native A3 showed the next independent bias at each TURN.
        # Keep XY hold, yaw cap, endpoint, and all stability/safety gates.
        for old, new in (
            ("  double gp_move_start_x = origin_x, gp_move_start_y = origin_y;", "  double gp_move_start_x = origin_x, gp_move_start_y = origin_y;\n  double gp_turn_start_yaw = origin_yaw;"),
            ("        command = CMD_TURN;", "        gp_turn_start_yaw = yaw;\n        command = CMD_TURN;\n        printf(\"GP_TURN_START id=%d t=%.9f yaw=%.9f goal=%.9f angle_deg=%.9f rate=%.9f\\n\",\n               active_id, now, yaw, target_yaw, active_value, actual.yaw_rate);\n        fflush(stdout);"),
            ("    } else if (command == CMD_TURN) {\n      const double error_x = target_x - x;\n      const double error_y = target_y - y;\n      const double body_x = error_x * cy + error_y * sy;\n      const double body_y = -error_x * sy + error_y * cy;\n      desired.vx = POSITION_KP * body_x;\n      desired.vy = POSITION_KP * body_y;\n      clip_vector(&desired.vx, &desired.vy, VX_MAX);\n      desired.yaw_rate = clip(YAW_KP * wrap_angle(target_yaw - yaw), YAW_RATE_MAX);\n      desired.altitude = target_z;\n      if (hypot(error_x, error_y) <= POSITION_TOL", "    } else if (command == CMD_TURN) {\n      const double error_x = target_x - x;\n      const double error_y = target_y - y;\n      const double body_x = error_x * cy + error_y * sy;\n      const double body_y = -error_x * sy + error_y * cy;\n      desired.vx = POSITION_KP * body_x;\n      desired.vy = POSITION_KP * body_y;\n      clip_vector(&desired.vx, &desired.vy, VX_MAX);\n      const double angle = active_value * PI / 180.0;\n      double fraction, reference_rate, reference_duration;\n      gp_motion_reference(fabs(angle), YAW_RATE_MAX, now - action_start,\n                          &fraction, &reference_rate, &reference_duration);\n      const double reference_yaw = wrap_angle(gp_turn_start_yaw + fraction * angle);\n      desired.yaw_rate = clip(copysign(reference_rate, angle) +\n                              YAW_KP * wrap_angle(reference_yaw - yaw), YAW_RATE_MAX);\n      desired.altitude = target_z;\n      if (now - action_start >= reference_duration &&\n          hypot(error_x, error_y) <= POSITION_TOL"),
            ("          trace_turn(active_value);", "          printf(\"GP_TURN_ACK id=%d t=%.9f yaw=%.9f goal=%.9f rate=%.9f\\n\",\n                 active_id, now, yaw, target_yaw, actual.yaw_rate);\n          fflush(stdout);\n          trace_turn(active_value);"),
        ):
            if result.count(old) != 1:
                raise RuntimeError("yaw experiment control anchor drift")
            result = result.replace(old, new, 1)
        # EXPERIMENT D: C native A3 froze each small TURN tracking residual
        # at the next MOVE. Keep the commanded yaw reference in nominal
        # non-turning requests; do not accumulate XY or change TURN's measured
        # start/relative endpoint. STOP, RESET, TAKEOFF and both LAND paths
        # retain their existing recapture/recovery logic.
        for kind, following in (("MOVE", "VERTICAL"), ("VERTICAL", "TURN"), ("WAIT", "LAND")):
            start = f"      if (request.kind == REQUEST_{kind}) {{"
            end = f"      if (request.kind == REQUEST_{following}) {{"
            if result.count(start) != 1 or result.count(end) != 1:
                raise RuntimeError("heading continuity request boundary drift")
            prefix, tail = result.split(start, 1)
            body, suffix = tail.split(end, 1)
            capture = "        target_yaw = yaw;\n"
            if body.count(capture) != 1:
                raise RuntimeError("heading continuity capture drift")
            body = body.replace(capture, "        /* Keep the commanded heading; XY/Z start from observation. */\n", 1)
            if kind == "MOVE":
                if body.count("cos(yaw)") != 4 or body.count("sin(yaw)") != 4:
                    raise RuntimeError("heading continuity direction drift")
                body = body.replace("cos(yaw)", "cos(target_yaw)").replace("sin(yaw)", "sin(target_yaw)")
            result = prefix + start + body + end + suffix
        # EXPERIMENT F: change only the native control/kinematic cadence.
        # Keep true range acquisition at 32 ms and its existing wire contract.
        # Do not rescale PID gains, stability windows, or safety thresholds.
        timing_edits = [
            ('    if (command == CMD_TAKEOFF) {\n      desired.altitude = gp_route_takeoff_next',
             '    if (command == CMD_TAKEOFF && gp_route_waiting_for_first_alive()) {\n'
             '      /* Admission is not yet authority to apply thrust. */\n'
             '      stop_motors(m1, m2, m3, m4);\n'
             '      previous_time = now; previous_x = x; previous_y = y; previous_z = z;\n'
             '      continue;\n'
             '    }\n'
             '    if (command == CMD_TAKEOFF) {\n      desired.altitude = gp_route_takeoff_next'),
            ('  const int step = 32; /* Preserve the shared PID/sensor update period. */',
             '  const int step = 8; /* Experimental 125 Hz control. */\n'
             '  const int range_step = 32; /* Preserve range acquisition. */'),
            ('dt <= 0.032001 &&',
             'dt <= 0.008001 &&\n'
             '      wb_gps_get_sampling_period(gps) == step &&\n'
             '      wb_inertial_unit_get_sampling_period(imu) == step &&\n'
             '      wb_gyro_get_sampling_period(gyro) == step &&'),
            ('  send_text(PREFIX " READY");',
             '  if (wb_gps_get_sampling_period(gps) != step ||\n'
             '      wb_inertial_unit_get_sampling_period(imu) != step ||\n'
             '      wb_gyro_get_sampling_period(gyro) != step) {\n'
             '    fprintf(stderr, "GP_ROUTE_CONTROL_PERIOD_MISMATCH\\n");\n'
             '    wb_robot_cleanup(); return 1;\n'
             '  }\n'
             '  printf("GP_ROUTE_CONTROL_TIMING physics_ms=%d control_ms=%d range_ms=%d\\n",\n'
             '         (int)wb_robot_get_basic_time_step(), step, range_step);\n'
             '  fflush(stdout);\n'
             '  send_text(PREFIX " READY");'),
        ]
        for side in ('front', 'back', 'left', 'right', 'up'):
            timing_edits.extend((
                (f'wb_distance_sensor_enable(range_{side}, step);',
                 f'wb_distance_sensor_enable(range_{side}, range_step);'),
                (f'wb_distance_sensor_get_sampling_period(range_{side}) == step',
                 f'wb_distance_sensor_get_sampling_period(range_{side}) == range_step'),
            ))
        for old, new in timing_edits:
            if result.count(old) != 1:
                raise RuntimeError('route 8-ms control anchor drift')
            result = result.replace(old, new, 1)
        from tools.grand_prix.route_multirate import compose
        result = compose(result)
        from tools.grand_prix.route_multirate_reference import compose as compose_reference
        result = compose_reference(result)
    destination=Path(output_dir) if output_dir is not None else ROOT/'controllers/grand_prix_u_flight/build'
    output=destination/'runtime_u.c'
    output.parent.mkdir(parents=True,exist_ok=True)
    if not output.exists() or output.read_text()!=result:output.write_text(result)
    broker=(ROOT/'controllers/crazyflie_runtime_v2/file_broker_runtime.cpp').read_text()
    anchor='  while ((message = wb_robot_wwi_receive_text()) != nullptr) {'
    if broker.count(anchor)!=1:raise RuntimeError('shared broker anchor changed; revalidation required')
    broker='#include "grand_prix_u_hook.h"\n'+broker.replace(anchor,anchor+'\n    if (!gp_u_filter_raw(message)) continue;')
    if route_observations:
        from tools.grand_prix.route_broker_outcome_v2 import compose_route_outcome_broker
        broker = compose_route_outcome_broker(broker)
    broker_output=output.with_name('file_broker_u.cpp')
    if not broker_output.exists() or broker_output.read_text()!=broker:broker_output.write_text(broker)
    print('GP_U_COMPOSED_BROKER_SHA256 '+hashlib.sha256(broker.encode()).hexdigest())
    if legacy_worlds and (ROOT/'tools/grand_prix/layout_u.py').exists():
        from tools.grand_prix.layout_u import generate,world_text
        for seed in (0,1,4):
            (ROOT/f'worlds/grand_prix_u_seed{seed}.wbt').write_text(world_text(generate(seed),controller='grand_prix_u_flight',window='grand_prix_u',evaluator=True))
    print('GP_U_SHARED_SOURCE_SHA256 '+hashlib.sha256(source.encode()).hexdigest())
    print('GP_U_COMPOSED_SOURCE_SHA256 '+hashlib.sha256(result.encode()).hexdigest())
if __name__=='__main__':prepare()

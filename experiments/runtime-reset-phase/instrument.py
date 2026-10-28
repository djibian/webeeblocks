"""Diagnostic-only source transform: log original RESET locals, never re-read sensors."""
def instrument(source):
    begin = '        action_start = now;\n        continue;\n      }\n      if (failsafe_latched)'
    sample = '      if (!pose_ready)\n        ++reset_pose_bad_samples;'
    if source.count(begin) != 1 or source.count(sample) != 1:
        raise ValueError('unrecognized RESET source; do not instrument')
    source = source.replace(begin, '''        action_start = now;
        fprintf(stderr, PREFIX " RESET_PHASE_BEGIN id=%d time=%.9f origin=%.9f,%.9f,%.9f origin_rpy=%.9f,%.9f,%.9f\\n",
                active_id, now, origin_x, origin_y, origin_z, origin_roll, origin_pitch, origin_yaw);
        continue;
      }
      if (failsafe_latched)''')
    source = source.replace(sample, '''      fprintf(stderr, PREFIX " RESET_PHASE_SAMPLE id=%d time=%.9f elapsed=%.9f dt=%.9f position=%.9f,%.9f,%.9f previous=%.9f,%.9f,%.9f rpy=%.9f,%.9f,%.9f gyro=%.9f,%.9f,%.9f velocity=%.9f,%.9f,%.9f pose_ready=%d motion_ready=%d stable_since=%.9f\\n",
              active_id, now, now - action_start, dt, x, y, z, previous_x, previous_y, previous_z,
              rpy[0], rpy[1], yaw, gyro_values[0], gyro_values[1], gyro_values[2],
              vx_global, vy_global, vz, pose_ready, motion_ready, stable_since);
      if (!pose_ready)
        ++reset_pose_bad_samples;''')

    # Optional #637 native timing: actual time inside Webots step, not the
    # interval between two sparse browser observations. Never edit product C.
    include = '#include <webots/supervisor.h>\n'
    define = '#define PI 3.14159265358979323846\n'
    loop = '  while (wb_robot_step(step) != -1) {'
    if source.count(include) != 1 or source.count(define) != 1 or source.count(loop) != 1:
        raise ValueError('unrecognized native step call; do not instrument')
    source = source.replace(include, include + '#include <time.h>\n')
    wrapper = r'''
/* WEBEEBLOCKS_RESET_CI_STEP_BEGIN: opt-in diagnosis, not product code. */
static int reset_ci_timed_robot_step(int step_ms) {
  static unsigned int samples = 0;
  static double sum_seconds = 0.0;
  static double max_seconds = 0.0;
  struct timespec before, after;
  const int available = clock_gettime(CLOCK_MONOTONIC, &before) == 0;
  const int result = wb_robot_step(step_ms);
  if (available && clock_gettime(CLOCK_MONOTONIC, &after) == 0) {
    const double seconds = (double)(after.tv_sec - before.tv_sec) +
                           (double)(after.tv_nsec - before.tv_nsec) / 1000000000.0;
    if (seconds >= 0.0) {
      ++samples;
      sum_seconds += seconds;
      if (seconds > max_seconds) max_seconds = seconds;
      if (seconds >= 1.0)
        fprintf(stderr, "WEBEEBLOCKS_RESET_CI_SLOW_STEP requested_ms=%d monotonic_seconds=%.6f\n",
                step_ms, seconds);
      if (samples == 128) {
        fprintf(stderr, "WEBEEBLOCKS_RESET_CI_STEP_BATCH count=128 requested_ms=%d monotonic_total=%.6f monotonic_max=%.6f\n",
                step_ms, sum_seconds, max_seconds);
        samples = 0;
        sum_seconds = 0.0;
        max_seconds = 0.0;
      }
    }
  }
  return result;
}
/* WEBEEBLOCKS_RESET_CI_STEP_END */
'''
    source = source.replace(define, wrapper + '\n' + define)
    return source.replace(loop, '  while (reset_ci_timed_robot_step(step) != -1) {')

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
    return source.replace(sample, '''      fprintf(stderr, PREFIX " RESET_PHASE_SAMPLE id=%d time=%.9f elapsed=%.9f dt=%.9f position=%.9f,%.9f,%.9f previous=%.9f,%.9f,%.9f rpy=%.9f,%.9f,%.9f gyro=%.9f,%.9f,%.9f velocity=%.9f,%.9f,%.9f pose_ready=%d motion_ready=%d stable_since=%.9f\\n",
              active_id, now, now - action_start, dt, x, y, z, previous_x, previous_y, previous_z,
              rpy[0], rpy[1], yaw, gyro_values[0], gyro_values[1], gyro_values[2],
              vx_global, vy_global, vz, pose_ready, motion_ready, stable_since);
      if (!pose_ready)
        ++reset_pose_bad_samples;''')

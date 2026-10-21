#!/usr/bin/env python3
"""Prepare observation-only C from the exact #655 composed Runtime.

Writes only the explicitly requested output. Does not run Webots or mutate a PR.
Records are text key/value (nan/inf stay explicit), not purported JSON.
"""
import argparse
import hashlib
from pathlib import Path

EXPECTED = 'c6b47c499dfe482f438432e9ed9a36d58611080f644644cd2ad42c18b00a3a99'


def patch(source):
    source = ('extern double pastAltitudeError, pastPitchError, pastRollError, pastYawRateError;\n'
              'extern double pastVxError, pastVyError, altitudeIntegrator;\n')+source
    edits = [
        ('    if (!position) position = gp_missing;', r'''    if (!position || !rpy || !gyro_values ||
        !isfinite(position[0]) || !isfinite(position[1]) || !isfinite(position[2]) ||
        !gp_valid_attitude(rpy) || !isfinite(gyro_values[0]) ||
        !isfinite(gyro_values[1]) || !isfinite(gyro_values[2])) {
      fprintf(stderr, "GP655_RAW_INVALID time_ms=%lld id=%d "
              "gps_present=%d imu_present=%d gyro_present=%d "
              "gps=%.17g,%.17g,%.17g rpy=%.17g,%.17g,%.17g gyro=%.17g,%.17g,%.17g\n",
              (long long)llround(now*1000.0),active_id,position!=NULL,rpy!=NULL,gyro_values!=NULL,
              position?position[0]:NAN,position?position[1]:NAN,position?position[2]:NAN,
              rpy?rpy[0]:NAN,rpy?rpy[1]:NAN,rpy?rpy[2]:NAN,
              gyro_values?gyro_values[0]:NAN,gyro_values?gyro_values[1]:NAN,gyro_values?gyro_values[2]:NAN);
      fflush(stderr);
    }
    if (!position) position = gp_missing;'''),
        ('      response_error(active_id, "UNSAFE_OR_TIMEOUT");', r'''      fprintf(stderr, "GP655_GUARD time_ms=%lld id=%d command=%d airborne=%d "
              "invalid_sample=%d roll_guard=%d pitch_guard=%d timeout_guard=%d "
              "dt=%.17g action_start=%.17g elapsed=%.17g "
              "gps=%.17g,%.17g,%.17g rpy=%.17g,%.17g,%.17g gyro=%.17g,%.17g,%.17g "
              "velocity=%.17g,%.17g,%.17g stable_since=%.17g\n",
              (long long)llround(now * 1000.0), active_id, (int)command, airborne,
              !gp_control_sample, fabs(actual.roll) > 1.2, fabs(actual.pitch) > 1.2,
              now - action_start > ACTION_TIMEOUT, dt, action_start, now-action_start,
              x,y,z,rpy[0],rpy[1],rpy[2],gyro_values[0],gyro_values[1],gyro_values[2],
              vx_global,vy_global,vz,stable_since);
      fflush(stderr);
      response_error(active_id, "UNSAFE_OR_TIMEOUT");'''),
        ('      pid_velocity_fixed_height_controller(actual, &desired, gains, dt, &power);', r'''      if (command == CMD_LAND || (program_clock.active && now-program_clock.start >= 209.0)) {
        fprintf(stderr, "GP655_LAND_INPUT time_ms=%lld id=%d command=%d dt=%.17g "
                "gps=%.17g,%.17g,%.17g previous_gps=%.17g,%.17g,%.17g "
                "rpy=%.17g,%.17g,%.17g gyro=%.17g,%.17g,%.17g "
                "body_velocity=%.17g,%.17g desired_velocity=%.17g,%.17g "
                "desired_altitude=%.17g past_altitude_error=%.17g altitude_integrator=%.17g "
                "past_velocity_error=%.17g,%.17g past_attitude_error=%.17g,%.17g,%.17g\n",
                (long long)llround(now * 1000.0),active_id,(int)command,dt,x,y,z,previous_x,previous_y,previous_z,
                rpy[0],rpy[1],rpy[2],gyro_values[0],gyro_values[1],gyro_values[2],
                actual.vx,actual.vy,desired.vx,desired.vy,desired.altitude,pastAltitudeError,altitudeIntegrator,
                pastVxError,pastVyError,pastRollError,pastPitchError,pastYawRateError);
        fflush(stderr);
      }
      pid_velocity_fixed_height_controller(actual, &desired, gains, dt, &power);'''),
        ('      wb_motor_set_velocity(m4, motor_power(power.m4));', r'''      wb_motor_set_velocity(m4, motor_power(power.m4));
      if (command == CMD_LAND || (program_clock.active && now-program_clock.start >= 209.0)) {
        fprintf(stderr, "GP655_LAND_OUTPUT time_ms=%lld id=%d command=%d "
                "attitude_cmd=%.17g,%.17g,%.17g raw_power=%.17g,%.17g,%.17g,%.17g "
                "signed_targets=%.17g,%.17g,%.17g,%.17g\n",
                (long long)llround(now * 1000.0),active_id,(int)command,desired.roll,desired.pitch,desired.yaw_rate,
                power.m1,power.m2,power.m3,power.m4,-motor_power(power.m1),motor_power(power.m2),
                -motor_power(power.m3),motor_power(power.m4));
        fflush(stderr);
      }'''),
        ('  wb_motor_set_velocity(m4, 0.0);', r'''  wb_motor_set_velocity(m4, 0.0);
  fprintf(stderr, "GP655_ZERO_TARGETS time_ms=%lld\n", (long long)llround(wb_robot_get_time()*1000.0));
  fflush(stderr);'''),
    ]
    for before, after in edits:
        if source.count(before) != 1:
            raise ValueError('changed/ambiguous diagnostic anchor: '+before)
        source = source.replace(before, after)
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('composed_source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    source = args.composed_source.read_bytes()
    if hashlib.sha256(source).hexdigest() != EXPECTED:
        raise ValueError('not the exact #655 composed source')
    if args.output.exists() or args.output.is_symlink():
        raise ValueError('output already exists')
    result = patch(source.decode()).encode()
    with args.output.open('xb') as stream:
        stream.write(result)
    print('GP655_OBSERVATION_SOURCE_SHA256 '+hashlib.sha256(result).hexdigest())


if __name__ == '__main__':
    main()

"""Route-only synchronous 8-ms feedback; G1 decimation retired after #1114."""

CASCADE = r'''
/* #1114 D2: do not hold roll/pitch across native feedback ticks.
 * Every powered tick uses the same shared velocity/height/attitude PID,
 * with the actual measured dt. Only the analytic reference cache is
 * multi-rate (32-ms knots); range, safety and motor latch are unchanged.
 * Keep the existing counters for comparable native diagnostic logs. */
typedef struct {
  unsigned long long ticks, updates;
} gp_multirate_t;

static void gp_multirate_pid(gp_multirate_t *s, actual_state_t actual,
                            desired_state_t *desired, gains_pid_t gains,
                            double dt, motor_power_t *power) {
  pid_velocity_fixed_height_controller(actual, desired, gains, dt, power);
  ++s->ticks;
  ++s->updates;
}
'''


def compose(source):
    edits = (
        ('static double gp_move_ramp_position(double u) {',
         CASCADE + '\nstatic double gp_move_ramp_position(double u) {'),
        ('  gains_pid_t gains;\n',
         '  gp_multirate_t gp_xy = {0};\n  gains_pid_t gains;\n'),
        ('        init_pid_attitude_fixed_height_controller();',
         '        init_pid_attitude_fixed_height_controller();\n'
         '        memset(&gp_xy, 0, sizeof(gp_xy));'),
        ('      pid_velocity_fixed_height_controller(actual, &desired, gains, dt, &power);',
         '      gp_multirate_pid(&gp_xy, actual, &desired, gains, dt, &power);\n'
         '      if (gp_xy.ticks % 125 == 0) {\n'
         '        printf("GP_ROUTE_MULTIRATE ticks=%llu xy_updates=%llu\\n",\n'
         '               gp_xy.ticks, gp_xy.updates);\n'
         '        fflush(stdout);\n'
         '      }'),
    )
    for old, new in edits:
        if source.count(old) != 1:
            raise RuntimeError('route multirate composition anchor drift')
        source = source.replace(old, new, 1)
    return source

"""Route-only experimental 8/16-ms cascade; no new control authority."""

CASCADE = r'''
/* G1: only the horizontal velocity PID is decimated. All trajectory,
 * attitude, altitude, motor and safety work remains on the 8-ms tick.
 * Held roll/pitch are controller outputs, not stale sensor observations. */
typedef struct {
  int valid, mode, request, fast;
  long long tick_ms;
  double xy_time, action_started, roll, pitch;
  unsigned long long ticks, updates;
} gp_multirate_t;

static void gp_multirate_pid(gp_multirate_t *s, actual_state_t actual,
                            desired_state_t *desired, gains_pid_t gains,
                            double now, double dt, int mode, int request,
                            double action_started, int fast, motor_power_t *power) {
  const long long ms = (long long)llround(now * 1000.0);
  const int contiguous = s->valid && ms == s->tick_ms + 8;
  const double elapsed = contiguous ? now - s->xy_time : dt;
  const int transition = !contiguous || mode != s->mode || request != s->request ||
                         action_started != s->action_started || fast != s->fast;
  if (transition || fast || elapsed >= 0.015999) {
    /* Never divide by a skipped 8-ms tick or integrate across an inactive gap. */
    pid_horizontal_velocity_controller(actual, desired, gains, elapsed);
    s->roll = desired->roll;
    s->pitch = desired->pitch;
    s->xy_time = now;
    ++s->updates;
  } else {
    desired->roll = s->roll;
    desired->pitch = s->pitch;
  }
  s->valid = 1; s->tick_ms = ms; s->mode = mode; s->request = request;
  s->action_started = action_started; s->fast = fast;
  ++s->ticks;
  control_commands_t commands = {0};
  pid_fixed_height_controller(actual, desired, gains, dt, &commands);
  pid_attitude_controller(actual, desired, gains, dt, &commands);
  motor_mixing(commands, power);
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
         '      gp_multirate_pid(&gp_xy, actual, &desired, gains, now, dt,\n'
         '        command, active_id, action_start,\n'
         '        command == CMD_LAND || command == CMD_TAKEOFF || failsafe_latched, &power);\n'
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

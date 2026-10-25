"""Bounded build-time extension of CURRENT shared simulation flight source.
No shared controller or physical source is edited. Changed anchors refuse.
"""
import hashlib
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
def prepare():
    source=(ROOT/'controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c').read_text()
    edits=[
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
    output=ROOT/'controllers/grand_prix_u_flight/build/runtime_u.c'
    output.parent.mkdir(parents=True,exist_ok=True)
    if not output.exists() or output.read_text()!=result:output.write_text(result)
    broker=(ROOT/'controllers/crazyflie_runtime_v2/file_broker_runtime.cpp').read_text()
    anchor='  while ((message = wb_robot_wwi_receive_text()) != nullptr) {'
    if broker.count(anchor)!=1:raise RuntimeError('shared broker anchor changed; revalidation required')
    broker='#include "grand_prix_u_hook.h"\n'+broker.replace(anchor,anchor+'\n    if (!gp_u_filter_raw(message)) continue;')
    broker_output=output.with_name('file_broker_u.cpp')
    if not broker_output.exists() or broker_output.read_text()!=broker:broker_output.write_text(broker)
    print('GP_U_COMPOSED_BROKER_SHA256 '+hashlib.sha256(broker.encode()).hexdigest())
    if (ROOT/'tools/grand_prix/layout_u.py').exists():
        from tools.grand_prix.layout_u import generate,world_text
        for seed in (0,1,4):
            (ROOT/f'worlds/grand_prix_u_seed{seed}.wbt').write_text(world_text(generate(seed),controller='grand_prix_u_flight',window='grand_prix_u',evaluator=True))
    print('GP_U_SHARED_SOURCE_SHA256 '+hashlib.sha256(source.encode()).hexdigest())
    print('GP_U_COMPOSED_SOURCE_SHA256 '+hashlib.sha256(result.encode()).hexdigest())
if __name__=='__main__':prepare()

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
      ('  const int step = (int)wb_robot_get_basic_time_step();',
       '  const int step = 32; /* Preserve the shared PID/sensor update period. */'),
      ('  while (wb_robot_step(step) != -1) {',
       '  while (wb_robot_step(gp_u_next_step(step)) != -1) {'),
      ('  send_text(PREFIX " READY");', '''  if ((long long)llround(wb_robot_get_basic_time_step()) != 8) {
    fprintf(stderr, "GP_U_PREPARE_ERROR required_basic_step_ms=8\\n");
    wb_robot_cleanup(); return 1;
  }
  send_text(PREFIX " READY");'''),
      ('    const char *message;\n    while ((message = wb_robot_wwi_receive_text()) != NULL) {', '''    if (gp_u_deadline(now, !airborne && command == CMD_IDLE)) {
      simulation_clock_revoke(&program_clock);
      const int interrupted_id = active_id;
      if (active_id >= 1) response_error(active_id, "TIME_LIMIT");
      target_x = x; target_y = y; target_yaw = yaw; target_z = origin_z;
      airborne = 1; /* Native LAND also completes if already grounded. */
      command = CMD_LAND; active_id = 2147483646;
      active_value = 0.0; active_direction[0] = '\\0';
      stable_since = -1.0; action_start = now;
      printf("GP_U_DEADLINE time_ms=%lld command=LAND interrupted_id=%d\\n",
             (long long)llround(now * 1000.0), interrupted_id);
      fflush(stdout);
    }
    const char *message;
    while ((message = wb_robot_wwi_receive_text()) != NULL) {'''),
      ('        simulation_clock_begin(&program_clock, now);\n        command = CMD_TAKEOFF;', '''        simulation_clock_begin(&program_clock, now);
        if (!gp_u_start(now)) {
          simulation_clock_revoke(&program_clock);
          response_error(active_id, "INVALID_ATTEMPT");
          active_id = -1; command = CMD_IDLE;
          continue;
        }
        command = CMD_TAKEOFF;'''),
      ('          trace_reset(x, y, z, origin_x, origin_y, origin_z);\n          response_ok(active_id);',
       '          trace_reset(x, y, z, origin_x, origin_y, origin_z);\n          response_ok(active_id);\n          gp_u_reset_complete();')]
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

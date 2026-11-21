"""Temporary native observation and interventions on the isolated A3 branch."""


def compose_trace_and_interventions(source):
    def replace(anchor, replacement):
        nonlocal source
        if source.count(anchor) != 1:
            raise RuntimeError('A3 diagnostic source anchor drift: ' + anchor)
        source = source.replace(anchor, replacement, 1)

    replace('  double target_z = origin_z;',
            '''  double target_z = origin_z;
  const char *gp_a3_case = getenv("WBB_A3_CASE");
  const int gp_a3_trace = getenv("WEBEEBLOCKS_GP_A3_TRACE") != NULL;
  int gp_a3_last_move = 0;''')
    replace('        command = CMD_MOVE;',
            '''        if (gp_a3_trace)
          printf("A3_MOVE_BEGIN id=%d t=%.6f d=%.6f x=%.9f y=%.9f z=%.9f "
                 "tx=%.9f ty=%.9f vx=%.9f vy=%.9f vz=%.9f\\n",
                 request.id, now, request.value, x, y, z, target_x, target_y,
                 vx_global, vy_global, vz);
        command = CMD_MOVE;''')
    replace('          trace_move(active_direction, active_value);',
            '''          gp_a3_last_move = active_id == 21 && gp_a3_trace;
          if (gp_a3_trace)
            printf("A3_MOVE_ACK id=%d t=%.6f x=%.9f y=%.9f z=%.9f "
                   "tx=%.9f ty=%.9f vx=%.9f vy=%.9f vz=%.9f\\n",
                   active_id, now, x, y, z, target_x, target_y, vx_global, vy_global, vz);
          if (gp_a3_last_move && gp_a3_case && strcmp(gp_a3_case, "short-freeze") == 0) {
            target_x = x;
            target_y = y;
          }
          trace_move(active_direction, active_value);''')
    replace('''        target_x = x;
        target_y = y;
        target_yaw = yaw;
        target_z = origin_z;
        land_start_z = z;''',
            '''        const int gp_keep_target = gp_a3_last_move && gp_a3_case &&
          (strcmp(gp_a3_case, "short-handoff") == 0 ||
           strcmp(gp_a3_case, "nominal-handoff") == 0) &&
          hypot(target_x - x, target_y - y) <= POSITION_TOL;
        if (gp_a3_trace)
          printf("A3_LAND_BEGIN id=%d t=%.6f x=%.9f y=%.9f z=%.9f tx=%.9f ty=%.9f "
                 "vx=%.9f vy=%.9f vz=%.9f keep=%d\\n",
                 request.id, now, x, y, z, target_x, target_y, vx_global, vy_global, vz,
                 gp_keep_target);
        gp_a3_last_move = 0;
        if (!gp_keep_target) {
          target_x = x;
          target_y = y;
        }
        target_yaw = yaw;
        target_z = origin_z;
        land_start_z = z;''')
    return source

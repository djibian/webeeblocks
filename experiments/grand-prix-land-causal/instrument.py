"""Experimental generated-source instrumentation; production files untouched."""
from pathlib import Path


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('changed experimental anchor: ' + old[:100])
    return text.replace(old, new)


def instrument(root: Path):
    path = root / 'controllers/grand_prix_u_flight/build/runtime_u.c'
    source = path.read_text()
    source = replace_once(source, '  double stable_since = -1.0;', '''  double stable_since = -1.0;
  int causal_contact = 0;
  const int causal_ablate = getenv("GP_LAND_ABLATE") && strcmp(getenv("GP_LAND_ABLATE"), "1") == 0;
  char causal_path[4096];
  snprintf(causal_path, sizeof(causal_path), "%s/causal-control.jsonl", getenv("WEBEEBLOCKS_CI_ARTIFACT_DIR"));
  FILE *causal_file = fopen(causal_path, "w");
  if (!causal_file) { wb_robot_cleanup(); return 2; }
  setvbuf(causal_file, NULL, _IOLBF, 0);
  extern double pastVxError, pastVyError;''')
    source = replace_once(source, '    desired.roll = 0.0;', r'''    fprintf(causal_file, "{\"phase\":\"sample\",\"time\":%.9f,\"command\":%d,\"airborne\":%d}\n", now, (int)command, airborne);
    desired.roll = 0.0;''')
    anchor = '      pid_velocity_fixed_height_controller(actual, &desired, gains, dt, &power);'
    source = replace_once(source, anchor, r'''      int causal_count = 0;
      if (command == CMD_LAND) {
        int count = 0;
        WbContactPoint *points = wb_supervisor_node_get_contact_points(self_node, true, &count);
        for (int i = 0; i < count; ++i)
          if (fabs(points[i].point[2]) <= 0.005) ++causal_count;
        if (causal_count) causal_contact = 1;
      }
      const double causal_ex = desired.vx - actual.vx;
      const double causal_ey = desired.vy - actual.vy;
      const double causal_dx = (causal_ex - pastVxError) / dt;
      const double causal_dy = (causal_ey - pastVyError) / dt;
      const int causal_active = command == CMD_LAND && causal_contact && causal_ablate;
      if (causal_active) { pastVxError = causal_ex; pastVyError = causal_ey; }
      pid_velocity_fixed_height_controller(actual, &desired, gains, dt, &power);
      fprintf(causal_file, "{\"phase\":\"control\",\"time\":%.9f,\"dt\":%.9f,\"land\":%d,\"contact_count\":%d,\"contact_seen\":%d,\"ablation\":%d,\"actual_body\":[%.12g,%.12g],\"error\":[%.12g,%.12g],\"derivative_before\":[%.12g,%.12g],\"attitude_cmd\":[%.12g,%.12g],\"motors\":[%.12g,%.12g,%.12g,%.12g]}\n",
        now, dt, command == CMD_LAND, causal_count, causal_contact, causal_active,
        actual.vx, actual.vy, causal_ex, causal_ey, causal_dx, causal_dy,
        desired.roll, desired.pitch, -motor_power(power.m1), motor_power(power.m2),
        -motor_power(power.m3), motor_power(power.m4));''')
    path.write_text(source)
    path = root / 'controllers/grand_prix_u_evaluator/grand_prix_u_evaluator.py'
    source = path.read_text()
    source = replace_once(source, 'while robot.step(step)!=-1:', '''# Public read-only access to native kinematic helix state, not motor targets.
rotors = [vehicle.getFromProtoDef('M'+str(i)).getField('slowHelix').getSFNode().getField('rotation') for i in range(1,5)]
rotor_file = (Path(trace_path)/'native-rotors.csv').open('w', buffering=1)
rotor_csv = csv.writer(rotor_file)
rotor_csv.writerow(['time', *[f'm{i}_{axis}' for i in range(1,5) for axis in ('x','y','z','angle')]])
while robot.step(step)!=-1:
    rotor_csv.writerow([robot.getTime(), *[v for field in rotors for v in field.getSFRotation()]])''')
    path.write_text(source)
